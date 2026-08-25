// Renders a client document to PDF. It lives here because this is where
// playwright is installed:  node topdf.mjs ../../docs/<file>.html <out>.pdf
import { chromium } from 'playwright'
const src = process.argv[2], out = process.argv[3]
const b = await chromium.launch()
const p = await (await b.newContext()).newPage()
await p.goto('file://' + src, { waitUntil: 'networkidle' })
await p.pdf({
  path: out, format: 'A4', printBackground: true,
  margin: { top: '18mm', bottom: '20mm', left: '16mm', right: '16mm' },
  displayHeaderFooter: true,
  headerTemplate: '<div></div>',
  footerTemplate: '<div style="width:100%;font:8pt Inter,Arial,sans-serif;color:#8a9099;padding:0 16mm;display:flex;justify-content:space-between"><span>Etham Eatery — Stock, Recipes and Purchasing</span><span class="pageNumber"></span></div>',
})
await b.close()
console.log('pdf written')
