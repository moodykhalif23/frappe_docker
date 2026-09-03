// Reproduce: edit a table's Description in the floor editor, save, read back.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const TABLE = process.env.TABLE || 'Table 9', NEW = process.env.NEW || 'Table Probe';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
const log = [];
p.on('pageerror', e => log.push('PAGEERROR ' + String(e).slice(0, 160)));
p.on('response', async r => { const u = r.url(); if (/api\/method\/(frappe\.(client|desk)|restaurant_management)/.test(u) && /save|rename|set_value|update|call/.test(u)) { let t=''; try { t = (await r.text()).slice(0, 160).replace(/\s+/g,' '); } catch(e){}; log.push(`${r.status()} ${decodeURIComponent(u).split('/').pop().split('?')[0]} -> ${t}`); } });
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
// pencil = edit mode, then select the tile, then its gear
await p.locator('.btn-edit-floor, button:has(.fa-pencil), .fa-pencil').first().click({ force: true }).catch(e => log.push('pencil click failed'));
await p.waitForTimeout(1500);
const tile = p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first();
await tile.click({ force: true }); await p.waitForTimeout(1200);
// the selected tile's own gear is an overlay the locator cannot "see"; click it in the DOM
const clicked = await p.evaluate((t) => {
  const tile = Array.from(document.querySelectorAll('.d-table')).find(e => new RegExp('\\b' + t + '\\b').test(e.innerText));
  const gear = tile && (tile.querySelector('.fa-gear, .fa-cog') || document.querySelector('.fa-gear, .fa-cog'));
  if (!gear) return 'no gear';
  (gear.closest('button, a, .btn, span') || gear).click(); return 'clicked';
}, TABLE);
log.push('gear: ' + clicked);
await p.waitForTimeout(2500);
const d = p.locator('.modal.show').last();
log.push('dialog: ' + (await d.locator('.modal-title').innerText().catch(() => 'none')));
const desc = d.locator('input[data-fieldname="description"]');
log.push('description field present: ' + (await desc.count()));
await desc.fill(NEW); await d.locator('input[data-fieldname="no_of_seats"]').fill('6');
await d.getByRole('button', { name: /^Save$/ }).click({ force: true }); await p.waitForTimeout(5000);
log.push('dialog after save: ' + (await p.locator('.modal.show .modal-title').innerText().catch(() => 'closed')) + ' | alerts: ' + (await p.locator('.desk-alert, .msgprint').allInnerTexts().catch(() => [])).join(' / ').slice(0, 160));
const db = await p.evaluate(async ([t, n]) => {
  const r = await frappe.call('frappe.client.get_list', { doctype: 'Restaurant Object', filters: { name: ['in', [t, n]] }, fields: ['name', 'description', 'no_of_seats', 'room'] });
  return r.message;
}, [TABLE, NEW]);
log.push('DB: ' + JSON.stringify(db));
console.log(log.join('\n'));
await b.close();
