import { chromium } from 'playwright';
const BASE = 'https://frappe.ikobriq.com';
const b = await chromium.launch();

const measure = async (ctx, label) => {
  const p = await ctx.newPage();
  const t0 = Date.now();
  await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  const nav = await p.evaluate(() => {
    const n = performance.getEntriesByType('navigation')[0];
    return n ? { ttfb: Math.round(n.responseStart) } : null;
  });
  const dcl = Date.now() - t0;
  await p.getByText('Main Hall', { exact: true }).first().click({ timeout: 30000 }).catch(() => {});
  await p.locator('.d-table:visible').first().waitFor({ timeout: 60000 }).catch(() => {});
  const tiles = Date.now() - t0;
  await p.waitForFunction(() => window.RM_seats && Object.keys(RM_seats.map || {}).length > 0,
    null, { timeout: 60000 }).catch(() => {});
  const seats = Date.now() - t0;
  console.log(`${label}: ttfb ${nav ? nav.ttfb : '?'}ms | dom ${(dcl / 1000).toFixed(1)}s | tiles usable ${(tiles / 1000).toFixed(1)}s | seat counts ${(seats / 1000).toFixed(1)}s`);
  await p.close();
};

const ctx = await b.newContext({ viewport: { width: 1600, height: 950 } });
const p0 = await ctx.newPage();
await p0.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await p0.fill('#login_email', 'Administrator');
await p0.fill('#login_password', process.env.LIVE_PASS);
await p0.click('button.btn-login');
await p0.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p0.close();

await measure(ctx, 'COLD');
await measure(ctx, 'WARM');
await measure(ctx, 'WARM2');
await b.close();
