// Resize a tile on a live floor by its corner handle, then by an edge handle,
// then put the size back. Reads the tile and the saved data_style each time.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://frappe.ikobriq.com', ROOM = process.env.ROOM || 'Upstairs', TABLE = process.env.TABLE || 'Table 11';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 140)));
const calls = []; p.on('response', r => { const m = /method=([a-z_]+)/.exec(r.request().postData() || ''); if (/api\.call/.test(r.url()) && m && m[1] === 'set_style') calls.push(r.status()); });
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 }); await p.waitForTimeout(15000);
await p.getByText(ROOM, { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
await p.locator('.fa-pencil').first().evaluate(el => el.closest('button, a, div').click()); await p.waitForTimeout(1500);
const tile = () => p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first();
const size = async () => tile().evaluate(el => { const r = el.getBoundingClientRect(); return `${Math.round(r.width)}x${Math.round(r.height)} sel=${el.classList.contains('selected')}`; });
const saved = async () => p.evaluate(async (t) => { const s = JSON.parse((await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { name: t }, fieldname: 'data_style' })).message.data_style || '{}'); return `${s.width}x${s.height}`; }, TABLE);
const handles = await tile().evaluate(el => Array.from(el.querySelectorAll('.resize-handle')).map(h => { const r = h.getBoundingClientRect(); const cs = getComputedStyle(h); return `${h.className.replace('resize-handle', '').trim()}:${Math.round(r.width)}x${Math.round(r.height)}/${cs.display}/${cs.pointerEvents}`; }));
console.log('handles (unselected):', handles.join(' '));
await tile().click({ force: true }); await p.waitForTimeout(1000);
console.log('handles (selected):', (await tile().evaluate(el => Array.from(el.querySelectorAll('.resize-handle')).map(h => { const r = h.getBoundingClientRect(); return `${h.className.replace('resize-handle', '').trim()}:${Math.round(r.width)}x${Math.round(r.height)}`; }))).join(' '));
const pull = async (sel, dx, dy) => {
  const h = tile().locator(sel); const box = await h.boundingBox(); if (!box) return 'no handle ' + sel;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await p.mouse.move(x, y); await p.mouse.down(); await p.mouse.move(x + dx / 2, y + dy / 2, { steps: 6 }); await p.mouse.move(x + dx, y + dy, { steps: 6 }); await p.mouse.up();
  await p.waitForTimeout(3500); return 'pulled';
};
console.log('start', await size(), 'saved', await saved());
if (process.env.CORNERS) {
  // which corners can actually be grabbed? the tool strip may cover one
  const over = await tile().evaluate(el => { const out = {}; for (const c of ['ne', 'nw', 'sw', 'se']) { const h = el.querySelector('.resize-handle.' + c); const r = h.getBoundingClientRect(); const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); out[c] = top === h ? 'handle' : (top ? (top.className || top.tagName).toString().slice(0, 40) : 'none'); } return out; });
  console.log('element on top of each corner:', JSON.stringify(over));
  console.log('corner .ne +30,-20:', await pull('.resize-handle.ne', 30, -20), await size(), 'saved', await saved());
  console.log('restore .se -30,-20:', await pull('.resize-handle.se', -30, -20), await size(), 'saved', await saved());
} else {
console.log('corner .se +60,+40:', await pull('.resize-handle.se', 60, 40), await size(), 'saved', await saved());
console.log('edge .e +40,0:', await pull('.resize-handle.e', 40, 0), await size(), 'saved', await saved());
console.log('restore corner -100,-40:', await pull('.resize-handle.se', -100, -40), await size(), 'saved', await saved());
}
console.log('set_style calls:', calls.join(','), 'PAGEERRORS', JSON.stringify(errs));
await b.close();
