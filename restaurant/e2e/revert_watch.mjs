// Resize a live tile, then watch its size every second for 20 s and log every
// realtime event addressed to the tile or its room — with the data_style it carries.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://frappe.ikobriq.com', ROOM = process.env.ROOM || 'Main Hall', TABLE = process.env.TABLE || 'Table 11';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 900 } })).newPage();
p.on('pageerror', e => console.log('PAGEERROR', String(e).slice(0, 140)));
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 }); await p.waitForTimeout(15000);
await p.getByText(ROOM, { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
await p.evaluate(([t, r]) => {
  window.__ev = [];
  const log = (who) => (d) => window.__ev.push({ t: Date.now(), who, action: d && d.action, style: d && d.data && d.data.data_style, keys: d ? Object.keys(d).join(',') : '' });
  frappe.realtime.on(t, log('tile:' + t)); frappe.realtime.on(r, log('room:' + r));
  // also anything the seats module repaints
  window.__paints = 0; const orig = window.RM_seats && RM_seats.paint; if (orig) RM_seats.paint = function () { window.__paints++; return orig.apply(this, arguments); };
}, [TABLE, ROOM]);
await p.locator('.fa-pencil').first().evaluate(el => el.closest('button, a, div').click()); await p.waitForTimeout(1500);
const tile = () => p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first();
const size = async () => tile().evaluate(el => { const r = el.getBoundingClientRect(); return `${Math.round(r.width)}x${Math.round(r.height)}`; });
const saved = async () => p.evaluate(async (t) => { const s = JSON.parse((await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { name: t }, fieldname: 'data_style' })).message.data_style || '{}'); return `${s.width}x${s.height}`; }, TABLE);
if (!(await tile().evaluate(el => el.classList.contains('selected')))) { await tile().click({ force: true }); await p.waitForTimeout(800); }
const before = await size();
const box = await tile().locator('.resize-handle.se').boundingBox(); const x = box.x + box.width / 2, y = box.y + box.height / 2;
await p.mouse.move(x, y); await p.mouse.down(); await p.mouse.move(x + 20, y + 10, { steps: 5 }); await p.mouse.move(x + 40, y + 20, { steps: 5 }); await p.mouse.up();
const t0 = Date.now(); let last = '';
for (let i = 0; i < 20; i++) {
  await p.waitForTimeout(1000);
  const s = await size();
  if (s !== last) { console.log(`${Date.now() - t0}ms tile ${s} saved ${await saved()}`); last = s; }
}
const ev = await p.evaluate(() => window.__ev.map(e => ({ ...e, t: e.t })));
console.log('EVENTS', JSON.stringify(ev.map(e => ({ at: e.t - t0, who: e.who, action: e.action, style: e.style && JSON.parse(e.style || '{}') && `${JSON.parse(e.style).width}x${JSON.parse(e.style).height}` })).filter(e => e.at > -60000)));
console.log('seat repaints during watch:', await p.evaluate(() => window.__paints), 'RM_BUILD', await p.evaluate(() => window.RM_BUILD), 'before', before);
// put it back
if (!(await tile().evaluate(el => el.classList.contains('selected')))) { await tile().click({ force: true }); await p.waitForTimeout(800); }
const b2 = await tile().locator('.resize-handle.se').boundingBox(); const x2 = b2.x + b2.width / 2, y2 = b2.y + b2.height / 2;
await p.mouse.move(x2, y2); await p.mouse.down(); await p.mouse.move(x2 - 40, y2 - 20, { steps: 6 }); await p.mouse.up(); await p.waitForTimeout(3000);
console.log('restored', await size(), 'saved', await saved());
await b.close();
