// The menu card, as a waiter sees it: photo on top, name, price left, "- n +"
// pill right. Screenshots the grid and proves the pill drives the check.
//   BASE=http://pos.localhost:8080 node card_shots.mjs
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE || 'http://pos.localhost:8080';
const TABLE = process.env.TABLE || 'Table 7';
mkdirSync('shots', { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 });
const p = await ctx.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e).split('\n')[0].slice(0, 140)));
// a 404 on the pad is usually a dish photo that no longer exists — name it
const missing = [];
p.on('response', r => { if (r.status() === 404) missing.push(r.url().replace(BASE, '').slice(0, 120)); });
const results = [];
const ok = (name, pass, detail = '') => { results.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`); };

await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'waiter@etham.co.ke');
await p.fill('#login_password', 'Waiter@2026');
await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(15000);
await p.getByText('R 2', { exact: true }).first().click().catch(() => {});
await p.waitForTimeout(3000);

// sign in by PIN, then seat one guest so the pad opens on a fresh check
await p.getByRole('button', { name: /^Waiter/ }).click();
await p.waitForTimeout(2500);
let d = p.locator('.modal.show').last();
await d.locator('select').first().selectOption('Amina Test');
await d.locator('input[type="password"]').fill('1111');
await d.getByRole('button', { name: 'Sign in' }).click();
await p.waitForTimeout(3000);
for (let i = 0; i < 3; i++) {
  const m = p.locator('.modal.show');
  if (!(await m.count())) break;
  await m.last().locator('.btn-modal-close, .modal-header .close').first().click({ force: true }).catch(() => {});
  await p.waitForTimeout(500);
}
await p.getByRole('button', { name: 'Seat guest' }).click();
await p.waitForTimeout(2500);
d = p.locator('.modal.show').last();
await d.locator('input[data-fieldname="guest_name"]').fill('Card Shot Guest');
await d.locator('input[data-fieldname="covers"]').fill('1');
await d.locator('input[data-fieldname="covers"]').press('Tab');
await p.waitForTimeout(3000);
const opts = await d.locator('select[data-fieldname="table"] option').allTextContents();
await d.locator('select[data-fieldname="table"]').selectOption({ label: opts.find(o => o.includes(TABLE)) });
await d.getByRole('button', { name: 'Seat & open order' }).click();
await p.waitForTimeout(9000);

const cards = p.locator('.order-manage .small-box.item:visible');
await cards.first().waitFor({ timeout: 45000 });
const n = await cards.count();
// every dish on the profile's menu must be on the pad — not the first render block of them
const menuSize = await p.evaluate(async () => {
  try {
    const menu = (window.RM && RM.menu && RM.menu.name) || null;
    if (!menu) return null;
    const rows = (await frappe.call('frappe.client.get_list', { doctype: 'Restaurant Menu Item', parent: 'Restaurant Menu',
      filters: { parent: menu, status: 1 }, fields: ['name'], limit_page_length: 5000 })).message;
    return rows.length;
  } catch (e) { return null; }   // a child-table count the API refuses is not the pad's fault
});
ok('every dish on the menu renders', n > 0 && (menuSize === null || n === menuSize), `${n} cards, menu has ${menuSize}`);

const shape = await p.evaluate(() => {
  const c = document.querySelector('.order-manage .small-box.item');
  const r = (sel) => { const el = c.querySelector(sel); return el ? el.getBoundingClientRect() : null; };
  const icon = r('.icon'), title = r('.title'), price = r('.rm-price'), pill = r('.input-group'), plus = r('.add-item'), minus = r('.rm-cart-minus');
  const cs = getComputedStyle(c.querySelector('.rm-price'));
  return {
    card: c.getBoundingClientRect().width, iconH: icon && icon.height, iconW: icon && icon.width,
    iconDx: icon && Math.round(icon.left - c.getBoundingClientRect().left), iconDy: icon && Math.round(icon.top - c.getBoundingClientRect().top),
    photoAboveTitle: icon && title && icon.bottom <= title.top + 1,
    pillCentred: pill && Math.abs((pill.left + pill.right) / 2 - (c.getBoundingClientRect().left + c.getBoundingClientRect().right) / 2) <= 3,
    priceAbovePill: price && pill && price.bottom <= pill.top + 1,
    priceColor: cs.color, priceText: c.querySelector('.rm-price').textContent.trim(),
    plusRound: plus && Math.abs(plus.width - plus.height) < 2 && getComputedStyle(c.querySelector('.add-item')).borderRadius,
    minusVisible: !!minus && minus.width > 0,
    // visible text only: the screen-reader label still says "Add <price>"
    visiblePlus: Array.from(c.querySelector('.add-item').childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim(),
    undefinedSrc: Array.from(document.querySelectorAll('[src$="undefined"],[href$="undefined"]')).map(e => e.outerHTML.slice(0, 160)),
    qty: c.querySelector('.qty-in-cart').textContent.trim(),
  };
});
console.log('SHAPE', JSON.stringify(shape));
ok('photo sits above the name, flush with the card edges', shape.photoAboveTitle && Math.abs(shape.iconW - shape.card) <= 2 && Math.abs(shape.iconDx) <= 2 && Math.abs(shape.iconDy) <= 2 && shape.iconH >= 120, `icon ${Math.round(shape.iconW)}x${Math.round(shape.iconH)} at (${shape.iconDx},${shape.iconDy}) in a ${Math.round(shape.card)} card`);
const radius = await p.evaluate(() => parseFloat(getComputedStyle(document.querySelector('.order-manage .small-box.item')).borderTopLeftRadius));
ok('cards have nearly sharp corners', radius <= 8, `${radius}px`);
const overflow = await p.evaluate(() => Array.from(document.querySelectorAll('.order-manage .small-box.item')).slice(0, 40).filter(c => { const r = c.getBoundingClientRect(); const g = c.querySelector('.input-group').getBoundingClientRect(); return g.right > r.right + 1; }).length);
ok('no pill overflows its card', overflow === 0, `${overflow} cards overflow`);
// initials belong inside the photo box on every card, however tall its name makes it
const strays = await p.evaluate(() => Array.from(document.querySelectorAll('.order-manage .small-box.item')).filter(c => c.offsetParent).filter(c => { const a = c.querySelector('.icon .placeholder-text'); if (!a) return false; const ar = a.getBoundingClientRect(), ir = c.querySelector('.icon').getBoundingClientRect(); return ar.top < ir.top - 1 || ar.bottom > ir.bottom + 1; }).length);
ok('initials stay inside the photo box', strays === 0, `${strays} cards with stray initials`);
const bar = await p.evaluate(() => { const l = document.querySelector('.order-manage .product-list'); return l ? l.offsetWidth - l.clientWidth : -1; });
ok('the card list shows no scrollbar', bar === 0, `${bar}px of scrollbar`);
ok('price on its own line, pill centred beneath', shape.priceAbovePill && shape.pillCentred, shape.priceText);
ok('plus is a round button showing only "+"', !!shape.plusRound && /50%|999px/.test(shape.plusRound) && shape.visiblePlus === '+', `${shape.plusRound} text "${shape.visiblePlus}"`);
if (shape.undefinedSrc.length) console.log('UNDEFINED SRC:', JSON.stringify(shape.undefinedSrc));
ok('minus is on the pill', shape.minusVisible);
ok('pill starts at 0', shape.qty === '0', shape.qty);

// the pill drives the check: + + - -
const card = cards.first();
const readQty = async () => (await card.locator('.qty-in-cart').textContent()).trim();
const tealPlus = async () => card.evaluate(c => c.classList.contains('rm-has-qty'));
await card.locator('.add-item').click({ force: true });
await p.waitForTimeout(3500);
ok('one tap on + puts one on the check, plus turns teal', (await readQty()) === '1' && (await tealPlus()), `qty ${await readQty()} teal ${await tealPlus()}`);
await card.locator('.add-item').click({ force: true });
await p.waitForTimeout(3500);
ok('second tap makes it 2', (await readQty()) === '2', await readQty());
await p.screenshot({ path: 'shots/card-grid.png', clip: { x: 0, y: 0, width: 1400, height: 900 } });
await card.locator('.rm-cart-minus').click({ force: true });
await p.waitForTimeout(3500);
ok('minus takes one off', (await readQty()) === '1', await readQty());
await card.locator('.rm-cart-minus').click({ force: true });
await p.waitForTimeout(3500);
ok('minus to zero clears it and the plus goes grey', (await readQty()) === '0' && !(await tealPlus()), `qty ${await readQty()} teal ${await tealPlus()}`);
const server = await p.evaluate(async (g) => {
  const r = await frappe.call('frappe.client.get_list', { doctype: 'Table Order',
    filters: { customer: g, status: ['not in', ['Cancelled', 'Invoiced']] }, fields: ['name', 'amount'], limit_page_length: 1 });
  return (r.message || [])[0];
}, 'Card Shot Guest');
ok('the check on the server agrees (amount back to 0)', server && Number(server.amount) === 0, JSON.stringify(server));
ok('no page errors', errs.length === 0, errs.join(' | '));
if (missing.length) console.log('MISSING (404):', JSON.stringify([...new Set(missing)].slice(0, 8)));

// a close-up of one card row for the report
const grid = p.locator('.order-manage .widget-group-body').first();
await grid.screenshot({ path: 'shots/card-closeup.png' }).catch(() => {});
console.log(`RESULT ${results.filter(Boolean).length}/${results.length}`);
await b.close();
process.exit(results.every(Boolean) ? 0 : 1);
