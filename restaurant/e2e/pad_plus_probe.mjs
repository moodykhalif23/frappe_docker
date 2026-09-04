// The pad's + is a door into the seating rule: it asks who is seating, opens
// Seat guest locked to this table with the seats left, and the new party's
// check appears in the pad — with its own waiter.
//   BASE=http://pos.localhost:8080 node pad_plus_probe.mjs   (test site: seats parties)
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 9';   // a six-seat table
const G1 = 'Plus A ' + Date.now().toString().slice(-4), G2 = 'Plus B ' + Date.now().toString().slice(-4);
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 220) : ''}`); };
const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'waiter@etham.co.ke'); await p.fill('#login_password', 'Waiter@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
const signIn = async (dlg, waiter, pin) => { await dlg.locator('select').first().selectOption(waiter); await dlg.locator('input[type="password"]').fill(pin); await dlg.getByRole('button', { name: 'Sign in' }).click(); await p.waitForTimeout(3000); };
// Amina seats two
await p.evaluate(() => localStorage.removeItem('rm_waiter_session'));
await p.getByRole('button', { name: 'Seat guest' }).click(); await p.waitForTimeout(2500);
let d = p.locator('.modal.show').last(); await signIn(d, 'Amina Test', '1111');
d = p.locator('.modal.show').last();
await d.locator('input[data-fieldname="guest_name"]').fill(G1); await d.locator('input[data-fieldname="covers"]').fill('2'); await d.locator('input[data-fieldname="covers"]').press('Tab'); await p.waitForTimeout(3000);
const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
// a table with room for two parties (2 + 3): the named one if it is offered whole, else the first with 5+ seats
const pickLabel = opts.find(o => o.includes(TABLE) && !/sharing/.test(o)) || opts.find(o => { const m = /· (\d+) seats$/.exec(o); return m && Number(m[1]) >= 5; });
const picked = (pickLabel || '').split(' · ')[0];
console.log('seating first party at', picked, 'from', JSON.stringify(opts.slice(0, 4)));
await d.locator('select[data-fieldname="table"]').selectOption({ label: pickLabel });
await d.getByRole('button', { name: 'Seat & open order' }).click(); await p.waitForTimeout(9000);
await p.locator('.order-manage .small-box.item:visible').first().waitFor({ timeout: 45000 });
const chipsBefore = await p.evaluate(() => document.querySelectorAll('.order-manage .btn-order').length);
// Moses taps the pad's + after the grace window
await p.evaluate(() => { RM_waiter.__policy = 1; }); await p.waitForTimeout(1500);
const plus = p.locator('.order-manage button.btn-app.btn-order').filter({ has: p.locator('.fa-plus') }).first();
ok('the pad has its + button', (await plus.count()) === 1);
await plus.click({ force: true }); await p.waitForTimeout(3000);
d = p.locator('.modal.show').filter({ hasText: "Who's on" }).last();
ok('the + asks who is seating', (await d.count()) > 0);
await signIn(d, 'Moses Test', '2222');
d = p.locator('.modal.show').filter({ hasText: /Seat another party/ }).last();
ok('Seat guest opens locked to this table', (await d.count()) > 0 && (await d.locator('.modal-title').innerText()).includes(picked), await d.locator('.modal-title').innerText().catch(() => ''));
await d.locator('input[data-fieldname="covers"]').fill('3'); await d.locator('input[data-fieldname="covers"]').press('Tab'); await p.waitForTimeout(3000);
const hint = await d.locator('[data-fieldname="hint"]').innerText().catch(() => '');
const tableOpts = await d.locator('select[data-fieldname="table"] option').allTextContents();
const m = /(\d+) of (\d+) free/.exec(tableOpts[0] || '');
ok('it shows the seats left at this table only', tableOpts.length === 1 && m && Number(m[1]) === Number(m[2]) - 2 && new RegExp(`${m[1]} seat\\(s\\) left at this table`).test(hint), `${hint.trim()} | ${JSON.stringify(tableOpts)}`);
await d.locator('input[data-fieldname="guest_name"]').fill(G2);
await d.getByRole('button', { name: 'Seat & open order' }).click(); await p.waitForTimeout(8000);
const chipsAfter = await p.evaluate(() => document.querySelectorAll('.order-manage .btn-order').length);
ok('the pad gains the new party\'s check', chipsAfter === chipsBefore + 1, `${chipsBefore} -> ${chipsAfter}`);
// the pad's title names the table's first guest; the selected check shows on its chip
const chips = await p.evaluate(() => Array.from(document.querySelectorAll('.order-manage .btn-order')).filter(e => /\d{5}/.test(e.textContent)).map(e => ({ text: e.textContent.replace(/\s+/g, ' ').trim().slice(0, 12), cls: e.className.replace(/btn-order|btn-app|btn-lg|btn|order-button|\s+/g, ' ').trim() })));
console.log('chips:', JSON.stringify(chips));
const newNo = await p.evaluate(async (g) => { const o = (await frappe.call('frappe.client.get_list', { doctype: 'Table Order', filters: { customer: g }, fields: ['name'], limit_page_length: 1 })).message[0]; return o ? o.name.slice(-5) : null; }, G2);
const newChip = chips.find(c => c.text.includes(newNo)), others = chips.filter(c => !c.text.includes(newNo));
ok('the new check is selected in the pad', !!newChip && others.every(o => o.cls !== newChip.cls), `new ${newNo}: ${JSON.stringify(newChip)} vs ${JSON.stringify(others.map(o => o.cls))}`);
const rec = await p.evaluate(async (g) => {
  const o = (await frappe.call('frappe.client.get_list', { doctype: 'Table Order', filters: { customer: g }, fields: ['name', 'waiter', 'table', 'booking'], limit_page_length: 1 })).message[0];
  const bk = o && o.booking ? (await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Booking', filters: { name: o.booking }, fieldname: ['no_of_people', 'waiter'] })).message : null;
  return { order: o, booking: bk };
}, G2);
ok('the new check is Moses\'s, with a party of three', rec.order && rec.order.waiter === 'Moses Test' && rec.booking && Number(rec.booking.no_of_people) === 3, JSON.stringify(rec));
for (let i = 0; i < 3; i++) { const m = p.locator('.modal.show'); if (!(await m.count())) break; await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {}); await p.waitForTimeout(600); }
await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(3000);
const tile = p.locator('.d-table:visible').filter({ hasText: new RegExp(`\\b${picked}\\b`) }).first();
const tileText = (await tile.innerText().catch(() => '')).replace(/\s+/g, ' ');
ok('the tile reads 5 seated with two party badges', m && new RegExp(`5/${m[2]}`).test(tileText) && /AT/.test(tileText) && /MT/.test(tileText), tileText);
ok('no page errors', errs.length === 0, errs.join(' | '));
console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
