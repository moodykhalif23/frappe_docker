// Account straight after a +: the bill must carry the tap. Local sites only —
// it seats a party and rings dishes.
//
// 6 Nov 2026 (OR-2026-03071): a bill pressed a second after a + on Special Tea
// printed lines adding to 620 under "Total Sh 470.00". The pad sends the + and
// prints the bill on separate requests and did not wait for the first.
//
// The + request is held in transit for 3 s, so the race is not left to luck.
//   1. the bill is requested only after the + has come back,
//   2. the printed bill has the tapped dish at its new quantity, and its Total
//      is the sum of its lines and the pad's Total,
//   3. a + that never comes back refuses the bill instead of printing without it.
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const USER = process.env.USER_ || 'Administrator';
const PASS = process.env.PASS || 'admin';
if (!/^https?:\/\/(pos\.)?localhost/.test(BASE)) {
  console.error(`REFUSING: ${BASE} is not a local site; this probe rings dishes.`);
  process.exit(2);
}

const results = [];
const ok = (name, pass, detail = '') => {
  results.push(pass);
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + String(detail).slice(0, 200) : ''}`);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errs = [];
page.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 140)));

// what happened, in order, on the wire
const events = [];
const t0 = Date.now();
const mark = (what, extra = {}) => events.push({ what, at: Date.now() - t0, ...extra });
let holdWrites = 0;          // ms to hold each push_item / delete_item in transit
await page.route('**/api/method/restaurant_management.api.call', async route => {
  const body = route.request().postData() || '';
  const write = /method=(push_item|delete_item)/.test(decodeURIComponent(body).replace(/\+/g, ' '));
  if (write) {
    mark('write-sent');
    if (holdWrites) await sleep(holdWrites);
  }
  const res = await route.fetch();
  if (write) mark('write-back');
  await route.fulfill({ response: res });
});
const bills = [];
page.on('request', r => { if (r.url().includes('/printview?')) mark('bill-requested'); });
page.on('response', async r => {
  if (!r.url().includes('/printview?') || r.url().includes('kitchen=1')) return;
  bills.push(await r.text().catch(() => ''));
});

const parseBill = html => {
  const lines = [...html.matchAll(/<td class="it">([^<]*)(?:<span[^>]*>[^<]*<\/span>|\s)*<\/td>\s*<td class="qt">([\d.]+)<\/td>\s*<td class="am">([\d.,]+)<\/td>/g)]
    .map(m => ({ item: m[1].trim(), qty: +m[2], amount: +m[3].replace(/,/g, '') }));
  const tot = html.match(/<tr class="tot"><td class="tl">[^<]*<\/td><td class="am">([^<]*)<\/td>/);
  return { lines, total: tot ? +tot[1].replace(/[^\d.]/g, '') : NaN };
};
// the open pad hangs off its table object
const CHECK = `(() => {
  const om = Object.values((window.RM && RM.objects) || {}).map(o => o && o.order_manage)
    .find(om => om && om.is_open && om.is_open());
  return om && om.current_order;
})()`;
const padTotal = () => page.evaluate(c => { const o = eval(c); return o ? +o.data.amount : NaN; }, CHECK);
const padQty = () => page.evaluate(c => { const o = eval(c); return o ? Object.values(o.items)[0].data.qty : NaN; }, CHECK);

// --- sign in, seat a party, ring one dish ---------------------------------
await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.fill('#login_email', USER);
await page.fill('#login_password', PASS);
await page.click('button.btn-login');
await page.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(11000);

await page.getByRole('button', { name: 'Seat guest' }).click();
await page.waitForTimeout(2000);
let seat = page.locator('.modal.show').last();
if ((await seat.locator('.modal-title').innerText().catch(() => '')).includes("Who's on")) {
  // bill_total_suite.py leaves this waiter with this PIN
  await seat.locator('select').first().selectOption('Bill Test Waiter');
  await seat.locator('input[type="password"]').fill('4821');
  await seat.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForTimeout(3500);
  seat = page.locator('.modal.show').last();
}
await seat.locator('input[data-fieldname="guest_name"]').fill('Bill Print Probe');
await seat.locator('input[data-fieldname="covers"]').fill('2');
await seat.locator('input[data-fieldname="covers"]').press('Tab');
await page.waitForTimeout(2500);
await seat.getByRole('button', { name: 'Seat & open order' }).click();
await page.waitForTimeout(9000);

const plus = page.locator('.order-manage .add-item:visible').first();
await plus.waitFor({ state: 'visible', timeout: 45000 }).catch(() => {});
ok('the pad opened on the party with a menu', await plus.count() > 0);
await plus.click({ force: true });
await page.waitForTimeout(5000);
const account = page.locator('.order-manage').getByText(/^Account$/).first();

// --- 1 + 2: + then Account at once, the + held in transit for 3 s ---------
const qtyBefore = await padQty();
events.length = 0; bills.length = 0;
holdWrites = 3000;
await plus.click({ force: true });
await account.click({ force: true });
await page.waitForTimeout(9000);
holdWrites = 0;

const back = events.find(e => e.what === 'write-back');
const asked = events.find(e => e.what === 'bill-requested');
ok('the bill is requested only after the + has come back',
   back && asked && asked.at >= back.at, JSON.stringify(events));
const bill = bills.length ? parseBill(bills[bills.length - 1]) : { lines: [], total: NaN };
const sum = bill.lines.reduce((a, l) => a + l.amount, 0);
ok('the bill carries the tap: the dish at its new quantity',
   bill.lines.length && bill.lines[0].qty === qtyBefore + 1, JSON.stringify(bill.lines));
ok('the bill Total is the sum of its lines', Math.abs(bill.total - sum) < 0.005, `${bill.total} vs ${sum}`);
ok('and it is the pad\'s Total', Math.abs(bill.total - await padTotal()) < 0.005,
   `${bill.total} vs ${await padTotal()}`);

// --- 3: a + that never comes back -----------------------------------------
events.length = 0; bills.length = 0;
holdWrites = 25000;
await plus.click({ force: true });
await account.click({ force: true });
await page.waitForTimeout(17500);
const refusal = await page.locator('.modal.show').filter({ hasText: 'Bill not printed' }).count();
ok('a + still in flight after 15 s refuses the bill', refusal > 0 && !events.some(e => e.what === 'bill-requested'),
   JSON.stringify(events));
holdWrites = 0;
await page.waitForTimeout(9000);

ok('no page errors', errs.length === 0, JSON.stringify(errs.slice(0, 3)));
console.log(`\nRESULT ${results.filter(Boolean).length} passed, ${results.filter(r => !r).length} failed`);
await browser.close();
process.exit(results.every(Boolean) ? 0 : 1);
