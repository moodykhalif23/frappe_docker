import { chromium } from 'playwright';
const BASE = 'http://pos.localhost:8080';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 })).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'Administrator'); await p.fill('#login_password', 'admin');
await p.click('button.btn-login'); await p.waitForURL(/\/app/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(15000);
await p.locator('.d-table').filter({ hasText: 'Table 4' }).first().click();
await p.waitForTimeout(5000);
await p.locator('.order-manage .add-item:visible').first().waitFor({ timeout: 45000 }).catch(() => {});

const dump = async (tag) => console.log(tag, JSON.stringify(await p.evaluate(() => {
  const root = document.getElementById('items-container-Table 4');
  const grid = root ? root.querySelector('.widget-group-body') : null;
  if (!grid) return null;
  const kids = [...grid.children];
  return {
    children: kids.length,
    head: kids.slice(0, 2).map(e => ({ cls: e.className.slice(0, 40), h: Math.round(e.getBoundingClientRect().height) })),
    tail: kids.slice(-3).map(e => ({ cls: e.className.slice(0, 40), h: Math.round(e.getBoundingClientRect().height) })),
    cardHeights: [...new Set(kids.filter(e => e.classList.contains('shortcut-widget-box'))
      .map(e => Math.round(e.getBoundingClientRect().height)))].sort((a, b) => a - b),
  };
})));

await dump('top   :');
await p.evaluate(() => { const s = document.getElementById('items-container-Table 4').closest('.pos-items') || document.querySelector('.pos-items'); s.scrollTop = s.scrollHeight; });
await p.waitForTimeout(2500);
await dump('bottom:');
await p.screenshot({ path: '/tmp/lastrow-local.png' });
await b.close();
