// Sol sidebar (aç/kapa), header sadeleştirme, trend grafikleri.
import { chromium } from 'playwright'
const URL = process.env.URL || 'http://127.0.0.1:5173'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1340, height: 1000 }, deviceScaleFactor: 2 })
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message))
const shot = (n, full = true) => page.screenshot({ path: `/tmp/${n}.png`, fullPage: full })
const tab = async (re) => { await page.getByRole('button', { name: re }).click(); await page.waitForTimeout(1000) }
const collapse = () => page.locator('button[title="Menüyü aç/kapat"]').click()

await page.goto(URL, { waitUntil: 'networkidle' })
await page.waitForSelector('.tcard', { timeout: 20000 })
await page.waitForTimeout(1200)
await shot('l_home')                 // sidebar açık + Ana Sayfa + OEE trendi

await collapse(); await page.waitForTimeout(500)
await shot('l_collapsed', false)      // daraltılmış sidebar (viewport)
await collapse(); await page.waitForTimeout(400) // tekrar aç

await tab(/Duruşlar/); await page.waitForTimeout(700)
await shot('l_duruslar')             // duruş zaman serisi + pareto + what-if

await page.locator('button[title="Tema değiştir"]').click()
await page.waitForTimeout(400)
await tab(/Ana Sayfa/)
await shot('l_dark')

await browser.close()
console.log('errors:', errors.length ? errors : 'YOK')
