// Adding assets must be one dialog that stays open: pick the category once, then type
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const CAT = 'ZZ Probe Furniture';
const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 200) : ''}`); };
const done = async (c) => { console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`); await b.close(); process.exit(c); };
const errs = []; p.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 140)));

await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'admin@etham.co.ke'); await p.fill('#login_password', 'Admin@2026');
await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});

await p.evaluate(async (cat) => {
  for (const a of (await frappe.call('frappe.client.get_list', { doctype: 'Restaurant Asset',
      filters: { asset_category: cat }, fields: ['name'], limit_page_length: 50 })).message || []) {
    await frappe.call('frappe.client.delete', { doctype: 'Restaurant Asset', name: a.name });
  }
  const had = (await frappe.call('frappe.client.get_list', { doctype: 'Restaurant Asset Category',
    filters: { name: cat }, fields: ['name'] })).message || [];
  if (!had.length) await frappe.call('frappe.client.insert', {
    doc: { doctype: 'Restaurant Asset Category', category_name: cat } });
}, CAT);

await p.goto(`${BASE}/app/restaurant-asset`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(9000);

const bulk = p.getByRole('button', { name: /Add several/i }).first();
ok('the list offers a bulk add', await bulk.count() > 0,
  (await p.locator('.page-actions').innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 120));
if (!(await bulk.count())) await done(1);
await bulk.click();
await p.waitForTimeout(2500);

const d = p.locator('.modal.show').last();
const labels = await d.locator('.frappe-control .control-label').allTextContents().catch(() => []);
ok('it asks only what it is, how many and where', labels.length <= 5, JSON.stringify(labels));
ok('and nothing about purchase or depreciation',
  !labels.some(l => /purchase|deprecia|amount|cost|value/i.test(l)), JSON.stringify(labels));

const setField = async (fn, val) => {
  const inp = d.locator(`input[data-fieldname="${fn}"], [data-fieldname="${fn}"] input`).first();
  await inp.waitFor({ state: 'visible', timeout: 15000 });
  await inp.fill(String(val));
};
await setField('asset_category', CAT);
await p.waitForTimeout(1200);
await d.locator('.awesomplete li').first().click().catch(() => {});
await setField('asset_name', 'Chairs');
await setField('quantity', 40);
await d.getByRole('button', { name: /Add and keep going/i }).first().click();
await p.waitForTimeout(4000);

ok('the dialog stays open for the next one',
  await p.locator('.modal.show').count() > 0, 'it closed');
const catAfter = await d.locator('input[data-fieldname="asset_category"], [data-fieldname="asset_category"] input').first().inputValue().catch(() => '');
ok('and keeps the category so the next thing goes in the same place', catAfter === CAT, catAfter);
const nameAfter = await d.locator('input[data-fieldname="asset_name"], [data-fieldname="asset_name"] input').first().inputValue().catch(() => 'x');
ok('while clearing the name, ready to type', nameAfter === '', `"${nameAfter}"`);

await setField('asset_name', 'Spoons');
await setField('quantity', 120);
await d.getByRole('button', { name: /Add and close/i }).first().click();
await p.waitForTimeout(5000);

const saved = await p.evaluate(async (cat) => (await frappe.call('frappe.client.get_list', {
  doctype: 'Restaurant Asset', filters: { asset_category: cat },
  fields: ['name', 'asset_name', 'quantity', 'status'], limit_page_length: 20 })).message || [], CAT);
ok('both went in, in one sitting', saved.length === 2, JSON.stringify(saved));
ok('with their counts kept',
  saved.some(r => r.asset_name === 'Chairs' && r.quantity === 40)
  && saved.some(r => r.asset_name === 'Spoons' && r.quantity === 120), JSON.stringify(saved));
ok('named readably', saved.every(r => /^AST-/.test(r.name)), JSON.stringify(saved.map(r => r.name)));

await p.evaluate(async (cat) => {
  for (const a of (await frappe.call('frappe.client.get_list', { doctype: 'Restaurant Asset',
      filters: { asset_category: cat }, fields: ['name'], limit_page_length: 50 })).message || []) {
    await frappe.call('frappe.client.delete', { doctype: 'Restaurant Asset', name: a.name });
  }
  await frappe.call('frappe.client.delete', { doctype: 'Restaurant Asset Category', name: cat });
}, CAT);

ok('no page errors', errs.length === 0, errs.join(' | '));
await done(report.every(Boolean) ? 0 : 1);
