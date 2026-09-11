// Tapping an empty table must ask who the waiter is and how many are sitting, before
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 200) : ''}`); };
const done = async (c) => { console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`); await b.close(); process.exit(c); };
const errs = []; p.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 140)));

await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'cashier@etham.co.ke'); await p.fill('#login_password', 'Cashier@2026');
await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(15000);

const pick = await p.evaluate(async () => {
  try {
    if (!(await frappe.call('restaurant_management.house.house_shift', {})).message) {
      await frappe.call('restaurant_management.house.open_day', { balances: JSON.stringify({ Cash: 5000 }) });
    }
    const free = ((await frappe.call('restaurant_management.house.free_tables', { whole_table: 1 })).message || [])
      .filter(t => t.description && !String(t.description).startsWith('Delivery'));
    return free.length ? { name: free[0].name, label: free[0].description, room: free[0].room }
                       : { error: 'no free table anywhere' };
  } catch (e) { return { error: String((e && (e.message || e.exc_type)) || e).slice(0, 160) }; }
});
ok('there is an empty table to tap', !pick.error, pick.error || JSON.stringify(pick));
if (pick.error) await done(1);

// the floor shows one room at a time, and it opens on Delivery
await p.getByText(pick.room, { exact: true }).first().click().catch(() => {});
await p.waitForTimeout(5000);

// tap the tile the way a waiter does
const tile = p.locator('.d-table').filter({ hasText: pick.label }).first();
ok(`the tile for ${pick.label} is on the floor`, await tile.count() > 0, `${await p.locator('.d-table').count()} tile(s)`);
await tile.click({ force: true });
await p.waitForTimeout(6000);

const first = p.locator('.modal.show').last();
const title = (await first.locator('.modal-title').innerText().catch(() => '')) || '';
const body = ((await first.locator('.modal-body').innerText().catch(() => '')) || '').replace(/\s+/g, ' ');
ok('tapping an empty table asks for the waiter first, not a customer name',
  /waiter|sign in|pin/i.test(title + ' ' + body), `${title} :: ${body.slice(0, 120)}`);
ok('and it is not the order pad with its customer box',
  !/Begin typing for results/i.test(body), body.slice(0, 140));

// sign the waiter in, then the seat dialog should follow
const pin = p.locator('.modal.show input[type="password"]').first();
if (await pin.count()) {
  const sel = p.locator('.modal.show select').first();
  if (await sel.count()) await sel.selectOption({ index: 1 }).catch(() => {});
  await pin.fill('1111');
  await p.locator('.modal.show').last().getByRole('button', { name: /Sign in|Confirm|Continue/i })
    .first().click({ force: true }).catch(() => {});
  await p.waitForTimeout(6000);
}

const seat = p.locator('.modal.show').last();
const seatTitle = (await seat.locator('.modal-title').innerText().catch(() => '')) || '';
const fields = await seat.locator('.frappe-control .control-label').allTextContents().catch(() => []);
ok('then it asks how many are sitting, on that table',
  /Seat/i.test(seatTitle) && fields.some(f => /guests|covers/i.test(f)),
  `${seatTitle} :: ${JSON.stringify(fields)}`);
ok('and asks the guest name as part of seating, not before it',
  fields.some(f => /guest name/i.test(f)), JSON.stringify(fields));
ok('the table is fixed to the one that was tapped',
  await seat.locator(`select[data-fieldname="table"] option`).count() <= 2
  || (await seat.locator('select[data-fieldname="table"]').inputValue().catch(() => '')) === pick.name,
  await seat.locator('select[data-fieldname="table"]').inputValue().catch(() => '(none)'));

ok('no page errors', errs.length === 0, errs.join(' | '));
await done(report.every(Boolean) ? 0 : 1);
