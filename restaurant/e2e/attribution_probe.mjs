// The moat: on a shared tablet, Amina seats a party; the grace window is set to
// one second, so when Moses taps Order the tablet asks "Who's on?" and he signs
// in. The check stays Amina's, every fired line is Moses's, the timeline says
// who fired what, and Sales by Waiter (Lines fired) credits Moses.
//   BASE=http://pos.localhost:8080 node attribution_probe.mjs   (test site: writes checks)
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 9';
const GUEST = 'Attribution ' + Date.now().toString().slice(-4);
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 200) : ''}`); };
p.on('pageerror', e => console.log('PAGEERROR', String(e).slice(0, 140)));
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'waiter@etham.co.ke'); await p.fill('#login_password', 'Waiter@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
const closeModals = async () => { for (let i = 0; i < 4; i++) { const m = p.locator('.modal.show'); if (!(await m.count())) break; await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {}); await p.waitForTimeout(500); } };
const signIn = async (dlg, waiter, pin) => { await dlg.locator('select').first().selectOption(waiter); await dlg.locator('input[type="password"]').fill(pin); await dlg.getByRole('button', { name: 'Sign in' }).click(); await p.waitForTimeout(3000); };

// a bare tablet: Seat guest must ask who is seating
await p.evaluate(() => localStorage.removeItem('rm_waiter_session'));
await p.getByRole('button', { name: 'Seat guest' }).click(); await p.waitForTimeout(2500);
let d = p.locator('.modal.show').last();
ok('Seat guest on a bare tablet asks "Who\'s on?"', /Who's on/.test(await d.locator('.modal-title').innerText().catch(() => '')));
await signIn(d, 'Amina Test', '1111');
d = p.locator('.modal.show').last();
ok('after the PIN the seat dialog opens', /Seat a guest/.test(await d.locator('.modal-title').innerText().catch(() => '')));
await d.locator('input[data-fieldname="guest_name"]').fill(GUEST);
await d.locator('input[data-fieldname="covers"]').fill('2'); await d.locator('input[data-fieldname="covers"]').press('Tab'); await p.waitForTimeout(3000);
const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
await d.locator('select[data-fieldname="table"]').selectOption({ label: opts.find(o => o.includes(TABLE)) });
await d.getByRole('button', { name: 'Seat & open order' }).click(); await p.waitForTimeout(9000);
const cards = p.locator('.order-manage .small-box.item:visible'); await cards.first().waitFor({ timeout: 45000 });
await p.evaluate(() => { window.__orders = 0; const o = TableOrder.prototype.order; TableOrder.prototype.order = function () { window.__orders++; return o.apply(this, arguments); }; });
await cards.first().locator('.add-item').click({ force: true }); await p.waitForTimeout(3500);
const btn = await p.evaluate(() => { const b = document.querySelector('.order-manage .pad-btn.btn-order'); return { disabled: b.classList.contains('disabled'), badge: (b.querySelector('.badge') || {}).textContent }; });
ok('the Order button enables when a dish lands', !btn.disabled, JSON.stringify(btn));

// the grace window is one second on this test site: Order must ask again
await p.evaluate(() => { if (window.RM_waiter) RM_waiter.__policy = 1; });
await p.waitForTimeout(1500);
await p.locator('.order-manage .pad-btn.btn-order').first().dblclick({ force: true }); await p.waitForTimeout(3000);
d = p.locator('.modal.show').filter({ hasText: "Who's on" }).last();
ok('Order after the grace window asks "Who\'s on?" again', (await d.count()) > 0, 'order() calls: ' + await p.evaluate(() => window.__orders));
await signIn(d, 'Moses Test', '2222'); await p.waitForTimeout(5000); await closeModals();

const rec = await p.evaluate(async (g) => {
  // read through the check itself: a waiter can read Table Order, not Comment
  try {
    // frappe.client.get drops _comments; get_list allows the optional column
    const o = (await frappe.call('frappe.client.get_list', { doctype: 'Table Order', filters: { customer: g }, fields: ['name', '_comments'], limit_page_length: 1 })).message[0];
    const doc = (await frappe.call('frappe.client.get', { doctype: 'Table Order', name: o.name })).message;
    let notes = []; try { notes = JSON.parse(o._comments || '[]').map(c => String(c.comment).replace(/<[^>]+>/g, '')); } catch (e) {}
    return { order: { name: doc.name, waiter: doc.waiter, status: doc.status }, lines: (doc.entry_items || []).map(l => ({ item_name: l.item_name, status: l.status, waiter: l.waiter })), notes };
  } catch (e) { return { error: String(e && e.message || e).slice(0, 200), order: null, lines: [], notes: [] }; }
}, GUEST);
ok('the check belongs to the seater (Amina)', rec.order && rec.order.waiter === 'Amina Test', JSON.stringify(rec.order));
ok('every fired line belongs to the firer (Moses)', rec.lines.length > 0 && rec.lines.every(l => l.status === 'Sent' && l.waiter === 'Moses Test'), JSON.stringify(rec.lines));
ok('the timeline says who fired what', rec.notes.some(n => /Moses Test fired 1 line/.test(n)), JSON.stringify(rec.notes));
console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
