// PDF dışa aktarma — ekrandaki AKTİF görünümü kurumsal PDF rapora çevirir.
// Grafikler recharts SVG'sinden 3x yüksek çözünürlüklü PNG'ye rasterize edilir
// (html2canvas KULLANILMAZ -> glassmorphism/modern CSS bozulmaz); KPI/tablo metni
// DOM'dan toplanır; hepsi backend /report/pdf'e yollanıp PDF olarak indirilir.

const BASE = '/api'

// --- recharts <svg> -> yüksek çözünürlüklü PNG data URL ---
async function svgToPng(svgEl, scale = 3) {
  const rect = svgEl.getBoundingClientRect()
  const w = Math.max(1, Math.ceil(rect.width))
  const h = Math.max(1, Math.ceil(rect.height))
  const clone = svgEl.cloneNode(true)
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  clone.setAttribute('width', w)
  clone.setAttribute('height', h)
  // Standalone render'da fontu garanti et (yoksa serif'e düşer).
  const style = document.createElementNS('http://www.w3.org/2000/svg', 'style')
  style.textContent =
    "text{font-family:Inter,-apple-system,'Segoe UI',Arial,sans-serif}"
  clone.insertBefore(style, clone.firstChild)

  const xml = new XMLSerializer().serializeToString(clone)
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml)
  const img = new Image()
  await new Promise((res, rej) => {
    img.onload = res
    img.onerror = rej
    img.src = url
  })
  const canvas = document.createElement('canvas')
  canvas.width = w * scale
  canvas.height = h * scale
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.scale(scale, scale)
  ctx.drawImage(img, 0, 0, w, h)
  return canvas.toDataURL('image/png')
}

const txt = (el) => (el ? el.innerText.replace(/\s+/g, ' ').trim() : '')

// Kart başlığı — aksiyon (link/durum) metni hariç sadece ilk span.
const cardTitle = (el, fallback) => {
  const head = el.closest('.tcard')?.querySelector('.tcard-head')
  return (head && (txt(head.querySelector('span')) || txt(head))) || fallback
}

// --- Aktif görünümün DOM'undan KPI / grafik / tablo toplar ---
async function collectFromDom(root) {
  // 1) KPI kartları (görünümlere göre farklı işaretleme)
  const kpis = []
  const seen = new Set()
  const push = (label, value, sub) => {
    if (!label || !value) return
    const key = label.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    kpis.push(sub ? { label, value, sub } : { label, value })
  }
  root.querySelectorAll('.kpi').forEach((el) =>
    push(txt(el.querySelector('.kpi-label')), txt(el.querySelector('.kpi-val')),
      txt(el.querySelector('.kpi-sub'))))
  root.querySelectorAll('.wf-kpi').forEach((el) =>
    push(txt(el.querySelector('.wf-kpi-l')), txt(el.querySelector('.wf-kpi-v')),
      txt(el.querySelector('.wf-kpi-s'))))
  root.querySelectorAll('.hbar-top').forEach((el) =>
    push(txt(el.querySelector('span')), txt(el.querySelector('b'))))
  root.querySelectorAll('.vbar').forEach((el) =>
    push(txt(el.querySelector('.vbar-name')), txt(el.querySelector('.vbar-pct'))))
  root.querySelectorAll('.chip').forEach((el) =>
    push(txt(el.querySelector('.cl')), txt(el.querySelector('.cv'))))

  // 2) Grafikler (recharts SVG) — başlık en yakın kart başlığından
  const charts = []
  const svgs = root.querySelectorAll('svg.recharts-surface')
  for (const svg of svgs) {
    const rect = svg.getBoundingClientRect()
    if (rect.width < 40 || rect.height < 40) continue // gizli/çok küçük olanları atla
    const title = cardTitle(svg, 'Grafik')
    try {
      charts.push({ title, image: await svgToPng(svg, 3) })
    } catch { /* tek grafik başarısızsa raporu bozma */ }
  }

  // 3) Tablolar
  const tables = []
  root.querySelectorAll('table.atable').forEach((t) => {
    const title = cardTitle(t, 'Tablo')
    const columns = [...t.querySelectorAll('thead th')].map((th) => txt(th))
    const rows = [...t.querySelectorAll('tbody tr')]
      .map((tr) => [...tr.querySelectorAll('td')].map((td) => txt(td)))
      .filter((r) => r.length === columns.length) // "colSpan" boş satırlarını atla
    if (columns.length) tables.push({ title, columns, rows })
  })

  return { kpis, charts, tables }
}

// --- Ana giriş: topla + backend'e yolla + indir ---
export async function exportToPdf({ pageTitle, machine, dateLabel, rootSelector = '.content' }) {
  const root = document.querySelector(rootSelector)
  if (!root) throw new Error('İçerik bulunamadı')
  const collected = await collectFromDom(root)
  const payload = { page_title: pageTitle, machine, date_label: dateLabel, ...collected }

  const r = await fetch(BASE + '/report/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail || detail } catch { /* boş */ }
    throw new Error(detail)
  }
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const stamp = new Date().toISOString().slice(0, 10)
  a.download = `OEE_${(pageTitle || 'rapor').replace(/\s+/g, '_')}_${stamp}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
