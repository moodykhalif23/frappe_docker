// Clicking a waiter on Sales by Waiter must open that waiter's day book, already
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1500, height: 950 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 220) : ''}`); };
const done = async (code) => { console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`); await b.close(); process.exit(code); };
const errors = []; p.on('pageerror', e => errors.push(String(e).split('\n')[0].slice(0, 160)));

await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'admin@etham.co.ke'); await p.fill('#login_password', 'Admin@2026');
await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});

const from = new Date(Date.now() - 60 * 864e5).toISOString().slice(0, 10);
const to = new Date().toISOString().slice(0, 10);
await p.goto(`${BASE}/app/query-report/Sales%20by%20Waiter?from_date=${from}&to_date=${to}`,
  { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(9000);

const cell = p.locator('.dt-cell__content a').first();
ok('the waiter name renders as a link to drill into',
  await cell.count() > 0, `${await p.locator('.dt-cell__content a').count()} link cell(s)`);
if (!(await cell.count())) await done(1);

const waiter = (await cell.innerText()).trim();
const href = await cell.getAttribute('href');
ok('the link points at the day book, carrying waiter and dates',
  /query-report\/Waiter(%20| )Day(%20| )Book/.test(href || '') && (href || '').includes(encodeURIComponent(waiter))
  && (href || '').includes(from) && (href || '').includes(to), href);

await cell.click();
await p.waitForTimeout(9000);
ok('the day book opens', /Waiter[%\s]*20?Day/i.test(p.url()) || /waiter-day-book|Waiter Day Book/i.test(await p.title()),
  `${p.url()} — ${await p.title()}`);

const filters = await p.evaluate(() => {
  try { return frappe.query_report.get_filter_values(); } catch (e) { return { error: String(e).slice(0, 120) }; }
});
ok('it arrives already filtered to the waiter that was clicked', filters.waiter === waiter,
  JSON.stringify(filters));
ok('and to the same dates', filters.from_date === from && filters.to_date === to, JSON.stringify(filters));

const grid = await p.evaluate(() => {
  try {
    const d = frappe.query_report.data || [];
    return { rows: d.length, first: d[0] || null,
             cols: (frappe.query_report.columns || []).map(c => c.fieldname) };
  } catch (e) { return { error: String(e).slice(0, 140) }; }
});
ok('it shows that waiter\'s rows', (grid.rows || 0) > 0, JSON.stringify(grid).slice(0, 200));
ok('per check shows the tables served, the seats and when it was paid',
  ['time', 'table_name', 'covers', 'items', 'amount', 'invoice'].every(c => (grid.cols || []).includes(c)),
  JSON.stringify(grid.cols));
ok('every row belongs to the waiter that was clicked',
  await p.evaluate(w => (frappe.query_report.data || []).every(r => !r.waiter || r.waiter === w), waiter),
  waiter);

// the other grain: what was actually sold, line by line
await p.evaluate(() => frappe.query_report.set_filter_value('view', 'Per item'));
await p.waitForTimeout(7000);
const items = await p.evaluate(() => {
  try {
    return { rows: (frappe.query_report.data || []).length,
             cols: (frappe.query_report.columns || []).map(c => c.fieldname),
             first: (frappe.query_report.data || [])[0] || null };
  } catch (e) { return { error: String(e).slice(0, 140) }; }
});
ok('per item names every dish sold, with qty, rate and the time it was fired',
  ['time', 'item', 'qty', 'rate', 'amount', 'table_name', 'covers', 'check_id'].every(
    c => (items.cols || []).includes(c)), JSON.stringify(items.cols));
ok('and returns lines for that waiter', (items.rows || 0) > 0, JSON.stringify(items).slice(0, 200));

ok('no page errors', errors.length === 0, errors.join(' | '));
await done(report.every(Boolean) ? 0 : 1);
