import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1600, height: 950 } })).newPage();
const bad = [];
p.on('response', async r => {
  if (r.status() >= 400 && r.url().includes('/api/')) {
    let body = ''; try { body = (await r.text()).slice(0, 200); } catch (e) {}
    bad.push(`HTTP ${r.status()} ${decodeURIComponent(r.url()).split('method/').pop().split('?')[0]} :: ${body.replace(/\s+/g, ' ').slice(0, 150)}`);
  }
});
await p.goto('https://frappe.ikobriq.com/login', { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.fill('#login_email', 'waiter@etham.co.ke'); await p.fill('#login_password', 'Waiter@2026');
await p.click('button.btn-login'); await p.waitForURL(/\/app|\/desk/, { timeout: 90000 }).catch(() => {});
await p.goto('https://frappe.ikobriq.com/app/restaurant-manage', { waitUntil: 'domcontentloaded', timeout: 90000 });
await p.getByRole('button', { name: 'Seat guest' }).waitFor({ timeout: 60000 });
await p.waitForTimeout(3000);
await p.getByText('Main Hall', { exact: true }).first().click().catch(() => {});
await p.waitForTimeout(8000);
// reuse the existing probe party's check instead of seating another
await p.locator('.d-table:visible').filter({ hasText: 'Table 2' }).first().click();
await p.waitForTimeout(5000);
const picker = p.locator('.modal.show').filter({ hasText: 'Whose check' }).last();
if (await picker.count()) {
  await picker.locator('select[data-fieldname="order"]').selectOption({ index: 0 });
  await picker.getByRole('button', { name: 'Open' }).click();
  await p.waitForTimeout(4000);
}
const add = p.locator('.order-manage .add-item:visible');
await add.first().waitFor({ timeout: 45000 });
await add.first().click({ force: true });
await p.waitForTimeout(3000);
const picker2 = p.locator('.modal.show').filter({ hasText: 'Whose check' }).last();
if (await picker2.count()) {
  await picker2.locator('select[data-fieldname="order"]').selectOption({ index: 0 });
  await picker2.getByRole('button', { name: 'Open' }).click();
  await p.waitForTimeout(3500);
  await add.first().click({ force: true });
  await p.waitForTimeout(3000);
}
await p.waitForTimeout(4000);
const state = await p.evaluate(async () => {
  const r = await frappe.call('frappe.client.get_list', { doctype: 'Table Order',
    filters: { status: ['not in', ['Cancelled', 'Invoiced']] },
    fields: ['name', 'status', 'amount'], limit_page_length: 5 });
  return r.message;
});
console.log('checks:', JSON.stringify(state));
console.log('4xx:', JSON.stringify(bad.slice(0, 6), null, 1));
await b.close();
