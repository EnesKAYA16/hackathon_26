// Yeni sekmeler + koyu tema görsel doğrulaması.
import { chromium } from 'playwright'

const URL = process.env.URL || 'http://127.0.0.1:5173'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1320, height: 1000 }, deviceScaleFactor: 2 })
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message))

const shot = (name) => page.screenshot({ path: `/tmp/${name}.png`, fullPage: true })
const tab = async (re) => { await page.getByRole('button', { name: re }).click(); await page.waitForTimeout(900) }

await page.goto(URL, { waitUntil: 'networkidle' })
await page.waitForSelector('.tcard', { timeout: 20000 })
await page.waitForTimeout(800)

await tab(/İş Emirleri/); await shot('n_workorders')
await tab(/Stok/);        await shot('n_stock')

// Koyu temaya geç
await page.locator('button[title="Tema değiştir"]').click()
await page.waitForTimeout(500)
await tab(/Ana Sayfa/);  await shot('n_dark_home')
await tab(/Duruşlar/);   await page.waitForTimeout(400)
const sim = page.getByRole('button', { name: 'Simüle Et' })
if (await sim.count()) { await sim.click(); await page.waitForTimeout(1200) }
await shot('n_dark_duruslar')

await browser.close()
console.log('errors:', errors.length ? errors : 'YOK')
