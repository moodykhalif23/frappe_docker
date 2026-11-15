// Delete from the floor, as a manager does it: pencil, then the trash.
//  - a clean table: one tap asks "Delete <table>?", Yes removes the tile and the record
//  - a table with sales: says it can't be deleted and why, offers no Yes
//  - a clean room: names what goes with it, Yes removes it all, the floor opens another
//    room, and a second screen parked on it loses the tab without errors
//  - a room with sales (else the delivery room): says why it stays, offers no Yes
// Writes ZZ Probe rooms — test sites only.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const USER = process.env.USER_ || 'Administrator', PASS = process.env.PASS || 'admin';
const ROOM = 'ZZ Probe Room', TABLES = ['ZZ Probe T1', 'ZZ Probe T2'], EXTRA = 'ZZ Probe T3';
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
const labelOf = (p, name) => p.evaluate(n => frappe.db.get_value('Restaurant Object', n, 'description').then(r => r.message.description || n), name);
async function floor(p) {
  await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
  await p.waitForFunction(() => window.RM && RM.rooms && RM.rooms.length, null, { timeout: 60000 });
  await p.waitForTimeout(4000);
}
async function openRoom(p, label) {
  await p.getByText(label, { exact: true }).first().click();
  await p.waitForFunction(l => RM.current_room && (RM.current_room.data.description || RM.current_room.data.name) === l, label, { timeout: 15000 });
  await p.waitForTimeout(1500);
}
async function editMode(p) {
  if (!(await p.evaluate(() => RM.editing))) await p.locator('.general-editor-button').first().click();
  await p.waitForFunction(() => RM.editing, null, { timeout: 5000 });
}
// the room's Edit/Delete sit in the floor editor, shown once the pencil turns edit mode on
async function roomTrash(p) {
  await editMode(p);
  await p.locator('.floor-map-editor.right button:has(.fa-trash)').first().click();
}
// a tile's trash shows on the selected tile; it is an overlay, so click it in the DOM
async function tableTrash(p, label) {
  await editMode(p);
  const tile = p.locator('.d-table:visible').filter({ hasText: new RegExp(`^\\s*${label}\\s*$|\\b${label}\\b`) }).first();
  await tile.click({ force: true }); await p.waitForTimeout(800);
  return p.evaluate((l) => {
    const t = Array.from(document.querySelectorAll('.d-table')).find(e => e.innerText.includes(l));
    const btn = t && t.querySelector('.fa-trash') && t.querySelector('.fa-trash').closest('button');
    if (!btn) return 'no trash';
    btn.click(); return 'clicked';
  }, label);
}
const dialog = async (p) => { const d = p.locator('.modal.show').last(); await d.waitFor({ timeout: 10000 }); return d; };
const text = async (d) => (await d.innerText()).replace(/\s+/g, ' ');

const p = await screen();
// a fresh room with three tables, made before either floor loads
for (const n of [EXTRA, ...TABLES, ROOM]) if (await exists(p, n)) await api(p, 'frappe.client.delete', { doctype: 'Restaurant Object', name: n });
await api(p, 'frappe.client.insert', { doc: { doctype: 'Restaurant Object', type: 'Room', description: ROOM } });
for (const t of [...TABLES, EXTRA]) await api(p, 'frappe.client.insert', { doc: { doctype: 'Restaurant Object', type: 'Table', description: t, room: ROOM, no_of_seats: 4 } });

const watcher = await screen();
await floor(watcher); await openRoom(watcher, ROOM);
await floor(p); await openRoom(p, ROOM);

// --- a clean table ----------------------------------------------------------
check('the clean table has a trash', (await tableTrash(p, EXTRA)) === 'clicked');
let d = await dialog(p);
let said = await text(d);
check('one tap asks to delete it by name', said.includes(`Delete ${EXTRA}?`), said.slice(0, 120));
await d.getByRole('button', { name: /^Yes$/ }).click();
await p.waitForFunction(n => !RM.busy && !Array.from(document.querySelectorAll('.d-table')).some(e => e.innerText.includes(n)), EXTRA, { timeout: 15000 }).catch(() => {});
check('the table is gone from the database', !(await exists(p, EXTRA)));
check('and its tile from the floor', (await p.locator('.d-table').filter({ hasText: EXTRA }).count()) === 0);

// --- the clean room ---------------------------------------------------------
await roomTrash(p);
d = await dialog(p);
said = await text(d);
check('one tap asks, naming the room and its tables', said.includes(ROOM) && TABLES.every(t => said.includes(t)) && !said.includes(EXTRA), said.slice(0, 160));
await d.getByRole('button', { name: /^Yes$/ }).click();
await p.waitForFunction(r => !RM.busy && RM.current_room && RM.current_room.data.name !== r && !RM.rooms.some(x => x.name === r), ROOM, { timeout: 20000 }).catch(() => {});
check('the room is gone from the database', !(await exists(p, ROOM)));
check('and so are its tables', !(await exists(p, TABLES[0])) && !(await exists(p, TABLES[1])));
check('its tab is gone from the floor', (await p.getByText(ROOM, { exact: true }).count()) === 0);
const now = await p.evaluate(() => RM.current_room && RM.current_room.data.name);
check('the floor opened another room', !!now && now !== ROOM, now);
check('the status bar reads Ready', (await p.locator('.restaurant-manage-status').innerText()).trim() === 'Ready');
await watcher.waitForTimeout(3000);
check('a second screen on that room lost its tab', (await watcher.getByText(ROOM, { exact: true }).count()) === 0);

// --- a table with sales stays ------------------------------------------------
const soldAt = await p.evaluate(() => frappe.db.get_value('Table Order', { status: 'Invoiced', table: ['is', 'set'] }, ['table', 'room']).then(r => r.message));
if (soldAt && soldAt.table) {
  const tLabel = await labelOf(p, soldAt.table);
  await openRoom(p, await labelOf(p, soldAt.room));
  check(`${tLabel} (sold) has a trash`, (await tableTrash(p, tLabel)) === 'clicked');
  d = await dialog(p);
  said = await text(d);
  check(`${tLabel} says it can't be deleted, and why`, said.includes("can't be deleted") && said.includes('check(s) on record') && said.includes('part of the books'), said.slice(0, 200));
  check('without offering to delete it', (await d.getByRole('button', { name: /^Yes$/ }).count()) === 0);
  await p.keyboard.press('Escape'); await p.waitForTimeout(500);
  check('and it is still there', await exists(p, soldAt.table));
} else console.log('SKIP  no invoiced check on this site (deploy.sh SIMULATE=1 seeds some)');

// --- a room that must stay: one with sales, else the delivery room ----------
const sold = soldAt && soldAt.room;
const delivery = await p.evaluate(() => frappe.db.get_single_value('Restaurant Settings', 'delivery_room'));
const kept = sold || delivery, why = sold ? 'check(s) on record' : 'delivery room';
if (kept) {
  const label = await labelOf(p, kept);
  await openRoom(p, label);
  await roomTrash(p);
  d = await dialog(p);
  said = await text(d);
  check(`${label} says it can't be deleted, and why (${why})`, said.includes("can't be deleted") && said.includes(why), said.slice(0, 200));
  check('the books explanation shows only when checks are the reason', said.includes('part of the books') === !!sold);
  check('without offering to delete it', (await d.getByRole('button', { name: /^Yes$/ }).count()) === 0);
  await p.keyboard.press('Escape');
  check('and it is still there', await exists(p, kept));
} else console.log('SKIP  no room with sales and no delivery room on this site');

check('no page errors on either screen', errors.length === 0, errors.join(' | '));
console.log(`RESULT ${results.filter(Boolean).length}/${results.length}`);
await b.close();
process.exit(results.every(Boolean) ? 0 : 1);
