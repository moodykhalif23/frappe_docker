import { chromium } from 'playwright';
const BASE = 'http://pos.localhost:8080';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'Administrator'); await p.fill('#login_password', 'admin');
await p.click('button.btn-login'); await p.waitForURL(/\/app/, { timeout: 60000 }).catch(()=>{});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(13000);
console.log(JSON.stringify(await p.evaluate(() => ({
  seats_module: !!window.RM_seats,
  mapped: Object.keys((window.RM_seats || {}).map || {}).length,
  occupied: Object.values((window.RM_seats || {}).map || {}).filter(s => s.occupied).map(s => [s.description, s.occupied + '/' + s.capacity, s.parties.map(x => x.initials + ':' + x.covers), s.room]),
  current_room: window.RM && RM.current_room && RM.current_room.data && RM.current_room.data.name,
  tiles: [...document.querySelectorAll('.d-table')].length,
  party_badges: document.querySelectorAll('.rm-party').length,
  section_badges: document.querySelectorAll('.d-waiter-badge').length,
})), null, 1));
await b.close();
