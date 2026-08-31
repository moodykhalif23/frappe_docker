import { chromium } from 'playwright';
const BASE = 'http://pos.localhost:8080';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 120)));
const ok = (n, pass, d = '') => console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + d : ''}`);
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'Administrator'); await p.fill('#login_password', 'admin');
await p.click('button.btn-login'); await p.waitForURL(/\/app/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(15000);

// 1. the orphaned check reads as "open check", not "? · ?"
const t6 = await p.evaluate(() => {
  const o = window.RM.object('Table 6');
  const el = o && o.obj && o.obj.obj;
  return el ? { badges: [...el.querySelectorAll('.rm-party')].map(e => e.textContent.trim()),
                pill: (el.querySelector('.d-table-seats') || {}).textContent } : null;
});
ok('orphaned check badge reads plainly', !!t6 && /open check/i.test(t6.badges.join(' ')), JSON.stringify(t6));

// 2. spacer spans its own grid row (no card can stretch to it)
await p.locator('.d-table').filter({ hasText: 'Table 4' }).first().click();
await p.waitForTimeout(5000);
await p.locator('.order-manage .add-item:visible').first().waitFor({ timeout: 45000 }).catch(() => {});
const spacer = await p.evaluate(() => {
  const root = document.getElementById('items-container-Table 4');
  const grid = root && root.querySelector('.widget-group-body');
  const sp = grid && grid.querySelector('.clusterize-extra-row');
  return sp ? { span: getComputedStyle(sp).gridColumn,
                maxCard: Math.max(...[...grid.querySelectorAll('.shortcut-widget-box')]
                  .map(e => Math.round(e.getBoundingClientRect().height))) } : null;
});
ok('scroll spacer spans the full row', !!spacer && /-1/.test(spacer.span), JSON.stringify(spacer));
ok('no card stretched to spacer height', !!spacer && spacer.maxCard < 400, `tallest card ${spacer && spacer.maxCard}px`);

// 3. Release: the dialog lists held tables and actually frees one
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(14000);
await p.getByRole('button', { name: 'Release', exact: true }).click();
await p.waitForTimeout(3000);
const d = p.locator('.modal.show').last();
const options = await d.locator('select[data-fieldname="table"] option').allTextContents();
ok('dialog lists what each table holds', options.some(o => /open check/i.test(o)) && options.some(o => /Achieng/.test(o)),
   JSON.stringify(options));
await d.locator('select[data-fieldname="table"]').selectOption('Table 6');
await p.screenshot({ path: '/tmp/release-dialog.png' });
await d.getByRole('button', { name: 'Release', exact: true }).click();
await p.waitForTimeout(6000);
const after = await p.evaluate(() => {
  const s = window.RM_seats.map['Table 6'];
  return s ? { occupied: s.occupied, parties: s.parties.length } : null;
});
ok('Table 6 is free after release', !!after && after.occupied === 0 && after.parties === 0, JSON.stringify(after));
ok('no page errors', errs.length === 0, JSON.stringify(errs.slice(0, 3)));
await b.close();
