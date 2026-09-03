import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const b = await chromium.launch(); const p = await (await b.newContext()).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
const r = await p.evaluate(async () => {
  const s = Array.from(document.scripts).map(x => x.src).find(x => /restaurant-object-class\.js\?v=/.test(x));
  const mine = s && /[?&]v=([^&]+)/.exec(s)[1];
  const server = (await frappe.call('restaurant_management.house.asset_version')).message;
  return { mine, server, same: String(mine) === String(server), has_watch: typeof RM_seats.watch_build === 'function' };
});
console.log(`${r.same && r.has_watch ? 'PASS' : 'FAIL'}  page version matches the server and the watcher is mounted  — ${JSON.stringify(r)}`);
await b.close();
