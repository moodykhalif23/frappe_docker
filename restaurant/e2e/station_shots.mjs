import { chromium } from 'playwright';
const BASE = 'https://frappe.ikobriq.com';
const OUT = '/home/patch/frappe_docker/docs/images/stations';
const b = await chromium.launch();
const ok = (n, pass, d = '') => console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + d : ''}`);

const open = async (email, pass) => {
  const ctx = await b.newContext({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.fill('#login_email', email);
  await p.fill('#login_password', pass);
  await p.click('button.btn-login');
  await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
  await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(16000);
  await p.getByText('Main Hall', { exact: true }).first().click().catch(() => {});
  await p.waitForTimeout(10000);
  return { ctx, p };
};
const survey = (p) => p.evaluate(() => ({
  tables: [...document.querySelectorAll('.floor-map .d-table:not(.p-center)')].filter(e => e.offsetParent).length,
  boards: [...document.querySelectorAll('.floor-map .d-table.p-center')].filter(e => e.offsetParent).length,
  buttons: [...document.querySelectorAll('.page-actions button')].filter(e => e.offsetParent)
    .map(e => e.textContent.trim()).filter(Boolean),
}));

// ---- WAITER: seats only, no boards, no money
const w = await open('waiter@etham.co.ke', 'Waiter@2026');
let s = await survey(w.p);
await w.p.screenshot({ path: `${OUT}/waiter-floor.png` });
ok('waiter sees tables, not the kitchen', s.tables > 0 && s.boards === 0, JSON.stringify(s));
ok('waiter has no money buttons', !s.buttons.some(x => /Open day|Close day|Release/.test(x)), JSON.stringify(s.buttons));
await w.p.locator('.d-table:visible').filter({ hasText: 'Table 2' }).first().click();
await w.p.waitForTimeout(8000);
const complete = await w.p.evaluate(() =>
  [...document.querySelectorAll('.order-manage button, .order-manage .pad-btn')]
    .filter(e => /^\s*Complete\s*$/.test(e.textContent) && e.offsetParent).length);
await w.p.screenshot({ path: `${OUT}/waiter-pad.png` });
ok('waiter pad has no Complete (money) button', complete === 0, `${complete} visible`);
await w.ctx.close();

// ---- KITCHEN: boards only
const k = await open('kitchen@etham.co.ke', 'Kitchen@2026');
s = await survey(k.p);
await k.p.screenshot({ path: `${OUT}/kitchen-floor.png` });
ok('kitchen sees only Kitchen and Bar', s.tables === 0 && s.boards > 0, JSON.stringify(s));
ok('kitchen has no seating or money buttons',
   !s.buttons.some(x => /Seat guest|^Waiter$|^Door|Open day|Close day|Release/.test(x)), JSON.stringify(s.buttons));
await k.ctx.close();

// ---- CASHIER: everything, including the table to be billed
const c = await open('cashier@etham.co.ke', 'Cashier@2026');
s = await survey(c.p);
const billed = await c.p.evaluate(() => {
  const m = (window.RM_seats && RM_seats.map) || {};
  return Object.values(m).filter(x => x.occupied).map(x => `${x.description} ${x.occupied}/${x.capacity}`);
});
await c.p.screenshot({ path: `${OUT}/cashier-floor.png` });
ok('cashier sees tables AND boards', s.tables > 0 && s.boards > 0, JSON.stringify({ tables: s.tables, boards: s.boards }));
const menuHasRelease = await c.p.evaluate(async () => {
  const toggle = document.querySelector('.menu-btn-group .menu-more-button, .menu-btn-group button');
  if (toggle) toggle.click();
  await new Promise(r => setTimeout(r, 800));
  return [...document.querySelectorAll('.menu-btn-group a, .dropdown-menu a')]
    .some(a => /Release a table/i.test(a.textContent));
});
ok('cashier has the day button and Release in the menu',
   s.buttons.some(x => /Close day|Open day/.test(x)) && menuHasRelease,
   JSON.stringify({ toolbar: s.buttons, releaseInMenu: menuHasRelease }));
ok('cashier sees the table to be billed', billed.length > 0, JSON.stringify(billed));
await c.ctx.close();
await b.close();
