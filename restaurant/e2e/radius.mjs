import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true })).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', process.env.USER_ || 'Administrator');
await p.fill('#login_password', process.env.PASS || 'admin');
await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(11000);
// open any table to reach the item panel
await p.evaluate(() => {
  const t = Object.values(RM.objects || {}).find(o => o.data && o.data.type === 'Table');
  if (t) { const r = RM.object(t.data.room); r && r.select && r.select(); setTimeout(() => t.open_modal(), 1500); }
});
await p.waitForTimeout(9000);
const out = await p.evaluate(() => {
  const pick = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return `${sel}: NOT FOUND`;
    const cs = getComputedStyle(el);
    return `${sel}: radius=${cs.borderRadius} height=${cs.minHeight}`;
  };
  return [
    pick('.pos-items .small-box.item'),
    pick('.pos-items .small-box.item .add-item'),
    pick('.pos-items .small-box.item .input-group'),
    `cards on screen: ${document.querySelectorAll('.pos-items .small-box.item').length}`,
  ].join('\n');
});
console.log(out);
await b.close();
