// Two screens. B seats a party, changes the table's seat count, then releases
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 9';
const b = await chromium.launch();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 220) : ''}`); };
const login = async (u, pw) => { const p = await (await b.newContext({ viewport: { width: 1400, height: 900 } })).newPage(); await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' }); await p.fill('#login_email', u); await p.fill('#login_password', pw); await p.click('button.btn-login'); await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {}); await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(12000); await p.getByText('R 2', { exact: true }).first().click().catch(() => {}); await p.waitForTimeout(2500); return p; };
const A = await login('cashier@etham.co.ke', 'Cashier@2026');
const B = await login('geff@etham.co.ke', 'Geff@2026');
let LABEL = TABLE;
const tile = (p) => p.evaluate((t) => { const el = Array.from(document.querySelectorAll('.d-table')).find(e => e.textContent.includes(t)); const pill = el && el.querySelector('.d-table-seats'); return el ? { seats: pill ? pill.textContent.trim() : '', badges: el.querySelectorAll('.rm-party-badges .rm-party-badge, .rm-party-badges span').length } : null; }, LABEL);
// sample A for `secs`; returns the sequence of distinct states with timestamps
const sample = async (secs) => { const out = []; const t0 = Date.now(); let last = null; while (Date.now() - t0 < secs * 1000) { const t = JSON.stringify(await tile(A)); if (t !== last) { out.push([Date.now() - t0, t]); last = t; } await A.waitForTimeout(150); } return out; };
const settle = (seq, pred, within = 2500) => { const hit = seq.find(([, s]) => pred(JSON.parse(s))); if (!hit) return { ok: false, why: 'never reached' }; const after = seq.filter(([ms]) => ms > hit[0]); const reverted = after.some(([, s]) => !pred(JSON.parse(s))); return { ok: hit[0] <= within && !reverted, why: `reached at ${hit[0]}ms${reverted ? ', then reverted' : ''}` }; };
// Take a table that is free right now rather than a hardcoded one: by the time
const pick = await B.evaluate(async (want) => {
  try {
    const free = ((await frappe.call('restaurant_management.house.free_tables', {})).message || [])
      .filter(t => t.description && !String(t.description).startsWith('Delivery'));
    const chosen = free.find(t => t.description === want) || free[0];
    if (!chosen) return { error: 'no free table on the floor' };
    const seats = (await frappe.call('frappe.client.get_value', {
      doctype: 'Restaurant Object', filters: { name: chosen.name }, fieldname: ['name', 'no_of_seats'] })).message;
    return { name: seats.name, description: chosen.description, room: chosen.room, cap: Number(seats.no_of_seats) };
  } catch (e) {
    return { error: String((e && (e.message || e.exc_type)) || JSON.stringify(e)).slice(0, 200) };
  }
}, TABLE);
ok('a free table is available to test on', !pick.error && pick.cap > 0, pick.error || JSON.stringify(pick));
if (pick.error || !pick.cap) { console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`); await b.close(); process.exit(1); }
// both screens must be looking at the room the table is in, or the tile is not rendered
LABEL = pick.description;
for (const page of [A, B]) {
  await page.getByText(pick.room, { exact: true }).first().click().catch(() => {});
  await page.waitForTimeout(2500);
}
await A.evaluate(() => RM_seats.refresh()); await A.waitForTimeout(1200);
const name = { name: pick.name };
const cap = pick.cap;
// 1. seat 3
let [seq] = await Promise.all([sample(6), B.evaluate(async (t) => (await frappe.call('restaurant_management.house.seat_walkin', { guest_name: 'Prop Guest', covers: 3, table: t, waiter: 'Amina Test', pin: '1111' })).message, pick.name)]);
let r = settle(seq, s => s && s.seats === `3/${cap}` && s.badges >= 1);
ok('a seated party reaches the other screen and stays', r.ok, r.why + ' ' + JSON.stringify(seq.map(x => x[1])).slice(0, 160));
// 2. seat count +2 while occupied
[seq] = await Promise.all([sample(6), B.evaluate(async ({ n, s }) => (await frappe.call('frappe.client.set_value', { doctype: 'Restaurant Object', name: n, fieldname: 'no_of_seats', value: s })).message, { n: name.name, s: cap + 2 })]);
r = settle(seq, s => s && s.seats === `3/${cap + 2}`);
ok('a seat-count change reaches the other screen and never reverts', r.ok, r.why + ' ' + JSON.stringify(seq.map(x => x[1])).slice(0, 200));
// 3. release
[seq] = await Promise.all([sample(6), B.evaluate(async (t) => (await frappe.call('restaurant_management.house.release_table', { table: t })).message, pick.name)]);
r = settle(seq, s => s && s.seats === String(cap + 2) && s.badges === 0);
ok('a release clears seats and badges on the other screen and they stay clear', r.ok, r.why + ' ' + JSON.stringify(seq.map(x => x[1])).slice(0, 200));
await B.evaluate(async ({ n, s }) => (await frappe.call('frappe.client.set_value', { doctype: 'Restaurant Object', name: n, fieldname: 'no_of_seats', value: s })).message, { n: name.name, s: cap });
console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
