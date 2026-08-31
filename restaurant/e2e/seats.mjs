// Seats, not tables: two parties on one six-top, each with its own check and
// waiter, and a counter that only a manager opens.
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
const WAITER = process.env.WAITER || 'Test Waiter';
const PIN = process.env.PIN || '4821';

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

const shot = async (label) => {
  n += 1;
  await page.screenshot({ path: `shots/seat-${String(n).padStart(2, '0')}-${label}.jpg`, type: 'jpeg', quality: 70 });
};
const server = (method, args) => page.evaluate(
  ([m, a]) => frappe.call('restaurant_management.house.' + m, a || {}).then(r => r.message),
  [method, args || {}]);

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.fill('#login_email', USER);
await page.fill('#login_password', PASS);
await page.click('button.btn-login');
await page.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
ok('signs in to the desk', /\/app|\/desk/.test(page.url()));

// A clean floor: close the day, which also sweeps sections and parties.
await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(11000);
await server('close_day', { force: 1 }).catch(() => null);
const shift = await server('house_shift');
ok('the counter is closed to start', !shift, JSON.stringify(shift));

// A six-top with nothing on it, and no leftover checks.
const table = await page.evaluate(async () => {
  const tables = (await frappe.call('frappe.client.get_list', {
    doctype: 'Restaurant Object', filters: { type: 'Table' },
    fields: ['name', 'description', 'no_of_seats'], limit_page_length: 0 })).message || [];
  const t = tables.find(x => x.no_of_seats >= 6) || tables[0];
  await frappe.call('frappe.client.set_value', {
    doctype: 'Restaurant Object', name: t.name, fieldname: 'no_of_seats', value: 6 });
  const orders = (await frappe.call('frappe.client.get_list', {
    doctype: 'Table Order', filters: { table: t.name, status: ['not in', ['Cancelled', 'Invoiced']] },
    fields: ['name'], limit_page_length: 0 })).message || [];
  for (const o of orders) {
    await frappe.call('frappe.client.set_value', {
      doctype: 'Table Order', name: o.name, fieldname: { status: 'Cancelled', show_in_pos: 0 } });
  }
  return t;
});
ok('a six-top to work with', !!table, `${table.description} (${table.name})`);

await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForTimeout(11000);
await shot('floor-closed');

const toolbar = () => page.locator('.page-actions button').allTextContents()
  .then(t => t.map(s => s.trim()).filter(Boolean));
const bar = await toolbar();
ok('Open day offered while closed', bar.includes('Open day'), JSON.stringify(bar));

// Billing must refuse while the counter is closed, not open it silently.
await page.getByRole('button', { name: 'Open day', exact: true }).click();
await page.waitForTimeout(2500);
await shot('open-day-dialog');
const openDlg = page.locator('.modal.show').last();
ok('the float is asked for', (await openDlg.innerText()).includes('float'));
await openDlg.locator('input[data-fieldname="mode_0"]').fill('5000');
await openDlg.getByRole('button', { name: 'Open the day' }).click();
await page.waitForTimeout(4000);
await shot('day-open');
const opened = await server('house_shift');
ok('the day opens with a counted float', !!opened && !opened.stale, JSON.stringify(opened && opened.name));
await page.keyboard.press('Escape');
await page.waitForTimeout(800);

// Two parties, one table.
const seatParty = async (guest, covers) => {
  await page.getByRole('button', { name: 'Seat guest' }).click();
  await page.waitForTimeout(2000);
  let d = page.locator('.modal.show').last();
  d = await answerGate(page, d);
  await d.locator('input[data-fieldname="guest_name"]').fill(guest);
  await d.locator('input[data-fieldname="covers"]').fill(String(covers));
  await d.locator('input[data-fieldname="covers"]').press('Tab');
  await page.waitForTimeout(3000);
  const options = await d.locator('select[data-fieldname="table"] option').allTextContents();
  await d.locator('select[data-fieldname="table"]').selectOption(table.name);
  await shot(`seat-${guest.split(' ')[0].toLowerCase()}`);
  await d.getByRole('button', { name: 'Seat & open order' }).click();
  await page.waitForTimeout(9000);
  return options;
};

await seatParty('Amina Two', 2);
let seats = (await server('table_occupancy'))[table.name];
ok('a party of 2 takes 2 of 6 seats', seats.occupied === 2 && seats.free === 4,
   `${seats.occupied}/${seats.capacity}`);

await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(11000);
const offered = await seatParty('Moses Three', 3);
ok('the half-full table is offered as shared',
   offered.some(o => /sharing with/i.test(o)), JSON.stringify(offered.slice(0, 3)));

seats = (await server('table_occupancy'))[table.name];
ok('two parties share the six-top', seats.occupied === 5 && seats.parties.length === 2,
   `${seats.occupied}/${seats.capacity}, ${seats.parties.length} parties`);
ok('each party has its own check',
   new Set(seats.parties.map(p => p.order)).size === 2,
   JSON.stringify(seats.parties.map(p => [p.guest, p.covers, p.order])));

// Attribution is per party, so a shared table has two owners at once.
const waiters = [{ name: 'Amina Test', pin: '1111', colour: '#2e844e' },
                 { name: 'Moses Test', pin: '2222', colour: '#97264f' }];
await page.evaluate(async (list) => {
  for (const w of list) {
    const found = (await frappe.call('frappe.client.get_list', {
      doctype: 'Restaurant Waiter', filters: { waiter_name: w.name },
      fields: ['name'], limit_page_length: 0 })).message || [];
    if (found.length) {
      await frappe.call('frappe.client.set_value', {
        doctype: 'Restaurant Waiter', name: w.name,
        fieldname: { pin: w.pin, active: 1, colour: w.colour } });
    } else {
      await frappe.call('frappe.client.insert', { doc: {
        doctype: 'Restaurant Waiter', waiter_name: w.name, pin: w.pin,
        active: 1, colour: w.colour } });
    }
  }
}, waiters);

const claimed = [];
for (const [i, p] of seats.parties.entries()) {
  claimed.push(await server('claim_party', { booking: p.booking, waiter: waiters[i].name, pin: waiters[i].pin }));
}
ok('each party is claimed by its own waiter',
   claimed.every(c => c && c.initials), JSON.stringify(claimed.map(c => c && c.initials)));

const stamped = await page.evaluate(async (names) => {
  const out = [];
  for (const n of names) {
    out.push((await frappe.call('frappe.client.get_value', {
      doctype: 'Table Order', filters: { name: n }, fieldname: ['waiter', 'booking', 'dinners'] })).message);
  }
  return out;
}, seats.parties.map(p => p.order));
ok('the check carries its party, waiter and covers',
   stamped.every(s => s && s.waiter && s.booking && s.dinners),
   JSON.stringify(stamped));

// It must refuse the party that does not fit in what is left.
const refused = await page.evaluate(([t]) => frappe.call('restaurant_management.house.seat_walkin',
  { guest_name: 'Too Big', covers: 4, table: t })
  .then(() => null, (e) => String(e).slice(0, 120)), [table.name]).catch(e => String(e).slice(0, 120));
ok('a party that does not fit is refused', !!refused, String(refused).slice(0, 90));

// The floor has to show it.
await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(13000);
await shot('floor-shared');
const tile = await page.evaluate((name) => {
  const o = window.RM && RM.object && RM.object(name);
  const el = o && o.obj && o.obj.obj;
  if (!el) return null;
  return {
    seats: (el.querySelector('.d-table-seats') || {}).textContent || '',
    badges: [...el.querySelectorAll('.rm-party')].map(b => b.textContent),
  };
}, table.name);
ok('the tile counts seats, not tables', !!tile && /5\s*\/\s*6/.test((tile.seats || '').replace(/\s/g, '')),
   JSON.stringify(tile));
ok('a badge per party on the tile', !!tile && tile.badges.length === 2, JSON.stringify(tile && tile.badges));
ok('each badge names its waiter', !!tile && /AT/.test(tile.badges.join('')) && /MT/.test(tile.badges.join('')),
   JSON.stringify(tile && tile.badges));
ok('no page errors', errs.length === 0, JSON.stringify(errs.slice(0, 3)));

const failed = results.filter(r => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);
