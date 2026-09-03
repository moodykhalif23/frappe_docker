// Where does the time go? Cold and warm floor loads, a room switch, opening a
// table's pad, with every API call's server time. Read-only apart from opening a pad.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://frappe.ikobriq.com', ROOM = process.env.ROOM || 'Main Hall', TABLE = process.env.TABLE || 'Table 1';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1600, height: 900 } });
const p = await ctx.newPage();
const calls = [];
p.on('requestfinished', async r => { try { const t = r.timing(); const u = r.url(); if (/api\/method/.test(u)) { const m = /method=([a-z_]+)/.exec(r.postData() || '') ; calls.push({ at: Date.now(), ms: Math.round(t.responseEnd), name: (u.split('/api/method/')[1] || '').split('?')[0].replace('restaurant_management.', '') + (m ? '(' + m[1] + ')' : ''), size: (await r.response())?.headers()['content-length'] || '' }); } } catch (e) {} });
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.fill('#login_email', 'cashier@etham.co.ke'); await p.fill('#login_password', 'Cashier@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
const floor = async (label) => {
  calls.length = 0; const t0 = Date.now();
  await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.locator('.d-table:visible').first().waitFor({ timeout: 60000 }).catch(() => {});
  const tiles = Date.now() - t0;
  await p.getByRole('button', { name: 'Seat guest' }).waitFor({ timeout: 60000 }).catch(() => {});
  const toolbar = Date.now() - t0;
  const nav = await p.evaluate(() => { const n = performance.getEntriesByType('navigation')[0]; return n ? { ttfb: Math.round(n.responseStart), dom: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd) } : null; });
  const res = await p.evaluate(() => performance.getEntriesByType('resource').filter(r => /\.(js|css)(\?|$)/.test(r.name)).length);
  console.log(`${label}: first tile ${tiles}ms, toolbar ${toolbar}ms, nav ${JSON.stringify(nav)}, ${res} scripts/styles, ${calls.length} api calls`);
  const slow = [...calls].sort((a, b) => b.ms - a.ms).slice(0, 6).map(c => `${c.ms}ms ${c.name}`);
  console.log('   slowest api:', slow.join(' | '));
};
await floor('COLD floor');
await floor('WARM floor');
calls.length = 0; let t0 = Date.now();
await p.getByText(ROOM, { exact: true }).first().click(); await p.locator('.d-table:visible').filter({ hasText: /Table/ }).first().waitFor({ timeout: 30000 }).catch(() => {}); await p.waitForTimeout(500);
console.log(`room switch to ${ROOM}: ${Date.now() - t0}ms, api: ${[...calls].sort((a, b) => b.ms - a.ms).slice(0, 4).map(c => `${c.ms}ms ${c.name}`).join(' | ')}`);
calls.length = 0; t0 = Date.now();
await p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first().click({ force: true });
const padReady = await p.locator('.order-manage .small-box.item:visible').first().waitFor({ timeout: 60000 }).then(() => Date.now() - t0).catch(() => -1);
const dialog = await p.locator('.modal.show .modal-title').first().innerText().catch(() => '');
console.log(`open pad on ${TABLE}: cards visible after ${padReady}ms (dialog "${dialog.trim()}"), api: ${[...calls].sort((a, b) => b.ms - a.ms).slice(0, 6).map(c => `${c.ms}ms ${c.name}${c.size ? ' ' + Math.round(c.size / 1024) + 'kB' : ''}`).join(' | ')}`);
const imgs = await p.evaluate(() => performance.getEntriesByType('resource').filter(r => /\/files\//.test(r.name)).length);
console.log(`dish photos fetched: ${imgs}`);
await b.close();
