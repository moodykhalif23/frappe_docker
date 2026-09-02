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
ok('cards render', n > 0, `${n} cards`);

const shape = await p.evaluate(() => {
  const c = document.querySelector('.order-manage .small-box.item');
  const r = (sel) => { const el = c.querySelector(sel); return el ? el.getBoundingClientRect() : null; };
  const icon = r('.icon'), title = r('.title'), price = r('.rm-price'), pill = r('.input-group'), plus = r('.add-item'), minus = r('.rm-cart-minus');
  const cs = getComputedStyle(c.querySelector('.rm-price'));
  return {
    card: c.getBoundingClientRect().width, iconH: icon && icon.height, iconW: icon && icon.width,
    photoAboveTitle: icon && title && icon.bottom <= title.top + 1,
    priceLeftOfPill: price && pill && price.right <= pill.left,
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
ok('photo sits above the name, full width', shape.photoAboveTitle && shape.iconW >= shape.card - 40 && shape.iconH >= 120, `icon ${Math.round(shape.iconW)}x${Math.round(shape.iconH)} in a ${Math.round(shape.card)} card`);
ok('price left, pill right', shape.priceLeftOfPill, shape.priceText);
ok('plus is a round button showing only "+"', !!shape.plusRound && shape.visiblePlus === '+', `${shape.plusRound} text "${shape.visiblePlus}"`);
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
