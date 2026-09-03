// On a live floor: resize a tile by its corner, HARD-RELOAD, read the tile and the
// saved style, then put the size back. The complaint was "back to original after
// a hard refresh" — this is that exact sequence.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://frappe.ikobriq.com', ROOM = process.env.ROOM || 'Upstairs', TABLE = process.env.TABLE || 'Table 11';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 900 } })).newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
const floor = async () => { await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 }); await p.waitForTimeout(15000); await p.getByText(ROOM, { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000); await p.locator('.fa-pencil').first().evaluate(el => el.closest('button, a, div').click()); await p.waitForTimeout(1500); };
const tile = () => p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first();
const size = async () => tile().evaluate(el => { const r = el.getBoundingClientRect(); return `${Math.round(r.width)}x${Math.round(r.height)}`; });
const saved = async () => p.evaluate(async (t) => { const s = JSON.parse((await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { name: t }, fieldname: 'data_style' })).message.data_style || '{}'); return `${s.width}x${s.height}`; }, TABLE);
const pull = async (dx, dy) => { if (!(await tile().evaluate(el => el.classList.contains('selected')))) { await tile().click({ force: true }); await p.waitForTimeout(800); } const box = await tile().locator('.resize-handle.se').boundingBox(); const x = box.x + box.width / 2, y = box.y + box.height / 2; await p.mouse.move(x, y); await p.mouse.down(); await p.mouse.move(x + dx / 2, y + dy / 2, { steps: 6 }); await p.mouse.move(x + dx, y + dy, { steps: 6 }); await p.mouse.up(); await p.waitForTimeout(3500); };
await floor();
const before = await size();
console.log('start', before, 'saved', await saved(), 'RM_BUILD', await p.evaluate(() => window.RM_BUILD));
await pull(40, 20);
const grown = await size(); console.log('after pull', grown, 'saved', await saved());
await p.reload({ waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText(ROOM, { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
const afterReload = await size();
console.log(`${afterReload === grown && grown !== before ? 'PASS' : 'FAIL'}  the resize survives a hard reload  — before ${before}, after pull ${grown}, after reload ${afterReload}, saved ${await saved()}`);
await p.locator('.fa-pencil').first().evaluate(el => el.closest('button, a, div').click()); await p.waitForTimeout(1500);
await pull(-40, -20);
console.log('restored', await size(), 'saved', await saved(), 'PAGEERRORS', JSON.stringify(errs));
await b.close();
