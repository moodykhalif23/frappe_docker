// Two overlapping occupancy refreshes: the one that gets overtaken must still
// resolve to the fresh map, never to the old one. 
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080', TABLE = process.env.TABLE || 'Table 9';
const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1400, height: 900 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 200) : ''}`); };
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'cashier@etham.co.ke'); await p.fill('#login_password', 'Cashier@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(12000);
// Take a table that is free right now: the map is keyed by table name, and a
// hardcoded one is usually occupied by the time this runs in the full sequence.
const pick = await p.evaluate(async (want) => {
  try {
    const free = ((await frappe.call('restaurant_management.house.free_tables', {})).message || [])
      .filter(t => t.description && !String(t.description).startsWith('Delivery'));
    const chosen = free.find(t => t.description === want) || free[0];
    return chosen ? { name: chosen.name } : { error: 'no free table on the floor' };
  } catch (e) {
    return { error: String((e && (e.message || e.exc_type)) || JSON.stringify(e)).slice(0, 200) };
  }
}, TABLE);
ok('a free table is available to test on', !pick.error, pick.error || JSON.stringify(pick));
if (pick.error) { console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`); await b.close(); process.exit(1); }
const r = await p.evaluate(async (t) => {
  // seat on the server without letting the floor hear about it first: stop the poll and events
  clearInterval(RM_seats.timer); RM_seats.stale = {};
  const before = JSON.parse(JSON.stringify(RM_seats.map));
  await frappe.call('restaurant_management.house.seat_walkin', { guest_name: 'guest', covers: 2, table: t, waiter: 'Amina Test', pin: '1111' });
  // two refreshes back to back: the first is overtaken by the second
  const [first, second] = await Promise.all([RM_seats.refresh(), RM_seats.refresh()]);
  const parties = (m) => ((m || {})[t] || { parties: [] }).parties.length;
  await frappe.call('restaurant_management.house.release_table', { table: t });
  return { before: parties(before), first: parties(first), second: parties(second), same: first === second };
}, pick.name);
ok('both refreshes resolve to the same fresh map', r.same && r.first === r.second, JSON.stringify(r));
ok('the overtaken refresh sees the new party, not the old map', r.first === r.before + 1, `before ${r.before}, first saw ${r.first}`);
ok('the winning refresh sees the new party', r.second === r.before + 1, `second saw ${r.second}`);
console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`);
await b.close();
process.exit(report.every(Boolean) ? 0 : 1);
