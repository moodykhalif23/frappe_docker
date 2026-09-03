// A delivery, end to end: a rider signs in by PIN, seats "the order" on a
// Delivery slot with an address, fires it, the kitchen ticket shows where it
// goes, the till completes it with the fee on the bill, and Sales by Waiter
// credits the rider. Runs on a test site — it writes an invoice.
//   BASE=http://pos.localhost:8080 node delivery_drill.mjs
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const RIDER = process.env.RIDER || 'Moses Test', PIN = process.env.PIN || '2222';
const GUEST = 'Delivery Drill ' + Date.now().toString().slice(-4);
const ADDRESS = 'Plot 12, Riverside Drive — blue gate';
const b = await chromium.launch();
const report = [];
const ok = (name, pass, detail = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + String(detail).slice(0, 200) : ''}`); };
const mk = async (email, pass) => {
  const p = await (await b.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
  p.on('pageerror', e => console.log('PAGEERROR', email, String(e).slice(0, 140)));
  await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.fill('#login_email', email); await p.fill('#login_password', pass); await p.click('button.btn-login');
  await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
  await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(15000);
  return p;
};
const closeModals = async (p) => { for (let i = 0; i < 4; i++) { const m = p.locator('.modal.show'); if (!(await m.count())) break; await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {}); await p.waitForTimeout(600); } };

const w = await mk('waiter@etham.co.ke', 'Waiter@2026');
const k = await mk('kitchen@etham.co.ke', 'Kitchen@2026');
const c = await mk('cashier@etham.co.ke', 'Cashier@2026');

const setup = await c.evaluate(async () => (await frappe.call('restaurant_management.house.delivery_room')).message);
ok('a Delivery room and a fee are configured', !!(setup && setup.room), JSON.stringify(setup));
const slot = await c.evaluate(async (room) => (await frappe.call('frappe.client.get_list', { doctype: 'Restaurant Object', filters: { room, type: 'Table' }, fields: ['name'], limit_page_length: 1 })).message[0].name, setup.room);

// the kitchen watches its board
await k.locator('.d-table:visible').filter({ hasText: 'Kitchen' }).first().click().catch(() => {}); await k.waitForTimeout(3000);

// rider: PIN, then seat the delivery with its address
await w.getByText(setup.room, { exact: true }).first().click().catch(() => {}); await w.waitForTimeout(3000);
await w.getByRole('button', { name: /^Waiter/ }).click(); await w.waitForTimeout(2500);
let d = w.locator('.modal.show').last();
await d.locator('select').first().selectOption(RIDER); await d.locator('input[type="password"]').fill(PIN);
await d.getByRole('button', { name: 'Sign in' }).click(); await w.waitForTimeout(3000); await closeModals(w);
await w.getByRole('button', { name: 'Seat guest' }).click(); await w.waitForTimeout(2500);
d = w.locator('.modal.show').last();
await d.locator('input[data-fieldname="guest_name"]').fill(GUEST);
await d.locator('input[data-fieldname="covers"]').fill('1'); await d.locator('input[data-fieldname="covers"]').press('Tab');
await d.locator('input[data-fieldname="contact"]').fill('0712 000 111');
await w.waitForTimeout(3000);
const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
const want = opts.find(o => o.includes(slot));
ok(`the Delivery slot ${slot} is offered`, !!want, opts.join(' | ').slice(0, 120));
await d.locator('select[data-fieldname="table"]').selectOption({ label: want }); await w.waitForTimeout(2500);
const addr = d.locator('textarea[data-fieldname="address"]');
ok('the address field appears for a Delivery slot', await addr.isVisible().catch(() => false));
await addr.fill(ADDRESS);
await d.getByRole('button', { name: 'Seat & open order' }).click(); await w.waitForTimeout(9000);

const check = await c.evaluate(async (g) => (await frappe.call('frappe.client.get_list', { doctype: 'Table Order', filters: { customer: g }, fields: ['name', 'is_delivery', 'delivery_notes', 'charge_amount', 'waiter', 'table'], limit_page_length: 1 })).message[0], GUEST);
ok('the check is flagged delivery, with the address and the fee, owned by the rider',
   !!check && check.is_delivery === 1 && (check.delivery_notes || '').includes('Riverside') && check.waiter === RIDER && Number(check.charge_amount) === Number(setup.fee), JSON.stringify(check));

const cards = w.locator('.order-manage .small-box.item:visible'); await cards.first().waitFor({ timeout: 45000 });
await cards.first().locator('.add-item').click({ force: true }); await w.waitForTimeout(3500);
await w.locator('.order-manage .pad-btn.btn-order').first().dblclick({ force: true }); await w.waitForTimeout(6000); await closeModals(w);

// the ticket names the guest in the open; the address sits behind its "Show Address" link
let board = '', hidden = '';
for (let i = 0; i < 15; i++) {
  board = await k.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
  hidden = await k.evaluate(() => Array.from(document.querySelectorAll('[data-name="delivery_address"]')).map(e => e.textContent).join(' | '));
  if (board.includes(GUEST) && hidden.includes('Riverside')) break;
  await k.waitForTimeout(2000);
}
ok('the kitchen ticket names the guest and carries the address', board.includes(GUEST) && hidden.includes('Riverside'),
   `visible: ${board.slice(Math.max(0, board.indexOf(slot) - 30), board.indexOf(slot) + 120)} | address: ${hidden.slice(0, 80)}`);

// the till completes it: the fee is on the pay screen and on the bill
await c.getByText(setup.room, { exact: true }).first().click().catch(() => {}); await c.waitForTimeout(3000);
await c.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${slot}\\b`) }).first().click({ force: true }); await c.waitForTimeout(6000);
await c.locator('.order-manage').getByText(/^Complete$/).first().click({ force: true }); await c.waitForTimeout(6000);
const pay = c.locator('.modal.show').last();
const payState = await pay.evaluate(m => ({
  is_delivery: (m.querySelector('input[data-fieldname="is_delivery"]') || {}).checked,
  charge: (m.querySelector('[data-fieldname="charge_amount"] input, input[data-fieldname="charge_amount"]') || {}).value,
  address_reqd: !!(m.querySelector('[data-fieldname="address"].has-error, [data-fieldname="address"] .reqd, [data-fieldname="address"] label.reqd')),
  fields: Array.from(m.querySelectorAll('input[data-fieldname], textarea[data-fieldname]')).map(i => i.dataset.fieldname + '=' + (i.type === 'checkbox' ? i.checked : i.value)).join(' '),
  text: m.innerText.replace(/\s+/g, ' ').slice(0, 120) }));
// Currency inputs carry no data-fieldname; ask the pay form object for its value
const feeShown = await c.evaluate(() => {
  const om = Object.values(RM.objects || {}).map(o => o && o.order_manage).find(Boolean);
  const pf = om && om.current_order && om.current_order.pay_form;
  return pf && pf.get_value ? pf.get_value('charge_amount') : null;
});
const feeNumber = Number(String(feeShown ?? '').replace(/[^0-9.]/g, ''));
ok('the pay screen opens as a delivery with the fee filled in', payState.is_delivery === true && feeNumber === Number(setup.fee), `fee shown "${feeShown}" | ${payState.fields.slice(0, 160)}`);
if (process.env.NO_PAY) {
  // a live site: prove the pay screen, then release the slot — no invoice is written
  await closeModals(c);
  const rel = await c.evaluate(async (t) => (await frappe.call('restaurant_management.house.release_table', { table: t })).message, slot);
  const after = await c.evaluate(async (t) => (await frappe.call('restaurant_management.house.table_occupancy')).message[t], slot);
  ok('the slot is released with nothing written to the books', !!rel && after && after.occupied === 0, JSON.stringify({ rel, after: after && `${after.occupied}/${after.capacity}` }));
  console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
  await b.close();
  process.exit(report.every(Boolean) ? 0 : 1);
}
const pagesBefore = c.context().pages().length;
// the receipt prints from THIS tab: the print view is fetched by a frame inside it, and no tab opens
const printFetches = [];
c.on('request', r => { if (/\/printview\?/.test(r.url()) && r.frame() !== c.mainFrame()) printFetches.push(r.url()); });
await pay.getByText(/^Pay\b/).first().click({ force: true }); await c.waitForTimeout(12000);
ok('the receipt prints from the same tab, no new tab', c.context().pages().length === pagesBefore && printFetches.length > 0 && /trigger_print=1/.test(printFetches[0]), JSON.stringify({ tabs: c.context().pages().length, fetches: printFetches.slice(0, 2).map(u => u.replace(/^.*\/printview\?/, '').slice(0, 90)) }));
console.log('after Pay:', await c.evaluate(() => Array.from(document.querySelectorAll('.modal.show .modal-title, .msgprint, .desk-alert')).map(e => e.innerText.trim().slice(0, 100)).join(' | ')));
await closeModals(c);

const inv = await c.evaluate(async (g) => {
  const r = (await frappe.call('frappe.client.get_list', { doctype: 'POS Invoice', filters: { customer: g, docstatus: 1 }, fields: ['name', 'grand_total', 'net_total', 'total_taxes_and_charges'], limit_page_length: 1 })).message[0];
  if (!r) return null;
  const taxes = (await frappe.call('frappe.client.get_list', { doctype: 'Sales Taxes and Charges', parent: 'POS Invoice', filters: { parent: r.name }, fields: ['account_head', 'tax_amount', 'description'], limit_page_length: 10 })).message;
  return { ...r, taxes };
}, GUEST);
ok('the bill carries the delivery fee on its own account line', !!inv && (inv.taxes || []).some(t => /Delivery/.test(t.account_head) && Number(t.tax_amount) === Number(setup.fee)) && Number(inv.grand_total) === Number(inv.net_total) + Number(setup.fee), JSON.stringify(inv));

const byWaiter = await c.evaluate(async (room) => {
  const r = await frappe.call('frappe.desk.query_report.run', { report_name: 'Sales by Waiter', filters: { from_date: frappe.datetime.get_today(), to_date: frappe.datetime.get_today(), room } });
  return (r.message.result || []).filter(x => x && x.waiter).map(x => [x.waiter, x.checks, x.sales]);
}, setup.room);
ok('Sales by Waiter, filtered to the Delivery room, credits the rider', byWaiter.some(x => x[0] === RIDER), JSON.stringify(byWaiter));
const after = await c.evaluate(async (t) => (await frappe.call('restaurant_management.house.table_occupancy')).message[t], slot);
ok('the slot is free again after payment', !!after && after.occupied === 0, after && `${after.occupied}/${after.capacity}`);
// and the cashier's OWN floor shows it free without any reload
await closeModals(c); await c.waitForTimeout(4000);
const tileNow = await c.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${slot}\\b`) }).first().evaluate(el => ({ text: el.innerText.replace(/\s+/g, ' ').trim(), badges: el.querySelectorAll('.rm-party').length }));
ok('the floor shows the slot free at once, no reload', tileNow.badges === 0 && !/\d+\/\d+/.test(tileNow.text.replace(/\b\d+\b(?!\/)/, '')) , JSON.stringify(tileNow));

console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
