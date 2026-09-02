// Live proof after a deploy, with nothing left in the books: a waiter by PIN
// seats a party in the second room and fires a dish, the kitchen screen shows
// the ticket with the waiter's name, the till opens the check and reaches the
// pay screen — then the till RELEASES the table instead of paying, so no
// invoice is written and the day stays open.
//   BASE=https://frappe.ikobriq.com WAITER=sharon PIN=5566 node live_smoke.mjs
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'https://frappe.ikobriq.com';
const ROOM = process.env.ROOM || 'R 2';
const TABLE = process.env.TABLE || 'Table 7';
const WAITER = process.env.WAITER || 'sharon';
const PIN = process.env.PIN || '5566';
const GUEST = 'Smoke ' + new Date().toISOString().slice(11, 16).replace(':', '');

const b = await chromium.launch();
const report = [];
const ok = (name, pass, detail = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + String(detail).slice(0, 180) : ''}`); };

const mk = async (name, email, pass) => {
  const ctx = await b.newContext({ viewport: { width: 1500, height: 900 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 120)));
  p.on('response', r => { if (r.status() >= 500) errs.push(`HTTP ${r.status()} ${r.url().split('?')[0].split('/').pop()}`); });
  await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.fill('#login_email', email); await p.fill('#login_password', pass); await p.click('button.btn-login');
  await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
  ok(`${name} signs in`, !/\/login/.test(p.url()));
  return { name, p, errs };
};
const floor = async (a, room = ROOM) => {
  await a.p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await a.p.waitForTimeout(15000);
  if (room) { await a.p.getByText(room, { exact: true }).first().click().catch(() => {}); await a.p.waitForTimeout(3500); }
};
const closeModals = async (p) => {
  for (let i = 0; i < 4; i++) {
    const m = p.locator('.modal.show'); if (!(await m.count())) break;
    await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {});
    await p.waitForTimeout(600);
  }
};

const w = await mk('waiter tablet', 'waiter@etham.co.ke', 'Waiter@2026');
const k = await mk('kitchen screen', 'kitchen@etham.co.ke', 'Kitchen@2026');
const c = await mk('till', 'cashier@etham.co.ke', 'Cashier@2026');

// the critical fix: stations see the floor again
await floor(w);
const wBody = await w.p.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
ok('waiter tablet shows the rooms and Room 2 tables', wBody.includes(ROOM) && /Table 7/.test(wBody), wBody.slice(0, 120));
ok('waiter tablet hides Kitchen/Bar and money', !/\bKitchen\b|\bBar\b|Open day|Close day/.test(wBody));
await floor(k, null);
const kBody = await k.p.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
ok('kitchen screen shows its boards, no tables', /Kitchen/.test(kBody) && /Bar/.test(kBody) && !/Table \d/.test(kBody), kBody.slice(0, 120));
await k.p.locator('.d-table:visible').filter({ hasText: 'Kitchen' }).first().click().catch(() => {});
await k.p.waitForTimeout(4000);

// waiter: PIN, seat, order, fire
await w.p.getByRole('button', { name: /^Waiter/ }).click();
await w.p.waitForTimeout(2500);
let d = w.p.locator('.modal.show').last();
await d.locator('select').first().selectOption(WAITER);
await d.locator('input[type="password"]').fill(PIN);
await d.getByRole('button', { name: 'Sign in' }).click();
await w.p.waitForTimeout(3000);
const pinErr = await w.p.locator('.modal.show').last().innerText().catch(() => '');
ok(`${WAITER} signs in with PIN ${PIN}`, !/Wrong PIN/i.test(pinErr));
await closeModals(w.p);

await w.p.getByRole('button', { name: 'Seat guest' }).click();
await w.p.waitForTimeout(2500);
d = w.p.locator('.modal.show').last();
await d.locator('input[data-fieldname="guest_name"]').fill(GUEST);
await d.locator('input[data-fieldname="covers"]').fill('2');
await d.locator('input[data-fieldname="covers"]').press('Tab');
await w.p.waitForTimeout(3000);
const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
const want = opts.find(o => o.includes(TABLE));
ok(`${TABLE} in ${ROOM} is offered`, !!want, opts.join(' | ').slice(0, 120));
await d.locator('select[data-fieldname="table"]').selectOption({ label: want });
await d.getByRole('button', { name: 'Seat & open order' }).click();
await w.p.waitForTimeout(9000);

const cards = w.p.locator('.order-manage .small-box.item:visible');
await cards.first().waitFor({ timeout: 45000 }).catch(() => {});
ok('the pad shows the menu as photo-first cards', (await cards.count()) > 0 && (await w.p.locator('.order-manage .rm-price').count()) > 0, `${await cards.count()} cards`);
const dish = (await cards.first().locator('.title').innerText()).trim();
await cards.first().locator('.add-item').click({ force: true });
await w.p.waitForTimeout(3500);
ok('+ puts the dish on the check', (await cards.first().locator('.qty-in-cart').innerText()).trim() === '1', dish);
await w.p.locator('.order-manage .pad-btn.btn-order').first().dblclick({ force: true });
await w.p.waitForTimeout(5000);
await closeModals(w.p);
const check = await c.p.evaluate(async (g) => {
  const r = await frappe.call('frappe.client.get_list', { doctype: 'Table Order',
    filters: { customer: g, status: ['not in', ['Cancelled', 'Invoiced']] }, fields: ['name', 'status', 'amount', 'table', 'waiter'], limit_page_length: 1 });
  return (r.message || [])[0];
}, GUEST);
ok('the check is fired, on the right table, owned by the waiter', !!check && check.amount > 0 && check.status !== 'Opened' && check.table === TABLE && check.waiter === WAITER, JSON.stringify(check));

// kitchen: the ticket arrives and names the waiter
let seen = '';
for (let i = 0; i < 20; i++) {
  seen = await k.p.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
  if (seen.includes(TABLE)) break;
  await k.p.waitForTimeout(2000);
}
ok(`kitchen board shows the ${ROOM} ticket`, seen.includes(TABLE), seen.slice(seen.indexOf(TABLE) - 40, seen.indexOf(TABLE) + 60));
ok('the ticket names the waiter and no "undefined"', new RegExp(WAITER, 'i').test(seen) && !/undefined/.test(seen));

// till: opens the check, reaches the pay screen, then releases instead of paying
await floor(c);
await c.p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first().click({ force: true });
await c.p.waitForTimeout(6000);
const complete = c.p.locator('.order-manage').getByText(/^Complete$/).first();
ok('till sees Complete on the check', (await complete.count()) > 0);
await complete.click({ force: true });
await c.p.waitForTimeout(6000);
const pay = c.p.locator('.modal.show').last();
const payText = await pay.innerText().catch(() => '');
ok('till reaches the pay screen with the total', /Pay/.test(payText) && new RegExp(String(Math.round(check ? check.amount : -1))).test(payText.replace(/,/g, '')), payText.replace(/\s+/g, ' ').slice(0, 120));
await closeModals(c.p);
await c.p.waitForTimeout(1500);

const released = await c.p.evaluate(async (tbl) => {
  try { return await frappe.call('restaurant_management.house.release_table', { table: tbl }).then(r => r.message); }
  catch (e) { return { err: String(e && e.message || e).slice(0, 120) }; }
}, TABLE);
const after = await c.p.evaluate(async (tbl) => (await frappe.call('restaurant_management.house.table_occupancy')).message[tbl], TABLE);
ok('till releases the table: no invoice written, seats free again', !(released && released.err) && after && after.occupied === 0 && after.parties.length === 0, JSON.stringify({ released, after: after && `${after.occupied}/${after.capacity}` }));
const books = await c.p.evaluate(async () => ({
  invoices: (await frappe.call('frappe.client.get_count', { doctype: 'POS Invoice' })).message,
  open_checks: (await frappe.call('frappe.client.get_count', { doctype: 'Table Order', filters: { status: ['not in', ['Cancelled', 'Invoiced']] } })).message,
}));
ok('books untouched: 0 invoices, 0 open checks', books.invoices === 0 && books.open_checks === 0, JSON.stringify(books));

console.log('PAGE ERRORS', JSON.stringify([...w.errs, ...k.errs, ...c.errs]));
ok('no page errors on any station', !w.errs.length && !k.errs.length && !c.errs.length);
console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
