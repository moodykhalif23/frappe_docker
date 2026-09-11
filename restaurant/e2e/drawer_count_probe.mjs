// Closing the day must ask what is in the drawer and record the difference it
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const OVER = 100;
const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1400, height: 900 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 220) : ''}`); };
const done = async (code) => { console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`); await b.close(); process.exit(code); };

await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'cashier@etham.co.ke'); await p.fill('#login_password', 'Cashier@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(12000);

// Running late in the sequence, this probe cannot assume the counter is open.
const counter = await p.evaluate(async () => {
  try {
    let rows = (await frappe.call('restaurant_management.house.day_float', {})).message;
    if (!rows || !rows.length) {
      await frappe.call('restaurant_management.house.open_day', { balances: JSON.stringify({ Cash: 5000 }) });
      rows = (await frappe.call('restaurant_management.house.day_float', {})).message;
    }
    return { rows: rows || [] };
  } catch (e) { return { error: String((e && (e.message || e.exc_type)) || JSON.stringify(e)).slice(0, 200) }; }
});
ok('the counter is open with a float to count against', (counter.rows || []).length > 0,
  counter.error || JSON.stringify(counter));
if (!(counter.rows || []).length) await done(1);
const mode = counter.rows[0].mode_of_payment, expected = counter.rows[0].expected;

await p.evaluate(() => window.RM_close_day && RM_close_day.open());
await p.waitForTimeout(3000);
let d = p.locator('.modal.show').last();
ok('the Day button offers to close the selling day',
  /Close the selling day/i.test(await d.locator('.modal-title').innerText().catch(() => '')),
  await d.locator('.modal-title').innerText().catch(() => '(no dialog)'));
await d.locator('.modal-footer .btn-primary').first().click();
await p.waitForTimeout(4000);

d = p.locator('.modal.show').last();
const title = await d.locator('.modal-title').innerText().catch(() => '(no dialog)');
ok('closing asks the cashier to count the drawer first', /Count the drawer/i.test(title), title);
if (!/Count the drawer/i.test(title)) await done(1);

const field = d.locator('input[data-fieldname="m_0"]');
ok(`it asks for ${mode}, pre-filled with the ${expected} it expects`,
  Math.abs(parseFloat(String(await field.inputValue().catch(() => '0')).replace(/,/g, '')) - expected) < 0.01,
  await field.inputValue().catch(() => '(no field)'));
const around = ((await d.locator('.frappe-control[data-fieldname="m_0"] .help-box').innerText()
  .catch(() => '')) || '').replace(/\s+/g, ' ');
ok('and it shows how that figure was reached', /float .* \+ sales /i.test(around), around.slice(0, 140) || '(no description)');

await field.fill(String(expected + OVER));
await field.press('Tab');
await p.waitForTimeout(500);
await d.locator('.modal-footer .btn-primary').first().click();
await p.waitForTimeout(12000);

const msg = await p.locator('.modal.show .modal-body').last().innerText().catch(() => '');
ok('the day closes', /Day closed|banked/i.test(msg), msg.replace(/\s+/g, ' ').slice(0, 200));
ok(`and says the drawer came up ${OVER} over`, new RegExp(`over[^0-9]*${OVER}`, 'i').test(msg.replace(/\s+/g, ' ')),
  msg.replace(/\s+/g, ' ').slice(0, 220));

// The record is the point: read the difference back off the closing entry.
const banked = await p.evaluate(async (m) => {
  try {
    const closing = (await frappe.call('frappe.client.get_list', {
      doctype: 'POS Closing Entry', fields: ['name'], order_by: 'creation desc', limit_page_length: 1,
    })).message[0].name;
    const rows = (await frappe.call('frappe.client.get_list', {
      doctype: 'POS Closing Entry Detail', parent: 'POS Closing Entry',
      filters: { parent: closing, mode_of_payment: m },
      fields: ['mode_of_payment', 'opening_amount', 'expected_amount', 'closing_amount', 'difference'],
    })).message;
    return { closing, row: rows[0] };
  } catch (e) { return { error: String((e && (e.message || e.exc_type)) || JSON.stringify(e)).slice(0, 200) }; }
}, mode);
ok('the closing entry records the count, not a nil difference',
  banked.row && Math.abs(banked.row.difference - OVER) < 0.01, JSON.stringify(banked));
ok('with the float on the record instead of zero',
  banked.row && Math.abs(banked.row.opening_amount - counter.rows[0].opening) < 0.01, JSON.stringify(banked.row || {}));

// With the day now shut, the open dialog is reachable: it must ask for cash only.
await p.locator('.modal.show .modal-footer .btn-primary, .modal.show .btn-modal-close').first().click().catch(() => {});
await p.waitForTimeout(1500);
await p.evaluate(() => window.RM_close_day && RM_close_day.open_day());
await p.waitForTimeout(4000);
const od = p.locator('.modal.show').last();
const asked = await od.locator('.frappe-control[data-fieldtype="Currency"] .control-label').allTextContents().catch(() => []);
ok('opening the day asks about cash and the M-Pesa till alike',
  asked.some(t => /cash/i.test(t)) && asked.some(t => /pesa/i.test(t)), JSON.stringify(asked));
ok('naming each for what it is: a drawer float against a till balance',
  asked.some(t => /cash float/i.test(t)) && asked.some(t => /pesa opening balance/i.test(t)),
  JSON.stringify(asked));
await od.locator('.modal-footer .btn-primary').first().click().catch(() => {});
await p.waitForTimeout(8000);

// Leave the counter as we found it, or every suite after this one fails.
const reopened = await p.evaluate(async () => {
  try {
    if (!(await frappe.call('restaurant_management.house.house_shift', {})).message) {
      await frappe.call('restaurant_management.house.open_day', { balances: JSON.stringify({ Cash: 5000 }) });
    }
    return !!(await frappe.call('restaurant_management.house.house_shift', {})).message;
  } catch (e) { return String((e && (e.message || e.exc_type)) || JSON.stringify(e)).slice(0, 200); }
});
ok('the counter is open again for whatever runs next', reopened === true, JSON.stringify(reopened));
await done(report.every(Boolean) ? 0 : 1);
