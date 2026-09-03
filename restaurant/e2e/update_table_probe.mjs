// Update Table must open with the record's numbers filled in, and a save that touches
// nothing must keep them. Prints the fields, the posted payload and the record.
import { chromium } from 'playwright';
const BASE = 'http://pos.localhost:8080', TABLE = 'Table 9';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
p.on('request', r => { if (/desk_form\.accept/.test(r.url())) console.log('POSTED', (r.postData() || '').slice(0, 600)); });
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
await p.locator('.fa-pencil').first().evaluate(el => el.closest('button, a, div').click()); await p.waitForTimeout(1500);
const tile = p.locator('.d-table:visible').filter({ hasText: /\bTable 9\b/ }).first();
await tile.click({ force: true }); await p.waitForTimeout(1000);
await tile.evaluate(el => { const g = el.querySelector('.fa-gear, .fa-cog') || document.querySelector('.fa-gear, .fa-cog'); (g.closest('button, a, .btn, span') || g).click(); });
await p.waitForTimeout(3000);
const d = p.locator('.modal.show').last();
console.log('FIELDS', JSON.stringify(await d.evaluate(m => Array.from(m.querySelectorAll('input[data-fieldname]')).map(i => [i.dataset.fieldname, i.value]))));
console.log('DB before', JSON.stringify(await p.evaluate(async () => (await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { name: 'Table 9' }, fieldname: ['no_of_seats', 'description'] })).message)));
await d.locator('input[data-fieldname="description"]').fill('Table 9');   // unchanged name: no rename, just a save
await d.getByRole('button', { name: /^Save$/ }).click({ force: true }); await p.waitForTimeout(4000);
console.log('DB after', JSON.stringify(await p.evaluate(async () => (await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { name: 'Table 9' }, fieldname: ['no_of_seats', 'description'] })).message)));
await b.close();
