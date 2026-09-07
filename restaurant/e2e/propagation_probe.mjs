// Two screens. B seats a party, changes the table's seat count, then releases
// it; A watches the tile. Each change must reach A within 2.5 s and, once
// there, never revert to the older value. Test site only — it seats and releases.
//   BASE=http://pos.localhost:8080 node propagation_probe.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 9';
const b = await chromium.launch();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 220) : ''}`); };
const login = async (u, pw) => { const p = await (await b.newContext({ viewport: { width: 1400, height: 900 } })).newPage(); await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' }); await p.fill('#login_email', u); await p.fill('#login_password', pw); await p.click('button.btn-login'); await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {}); await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(12000); await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(2500); return p; };
const A = await login('cashier@etham.co.ke', 'Cashier@2026');
const B = await login('geff@etham.co.ke', 'Geff@2026');
const tile = (p) => p.evaluate((t) => { const el = Array.from(document.querySelectorAll('.d-table')).find(e => e.textContent.includes(t)); const pill = el && el.querySelector('.d-table-seats'); return el ? { seats: pill ? pill.textContent.trim() : '', badges: el.querySelectorAll('.rm-party-badges .rm-party-badge, .rm-party-badges span').length } : null; }, TABLE);
// sample A for `secs`; returns the sequence of distinct states with timestamps
const sample = async (secs) => { const out = []; const t0 = Date.now(); let last = null; while (Date.now() - t0 < secs * 1000) { const t = JSON.stringify(await tile(A)); if (t !== last) { out.push([Date.now() - t0, t]); last = t; } await A.waitForTimeout(150); } return out; };
const settle = (seq, pred, within = 2500) => { const hit = seq.find(([, s]) => pred(JSON.parse(s))); if (!hit) return { ok: false, why: 'never reached' }; const after = seq.filter(([ms]) => ms > hit[0]); const reverted = after.some(([, s]) => !pred(JSON.parse(s))); return { ok: hit[0] <= within && !reverted, why: `reached at ${hit[0]}ms${reverted ? ', then reverted' : ''}` }; };
const name = await B.evaluate(async (t) => (await frappe.call('frappe.client.get_value', { doctype: 'Restaurant Object', filters: { description: t }, fieldname: ['name', 'no_of_seats'] })).message, TABLE);
const cap = Number(name.no_of_seats);
// 1. seat 3
let [seq] = await Promise.all([sample(6), B.evaluate(async (t) => (await frappe.call('restaurant_management.house.seat_walkin', { guest_name: 'Prop Guest', covers: 3, table: t, waiter: 'Amina Test', pin: '1111' })).message, TABLE)]);
let r = settle(seq, s => s && s.seats === `3/${cap}` && s.badges >= 1);
ok('a seated party reaches the other screen and stays', r.ok, r.why + ' ' + JSON.stringify(seq.map(x => x[1])).slice(0, 160));
// 2. seat count +2 while occupied
[seq] = await Promise.all([sample(6), B.evaluate(async ({ n, s }) => (await frappe.call('frappe.client.set_value', { doctype: 'Restaurant Object', name: n, fieldname: 'no_of_seats', value: s })).message, { n: name.name, s: cap + 2 })]);
r = settle(seq, s => s && s.seats === `3/${cap + 2}`);
ok('a seat-count change reaches the other screen and never reverts', r.ok, r.why + ' ' + JSON.stringify(seq.map(x => x[1])).slice(0, 200));
// 3. release
[seq] = await Promise.all([sample(6), B.evaluate(async (t) => (await frappe.call('restaurant_management.house.release_table', { table: t })).message, TABLE)]);
r = settle(seq, s => s && s.seats === String(cap + 2) && s.badges === 0);
ok('a release clears seats and badges on the other screen and they stay clear', r.ok, r.why + ' ' + JSON.stringify(seq.map(x => x[1])).slice(0, 200));
await B.evaluate(async ({ n, s }) => (await frappe.call('frappe.client.set_value', { doctype: 'Restaurant Object', name: n, fieldname: 'no_of_seats', value: s })).message, { n: name.name, s: cap });
console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
