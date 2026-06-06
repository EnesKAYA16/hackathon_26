import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import HomeView from './components/HomeView.jsx'
import ParetoChart from './components/ParetoChart.jsx'
import WhatIfPanel from './components/WhatIfPanel.jsx'
import AlarmlarView from './components/AlarmlarView.jsx'
import WorkOrdersView from './components/WorkOrdersView.jsx'
import StockView from './components/StockView.jsx'

const TABS = [
  { id: 'home', label: 'Ana Sayfa', icon: '🏠' },
  { id: 'duruslar', label: 'Duruşlar', icon: '⏸️' },
  { id: 'workorders', label: 'İş Emirleri', icon: '📋' },
  { id: 'stock', label: 'Stok', icon: '📦' },
  { id: 'alarmlar', label: 'Alarmlar', icon: '🔔' },
]

export default function App() {
  const [machines, setMachines] = useState([])
  const [machine, setMachine] = useState('')
  const [dates, setDates] = useState([])
  const [date, setDate] = useState('')
  const [tab, setTab] = useState('home')

  const [baseline, setBaseline] = useState(null)
  const [pareto, setPareto] = useState(null)
  const [alarmDates, setAlarmDates] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [refreshedAt, setRefreshedAt] = useState('')

  // Tema (açık/koyu) — localStorage'da kalıcı
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])
  const dark = theme === 'dark'

  useEffect(() => {
    api.machines().then((ms) => {
      const enabled = ms.filter((m) => m.is_enabled)
      setMachines(enabled)
      setMachine(enabled.find((m) => m.name === 'Makine 1')?.name || enabled[0]?.name || '')
    }).catch((e) => setErr(e.message))
  }, [])

  useEffect(() => {
    if (!machine) return
    api.dates(machine).then((ds) => {
      setDates(ds)
      setDate(ds.includes('2025-11-10') ? '2025-11-10' : ds[ds.length - 1] || '')
    }).catch((e) => setErr(e.message))
    api.alerts(machine).then((res) => {
      const uniq = [...new Set(res.alerts.map((a) => a.started_on.slice(0, 10)))].sort()
      setAlarmDates(uniq)
    }).catch(() => setAlarmDates([]))
  }, [machine])

  useEffect(() => {
    if (!machine || !date) return
    setLoading(true); setErr(null)
    Promise.all([api.baseline(machine, date), api.pareto(machine, date, 5)])
      .then(([b, p]) => { setBaseline(b); setPareto(p); setRefreshedAt(new Date().toLocaleTimeString('tr-TR', { hour12: false })) })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [machine, date])

  const reasons = useMemo(() => (pareto?.items || []).map((i) => i.reason), [pareto])
  const showDatePill = tab !== 'alarmlar'

  return (
    <>
      <header className="tc-header">
        <div className="tc-logo"><span className="mark">📊</span><span className="t1">OEE</span><span className="t2">Panosu</span></div>
        <div className="tc-head-right">
          <div className="tc-search">🔍 <span>Ara…</span><span className="kbd">CTRL K</span></div>
          <span className="tc-ico">🌐 TR</span>
          <button className="tc-ico-btn" title="Tema değiştir" onClick={() => setTheme(dark ? 'light' : 'dark')}>
            {dark ? '🌙' : '☀️'}
          </button>
          <span className="tc-ico">👤 admin</span>
        </div>
      </header>

      <div className="tc-toolbar">
        <div className="field">
          <span className="ic">🏭</span>
          <select value={machine} onChange={(e) => setMachine(e.target.value)}>
            {machines.map((m) => <option key={m.unit_uid} value={m.name}>{m.name}</option>)}
          </select>
        </div>
        <div className="tc-tabs">
          {TABS.map((t) => (
            <button key={t.id} className={`tc-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
              <span>{t.icon}</span>{t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="app">
        {showDatePill && (
          <div className="center">
            <div className="datepill">
              <div className="dt">📅
                <select value={date} onChange={(e) => setDate(e.target.value)}
                        style={{ border: 'none', boxShadow: 'none', fontWeight: 700, padding: '2px 4px' }}>
                  {dates.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="rf">SON YENİLEME<br />{refreshedAt || '—'}</div>
              {loading && <span className="muted small">↻ yükleniyor…</span>}
            </div>
          </div>
        )}

        {err && <div className="err" style={{ marginBottom: 16 }}>{err}</div>}

        {tab === 'home' && <HomeView baseline={baseline} dark={dark} onGoStoppages={() => setTab('duruslar')} />}

        {tab === 'duruslar' && (
          <div className="grid cols-2">
            <ParetoChart data={pareto} dark={dark} />
            <WhatIfPanel machine={machine} date={date} reasons={reasons} />
          </div>
        )}

        {tab === 'workorders' && <WorkOrdersView machine={machine} date={date} />}
        {tab === 'stock' && <StockView machine={machine} date={date} />}
        {tab === 'alarmlar' && <AlarmlarView machine={machine} alarmDates={alarmDates} />}

        <footer className="small muted" style={{ marginTop: 28, textAlign: 'center' }}>
          OEE What-If & Kök Neden · RCA → What-If → ROI
        </footer>
      </div>
    </>
  )
}
