// Delete a room from the floor: a clean room goes with its tables and the floor
// lands on another room; a room with sales on record is refused with the reason.
// A second screen parked on the deleted room must lose its tab without errors.
// Writes ZZ Test rooms — test sites only.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const USER = process.env.USER_ || 'Administrator', PASS = process.env.PASS || 'admin';
const ROOM = 'ZZ Probe Room', TABLES = ['ZZ Probe T1', 'ZZ Probe T2'];
const results = [], errors = [];
const check = (name, cond, detail = '') => { results.push(!!cond); console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? `   [${detail}]` : ''}`); };

const b = await chromium.launch();
async function screen() {
  const ctx = await b.newContext({ viewport: { width: 1500, height: 900 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errors.push(String(e).slice(0, 200)));
  await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await p.fill('#login_email', USER); await p.fill('#login_password', PASS); await p.click('button.btn-login');
  await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
  return p;
}
const api = (p, method, args) => p.evaluate(([m, a]) => frappe.call(m, a).then(r => r.message), [method, args]);
const exists = (p, name) => p.evaluate(n => frappe.db.exists('Restaurant Object', n), name);
async function floor(p) {
  await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
  await p.waitForFunction(() => window.RM && RM.rooms && RM.rooms.length, null, { timeout: 60000 });
  await p.waitForTimeout(4000);
}
async function openRoom(p, label) {
  await p.getByText(label, { exact: true }).first().click();
  await p.waitForFunction(l => RM.current_room && (RM.current_room.data.description || RM.current_room.data.name) === l, label, { timeout: 15000 });
}
// the room's Edit/Delete sit in the floor editor, shown once the pencil turns edit mode on
async function deleteButton(p) {
  if (!(await p.evaluate(() => RM.editing))) await p.locator('.general-editor-button').first().click();
  await p.waitForFunction(() => RM.editing, null, { timeout: 5000 });
  return p.locator('.floor-map-editor.right button:has(.fa-trash)').first();
}

const p = await screen();
// fresh room with two tables, made before either floor loads
for (const n of [...TABLES, ROOM]) if (await exists(p, n)) await api(p, 'frappe.client.delete', { doctype: 'Restaurant Object', name: n });
await api(p, 'frappe.client.insert', { doc: { doctype: 'Restaurant Object', type: 'Room', description: ROOM } });
for (const t of TABLES) await api(p, 'frappe.client.insert', { doc: { doctype: 'Restaurant Object', type: 'Table', description: t, room: ROOM, no_of_seats: 4 } });

const watcher = await screen();
await floor(watcher); await openRoom(watcher, ROOM);
await floor(p); await openRoom(p, ROOM);

// --- the clean room --------------------------------------------------------
await (await deleteButton(p)).click();
const confirm = p.locator('.modal.show').last();
await confirm.waitFor({ timeout: 10000 });
const asked = (await confirm.innerText()).replace(/\s+/g, ' ');
check('one tap asks, naming the room and its tables', asked.includes(ROOM) && TABLES.every(t => asked.includes(t)), asked.slice(0, 160));
await confirm.getByRole('button', { name: /^Yes$/ }).click();
await p.waitForFunction(r => !RM.busy && RM.current_room && RM.current_room.data.name !== r && !RM.rooms.some(x => x.name === r), ROOM, { timeout: 20000 }).catch(() => {});
check('the room is gone from the database', !(await exists(p, ROOM)));
check('and so are its tables', !(await exists(p, TABLES[0])) && !(await exists(p, TABLES[1])));
check('its tab is gone from the floor', (await p.getByText(ROOM, { exact: true }).count()) === 0);
const now = await p.evaluate(() => RM.current_room && RM.current_room.data.name);
check('the floor opened another room', !!now && now !== ROOM, now);
check('the status bar reads Ready', (await p.locator('.restaurant-manage-status').innerText()).trim() === 'Ready');
await watcher.waitForTimeout(3000);
check('a second screen on that room lost its tab', (await watcher.getByText(ROOM, { exact: true }).count()) === 0);

// --- a room that must stay: one with sales, else the delivery room ----------
const sold = await p.evaluate(() => frappe.db.get_value('Table Order', { status: 'Invoiced', room: ['is', 'set'] }, 'room').then(r => r.message && r.message.room));
const delivery = await p.evaluate(() => frappe.db.get_single_value('Restaurant Settings', 'delivery_room'));
const kept = sold || delivery, why = sold ? 'check(s) on record' : 'delivery room';
if (kept) {
  const label = await p.evaluate(n => frappe.db.get_value('Restaurant Object', n, 'description').then(r => r.message.description || n), kept);
  await openRoom(p, label);
  await (await deleteButton(p)).click();
  const msg = p.locator('.modal.show').last();
  await msg.waitFor({ timeout: 10000 });
  const said = (await msg.innerText()).replace(/\s+/g, ' ');
  check(`${label} says it can't be deleted, and why (${why})`, said.includes("can't be deleted") && said.includes(why), said.slice(0, 200));
  check('the books explanation shows only when checks are the reason', said.includes('part of the books') === !!sold);
  check('without offering to delete it', (await msg.getByRole('button', { name: /^Yes$/ }).count()) === 0);
  await p.keyboard.press('Escape');
  check('and it is still there', await exists(p, kept));
} else console.log('SKIP  no room with sales and no delivery room on this site');

check('no page errors on either screen', errors.length === 0, errors.join(' | '));
console.log(`RESULT ${results.filter(Boolean).length}/${results.length}`);
await b.close();
process.exit(results.every(Boolean) ? 0 : 1);
