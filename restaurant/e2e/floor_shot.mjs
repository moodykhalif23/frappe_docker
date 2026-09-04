// Screenshots for a look review on a test site: the floor with one seated party
// (badges, no upstream dot), and the pad filtered to a row of long dish names.
//   BASE=http://pos.localhost:8080 node floor_shot.mjs   → shots/floor.png, shots/pad-tall-names.png
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 9', FILTER = process.env.FILTER || 'Ma';
mkdirSync('shots', { recursive: true });
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1920, height: 930 }, deviceScaleFactor: 1 })).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'waiter@etham.co.ke'); await p.fill('#login_password', 'Waiter@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(12000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(2500);
await p.evaluate(() => localStorage.removeItem('rm_waiter_session'));
await p.getByRole('button', { name: 'Seat guest' }).click(); await p.waitForTimeout(2500);
let d = p.locator('.modal.show').last();
await d.locator('select').first().selectOption('Amina Test'); await d.locator('input[type="password"]').fill('1111'); await d.getByRole('button', { name: 'Sign in' }).click(); await p.waitForTimeout(3000);
d = p.locator('.modal.show').last();
await d.locator('input[data-fieldname="guest_name"]').fill('Review Party'); await d.locator('input[data-fieldname="covers"]').fill('3'); await d.locator('input[data-fieldname="covers"]').press('Tab'); await p.waitForTimeout(3000);
const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
await d.locator('select[data-fieldname="table"]').selectOption({ label: opts.find(o => o.includes(TABLE)) });
await d.getByRole('button', { name: 'Seat & open order' }).click(); await p.waitForTimeout(9000);
const cards = p.locator('.order-manage .small-box.item:visible'); await cards.first().waitFor({ timeout: 45000 });
await cards.first().locator('.add-item').click({ force: true }); await p.waitForTimeout(3000);
await p.locator('.order-manage input[placeholder*="Search"], .order-manage .search-input input, .order-manage input.search').first().fill(FILTER).catch(async () => { await p.locator('.order-manage').getByPlaceholder(/Search/).first().fill(FILTER); });
await p.waitForTimeout(2500);
await p.screenshot({ path: 'shots/pad-tall-names.png' });
// close the pad and shoot the floor
for (let i = 0; i < 3; i++) { const m = p.locator('.modal.show'); if (!(await m.count())) break; await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {}); await p.waitForTimeout(700); }
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
await p.screenshot({ path: 'shots/floor.png' });
console.log('shots: pad-tall-names.png, floor.png; dot elements visible on tiles:', await p.evaluate(() => Array.from(document.querySelectorAll('.d-table .has-customer')).filter(e => e.offsetParent).length));
await b.close();
