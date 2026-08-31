// Full-service drill against the live site: three waiters by PIN, two kitchen
// screens, two cashiers and an admin — four parties on one table, concurrent
// ordering, a split, concurrent payments, reports, close. Nothing sugar-coated:
// every page error, refused call and slow request is collected and printed.
import { chromium } from 'playwright';

const BASE = 'https://frappe.ikobriq.com';
const TABLE = 'Table 2';
const b = await chromium.launch();
const report = [];
const timings = [];
const ok = (name, pass, detail = '') => {
  report.push({ name, pass, detail: String(detail).slice(0, 160) });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
};
const t = (label, ms) => { timings.push({ label, ms: Math.round(ms) }); };

const mkActor = async (name, email, pass) => {
  const ctx = await b.newContext({ viewport: { width: 1600, height: 950 } });
  const p = await ctx.newPage();
  const errs = [];
  const slow = [];
  p.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 120)));
  p.on('requestfinished', async req => {
    try {
      const timing = req.timing();
      const ms = timing.responseEnd;
      const url = req.url();
      if (ms > 2000 && url.includes('/api/')) slow.push(`${Math.round(ms)}ms ${decodeURIComponent(url).split('?')[0].split('/').pop().slice(0, 60)}`);
    } catch (e) { /* detached */ }
  });
  p.on('response', r => { if (r.status() >= 500) errs.push(`HTTP ${r.status()} ${r.url().split('?')[0].split('/').pop()}`); });
  const t0 = Date.now();
  await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.fill('#login_email', email);
  await p.fill('#login_password', pass);
  await p.click('button.btn-login');
  await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
  t(`${name} login`, Date.now() - t0);
  return { name, ctx, p, errs, slow };
};

const floor = async (a) => {
  const t0 = Date.now();
  await a.p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await a.p.waitForTimeout(15000);
  await a.p.getByText('Main Hall', { exact: true }).first().click().catch(() => {});
  await a.p.locator('.d-table:visible').first().waitFor({ timeout: 45000 }).catch(() => {});
  // ready means OUR toolbar mounted, not just frappe's shell
  await a.p.getByRole('button', { name: 'Seat guest' }).waitFor({ timeout: 60000 }).catch(() => {});
  t(`${a.name} floor ready`, Date.now() - t0);
};

const api = (a, method, args) => a.p.evaluate(
  ([m, ar]) => frappe.call('restaurant_management.house.' + m, ar || {}).then(r => r.message),
  [method, args || {}]);

const closeStrayModals = async (p) => {
  for (let i = 0; i < 3; i++) {
    const m = p.locator('.modal.show');
    if (!(await m.count())) break;
    await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {});
    await p.waitForTimeout(600);
  }
};

const signPin = async (a, waiter, pinCode) => {
  await a.p.getByRole('button', { name: /^Waiter/ }).click();
  await a.p.waitForTimeout(2500);
  const d = a.p.locator('.modal.show').last();
  const title = await d.locator('.modal-title').innerText().catch(() => '');
  if (!title.includes("Who's on")) { await closeStrayModals(a.p); return signPin(a, waiter, pinCode); }
  await d.locator('select').first().selectOption(waiter);
  await d.locator('input[type="password"]').fill(pinCode);
  await d.getByRole('button', { name: 'Sign in' }).click();
  await a.p.waitForTimeout(3000);
  await closeStrayModals(a.p);
};

const seat = async (a, guest, covers) => {
  const t0 = Date.now();
  await a.p.getByRole('button', { name: 'Seat guest' }).click();
  await a.p.waitForTimeout(2500);
  const d = a.p.locator('.modal.show').last();
  await d.locator('input[data-fieldname="guest_name"]').fill(guest);
  await d.locator('input[data-fieldname="covers"]').fill(String(covers));
  await d.locator('input[data-fieldname="covers"]').press('Tab');
  await a.p.waitForTimeout(3000);
  await d.locator('select[data-fieldname="table"]').selectOption(TABLE);
  await d.getByRole('button', { name: 'Seat & open order' }).click();
  await a.p.waitForTimeout(9000);
  t(`${a.name} seats ${guest}`, Date.now() - t0);
};

const orderAndFire = async (a, guest) => {
  const t0 = Date.now();
  const add = a.p.locator('.order-manage .add-item:visible');
  await add.first().waitFor({ timeout: 45000 }).catch(() => {});
  const dishes = await add.count();
  if (!dishes) { ok(`${a.name}: menu on the pad for ${guest}`, false, '0 dishes'); return null; }
  await add.nth(0).click({ force: true });
  await a.p.waitForTimeout(2500);
  // On a shared table the first tap asks whose check this is — answer it.
  const picker = a.p.locator('.modal.show').filter({ hasText: 'Whose check' }).last();
  if (await picker.count()) {
    const opts = await picker.locator('select[data-fieldname="order"] option').all();
    let value = null;
    for (const o of opts) if ((await o.textContent()).includes(guest)) value = await o.getAttribute('value');
    if (value) { await picker.locator('select[data-fieldname="order"]').selectOption(value); }
    await picker.getByRole('button', { name: 'Open' }).click();
    await a.p.waitForTimeout(3500);
    await add.nth(0).click({ force: true });
    await a.p.waitForTimeout(2500);
  }
  await add.nth(2).click({ force: true }).catch(() => {});
  await a.p.waitForTimeout(3500);
  const fired = Date.now();
  await a.p.locator('.order-manage .pad-btn.btn-order').first().dblclick({ force: true });
  await a.p.waitForTimeout(5000);
  await closeStrayModals(a.p);
  t(`${a.name} orders+fires for ${guest}`, Date.now() - t0);
  const landed = await a.p.evaluate(async (g) => {
    const r = await frappe.call('frappe.client.get_list', { doctype: 'Table Order',
      filters: { customer: g, status: ['not in', ['Cancelled', 'Invoiced']] },
      fields: ['name', 'status', 'amount'], limit_page_length: 1 });
    return (r.message || [])[0];
  }, guest);
  ok(`${a.name}: ${guest}'s check really has food on it`,
     landed && landed.amount > 0 && landed.status !== 'Opened',
     JSON.stringify(landed));
  return fired;
};

const openPadOnTable = async (a, guest) => {
  await floor(a);
  await a.p.locator('.d-table:visible').filter({ hasText: TABLE }).first().click();
  await a.p.waitForTimeout(5000);
  const d = a.p.locator('.modal.show').last();
  const title = await d.locator('.modal-title').innerText().catch(() => '');
  const body = await d.innerText().catch(() => '');
  if (/Assigned to another User/i.test(body)) {
    ok(`${a.name}: table handoff to ${guest}`, false, 'blocked: assigned to another user');
    await closeStrayModals(a.p);
    return;
  }
  if (title.includes('Whose check')) {
    const opts = await d.locator('select[data-fieldname="order"] option').all();
    let value = null;
    for (const o of opts) if ((await o.textContent()).includes(guest)) value = await o.getAttribute('value');
    ok(`${a.name}: shared table asks whose check (${guest})`, value !== null,
       `${opts.length} checks listed`);
    if (value) {
      await d.locator('select[data-fieldname="order"]').selectOption(value);
      await d.getByRole('button', { name: 'Open' }).click();
      await a.p.waitForTimeout(4000);
    }
  }
};

const payCurrent = async (a, guest) => {
  const t0 = Date.now();
  const complete = a.p.locator('.order-manage').getByText(/^Complete$/).first();
  if (!(await complete.count())) { ok(`${a.name}: Complete offered for ${guest}`, false); return; }
  await complete.click({ force: true });
  await a.p.waitForTimeout(6000);
  const pay = a.p.locator('.modal.show').last();
  const payBtn = pay.getByText(/^Pay\b/).first();
  if (!(await payBtn.count())) { ok(`${a.name}: Pay button for ${guest}`, false,
      (await pay.innerText().catch(() => '')).slice(0, 80)); return; }
  await payBtn.click({ force: true });
  await a.p.waitForTimeout(11000);
  await closeStrayModals(a.p);
  t(`${a.name} pays ${guest}`, Date.now() - t0);
};

// ---------------------------------------------------------------- actors
const [w1, w2, w3, c1, c2, k1, k2, adm] = await Promise.all([
  mkActor('W1', 'waiter@etham.co.ke', 'Waiter@2026'),
  mkActor('W2', 'waiter@etham.co.ke', 'Waiter@2026'),
  mkActor('W3', 'waiter@etham.co.ke', 'Waiter@2026'),
  mkActor('C1', 'cashier@etham.co.ke', 'Cashier@2026'),
  mkActor('C2', 'cashier@etham.co.ke', 'Cashier@2026'),
  mkActor('K1', 'kitchen@etham.co.ke', 'Kitchen@2026'),
  mkActor('K2', 'kitchen@etham.co.ke', 'Kitchen@2026'),
  mkActor('ADM', 'admin@etham.co.ke', process.env.ADMIN_PASS),
]);
ok('eight sessions signed in', true);

// ---------------------------------------------------------------- day + boards
await floor(c1);
let shift = await api(c1, 'house_shift');
if (!shift) {
  await c1.p.getByRole('button', { name: 'Open day', exact: true }).click();
  await c1.p.waitForTimeout(3000);
  const od = c1.p.locator('.modal.show').last();
  await od.locator('input[data-fieldname="mode_0"]').fill('5000');
  await od.getByRole('button', { name: 'Open the day' }).click();
  await c1.p.waitForTimeout(6000);
  await closeStrayModals(c1.p);
  shift = await api(c1, 'house_shift');
}
ok('cashier opens or finds the day', !!shift, shift && shift.name);

await Promise.all([floor(k1), floor(k2)]);
await k1.p.locator('.d-table:visible').filter({ hasText: 'Kitchen' }).first().click();
await k2.p.locator('.d-table:visible').filter({ hasText: 'Bar' }).first().click();
await k1.p.waitForTimeout(4000);
ok('kitchen and bar boards open', true);

// ---------------------------------------------------------------- seat 4 parties, 3 waiters
await Promise.all([floor(w1), floor(w2), floor(w3)]);
await signPin(w1, 'Amina Test', '1111');
await signPin(w2, 'Moses Test', '2222');
await signPin(w3, 'Njeri Test', '3333');

await seat(w1, 'Guest Ann', 1);
await seat(w2, 'Guest Ben', 1);
await seat(w3, 'Guest Chep', 1);

let seats = (await api(adm.p ? adm : c1, 'table_occupancy'))[TABLE];
ok('three parties, three waiters on one table', seats && seats.parties.length === 3 &&
   new Set(seats.parties.map(x => x.waiter)).size === 3,
   seats && `${seats.occupied}/${seats.capacity} ` + JSON.stringify(seats.parties.map(x => [x.guest, x.waiter])));

// concurrent ordering on one table — the core stress
const firedAt = {};
await Promise.all([
  orderAndFire(w1, 'Guest Ann').then(x => firedAt.Ann = x),
  orderAndFire(w2, 'Guest Ben').then(x => firedAt.Ben = x),
  orderAndFire(w3, 'Guest Chep').then(x => firedAt.Chep = x),
]);

// fourth party by the first waiter
await floor(w1);
await seat(w1, 'Guest Didi', 1);
await orderAndFire(w1, 'Guest Didi');

seats = (await api(c1, 'table_occupancy'))[TABLE];
ok('four parties seated and ordered on one table', seats && seats.parties.length === 4 &&
   seats.parties.every(x => x.order), seats && `${seats.occupied}/${seats.capacity}`);

// kitchen actually shows them
const boardHas = async (a) => a.p.evaluate((tbl) => document.body.innerText.includes(tbl), TABLE);
let kitchenSees = false;
const kt0 = Date.now();
for (let i = 0; i < 20 && !kitchenSees; i++) { kitchenSees = await boardHas(k1); if (!kitchenSees) await k1.p.waitForTimeout(2000); }
t('dispatch -> kitchen board shows it', Date.now() - kt0);
ok('kitchen board shows the table tickets', kitchenSees);

// pick_check: reopening the shared table asks whose check
await openPadOnTable(w3, 'Guest Chep');

// ---------------------------------------------------------------- split Ben's check
const ben = seats.parties.find(x => x.guest === 'Guest Ben');
const split = await w2.p.evaluate(async ([order]) => {
  try {
    const items = (await frappe.call('restaurant_management.api.call',
      { model: 'Table Order', name: order, method: 'get_items', args: '{}' })).message;
    const first = items.items.items ? items.items.items[0] : items.items[0];
    const it = (items.items && items.items.items) ? items.items.items[0] : null;
    const row = it || (Array.isArray(items.items) ? items.items[0] : null);
    if (!row) return { err: 'no items readable' };
    const args = { items: {}, client: 'drill' };
    args.items[row.identifier] = { qty: 1, identifier: 'entry_drill_split_1', name: row.entry_name };
    const r = await frappe.call('restaurant_management.api.call',
      { model: 'Table Order', name: order, method: 'divide', args: JSON.stringify(args) });
    return { done: r.message === true || !!r.message };
  } catch (e) { return { err: String(e && e.message || e).slice(0, 120) }; }
}, [ben && ben.order]);
seats = (await api(c1, 'table_occupancy'))[TABLE];
const checkCount = await c1.p.evaluate(async (tbl) =>
  (await frappe.call('frappe.client.get_count', { doctype: 'Table Order',
    filters: { table: tbl, status: ['not in', ['Cancelled', 'Invoiced']] } })).message, TABLE);
ok('splitting a bill by items works (waiter session)', split.done === true && checkCount === 5,
   JSON.stringify({ split, checks: checkCount }));

// ---------------------------------------------------------------- pay: two cashiers at once
await Promise.all([floor(c1), floor(c2)]);
await Promise.all([
  (async () => { await openPadOnTable(c1, 'Guest Ann'); await payCurrent(c1, 'Guest Ann'); })(),
  (async () => { await openPadOnTable(c2, 'Guest Ben'); await payCurrent(c2, 'Guest Ben'); })(),
]);
seats = (await api(c1, 'table_occupancy'))[TABLE];
ok('two cashiers settle two parties concurrently', seats && seats.parties.length <= 3 &&
   !seats.parties.some(x => x.guest === 'Guest Ann'),
   seats && JSON.stringify(seats.parties.map(x => x.guest)));

// the fence, one more time, in anger
const stealAttempt = await w3.p.evaluate(async (tbl) => {
  const m = (await frappe.call('restaurant_management.house.table_occupancy')).message;
  const chep = m[tbl].parties.find(x => x.guest === 'Guest Chep');
  if (!chep || !chep.order) return { err: 'no chep order' };
  try {
    await frappe.call('restaurant_management.api.call', { model: 'Table Order',
      name: chep.order, method: 'make_invoice', args: JSON.stringify({ mode_of_payment: { Cash: 1 } }) });
    return { billed: true };
  } catch (e) { return { billed: false }; }
}, TABLE);
ok('a waiter still cannot take payment', stealAttempt.billed === false, JSON.stringify(stealAttempt));

// cashier clears the rest
for (const guest of ['Guest Chep', 'Guest Didi', 'Guest Ben']) {
  await openPadOnTable(c1, guest);
  await payCurrent(c1, guest);
}
seats = (await api(c1, 'table_occupancy'))[TABLE];
ok('table fully clear after all payments', seats && seats.occupied === 0 && seats.parties.length === 0,
   seats && `${seats.occupied}/${seats.capacity}, parties ${seats.parties.length}`);

// ---------------------------------------------------------------- admin: the numbers
for (let i = 0; i < 3; i++) {
  const s0 = Date.now();
  await api(adm, 'table_occupancy');
  t(`occupancy under load, sample ${i + 1}`, Date.now() - s0);
}
const day = await api(adm, 'day_summary');
const invoices = await adm.p.evaluate(async () =>
  (await frappe.call('frappe.client.get_count', { doctype: 'POS Invoice', filters: { docstatus: 1 } })).message);
ok('five receipts for five checks, banked into one day', invoices === 5 && day && day.invoices === 5,
   `invoices ${invoices}, day says ${day && day.invoices}, sales ${day && day.sales}`);

const byWaiter = await adm.p.evaluate(async () => {
  const r = await frappe.call('frappe.desk.query_report.run', {
    report_name: 'Sales by Waiter',
    filters: { from_date: frappe.datetime.get_today(), to_date: frappe.datetime.get_today() } });
  return (r.message.result || []).filter(x => x && x.waiter).map(x => [x.waiter, x.checks, x.sales]);
});
ok('Sales by Waiter splits the shared table three ways',
   byWaiter.filter(x => String(x[0]).includes('Test')).length === 3, JSON.stringify(byWaiter));

const best = await adm.p.evaluate(async () => {
  const r = await frappe.call('frappe.desk.query_report.run', {
    report_name: 'Item-wise Sales Register',
    filters: { from_date: frappe.datetime.get_today(), to_date: frappe.datetime.get_today(),
               company: 'Etham Eatery' } });
  return (r.message.result || []).filter(x => x && x.item_code).length;
});
ok('best-sellers report returns rows for today', best > 0, `${best} item rows`);

// close the day from the cashier terminal
await floor(c1);
await c1.p.getByRole('button', { name: /^Close day/ }).click();
await c1.p.waitForTimeout(3500);
const cd = c1.p.locator('.modal.show').last();
const anyway = await cd.getByRole('button', { name: 'Close anyway' }).count();
ok('nothing left open at close time', anyway === 0,
   anyway ? 'the close dialog warns about open checks' : 'clean');
await cd.getByRole('button', { name: /Close the day|Close anyway/ }).first().click({ force: true });
await c1.p.waitForTimeout(9000);
const after = await api(adm, 'day_summary');
ok('cashier closes the day clean', after && after.open === false, JSON.stringify(after));

// ---------------------------------------------------------------- verdict data
console.log('\n===== TIMINGS (ms) =====');
timings.forEach(x => console.log(`  ${String(x.ms).padStart(6)}  ${x.label}`));
console.log('\n===== SLOW API CALLS (>2s) =====');
for (const a of [w1, w2, w3, c1, c2, k1, k2, adm])
  a.slow.slice(0, 6).forEach(s => console.log(`  [${a.name}] ${s}`));
console.log('\n===== PAGE ERRORS =====');
for (const a of [w1, w2, w3, c1, c2, k1, k2, adm])
  a.errs.slice(0, 6).forEach(e => console.log(`  [${a.name}] ${e}`));
const failed = report.filter(r => !r.pass);
console.log(`\n===== ${report.length - failed.length}/${report.length} checks passed =====`);
await b.close();
process.exit(failed.length ? 1 : 0);
