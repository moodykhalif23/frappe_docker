// The door in a real browser: the panel opens, a party joins the queue, and
// seating them lands on that table's pad. Writes real records — demo sites only.
import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const USER = process.env.USER_ || 'Administrator';
const PASS = process.env.PASS || 'admin';
// unique per run: two parties with the same name make every assertion ambiguous
const GUEST = (process.env.GUEST || 'Door Test Party') + ' ' + Date.now().toString().slice(-6);

mkdirSync('shots', { recursive: true });
let n = 0;
const results = [];
const ok = (name, pass, detail = '') => {
  results.push({ name, pass, detail: String(detail).slice(0, 120) });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 120)));

const api = (method, args = {}) => page.evaluate(
  ([m, a]) => frappe.call('restaurant_management.house.' + m, a).then(r => r.message),
  [method, args]);

const shot = async (label) => {
  n += 1;
  const file = `shots/door-${String(n).padStart(2, '0')}-${label}.jpg`;
  await page.screenshot({ path: file, type: 'jpeg', quality: 70 });
  console.log('   shot ' + file);
};

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.fill('#login_email', USER);
await page.fill('#login_password', PASS);
await page.click('button.btn-login');
await page.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});

await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(11000);
await shot('floor');

const doorBtn = page.locator('.page-actions button').filter({ hasText: /^Door/ }).first();
ok('Door sits on the toolbar', await doorBtn.count() > 0,
   JSON.stringify((await page.locator('.page-actions button').allTextContents()).map(t => t.trim())));
if (!(await doorBtn.count())) { console.log('\nRESULT aborted'); await browser.close(); process.exit(1); }

await doorBtn.click();
await page.waitForTimeout(3000);
await shot('panel');
const dlg = page.locator('.modal.show').last();
ok('the door panel opens', await dlg.isVisible());

const summary = await dlg.locator('.rm-door-summary').innerText().catch(() => '');
ok('the summary strip renders', summary.length > 0, summary.replace(/\s+/g, ' '));
ok('it shows the average turn', /avg turn/i.test(summary), summary.replace(/\s+/g, ' '));
ok('it shows tables free', /tables free/i.test(summary));

// join the queue
await dlg.locator('input[data-fieldname="guest_name"]').fill(GUEST);
await dlg.locator('input[data-fieldname="covers"]').fill('2');
await shot('queue-filled');
await dlg.getByRole('button', { name: 'Add to queue' }).click();
await page.waitForTimeout(4000);
await shot('queued');

const rows = dlg.locator('.rm-door-row');
const queued = await rows.filter({ hasText: GUEST }).count();
ok('the party appears in the queue', queued > 0, `${await rows.count()} row(s)`);
ok('the wait is counted', /waiting \d+ min/.test(await dlg.innerText()));

const badge = (await page.locator('.page-actions button').filter({ hasText: /^Door/ }).innerText().catch(() => ''));
ok('the toolbar badge counts the queue', /\(\d+\)/.test(badge), badge);

// phone width, panel open — the door is used standing up
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(2500);
await shot('panel-phone');
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
ok('phone: no horizontal overflow', overflow <= 2, `${overflow}px`);
const tap = await dlg.locator('.rm-seat').first().boundingBox().catch(() => null);
ok('Seat is a thumb-sized target', tap && tap.height >= 30, tap ? `${Math.round(tap.height)}px` : 'not found');
await page.setViewportSize({ width: 1440, height: 900 });
await page.waitForTimeout(1500);

// seat them
await dlg.locator('.rm-door-row').filter({ hasText: GUEST }).locator('.rm-seat').first().click();
await page.waitForTimeout(3500);
await shot('seat-picker');
const pick = page.locator('.modal.show').last();
const opts = await pick.locator('select[data-fieldname="table"] option').allTextContents();
ok('offers tables that fit', opts.length > 0, JSON.stringify(opts.slice(0, 3)));
await pick.getByRole('button', { name: 'Seat & open order' }).click();
await page.waitForTimeout(9000);
await shot('seated');

ok('seating raises no page error', errs.length === 0, JSON.stringify(errs.slice(0, 2)));
const pad = await page.locator('.order-manage').count();
ok('it lands on the table pad', pad > 0, `${pad} pad(s)`);

await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(9000);
await page.locator('.page-actions button').filter({ hasText: /^Door/ }).first().click();
await page.waitForTimeout(3000);
await shot('queue-after');
const waiting = await api('waitlist');
ok('the seated party has left the queue', !waiting.some(w => w.guest === GUEST),
   `${waiting.length} still waiting`);
const expected = await api('reservations');
ok('and is not still listed as expected', !expected.some(r => r.guest === GUEST),
   `${expected.length} expected`);

// leave the floor as we found it
const removed = await page.evaluate(async (guest) => {
  const del = (doctype, name) => frappe.call('frappe.client.delete', { doctype, name })
    .then(() => 1).catch(() => 0);
  const cs = await frappe.call('frappe.client.get_list',
    { doctype: 'Customer', filters: { customer_name: guest }, fields: ['name'], limit_page_length: 0 });
  let n = 0;
  for (const c of (cs.message || [])) {
    // A party's check links to its booking, so the check goes first.
    const os = await frappe.call('frappe.client.get_list',
      { doctype: 'Table Order', filters: { customer: c.name }, fields: ['name'], limit_page_length: 0 });
    for (const o of (os.message || [])) await del('Table Order', o.name);
    const bs = await frappe.call('frappe.client.get_list',
      { doctype: 'Restaurant Booking', filters: { customer: c.name }, fields: ['name'], limit_page_length: 0 });
    for (const b of (bs.message || [])) n += await del('Restaurant Booking', b.name);
    n += await del('Customer', c.name);
  }
  return n;
}, GUEST);
ok('the test party was cleaned up', removed > 0, `${removed} record(s) removed`);

console.log('\nRESULT ' + results.filter(r => r.pass).length + ' passed, ' + results.filter(r => !r.pass).length + ' failed');
console.log('PAGE ERRORS ' + JSON.stringify(errs.slice(0, 5)));
await browser.close();
process.exit(results.some(r => !r.pass) ? 1 : 0);
