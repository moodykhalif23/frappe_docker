// Kept as a regression probe: a body drag must move the tile from an unselected start and from a selected one.
// Drag a tile's BODY on the live floor (as the manager), then drag it back.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://frappe.ikobriq.com', ROOM = process.env.ROOM || 'R 2', TABLE = process.env.TABLE || 'T-267';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 140)));
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 }); await p.waitForTimeout(15000);
console.log('RM_BUILD', await p.evaluate(() => window.RM_BUILD), 'drag_selects in loaded JS:', await p.evaluate(() => Array.from(document.scripts).some(s => /restaurant-object-class/.test(s.src))), await p.evaluate(async () => { const s = Array.from(document.scripts).find(s => /restaurant-object-class/.test(s.src)); if (!s) return 'no script tag'; const t = await (await fetch(s.src)).text(); return { url: s.src.replace(location.origin, ''), has_fix: /rm_drag_selects/.test(t) }; }));
await p.getByText(ROOM, { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
await p.locator('.fa-pencil').first().evaluate(el => el.closest('button, a, div').click()); await p.waitForTimeout(1500);
const tile = () => p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first();
const pos = async () => tile().evaluate(el => { const r = el.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), selected: el.classList.contains('selected') }; });
const style = async () => p.evaluate(async (t) => (await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { name: t }, fieldname: 'data_style' })).message.data_style, TABLE);
const drag = async (dx, dy) => { const box = await tile().boundingBox(); const cx = box.x + box.width / 2, cy = box.y + box.height / 2; await p.mouse.move(cx, cy); await p.mouse.down(); await p.mouse.move(cx + dx / 2, cy + dy / 2, { steps: 6 }); await p.mouse.move(cx + dx, cy + dy, { steps: 6 }); await p.mouse.up(); await p.waitForTimeout(3000); };
console.log('before', JSON.stringify(await pos()), await style());
await drag(120, 0);
console.log('after drag +120 (unselected start)', JSON.stringify(await pos()), await style());
await drag(-120, 0);
console.log('after drag -120 (selected start)', JSON.stringify(await pos()), await style());
console.log('PAGEERRORS', JSON.stringify(errs));
await b.close();
