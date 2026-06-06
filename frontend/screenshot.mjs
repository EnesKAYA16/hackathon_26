// Faz 5 + UI: lucide ikonlar, glassmorphism, What-If kaldıraçları/şelale, hipotez/sapma, filo.
import { chromium } from 'playwright'
const URL = process.env.URL || 'http://127.0.0.1:5173'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1320, height: 1000 }, deviceScaleFactor: 2 })
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message))
const shot = (n) => page.screenshot({ path: `/tmp/${n}.png`, fullPage: true })
const tab = async (re) => { await page.getByRole('button', { name: re }).click(); await page.waitForTimeout(900) }

await page.goto(URL, { waitUntil: 'networkidle' })
await page.waitForSelector('.tcard', { timeout: 20000 })
await page.waitForTimeout(900)
await shot('p5_home')

// Glass efekti: kaydır, sticky header'ın altından içerik geçsin (viewport shot)
await page.evaluate(() => window.scrollTo(0, 230))
await page.waitForTimeout(400)
await page.screenshot({ path: '/tmp/p5_glass.png' })
await page.evaluate(() => window.scrollTo(0, 0))

// Duruşlar: P+Q kaldıraçlarını ayarla, simüle et -> şelale 3 bileşenli
await tab(/Duruşlar/)
const ranges = page.locator('.tcard input[type="range"]')
if (await ranges.count() >= 3) {
  await ranges.nth(1).fill('15') // çevrim %15
  await ranges.nth(2).fill('3')  // fire %3
}
const sim = page.getByRole('button', { name: /Simüle Et/ })
if (await sim.count()) { await sim.click(); await page.waitForTimeout(1300) }
await shot('p5_duruslar')

await tab(/Alarmlar/); await page.waitForTimeout(3200); await shot('p5_alarmlar')
await tab(/Filo/);     await page.waitForTimeout(1200); await shot('p5_fleet')

// Koyu tema
await page.locator('button[title="Tema değiştir"]').click()
await page.waitForTimeout(400)
await tab(/Ana Sayfa/); await shot('p5_dark_home')

await browser.close()
console.log('errors:', errors.length ? errors : 'YOK')
