// Menu Management must end where its last card ends: no phantom scroller spacer below.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1900, height: 900 } })).newPage();
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
await p.evaluate(() => { if (!RM.menu_manage) RM.menu_manage = new MenuManage(); RM.menu_manage.show(); }); await p.waitForTimeout(8000);
await p.evaluate(() => { const s = document.querySelector('.modal.show .modal-body') || document.scrollingElement; s.scrollTop = 1e6; }); await p.waitForTimeout(1500);
const info = await p.evaluate(() => {
  const vis = sel => Array.from(document.querySelectorAll(sel)).filter(e => e.offsetParent);
  const counts = {};
  for (const sel of ['.small-box.item', '.item-code', '[item-code]', '.widget-group-body > *', '.clusterize-content > *', '.clusterize-extra-row', '.menu-manage', '.product-list', '.pos-items']) counts[sel] = vis(sel).length;
  const cards = vis('[item-code]').length ? vis('[item-code]') : vis('.small-box');
  const last = cards[cards.length - 1];
  let scroller = null;
  if (last) { let e = last; while (e && e !== document.body) { const cs = getComputedStyle(e); if (/(auto|scroll)/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 5) { scroller = e; break; } e = e.parentElement; } }
  const extras = Array.from(document.querySelectorAll('.clusterize-extra-row')).map(e => ({ h: Math.round(e.getBoundingClientRect().height), inline: e.getAttribute('style'), vis: !!e.offsetParent }));
  const out = { title: (document.querySelector('.modal.show .modal-title, .page-title, .title-text') || {}).innerText, counts, extras: extras.slice(0, 4) };
  if (last && scroller) {
    const sr = scroller.getBoundingClientRect(), lr = last.getBoundingClientRect();
    out.scroller = (scroller.className || scroller.tagName).toString().slice(0, 80);
    out.scrollHeight = scroller.scrollHeight; out.clientHeight = scroller.clientHeight;
    out.blankBelowLastCard = Math.round(scroller.scrollHeight - (lr.bottom - sr.top + scroller.scrollTop));
  } else if (last) {
    out.docScrollHeight = document.scrollingElement.scrollHeight; out.lastBottom = Math.round(last.getBoundingClientRect().bottom + window.scrollY);
  }
  return out;
});
console.log(JSON.stringify(info, null, 1));
const blank = info.blankBelowLastCard ?? 0;
console.log(`${blank < 60 ? 'PASS' : 'FAIL'}  the page ends where the last card ends  — ${blank}px below it, ${info.counts['[item-code]']} cards`);
process.exitCode = blank < 60 ? 0 : 1;
await b.close();
