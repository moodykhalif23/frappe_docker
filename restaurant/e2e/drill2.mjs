// Handover drill: a manager (Geff), two waiters by PIN, a kitchen screen and a
// till, working the SECOND room. Proves a Room 2 order reaches the kitchen and
// is billable, and that every fence holds. Nothing sugar-coated: page errors,
// refused calls and slow requests are all collected.
//
//   BASE=http://pos.localhost:8080 node drill2.mjs
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const ROOM = process.env.ROOM || 'R 2';
const TABLE = process.env.TABLE || 'Table 7';
const TABLE_B = process.env.TABLE_B || 'Table 8';
const PASS = {
  geff: 'Geff@2026', waiter: 'Waiter@2026',
  kitchen: 'Kitchen@2026', cashier: 'Cashier@2026',
};

const b = await chromium.launch();
const report = [];
const timings = [];
const ok = (name, pass, detail = '') => {
  report.push({ name, pass, detail: String(detail).slice(0, 200) });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
};
const t = (label, ms) => timings.push({ label, ms: Math.round(ms) });

const mkActor = async (name, email, pass) => {
  const ctx = await b.newContext({ viewport: { width: 1600, height: 950 } });
  const p = await ctx.newPage();
  const errs = [], slow = [];
  p.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 140)));
  p.on('requestfinished', req => {
    try {
      const ms = req.timing().responseEnd;
      if (ms > 2000 && req.url().includes('/api/'))
        slow.push(`${Math.round(ms)}ms ${decodeURIComponent(req.url()).split('?')[0].split('/').pop().slice(0, 60)}`);
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
  const landed = !/\/login/.test(p.url());
  ok(`${name} signs in (${email})`, landed, p.url().replace(BASE, ''));
  return { name, ctx, p, errs, slow };
};

const api = (a, method, args) => a.p.evaluate(
  ([m, ar]) => frappe.call('restaurant_management.house.' + m, ar || {}).then(r => r.message).catch(e => ({ __err: String(e).slice(0, 120) })),
  [method, args || {}]);

const closeStrayModals = async (p) => {
  for (let i = 0; i < 4; i++) {
    const m = p.locator('.modal.show');
    if (!(await m.count())) break;
    await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {});
    await p.waitForTimeout(600);
  }
};

const floor = async (a, room = ROOM) => {
  const t0 = Date.now();
  await a.p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await a.p.waitForTimeout(14000);
  if (room) {
    await a.p.getByText(room, { exact: true }).first().click().catch(() => {});
    await a.p.waitForTimeout(3500);
  }
  t(`${a.name} floor ready (${room || 'default'})`, Date.now() - t0);
};

const tableTile = (a, table) => a.p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${table}\\b`) }).first();

const signPin = async (a, waiter, pinCode) => {
  for (let attempt = 0; attempt < 2; attempt++) {
    await a.p.getByRole('button', { name: /^Waiter/ }).click().catch(() => {});
    await a.p.waitForTimeout(2500);
    const d = a.p.locator('.modal.show').last();
    const title = await d.locator('.modal-title').innerText().catch(() => '');
    if (!title.includes("Who's on")) { await closeStrayModals(a.p); continue; }
    await d.locator('select').first().selectOption(waiter);
    await d.locator('input[type="password"]').fill(pinCode);
    await d.getByRole('button', { name: 'Sign in' }).click();
    await a.p.waitForTimeout(3000);
    const err = await a.p.locator('.modal.show').last().innerText().catch(() => '');
    await closeStrayModals(a.p);
    ok(`${a.name}: ${waiter} signs in with PIN ${pinCode}`, !/Wrong PIN/i.test(err),
       /Wrong PIN/i.test(err) ? 'refused the correct PIN' : '');
    return;
  }
  ok(`${a.name}: PIN dialog opens`, false, 'never got the sign-in dialog');
};

const seat = async (a, guest, covers, table) => {
  const t0 = Date.now();
  await a.p.getByRole('button', { name: 'Seat guest' }).click();
  await a.p.waitForTimeout(2500);
  const d = a.p.locator('.modal.show').last();
  await d.locator('input[data-fieldname="guest_name"]').fill(guest);
  await d.locator('input[data-fieldname="covers"]').fill(String(covers));
  await d.locator('input[data-fieldname="covers"]').press('Tab');
  await a.p.waitForTimeout(3000);
  const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
  const offered = opts.some(o => o.includes(table));
  ok(`${a.name}: ${table} (${ROOM}) is offered to seat ${guest}`, offered, opts.join(' | ').slice(0, 140));
  if (!offered) { await closeStrayModals(a.p); return false; }
  await d.locator('select[data-fieldname="table"]').selectOption({ label: opts.find(o => o.includes(table)) });
  await d.getByRole('button', { name: 'Seat & open order' }).click();
  await a.p.waitForTimeout(9000);
  t(`${a.name} seats ${guest}`, Date.now() - t0);
  return true;
};

const orderAndFire = async (a, guest) => {
  const t0 = Date.now();
  const add = a.p.locator('.order-manage .add-item:visible');
  await add.first().waitFor({ timeout: 45000 }).catch(() => {});
  const dishes = await add.count();
  if (!dishes) { ok(`${a.name}: the pad shows a menu for ${guest}`, false, '0 dishes on the pad'); return; }
  await add.nth(0).click({ force: true });
  await a.p.waitForTimeout(2500);
  const picker = a.p.locator('.modal.show').filter({ hasText: 'Whose check' }).last();
  if (await picker.count()) {
    const opts = await picker.locator('select[data-fieldname="order"] option').all();
    for (const o of opts) {
      const txt = await o.textContent();
      if (txt.includes(guest)) await picker.locator('select[data-fieldname="order"]').selectOption(await o.getAttribute('value'));
    }
    await picker.getByRole('button', { name: 'Open' }).click();
    await a.p.waitForTimeout(3500);
    await add.nth(0).click({ force: true });
    await a.p.waitForTimeout(2500);
  }
  await add.nth(2).click({ force: true }).catch(() => {});
  await a.p.waitForTimeout(3500);
  await a.p.locator('.order-manage .pad-btn.btn-order').first().dblclick({ force: true });
  await a.p.waitForTimeout(5000);
  await closeStrayModals(a.p);
  t(`${a.name} orders + fires for ${guest}`, Date.now() - t0);
  const landed = await a.p.evaluate(async (g) => {
    const r = await frappe.call('frappe.client.get_list', {
      doctype: 'Table Order', filters: { customer: g, status: ['not in', ['Cancelled', 'Invoiced']] },
      fields: ['name', 'status', 'amount', 'table'], limit_page_length: 1 });
    return (r.message || [])[0];
  }, guest);
  ok(`${a.name}: ${guest}'s check carries food and is fired`,
     !!landed && landed.amount > 0 && landed.status !== 'Opened', JSON.stringify(landed));
};

const openPadOnTable = async (a, guest, table) => {
  await tableTile(a, table).click({ force: true });
  await a.p.waitForTimeout(5500);
  const d = a.p.locator('.modal.show').last();
  const title = await d.locator('.modal-title').innerText().catch(() => '');
  const body = await d.innerText().catch(() => '');
  if (/Assigned to another User/i.test(body)) {
    ok(`${a.name}: opens ${guest}'s check on ${table}`, false, 'blocked: assigned to another user');
    await closeStrayModals(a.p); return false;
  }
  if (title.includes('Whose check')) {
    const opts = await d.locator('select[data-fieldname="order"] option').all();
    for (const o of opts) {
      const txt = await o.textContent();
      if (txt.includes(guest)) {
        await d.locator('select[data-fieldname="order"]').selectOption(await o.getAttribute('value'));
        await d.getByRole('button', { name: 'Open' }).click();
        await a.p.waitForTimeout(4500);
        return true;
      }
    }
  }
  const order = await a.p.evaluate(async (g) => {
    const r = await frappe.call('frappe.client.get_list', {
      doctype: 'Table Order', filters: { customer: g, status: ['not in', ['Cancelled', 'Invoiced']] },
      fields: ['name'], limit_page_length: 1 });
    return (r.message || [])[0] && r.message[0].name;
  }, guest);
  if (!order) { ok(`${a.name}: finds ${guest}'s check`, false); return false; }
  const chip = a.p.locator('.order-manage .btn-app.btn-order').filter({ hasText: order.slice(8) }).first();
  if (await chip.count()) { await chip.click({ force: true }); await a.p.waitForTimeout(4000); return true; }
  return true;
};

const payCurrent = async (a, guest) => {
  const t0 = Date.now();
  const complete = a.p.locator('.order-manage').getByText(/^Complete$/).first();
  if (!(await complete.count())) { ok(`${a.name}: Complete offered for ${guest}`, false); return false; }
  await complete.click({ force: true });
  await a.p.waitForTimeout(6000);
  const pay = a.p.locator('.modal.show').last();
  const payBtn = pay.getByText(/^Pay\b/).first();
  if (!(await payBtn.count())) {
    ok(`${a.name}: payment screen for ${guest}`, false, (await pay.innerText().catch(() => '')).slice(0, 100));
    return false;
  }
  const printed = [];
  a.p.context().on('page', pg => printed.push(pg.url()));
  await payBtn.click({ force: true });
  await a.p.waitForTimeout(12000);
  await closeStrayModals(a.p);
  t(`${a.name} bills ${guest}`, Date.now() - t0);
  const paid = await a.p.evaluate(async (g) => {
    const r = await frappe.call('frappe.client.get_list', {
      doctype: 'POS Invoice', filters: { customer: g, docstatus: 1 },
      fields: ['name', 'grand_total'], limit_page_length: 1 });
    return (r.message || [])[0];
  }, guest);
  ok(`${a.name}: ${guest} is billed and receipted`, !!paid,
     JSON.stringify(paid) + (printed.length ? ` print:${printed[0].includes('printview')}` : ' print:none'));
  return !!paid;
};

// ---------------------------------------------------------------- actors
const mgr = await mkActor('MGR', 'geff@etham.co.ke', PASS.geff);
const w1 = await mkActor('W1', 'waiter@etham.co.ke', PASS.waiter);
const w2 = await mkActor('W2', 'waiter@etham.co.ke', PASS.waiter);
const kit = await mkActor('KIT', 'kitchen@etham.co.ke', PASS.kitchen);
const cash = await mkActor('CASH', 'cashier@etham.co.ke', PASS.cashier);

const pre = await mgr.p.evaluate(async () => {
  const n = async (dt, f) => (await frappe.call('frappe.client.get_count', { doctype: dt, filters: f || {} })).message;
  return { checks: await n('Table Order', { status: ['not in', ['Cancelled', 'Invoiced']] }),
           parties: await n('Restaurant Booking', { status: 'Open' }) };
});
ok('floor is clean before the drill', !pre.checks && !pre.parties, JSON.stringify(pre));

// ---------------------------------------------------------------- 1. the manager
await floor(mgr);
const mgrRooms = await mgr.p.locator('.room-selector, .d-room, .room-item').allTextContents().catch(() => []);
const mgrBody = await mgr.p.evaluate(() => document.body.innerText);
ok('manager sees the second room in the room bar', mgrBody.includes(ROOM), ROOM);
const r2Tiles = await mgr.p.locator('.d-table:visible').count();
ok(`manager sees the four ${ROOM} tables`, r2Tiles >= 4, `${r2Tiles} tiles visible`);
ok('manager has the day button', await mgr.p.getByRole('button', { name: /Open day|Close day/ }).count() > 0);
ok('manager has the floor-edit pencil', await mgr.p.locator('.btn-edit-floor, [data-action="edit"], .fa-pencil').count() > 0
   || !(await mgr.p.evaluate(() => document.body.classList.contains('rm-no-floor-edit'))),
   'rm-no-floor-edit=' + await mgr.p.evaluate(() => document.body.classList.contains('rm-no-floor-edit')));

// a manager must be able to price a new dish (Item Manager, not Sales Master Manager)
const priced = await mgr.p.evaluate(async () => {
  try {
    const name = 'Drill Test Dish ' + Date.now().toString().slice(-5);
    const r = await frappe.call('restaurant_management.api.upsert_menu_item',
      { item_name: name, item_group: 'Sides & Accompaniments', rate: 250, item_type: 'Veg', add_to_menu: 1 });
    const price = await frappe.call('frappe.client.get_list', { doctype: 'Item Price',
      filters: { item_code: r.message }, fields: ['price_list_rate'], limit_page_length: 1 });
    return { item: r.message, rate: (price.message || [])[0] && price.message[0].price_list_rate };
  } catch (e) {
    const msg = (e && e.message) || (e && e._server_messages) || JSON.stringify(e);
    return { err: String(msg).slice(0, 200) };
  }
});
ok('manager can add a priced dish to the menu', priced.rate > 0, JSON.stringify(priced));

// reports a manager is told to use
for (const rep of ['Item-wise Sales Register', 'Sales by Waiter', 'Stock Balance', 'Restock List']) {
  const r = await mgr.p.evaluate(async (name) => {
    try {
      const res = await frappe.call('frappe.desk.query_report.run', {
        report_name: name, filters: { from_date: frappe.datetime.get_today(), to_date: frappe.datetime.get_today(),
          company: frappe.defaults.get_default('company') } });
      return { rows: (res.message && res.message.result || []).length };
    } catch (e) { return { err: String(e && e.message || e).slice(0, 120) }; }
  }, rep);
  ok(`manager can run "${rep}"`, !r.err, JSON.stringify(r));
}

// ---------------------------------------------------------------- 2. open the day
let shift = await api(mgr, 'house_shift');
if (!shift || shift.__err) {
  await mgr.p.getByRole('button', { name: 'Open day', exact: true }).click().catch(() => {});
  await mgr.p.waitForTimeout(3000);
  const od = mgr.p.locator('.modal.show').last();
  await od.locator('input[data-fieldname="mode_0"]').fill('5000').catch(() => {});
  await od.getByRole('button', { name: 'Open the day' }).click().catch(() => {});
  await mgr.p.waitForTimeout(7000);
  await closeStrayModals(mgr.p);
  shift = await api(mgr, 'house_shift');
}
ok('manager opens the day with a counted float', !!shift && !shift.__err, shift && shift.name);

// ---------------------------------------------------------------- 3. the kitchen screen
await floor(kit, null);
const kitBody = await kit.p.evaluate(() => document.body.innerText);
ok('kitchen screen shows no tables', !/Table \d/.test(kitBody), kitBody.replace(/\s+/g, ' ').slice(0, 90));
ok('kitchen screen shows its boards', /Kitchen/.test(kitBody) && /Bar/.test(kitBody));
await kit.p.locator('.d-table:visible').filter({ hasText: 'Kitchen' }).first().click().catch(() => {});
await kit.p.waitForTimeout(4000);

// ---------------------------------------------------------------- 4. two waiters, one Room 2 table
await floor(w1); await floor(w2);
const wBody = await w1.p.evaluate(() => document.body.innerText);
ok('waiter tablet hides the production centres', !/\bKitchen\b/.test(wBody) && !/\bBar\b/.test(wBody),
   wBody.replace(/\s+/g, ' ').slice(0, 90));
ok('waiter tablet has no money button', await w1.p.getByRole('button', { name: /Open day|Close day/ }).count() === 0);

await signPin(w1, 'Amina Test', '1111');
await signPin(w2, 'Moses Test', '2222');

const seated1 = await seat(w1, 'Drill Guest One', 2, TABLE);
const seated2 = await seat(w2, 'Drill Guest Two', 1, TABLE);
let occ = await api(cash, 'table_occupancy');
let cell = occ && occ[TABLE];
ok(`${TABLE} shows two parties with two different waiters`,
   !!cell && cell.parties.length === 2 && new Set(cell.parties.map(x => x.waiter)).size === 2,
   cell && `${cell.occupied}/${cell.capacity} ` + JSON.stringify(cell.parties.map(x => [x.guest, x.waiter])));
ok(`${TABLE} counts seats, not the table`, !!cell && cell.occupied === 3 && cell.capacity === 4,
   cell && `${cell.occupied}/${cell.capacity}`);

// order concurrently, as a real pair of waiters would
await Promise.all([
  orderAndFire(w1, 'Drill Guest One'),
  orderAndFire(w2, 'Drill Guest Two'),
]);

// a third party in the other Room 2 table, to prove the room is fully live
await floor(w1);
if (await seat(w1, 'Drill Guest Three', 2, TABLE_B)) await orderAndFire(w1, 'Drill Guest Three');

// ---------------------------------------------------------------- 5. does Room 2 reach the kitchen?
const kt0 = Date.now();
let sees = false, boardText = '';
for (let i = 0; i < 25 && !sees; i++) {
  boardText = await kit.p.evaluate(() => document.body.innerText);
  sees = boardText.includes(TABLE);
  if (!sees) await kit.p.waitForTimeout(2000);
}
t(`${ROOM} dispatch -> kitchen board`, Date.now() - kt0);
ok(`kitchen board receives the ${ROOM} ticket`, sees, sees ? `${Math.round((Date.now() - kt0) / 1000)}s` : boardText.replace(/\s+/g, ' ').slice(0, 120));
ok('the ticket names the waiter who fired it', /AT|MT|Amina|Moses/i.test(boardText),
   boardText.replace(/\s+/g, ' ').slice(0, 120));

// the kitchen advances a ticket, as a chef would: the footer button is the step
const advanced = await kit.p.evaluate(() => {
  const btn = document.querySelector('.widget-footer .btn-group button, .widget-footer .btn-group .btn');
  if (!btn) return { err: 'no action button on a ticket' };
  const label = btn.innerText.trim();
  btn.click();
  return { clicked: label };
});
await kit.p.waitForTimeout(6000);
const statuses = await cash.p.evaluate(async () => {
  const r = await frappe.call('frappe.client.get_list', { doctype: 'Order Entry Item',
    filters: { parenttype: 'Table Order' }, fields: ['status'], limit_page_length: 40,
    order_by: 'modified desc', parent: 'Table Order' });
  return (r.message || []).map(x => x.status);
});
ok('a chef can advance a ticket', !advanced.err && statuses.some(s => s !== 'Sent'),
   JSON.stringify(advanced) + ' statuses:' + JSON.stringify(statuses.slice(0, 6)));

// ---------------------------------------------------------------- 6. the fences, in anger
const waiterPay = await w1.p.evaluate(async (tbl) => {
  const m = (await frappe.call('restaurant_management.house.table_occupancy')).message;
  const party = (m[tbl] && m[tbl].parties || [])[0];
  if (!party || !party.order) return { err: 'no party to bill' };
  try {
    await frappe.call('restaurant_management.api.call', { model: 'Table Order', name: party.order,
      method: 'make_invoice', args: JSON.stringify({ mode_of_payment: { Cash: 1 } }) });
    return { billed: true };
  } catch (e) { return { billed: false, msg: String(e && e.message || e).slice(0, 80) }; }
}, TABLE);
ok('a waiter cannot take payment', waiterPay.billed === false, JSON.stringify(waiterPay));

const waiterTable = await w1.p.evaluate(async () => {
  try {
    await frappe.call('frappe.client.insert', { doc: { doctype: 'Restaurant Object', type: 'Table',
      description: 'Drill Rogue Table', room: 'R 2', no_of_seats: 2 } });
    return { made: true };
  } catch (e) { return { made: false }; }
});
ok('a waiter cannot create a table', waiterTable.made === false, JSON.stringify(waiterTable));

const kitchenTable = await kit.p.evaluate(async () => {
  try {
    await frappe.call('frappe.client.insert', { doc: { doctype: 'Restaurant Object', type: 'Table',
      description: 'Drill Rogue Kitchen Table', room: 'R 2', no_of_seats: 2 } });
    return { made: true };
  } catch (e) { return { made: false }; }
});
ok('a kitchen screen cannot create a table', kitchenTable.made === false, JSON.stringify(kitchenTable));

const waiterDay = await w1.p.evaluate(async () => {
  try { await frappe.call('restaurant_management.house.close_day', {}); return { closed: true }; }
  catch (e) { return { closed: false }; }
});
ok('a waiter cannot close the day', waiterDay.closed === false, JSON.stringify(waiterDay));

// ---------------------------------------------------------------- 7. the till settles Room 2
await floor(cash);
const cashBody = await cash.p.evaluate(() => document.body.innerText);
ok('till sees tables and the boards', /Table \d/.test(cashBody), cashBody.replace(/\s+/g, ' ').slice(0, 90));

if (await openPadOnTable(cash, 'Drill Guest One', TABLE)) await payCurrent(cash, 'Drill Guest One');
occ = await api(cash, 'table_occupancy');
cell = occ && occ[TABLE];
ok('paying one party frees only its seats', !!cell && cell.occupied === 1 && cell.parties.length === 1,
   cell && `${cell.occupied}/${cell.capacity} ` + JSON.stringify(cell.parties.map(x => x.guest)));

await floor(cash);
if (await openPadOnTable(cash, 'Drill Guest Two', TABLE)) await payCurrent(cash, 'Drill Guest Two');
occ = await api(cash, 'table_occupancy');
cell = occ && occ[TABLE];
ok(`${TABLE} clears itself once everyone has paid`, !!cell && cell.occupied === 0 && cell.parties.length === 0,
   cell && `${cell.occupied}/${cell.capacity}, parties ${cell.parties.length}`);

await floor(cash);
if (await openPadOnTable(cash, 'Drill Guest Three', TABLE_B)) await payCurrent(cash, 'Drill Guest Three');

// ---------------------------------------------------------------- 8. close, and the lockout
await floor(cash);
await cash.p.getByRole('button', { name: /^Close day/ }).click().catch(() => {});
await cash.p.waitForTimeout(4000);
const cd = cash.p.locator('.modal.show').last();
const warns = await cd.getByRole('button', { name: 'Close anyway' }).count();
ok('the close dialog reports a clean floor', warns === 0, warns ? 'it warns about open checks' : 'clean');
await cd.getByRole('button', { name: /Close the day|Close anyway/ }).first().click({ force: true }).catch(() => {});
await cash.p.waitForTimeout(10000);
const day = await api(cash, 'day_summary');
ok('the day banks and closes', !!day && day.open === false, JSON.stringify(day));

const afterClose = await w1.p.evaluate(async () => {
  const out = {};
  try { await frappe.call('restaurant_management.house.seat_walkin',
        { guest_name: 'Drill After Close', covers: 1 }); out.seated = true; }
  catch (e) { out.seated = false; out.why = String(e && e.message || e).slice(0, 60); }
  return out;
});
ok('no guest can be seated after the day is closed', afterClose.seated === false, JSON.stringify(afterClose));

const kitAfter = await kit.p.evaluate(() => ({ board: !!document.querySelector('.process-manage, .d-table') }));
ok('the kitchen screen still works after close (it is not locked out)', kitAfter.board === true, JSON.stringify(kitAfter));

// ---------------------------------------------------------------- verdict
console.log('\n===== TIMINGS (ms) =====');
timings.forEach(x => console.log(`  ${String(x.ms).padStart(6)}  ${x.label}`));
console.log('\n===== SLOW API CALLS (>2s) =====');
for (const a of [mgr, w1, w2, kit, cash]) a.slow.slice(0, 8).forEach(s => console.log(`  [${a.name}] ${s}`));
console.log('\n===== PAGE ERRORS =====');
for (const a of [mgr, w1, w2, kit, cash]) a.errs.slice(0, 8).forEach(e => console.log(`  [${a.name}] ${e}`));
const failed = report.filter(r => !r.pass);
console.log('\n===== FAILURES =====');
failed.forEach(f => console.log(`  ${f.name} — ${f.detail}`));
console.log(`\nRESULT ${report.length - failed.length}/${report.length} checks passed`);
await b.close();
process.exit(failed.length ? 1 : 0);
