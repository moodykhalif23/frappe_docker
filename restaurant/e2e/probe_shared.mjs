// Why does the SECOND party seated on a table get an empty check? Watches the
// pad state, the picker dialog and every server reply as it happens.
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const TABLE = process.env.TABLE || 'Table 9';
const b = await chromium.launch();

const open = async (label) => {
  const ctx = await b.newContext({ viewport: { width: 1500, height: 900 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => console.log(`[${label}] pageerror ${String(e).split('\n')[0].slice(0, 120)}`));
  p.on('console', m => { if (/error|refus|not order|denied/i.test(m.text())) console.log(`[${label}] console ${m.text().slice(0, 140)}`); });
  p.on('response', async r => {
    const u = r.url();
    if (!/api\/method/.test(u)) return;
    const m = decodeURIComponent(u).split('/').pop().split('?')[0];
    if (!/set_items|calculate|add_item|call|synchronize|pick|order/i.test(m)) return;
    let body = '';
    try { body = (await r.text()).slice(0, 220); } catch (e) { body = '(unreadable)'; }
    console.log(`[${label}] ${r.status()} ${m} -> ${body.replace(/\s+/g, ' ')}`);
  });
  await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await p.fill('#login_email', 'waiter@etham.co.ke');
  await p.fill('#login_password', 'Waiter@2026');
  await p.click('button.btn-login');
  await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
  await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(15000);
  await p.getByText('R 2', { exact: true }).first().click().catch(() => {});
  await p.waitForTimeout(3000);
  return { label, p };
};

const pin = async (a, waiter, code) => {
  await a.p.getByRole('button', { name: /^Waiter/ }).click().catch(() => {});
  await a.p.waitForTimeout(2500);
  const d = a.p.locator('.modal.show').last();
  await d.locator('select').first().selectOption(waiter).catch(() => {});
  await d.locator('input[type="password"]').fill(code).catch(() => {});
  await d.getByRole('button', { name: 'Sign in' }).click().catch(() => {});
  await a.p.waitForTimeout(3000);
  for (let i = 0; i < 3; i++) {
    const m = a.p.locator('.modal.show');
    if (!(await m.count())) break;
    await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {});
    await a.p.waitForTimeout(500);
  }
};

const seat = async (a, guest, covers) => {
  await a.p.getByRole('button', { name: 'Seat guest' }).click();
  await a.p.waitForTimeout(2500);
  const d = a.p.locator('.modal.show').last();
  await d.locator('input[data-fieldname="guest_name"]').fill(guest);
  await d.locator('input[data-fieldname="covers"]').fill(String(covers));
  await d.locator('input[data-fieldname="covers"]').press('Tab');
  await a.p.waitForTimeout(3000);
  const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
  const want = opts.find(o => o.includes(TABLE));
  if (!want) { console.log(`[${a.label}] ${TABLE} not offered: ${opts.join(' | ')}`); return false; }
  await d.locator('select[data-fieldname="table"]').selectOption({ label: want });
  await d.getByRole('button', { name: 'Seat & open order' }).click();
  await a.p.waitForTimeout(9000);
  return true;
};

const padState = async (a) => a.p.evaluate(() => {
  const om = window.RM && RM.order_manage;
  const modal = document.querySelector('.modal.show');
  return {
    pad_open: !!(om && om.wrapper && document.querySelector('.order-manage')),
    selected_order: om && om.order && om.order.data ? om.order.data.name : null,
    orders_in_rail: Array.from(document.querySelectorAll('.order-manage .btn-app.btn-order')).map(e => e.innerText.trim()).slice(0, 6),
    modal_title: modal ? (modal.querySelector('.modal-title') || {}).innerText : null,
    add_items_visible: document.querySelectorAll('.order-manage .add-item').length,
    toast: Array.from(document.querySelectorAll('.desk-alert, .alert')).map(e => e.innerText.trim().slice(0, 60)),
  };
});

const w1 = await open('W1');
const w2 = await open('W2');
await pin(w1, 'Amina Test', '1111');
await pin(w2, 'Moses Test', '2222');

console.log('--- W1 seats the first party ---');
await seat(w1, 'Probe One', 1);
console.log('[W1] pad', JSON.stringify(await padState(w1)));
const add1 = w1.p.locator('.order-manage .add-item:visible');
await add1.first().waitFor({ timeout: 30000 }).catch(() => {});
await add1.nth(0).click({ force: true });
await w1.p.waitForTimeout(4000);
console.log('[W1] after one tap', JSON.stringify(await padState(w1)));
await w1.p.locator('.order-manage .pad-btn.btn-order').first().dblclick({ force: true }).catch(() => {});
await w1.p.waitForTimeout(5000);

console.log('--- W2 seats the second party on the SAME table ---');
await w2.p.reload({ waitUntil: 'domcontentloaded' });
await w2.p.waitForTimeout(15000);
await w2.p.getByText('R 2', { exact: true }).first().click().catch(() => {});
await w2.p.waitForTimeout(3000);
await seat(w2, 'Probe Two', 1);
console.log('[W2] pad right after seating', JSON.stringify(await padState(w2)));
const add2 = w2.p.locator('.order-manage .add-item:visible');
await add2.first().waitFor({ timeout: 30000 }).catch(() => {});
await add2.nth(0).click({ force: true });
await w2.p.waitForTimeout(5000);
console.log('[W2] after one tap', JSON.stringify(await padState(w2)));

const checks = await w1.p.evaluate(async (tbl) => {
  const r = await frappe.call('frappe.client.get_list', { doctype: 'Table Order',
    filters: { table: tbl, status: ['not in', ['Cancelled', 'Invoiced']] },
    fields: ['name', 'customer', 'status', 'amount'], limit_page_length: 10 });
  return r.message;
}, TABLE);
console.log('CHECKS ' + JSON.stringify(checks));
await b.close();
