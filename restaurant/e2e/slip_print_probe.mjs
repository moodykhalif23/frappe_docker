// The only honest test of a receipt is printing it: Chrome decides where the page
// ends, and one row too many costs a whole second slip of paper.
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'http://pos.localhost:8080';
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
const report = []; const ok = (n, pass, d = '') => { report.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + String(d).slice(0, 200) : ''}`); };
const done = async (c) => { console.log(`RESULT ${report.filter(Boolean).length}/${report.length}`); await b.close(); process.exit(c); };

await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'admin@etham.co.ke'); await p.fill('#login_password', 'Admin@2026');
await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});

const SLIPS = [['receipt', 'POS Invoice', 'Etham Receipt'],
               ['day report', 'POS Closing Entry', 'Etham Day Report']];
// the printview has no frappe object, so every name is looked up before leaving the desk
const names = await p.evaluate(async (slips) => {
  const out = {};
  for (const [label, dt] of slips) {
    out[label] = ((await frappe.call('frappe.client.get_list', { doctype: dt, filters: { docstatus: 1 },
      fields: ['name'], order_by: 'creation desc', limit_page_length: 1 })).message || [])[0]?.name;
  }
  return out;
}, SLIPS.map(([l, d]) => [l, d]));

for (const [label, dt, fmt] of SLIPS) {
  const name = names[label];
  if (!name) { ok(`${label}: something to print`, false, `no submitted ${dt}`); continue; }
  await p.goto(`${BASE}/printview?doctype=${encodeURIComponent(dt)}&name=${encodeURIComponent(name)}`
    + `&format=${encodeURIComponent(fmt)}&no_letterhead=1`, { waitUntil: 'networkidle' });
  // screen styling gives .print-format an 11.69in min-height; only print media measures the slip
  await p.emulateMedia({ media: 'print' });
  await p.setViewportSize({ width: 302, height: 1200 });
  const used = await p.evaluate(() => +(document.body.scrollHeight / (96 / 25.4)).toFixed(1));
  const pdf = await p.pdf({ preferCSSPageSize: true, printBackground: true });
  const s = pdf.toString('latin1');
  const pages = (s.match(/\/Type\s*\/Page[^s]/g) || []).length;
  const mb = s.match(/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)/);
  const [w, h] = [+mb[1] / 72 * 25.4, +mb[2] / 72 * 25.4];
  ok(`the ${label} is 80mm wide`, Math.abs(w - 80) < 1.5, `${w.toFixed(1)}mm`);
  ok(`the ${label} comes off as one slip`, pages === 1, `${pages} page(s), ${h.toFixed(1)}mm`);
  ok(`and does not waste the roll`, h - used > 0 && h - used < 45,
    `page ${h.toFixed(1)}mm for ${used}mm of slip`);
  await p.emulateMedia({ media: 'screen' });
  await p.setViewportSize({ width: 1440, height: 950 });
}
await done(report.every(Boolean) ? 0 : 1);
