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
  oeeTrend: (m, days = 30) => get(`/oee/trend?machine=${q(m)}&days=${days}`),
  whatif: (body) => post('/oee/whatif', body),
  financeDefaults: () => get('/finance/assumptions'),
  alerts: (m, d) => get(`/rca/alerts?machine=${q(m)}${d ? `&date=${d}` : ''}`),
  alertPareto: (m, n = 10) => get(`/rca/alert-pareto?machine=${q(m)}&top_n=${n}`),
  rootCause: (m, d, w) => get(`/rca/root-cause?machine=${q(m)}&date=${d}${w ? `&window_min=${w}` : ''}`),
  workorders: (m, d) => get(`/workorders?machine=${q(m)}&date=${d}`),
  stock: (m, d) => get(`/stock?machine=${q(m)}&date=${d}`),
  deviation: (m, center, signal) => get(`/rca/deviation?machine=${q(m)}&center=${q(center)}${signal ? `&signal=${q(signal)}` : ''}`),
  fleetOverview: (d) => get(`/fleet/overview?date=${d}`),
  fleetAlarmPatterns: () => get('/fleet/alarm-patterns'),
}

// Yardımcılar
export const fmtHM = (ms) => {
  const min = Math.round(ms / 60000)
  return `${Math.floor(min / 60)}s ${min % 60}d`
}
export const pct = (x) => `${(x * 100).toFixed(2)}%`
