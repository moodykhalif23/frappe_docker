// Paying by M-Pesa on the till: the code is asked for beside the amount, a
// missing or malformed code is refused before anything is saved, a good one
// pays and lands on the invoice's payment row as its reference.
//   BASE=http://pos.localhost:8080 node mpesa_probe.mjs   (test site: bills a real invoice)
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 9';
const GUEST = 'Mpesa ' + Date.now().toString().slice(-4);
const CODE = 'Q' + Date.now().toString(36).toUpperCase().slice(-9).padStart(9, 'X');
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 220) : ''}`); };
const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'cashier@etham.co.ke'); await p.fill('#login_password', 'Cashier@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
const closeModals = async () => { for (let i = 0; i < 4; i++) { const m = p.locator('.modal.show'); if (!(await m.count())) break; await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {}); await p.waitForTimeout(500); } };
// seat as Amina, one dish, fire it
await p.evaluate(() => localStorage.removeItem('rm_waiter_session'));
await p.getByRole('button', { name: 'Seat guest' }).click(); await p.waitForTimeout(2500);
let d = p.locator('.modal.show').last();
await d.locator('select').first().selectOption('Amina Test'); await d.locator('input[type="password"]').fill('1111'); await d.getByRole('button', { name: 'Sign in' }).click(); await p.waitForTimeout(3000);
d = p.locator('.modal.show').last();
await d.locator('input[data-fieldname="guest_name"]').fill(GUEST); await d.locator('input[data-fieldname="covers"]').fill('1'); await d.locator('input[data-fieldname="covers"]').press('Tab'); await p.waitForTimeout(3000);
const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
await d.locator('select[data-fieldname="table"]').selectOption({ label: opts.find(o => o.includes(TABLE)) });
await d.getByRole('button', { name: 'Seat & open order' }).click(); await p.waitForTimeout(9000);
const cards = p.locator('.order-manage .small-box.item:visible'); await cards.first().waitFor({ timeout: 45000 });
await cards.first().locator('.add-item').click({ force: true }); await p.waitForTimeout(3500);
await p.locator('.order-manage .pad-btn.btn-order').first().dblclick({ force: true }); await p.waitForTimeout(6000);
// the pad is still open on the fired check: straight to Complete
await p.locator('.order-manage').getByText(/^Complete$/).first().click({ force: true }); await p.waitForTimeout(5000);
// the pay form is the modal that carries the code field; refusals open modals on top of it
const pay = p.locator('.modal.show').filter({ has: p.locator('.rm-mpesa-code') }).first();
const input = (label) => pay.locator('.form-group').filter({ has: p.locator(`label:text-is("${label}")`) }).locator('input').first();
ok('the pay form offers an M-Pesa code field', await pay.locator('.rm-mpesa-code').count() === 1);
const total = await input('Cash').inputValue();
await input('Cash').fill('0'); await input('Cash').dispatchEvent('change');
await input('M-Pesa').fill(total); await input('M-Pesa').dispatchEvent('change'); await p.waitForTimeout(800);
const payBtn = () => pay.getByText(/^Pay\b/).first();
await payBtn().click({ force: true }); await p.waitForTimeout(2500);
const toast = () => p.locator('.desk-alert, .alert').filter({ hasText: /confirmation code/ });
ok('Pay without a code is refused, the pay form stays', (await toast().count()) > 0 && (await pay.count()) === 1, await toast().first().innerText().catch(() => 'no toast'));
await p.waitForTimeout(7500);
ok('the Pay button is given back after a refusal', (await payBtn().count()) === 1);
await pay.locator('.rm-mpesa-code').fill('abc12'); await pay.locator('.rm-mpesa-code').dispatchEvent('change');
await payBtn().click({ force: true }); await p.waitForTimeout(2500);
ok('a short code is refused', (await toast().count()) > 0);
await p.waitForTimeout(7500);
await pay.locator('.rm-mpesa-code').fill(CODE.toLowerCase()); await pay.locator('.rm-mpesa-code').dispatchEvent('keyup');
ok('the code is upper-cased as typed', (await pay.locator('.rm-mpesa-code').inputValue()) === CODE, await pay.locator('.rm-mpesa-code').inputValue());
await payBtn().click({ force: true }); await p.waitForTimeout(12000); await closeModals();
const inv = await p.evaluate(async (g) => {
  const i = (await frappe.call('frappe.client.get_list', { doctype: 'POS Invoice', filters: { customer_name: g, docstatus: 1 }, fields: ['name', 'paid_amount'], limit_page_length: 1 })).message[0];
  if (!i) return null;
  const doc = (await frappe.call('frappe.client.get', { doctype: 'POS Invoice', name: i.name })).message;
  return { name: doc.name, paid: doc.paid_amount, payments: (doc.payments || []).map(r => ({ mode: r.mode_of_payment, amount: r.amount, ref: r.reference_no })) };
}, GUEST);
ok('the invoice is paid by M-Pesa with the code as its reference', inv && inv.payments.some(r => /pesa/i.test(r.mode) && r.amount > 0 && r.ref === CODE), JSON.stringify(inv));
ok('no page errors', errs.length === 0, errs.join(' | '));
console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
