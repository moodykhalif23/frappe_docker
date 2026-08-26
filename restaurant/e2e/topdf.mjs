// Renders a client document to PDF. It lives here because this is where
// playwright is installed:
//   node topdf.mjs <in>.html <out>.pdf ["Footer title"]
import { chromium } from 'playwright'
import { resolve } from 'node:path'
const src = resolve(process.argv[2]), out = process.argv[3]
const footer = process.argv[4] || 'Etham Eatery'
const b = await chromium.launch()
const p = await (await b.newContext()).newPage()
await p.goto('file://' + src, { waitUntil: 'networkidle' })
await p.pdf({
  path: out, format: 'A4', printBackground: true,
  margin: { top: '18mm', bottom: '20mm', left: '16mm', right: '16mm' },
  displayHeaderFooter: true,
  headerTemplate: '<div></div>',
  footerTemplate: '<div style="width:100%;font:8pt Inter,Arial,sans-serif;color:#8a9099;padding:0 16mm;display:flex;justify-content:space-between"><span>' + footer + '</span><span class="pageNumber"></span></div>',
})
await b.close()
console.log('pdf written')
