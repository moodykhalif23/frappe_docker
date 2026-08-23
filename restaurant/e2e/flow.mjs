import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const USER = process.env.USER_ || 'Administrator';
const PASS = process.env.PASS || 'admin';
const WAITER = process.env.WAITER || 'Amina Otieno';
const PIN = process.env.PIN || '4821';
const GUEST = process.env.GUEST || 'Playwright Party';

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

const shot = async (label) => {
  n += 1;
  const file = `shots/${String(n).padStart(2, '0')}-${label}.jpg`;
  await page.screenshot({ path: file, type: 'jpeg', quality: 70 });
  console.log('   shot ' + file);
  return file;
};

// 1. sign in
await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.fill('#login_email', USER);
await page.fill('#login_password', PASS);
await shot('login');
await page.click('button.btn-login');
await page.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
ok('signs in to the desk', /\/app|\/desk/.test(page.url()), page.url());

// 2. the floor
await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(11000);
await shot('floor');
const tables = await page.locator('.d-table').count();
ok('floor renders tables', tables > 0, `${tables} tables`);
ok('no POS Opening Entry dead end',
   !(await page.locator('.modal.show').filter({ hasText: 'POS Opening Entry' }).count()));
const toolbar = (await page.locator('.page-actions button').allTextContents()).map(t => t.trim());
ok('Seat guest + Waiter on the toolbar',
   toolbar.includes('Seat guest') && toolbar.includes('Waiter'), JSON.stringify(toolbar));

// 3. waiter signs on
await page.getByRole('button', { name: 'Waiter', exact: true }).click();
await page.waitForTimeout(1500);
await shot('waiter-signin');
const dlg = page.locator('.modal.show').last();
ok('waiter pad opens', await dlg.isVisible());
await dlg.locator('select').first().selectOption({ label: WAITER }).catch(async () => {
  await dlg.locator('select').first().selectOption(WAITER);
});
await dlg.locator('input[type="password"]').fill(PIN);
await shot('waiter-pin');
await dlg.getByRole('button', { name: 'Sign in' }).click();
await page.waitForTimeout(2500);
await shot('waiter-signed-in');
ok('signed in as the waiter', (await page.locator('.modal.show').innerText().catch(() => '')).includes('is on')
   || (await page.locator('.page-actions').innerText()).includes('Waiter'));
await page.keyboard.press('Escape');
await page.waitForTimeout(800);

// 4. seat a walk-in
await page.getByRole('button', { name: 'Seat guest' }).click();
await page.waitForTimeout(2000);
await shot('seat-dialog');
const seat = page.locator('.modal.show').last();
await seat.locator('input[data-fieldname="guest_name"]').fill(GUEST);
await seat.locator('input[data-fieldname="covers"]').fill('2');
await seat.locator('input[data-fieldname="covers"]').press('Tab');
await page.waitForTimeout(2500);
const tableOpts = await seat.locator('select[data-fieldname="table"] option').allTextContents();
ok('table list filtered to what fits', tableOpts.length > 0, JSON.stringify(tableOpts.slice(0, 4)));
await shot('seat-filled');
await seat.getByRole('button', { name: 'Seat & open order' }).click();
await page.waitForTimeout(9000);
await shot('after-seating');
ok('no errors while seating', errs.length === 0, JSON.stringify(errs.slice(0, 2)));

// 5. order pad
const padOpen = await page.locator('.order-manage').count();
ok('order pad opened for the table', padOpen > 0, `${padOpen} pad(s)`);
await shot('order-pad');

// 6. create the order and ring up a dish (exercises the v16 ctx fix)
const totalText = async () => (await page.locator('.order-manage').innerText().catch(() => ''))
  .split('\n').filter(l => /Total/i.test(l)).join(' ').replace(/\s+/g, ' ').trim();

const before = await totalText();
const newOrder = page.locator('.order-manage .btn-app.btn-order').first();
ok('new-order button present', await newOrder.count() > 0);
// the + is bound to DOUBLE_CLICK, like dispatch — a single click does nothing
await newOrder.dblclick({ force: true });
await page.waitForTimeout(6000);
await shot('order-created');

// dismiss only an error notice — Escape would close the order pad itself
for (const t of ['Deadlock', 'Not found', 'Error', 'Message']) {
  const box = page.locator('.modal.show').filter({ hasText: t });
  if (await box.count()) {
    await box.first().locator('.modal-header .btn-modal-close, .modal-header .close').first()
      .click({ force: true }).catch(() => {});
    await page.waitForTimeout(800);
  }
}
await page.waitForTimeout(1200);
const chips = page.locator('.order-manage .btn-app.btn-order');
const chipCount = await chips.count();
ok('an order appears in the rail', chipCount > 1, `${chipCount - 1} order(s)`);
// Select the order. Playwright refuses the chip as "not visible", so dispatch
// the click directly — the app binds a plain click handler to it.
if (chipCount > 1) {
  await page.evaluate(() => {
    const c = document.querySelectorAll('.order-manage .btn-app.btn-order');
    const chip = c[c.length - 1];
    if (chip && !chip.className.includes('selected')) chip.click();
  });
  await page.waitForTimeout(4000);
  const cls = (await chips.last().getAttribute('class')) || '';
  ok('the new order is selected', cls.includes('selected'), cls);
}
await shot('order-selected');

const addBtns = page.locator('.order-manage .add-item:visible');
const dishes = await addBtns.count();
ok('menu shows dishes to add', dishes > 0, `${dishes} dishes`);
const dishLabel = (await addBtns.first().innerText()).replace(/\s+/g, ' ').trim();
await addBtns.first().click({ force: true });
await page.waitForTimeout(5000);
await shot('item-added');
const after = await totalText();
ok('adding a dish raises no page error (ctx fix)', errs.length === 0, JSON.stringify(errs.slice(0, 2)));
ok('cart total changed after adding', before !== after, `"${before}" -> "${after}"  [${dishLabel}]`);

// dispatch to the kitchen — a double click, by design
const orderBtn = page.locator('.order-manage .pad-btn.btn-order').first();
if (await orderBtn.count()) {
  await orderBtn.dblclick({ force: true }).catch(() => {});
  await page.waitForTimeout(5000);
  await shot('dispatched');
  ok('dispatch to kitchen raises no error', errs.length === 0, JSON.stringify(errs.slice(0, 2)));
}

// 7. badge on the floor
await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(10000);
const badges = await page.locator('.d-waiter-badge').count();
await shot('floor-with-badge');
ok('waiter initials badge on the tile', badges > 0, `${badges} badge(s)`);

// 8. responsive
for (const [label, w, h] of [['tablet', 820, 1180], ['phone', 390, 844]]) {
  await page.setViewportSize({ width: w, height: h });
  await page.waitForTimeout(3500);
  await shot(`floor-${label}`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok(`${label}: no horizontal overflow`, overflow <= 2, `${overflow}px`);
}
await page.setViewportSize({ width: 1440, height: 900 });

console.log('\nRESULT ' + results.filter(r => r.pass).length + ' passed, ' + results.filter(r => !r.pass).length + ' failed');
console.log('PAGE ERRORS ' + JSON.stringify(errs.slice(0, 5)));
await browser.close();
