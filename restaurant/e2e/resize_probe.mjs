// Resize a tile by dragging its SE handle in edit mode; then use Update Table
// and resize again — does the second resize still persist?
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 10';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
const log = [];
p.on('pageerror', e => log.push('PAGEERROR ' + String(e).slice(0, 160)));
p.on('response', async r => { if (/api\.call/.test(r.url())) { const m = /method=([a-z_]+)/.exec(r.request().postData() || ''); if (m && /set_style|accept/.test(m[1])) log.push(`${r.status()} ${m[1]}`); } if (/desk_form\.accept/.test(r.url())) log.push(`${r.status()} accept`); });
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
await p.locator('.fa-pencil').first().evaluate(el => el.closest('button, a, div').click()); await p.waitForTimeout(1500);
const tile = () => p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${TABLE}\\b`) }).first();
const size = async () => tile().evaluate(el => ({ w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height), saving: !!window.saving }));
const db = async () => p.evaluate(async (t) => { const r = await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { name: t }, fieldname: 'data_style' }); const s = JSON.parse(r.message.data_style || '{}'); return `${s.width}x${s.height}`; }, TABLE);
const resize = async (label, dx, dy) => {
  await tile().click({ force: true }); await p.waitForTimeout(800);            // select first
  const h = tile().locator('.resize-handle.se'); const box = await h.boundingBox();
  if (!box) { log.push(`${label}: no SE handle`); return; }
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await p.mouse.move(x, y); await p.mouse.down(); await p.mouse.move(x + dx / 2, y + dy / 2, { steps: 5 }); await p.mouse.move(x + dx, y + dy, { steps: 5 }); await p.mouse.up();
  await p.waitForTimeout(3500);
  log.push(`${label}: tile ${JSON.stringify(await size())} db ${await db()}`);
};
log.push(`start: tile ${JSON.stringify(await size())} db ${await db()}`);
// a drag on an UNSELECTED tile must act at once: drag its body to move it
{
  const pos = async () => tile().evaluate(el => { const r = el.getBoundingClientRect(); return `${Math.round(r.x)},${Math.round(r.y)}`; });
  const before = await pos(); const box = await tile().boundingBox();
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  await p.mouse.move(cx, cy); await p.mouse.down(); await p.mouse.move(cx + 40, cy + 25, { steps: 6 }); await p.mouse.move(cx + 80, cy + 50, { steps: 6 }); await p.mouse.up();
  await p.waitForTimeout(3000);
  log.push(`unselected drag: ${before} -> ${await pos()} (selected now: ${await tile().evaluate(el => el.classList.contains('selected'))})`);
  await tile().click({ force: true }); await p.waitForTimeout(600);   // deselect again for the next steps
}
await resize('resize #1 (+60,+40)', 60, 40);
// now the dialog: open Update Table on this tile, change seats, save
await tile().click({ force: true }); await p.waitForTimeout(800);
await tile().evaluate(el => { const g = el.querySelector('.fa-gear, .fa-cog') || document.querySelector('.fa-gear, .fa-cog'); (g.closest('button, a, .btn, span') || g).click(); });
await p.waitForTimeout(2500);
const d = p.locator('.modal.show').last();
await d.locator('input[data-fieldname="no_of_seats"]').fill('5'); await d.getByRole('button', { name: /^Save$/ }).click({ force: true }); await p.waitForTimeout(4000);
log.push(`after dialog: saving=${await p.evaluate(() => !!window.saving)} modal=${await p.locator('.modal.show').count()}`);
await resize('resize #2 (+40,+30)', 40, 30);
await p.reload({ waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
log.push(`after reload: tile ${JSON.stringify(await size())} db ${await db()}`);
console.log(log.join('\n'));
await b.close();
