// Backend API istemcisi. Vite proxy sayesinde '/api' -> http://127.0.0.1:8000

const BASE = '/api'

async function get(path) {
  const r = await fetch(BASE + path)
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail || detail } catch {}
    throw new Error(detail)
  }
  return r.json()
}

async function post(path, body) {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail || detail } catch {}
    throw new Error(detail)
  }
  return r.json()
}

const q = encodeURIComponent

export const api = {
  machines: () => get('/machines'),
  dates: (m) => get(`/machines/${q(m)}/dates`),
  baseline: (m, d) => get(`/oee/baseline?machine=${q(m)}&date=${d}`),
  pareto: (m, d, n = 5) => get(`/oee/pareto?machine=${q(m)}&date=${d}&top_n=${n}`),
  stoppageTrend: (m, d) => get(`/oee/stoppage-trend?machine=${q(m)}&date=${d}`),
  stoppageKpis: (m, d) => get(`/oee/stoppage-kpis?machine=${q(m)}&date=${d}`),
  oeeHourlyTrend: (m, d) => get(`/oee/hourly-trend?machine=${q(m)}&date=${d}`),
  oeeTrend: (m, { start, end, days = 30 } = {}) =>
    get(`/oee/trend?machine=${q(m)}` + (start && end ? `&start=${start}&end=${end}` : `&days=${days}`)),
  counterTrend: (m, d) => get(`/oee/counter-trend?machine=${q(m)}&date=${d}`),
  whatif: (body) => post('/oee/whatif', body),
  financeDefaults: () => get('/finance/assumptions'),
  alerts: (m, d) => get(`/rca/alerts?machine=${q(m)}${d ? `&date=${d}` : ''}`),
  alertPareto: (m, n = 10) => get(`/rca/alert-pareto?machine=${q(m)}&top_n=${n}`),
  rootCause: (m, d, w) => get(`/rca/root-cause?machine=${q(m)}&date=${d}${w ? `&window_min=${w}` : ''}`),
  analyzeRootCause: (m, d) => post(`/rca/analyze?machine=${q(m)}&date=${d}`, {}),
  workorders: (m, d) => get(`/workorders?machine=${q(m)}&date=${d}`),
  stock: (m, start, end) => get(`/stock?machine=${q(m)}&start=${start}${end ? `&end=${end}` : ''}`),
  deviation: (m, center, signal) => get(`/rca/deviation?machine=${q(m)}&center=${q(center)}${signal ? `&signal=${q(signal)}` : ''}`),
  fleetDashboard: (d) => get(`/fleet/dashboard?date=${d}`),
  fleetRanking: (start, end, n = 3) => get(`/fleet/ranking?start=${start}&end=${end}&top_n=${n}`),
  fleetAlarmPatterns: () => get('/fleet/alarm-patterns'),
}

// Yardımcılar
export const fmtHM = (ms) => {
  const min = Math.round(ms / 60000)
  return `${Math.floor(min / 60)}s ${min % 60}d`
}
export const pct = (x) => `${(x * 100).toFixed(2)}%`

// Tarih/saat: dataset UTC -> AYNI saat (yerel +3 kayması YOK) + Türkiye formatı DD.MM.YYYY
export const fmtDate = (s) => {
  if (!s) return '—'
  const d = new Date(s.length <= 10 ? `${s}T00:00:00Z` : s)
  return d.toLocaleDateString('tr-TR', { timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric' })
}
export const fmtTime = (iso) =>
  iso ? new Date(iso).toLocaleTimeString('tr-TR', { timeZone: 'UTC', hour12: false }) : ''
export const fmtDateTime = (iso) => (iso ? `${fmtDate(iso)} ${fmtTime(iso)}` : '—')

// Çevrim/kısa süreler için saniye hassasiyetli format (örn. 8sn, 1d 30sn, 1s 3d).
export const fmtCycle = (ms) => {
  if (ms == null) return '—'
  const s = Math.round(ms / 1000)
  if (s >= 3600) return `${Math.floor(s / 3600)}s ${Math.round((s % 3600) / 60)}d`
  if (s >= 60) return `${Math.floor(s / 60)}d ${s % 60}sn`
  return `${s}sn`
}
