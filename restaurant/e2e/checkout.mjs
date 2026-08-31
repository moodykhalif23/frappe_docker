// The money path: seat a party, ring a dish, take payment, and prove the table
// came back free with a turn recorded against it. Writes real records.
import { chromium } from 'playwright';
// the floor demands a signed-in waiter before seating; answer the PIN pad
const answerGate = async (pg, dlg) => {
  const title = await dlg.locator('.modal-title').innerText().catch(() => '');
  if (!title.includes("Who's on")) return dlg;
  await pg.evaluate(async () => {
    const found = await frappe.call('frappe.client.get_list', { doctype: 'Restaurant Waiter',
      filters: { waiter_name: 'Test Waiter' }, fields: ['name'], limit_page_length: 1 });
    if ((found.message || []).length) {
      await frappe.call('frappe.client.set_value', { doctype: 'Restaurant Waiter',
        name: found.message[0].name, fieldname: { pin: '4821', active: 1 } });
    } else {
      await frappe.call('frappe.client.insert', { doc: { doctype: 'Restaurant Waiter',
        waiter_name: 'Test Waiter', pin: '4821', active: 1, colour: '#2563eb' } });
    }
  });
  await dlg.locator('select').first().selectOption('Test Waiter');
  await dlg.locator('input[type="password"]').fill('4821');
  await dlg.getByRole('button', { name: 'Sign in' }).click();
  await pg.waitForTimeout(3500);
  return pg.locator('.modal.show').last();
};

import { mkdirSync } from 'fs';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const USER = process.env.USER_ || 'Administrator';
const PASS = process.env.PASS || 'admin';
const GUEST = process.env.GUEST || 'Checkout Test Party';

// Submits a real POS Invoice that lands in the books — on a client's site that
// is a fake sale, so a non-local target has to be asked for explicitly.
if (!/^https?:\/\/(pos\.)?localhost/.test(BASE) && process.env.ALLOW_REAL_SALE !== '1') {
  console.error(`REFUSING: ${BASE} is not a local site and this test submits a real POS Invoice.`);
  console.error('Set ALLOW_REAL_SALE=1 only on a demo site, and cancel the invoice afterwards.');
  process.exit(2);
}

mkdirSync('shots', { recursive: true });
let n = 0;
const results = [];
const ok = (name, pass, detail = '') => {
  results.push({ name, pass, detail: String(detail).slice(0, 140) });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 140)));
const shot = async (l) => {
  n += 1;
  await page.screenshot({ path: `shots/pay-${String(n).padStart(2, '0')}-${l}.jpg`, type: 'jpeg', quality: 70 });
  console.log('   shot ' + l);
};
// the page already holds an authenticated frappe client — ask the app directly
const api = (method, args = {}) => page.evaluate(
  ([m, a]) => frappe.call('restaurant_management.house.' + m, a).then(r => r.message),
  [method, args]);

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.fill('#login_email', USER);
await page.fill('#login_password', PASS);
await page.click('button.btn-login');
await page.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});

await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(11000);
await shot('floor');

const freeBefore = (await api('free_tables', { whole_table: 1 })).length;
const turnsBefore = (await api('turn_metrics')).turns;
ok('the floor has a free table to seat', freeBefore > 0, `${freeBefore} free, ${turnsBefore} turns so far`);

// seat a party
await page.getByRole('button', { name: 'Seat guest' }).click();
await page.waitForTimeout(2000);
let seat = page.locator('.modal.show').last();
seat = await answerGate(page, seat);
await seat.locator('input[data-fieldname="guest_name"]').fill(GUEST);
await seat.locator('input[data-fieldname="covers"]').fill('2');
await seat.locator('input[data-fieldname="covers"]').press('Tab');
await page.waitForTimeout(2500);
await shot('seat');
await seat.getByRole('button', { name: 'Seat & open order' }).click();
await page.waitForTimeout(9000);
await shot('pad');
ok('seating opened the pad', await page.locator('.order-manage').count() > 0);
ok('the seated table is no longer offered whole',
   (await api('free_tables', { whole_table: 1 })).length === freeBefore - 1,
   `${freeBefore} -> ${(await api('free_tables', { whole_table: 1 })).length}`);

// open a check and ring a dish — both are double-click by design
await page.locator('.order-manage .btn-app.btn-order').first().dblclick({ force: true });
await page.waitForTimeout(6000);
for (const t of ['Deadlock', 'Not found', 'Error', 'Message']) {
  const box = page.locator('.modal.show').filter({ hasText: t });
  if (await box.count()) {
    await box.first().locator('.modal-header .btn-modal-close, .modal-header .close').first()
      .click({ force: true }).catch(() => {});
    await page.waitForTimeout(700);
  }
}
await page.evaluate(() => {
  const c = document.querySelectorAll('.order-manage .btn-app.btn-order');
  const chip = c[c.length - 1];
  if (chip && !chip.className.includes('selected')) chip.click();
});
await page.waitForTimeout(4000);
const add = page.locator('.order-manage .add-item:visible').first();
// The menu loads from the server; under load it is slower than a fixed sleep.
await add.waitFor({ state: 'visible', timeout: 45000 }).catch(() => {});
ok('the menu offers a dish', await add.count() > 0);
await add.click({ force: true });
await page.waitForTimeout(5000);
await shot('dish-added');

// pay
const complete = page.locator('.order-manage').getByText(/^Complete$/).first();
ok('Complete is on the pad', await complete.count() > 0);
await complete.click({ force: true });
await page.waitForTimeout(7000);
await shot('pay-form');
const pay = page.locator('.modal.show').last();
ok('the pay form opens', await pay.count() > 0,
   (await pay.innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 90));
ok('covers do not block payment', errs.length === 0, JSON.stringify(errs.slice(0, 2)));

const payBtn = pay.getByText(/^Pay\b/).first();
ok('a Pay button is offered', await payBtn.count() > 0);
await payBtn.click({ force: true });
await page.waitForTimeout(12000);
await shot('paid');
ok('payment raises no page error', errs.length === 0, JSON.stringify(errs.slice(0, 2)));

// the loop closes: table free again, turn on the board
await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(10000);
const freeAfter = (await api('free_tables', { whole_table: 1 })).length;
const metrics = await api('turn_metrics');
await shot('floor-after');
ok('the table is free for the next party', freeAfter === freeBefore, `${freeBefore} -> ${freeAfter}`);
ok('the turn was recorded', metrics.turns === turnsBefore + 1, `${turnsBefore} -> ${metrics.turns}`);
ok('the turn carries covers', metrics.covers >= 2, `${metrics.covers} covers`);

console.log('\nRESULT ' + results.filter(r => r.pass).length + ' passed, ' + results.filter(r => !r.pass).length + ' failed');
console.log('PAGE ERRORS ' + JSON.stringify(errs.slice(0, 5)));
await browser.close();
process.exit(results.some(r => !r.pass) ? 1 : 0);
