// Screenshots for docs/etham-manual.html. Stages a realistic floor first, so the
// pictures show a working service rather than an empty demo.
import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const OUT = process.env.OUT || '../../docs/images/manual';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const done = [];

const shot = async (name, opts = {}) => {
  await page.screenshot({ path: `${OUT}/${name}.png`, ...opts });
  done.push(name);
  console.log('  shot ' + name);
};
const server = (m, a) => page.evaluate(([m, a]) =>
  frappe.call('restaurant_management.house.' + m, a || {}).then(r => r.message).catch(e => null), [m, a || {}]);
const floor = async (wait = 12000) => {
  await page.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(wait);
};
const step = async (name, fn) => {
  try { await fn(); } catch (e) { console.log(`  SKIP ${name}: ${String(e).split('\n')[0].slice(0, 90)}`); }
};

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.fill('#login_email', 'Administrator');
await page.fill('#login_password', process.env.PASS || 'admin');
await page.click('button.btn-login');
await page.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});

// A clean floor, counter closed, so the first pictures show the real starting point.
await floor();
await server('close_day', { force: 1 });
// The floor is reset server-side before this script runs.

await step('floor-closed', async () => { await floor(); await shot('01-floor-closed'); });

await step('open-day', async () => {
  await page.getByRole('button', { name: 'Open day', exact: true }).click();
  await page.waitForTimeout(2500);
  await shot('02-open-day');
  const d = page.locator('.modal.show').last();
  await d.locator('input[data-fieldname="mode_0"]').fill('5000');
  await d.getByRole('button', { name: 'Open the day' }).click();
  await page.waitForTimeout(3500);
  await page.keyboard.press('Escape');
});

await step('edit-mode', async () => {
  await floor();
  await page.locator('.general-editor-button').first().click();
  await page.waitForTimeout(1500);
  await shot('03-edit-mode');
  await page.locator('.general-editor-button').first().click();
  await page.waitForTimeout(800);
});

await step('waiter-pad', async () => {
  await page.getByRole('button', { name: 'Waiter', exact: true }).click();
  await page.waitForTimeout(2000);
  await shot('04-waiter-pad');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(600);
});

await step('seat-guest', async () => {
  await page.getByRole('button', { name: 'Seat guest' }).click();
  await page.waitForTimeout(2000);
  const d = page.locator('.modal.show').last();
  await d.locator('input[data-fieldname="guest_name"]').fill('Achieng');
  await d.locator('input[data-fieldname="covers"]').fill('2');
  await d.locator('input[data-fieldname="covers"]').press('Tab');
  await page.waitForTimeout(3000);
  await shot('05-seat-guest');
  await d.getByRole('button', { name: 'Seat & open order' }).click();
  await page.waitForTimeout(9000);
  await shot('06-order-pad');
});

await step('share-table', async () => {
  await floor();
  await page.getByRole('button', { name: 'Seat guest' }).click();
  await page.waitForTimeout(2000);
  const d = page.locator('.modal.show').last();
  await d.locator('input[data-fieldname="guest_name"]').fill('Otieno');
  await d.locator('input[data-fieldname="covers"]').fill('3');
  await d.locator('input[data-fieldname="covers"]').press('Tab');
  await page.waitForTimeout(3000);
  await shot('07-share-table');
  const shared = (await d.locator('select[data-fieldname="table"] option').allTextContents())
    .findIndex(t => /sharing with/i.test(t));
  if (shared >= 0) {
    const value = await d.locator('select[data-fieldname="table"] option').nth(shared).getAttribute('value');
    await d.locator('select[data-fieldname="table"]').selectOption(value);
  }
  await d.getByRole('button', { name: 'Seat & open order' }).click();
  await page.waitForTimeout(9000);
});

await step('floor-busy', async () => { await floor(14000); await shot('08-floor-busy'); });

await step('door', async () => {
  await page.getByRole('button', { name: /^Door/ }).click();
  await page.waitForTimeout(2500);
  await shot('09-door');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(600);
});

await step('close-day', async () => {
  await page.getByRole('button', { name: /^Close day/ }).click();
  await page.waitForTimeout(2500);
  await shot('10-close-day');
  await page.keyboard.press('Escape');
});

const pages = [
  ['11-pos-profile', '/app/pos-profile'],
  ['12-restaurant-settings', '/app/restaurant-settings'],
  ['13-waiters', '/app/restaurant-waiter'],
  ['14-items', '/app/item'],
  ['15-sales-by-waiter', '/app/query-report/Sales by Waiter'],
  ['16-table-turns', '/app/query-report/Table Turns'],
  ['17-restock-list', '/app/query-report/Restock List'],
  ['18-rooms-tables', '/app/restaurant-object'],
];
for (const [name, path] of pages) {
  await step(name, async () => {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(6000);
    await shot(name);
  });
}

console.log(`\n${done.length} screenshot(s) written to ${OUT}`);
await browser.close();
