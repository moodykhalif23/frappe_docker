// Every app script/style the floor loads, its version stamp and the CDN cache status.
// Bare URLs (no ?v=) are the ones an edge cache serves stale after a deploy.
// Which restaurant_management scripts/styles does the floor load, with or without a version stamp?
import { chromium } from 'playwright';
const BASE = process.env.BASE || 'https://frappe.ikobriq.com';
const b = await chromium.launch();
const p = await (await b.newContext()).newPage();
const seen = [];
p.on('response', r => { const u = r.url(); if (/restaurant_management|restaurant-manage/.test(u) && /\.(js|css)(\?|$)/.test(u)) seen.push({ url: u.replace(BASE, ''), cf: r.headers()['cf-cache-status'] || '-', age: r.headers()['age'] || '-', cc: (r.headers()['cache-control'] || '-').slice(0, 40) }); });
await p.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await p.fill('#login_email', 'geff@etham.co.ke'); await p.fill('#login_password', 'Geff@2026'); await p.click('button.btn-login');
await p.waitForURL(/\/app|\/desk/, { timeout: 60000 }).catch(() => {});
await p.goto(`${BASE}/app/restaurant-manage`, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(15000);
for (const s of seen) console.log(`${s.cf.padEnd(8)} age=${String(s.age).padEnd(6)} ${s.cc.padEnd(28)} ${s.url}`);
console.log('RM_BUILD', await p.evaluate(() => window.RM_BUILD));
await b.close();
