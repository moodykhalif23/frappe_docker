import { chromium } from 'playwright';
const BASE = 'https://frappe.ikobriq.com';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 })).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await p.fill('#login_email', 'Administrator');
await p.fill('#login_password', process.env.LIVE_PASS);
await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await p.waitForTimeout(16000);
await p.getByText('Main Hall', { exact: true }).first().click();
await p.waitForTimeout(12000);
await p.locator('.d-table').filter({ hasText: 'Table 1' }).first().click();
await p.waitForTimeout(5000);
await p.locator('.order-manage .add-item:visible').first().waitFor({ timeout: 45000 }).catch(() => {});

// scroll the items pane to the bottom so clusterize renders the tail
await p.evaluate(() => {
  const s = document.querySelector('.pos-items');
  if (s) s.scrollTop = s.scrollHeight;
});
await p.waitForTimeout(3000);
await p.screenshot({ path: '/tmp/lastrow.png' });
console.log(JSON.stringify(await p.evaluate(() => {
  const grid = document.querySelector('.widget-group-body');
  const kids = [...grid.children];
  const tail = kids.slice(-8).map(e => ({
    cls: e.className.split(' ').slice(0, 3).join(' '),
    w: Math.round(e.getBoundingClientRect().width),
    h: Math.round(e.getBoundingClientRect().height),
  }));
  const widths = kids.filter(e => e.classList.contains('shortcut-widget-box'))
    .map(e => Math.round(e.getBoundingClientRect().width));
  return {
    children: kids.length,
    cardWidths: [...new Set(widths)],
    tail,
    gridCols: getComputedStyle(grid).gridTemplateColumns.split(' ').length,
  };
}), null, 1));
await b.close();
