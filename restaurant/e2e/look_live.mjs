// Read-only look check on a live site's Menu Management: 6px corners, photo flush
// with the card edges, no control overflowing its card, page ends at the last card.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://frappe.ikobriq.com';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1900, height: 900 } })).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded', timeout: 90000 }); await p.waitForTimeout(15000);
await p.evaluate(() => { if (!RM.menu_manage) RM.menu_manage = new MenuManage(); RM.menu_manage.show(); }); await p.waitForTimeout(8000);
const r = await p.evaluate(() => {
  const cards = Array.from(document.querySelectorAll('.small-box.item')).filter(e => e.offsetParent);
  const c = cards[0]; const cr = c.getBoundingClientRect(); const ir = c.querySelector('.icon').getBoundingClientRect();
  const overflow = cards.slice(0, 60).filter(x => Array.from(x.querySelectorAll('.btn, .input-group, .widget-action')).some(el => el.getBoundingClientRect().right > x.getBoundingClientRect().right + 1)).length;
  const scroller = document.querySelector('.modal.show .modal-body'); scroller.scrollTop = 1e6;
  const last = cards[cards.length - 1].getBoundingClientRect();
  return { cards: cards.length, radius: getComputedStyle(c).borderTopLeftRadius, iconFlush: Math.abs(ir.width - cr.width) <= 2 && Math.abs(ir.top - cr.top) <= 2, overflow, blankBelow: Math.round(scroller.scrollHeight - (last.bottom - scroller.getBoundingClientRect().top + scroller.scrollTop)), build: window.RM_BUILD };
});
console.log(`${parseFloat(r.radius) <= 8 && r.iconFlush && r.overflow === 0 && r.blankBelow < 60 ? 'PASS' : 'FAIL'}  the live cards look right  — ${JSON.stringify(r)}`);
await b.close();
