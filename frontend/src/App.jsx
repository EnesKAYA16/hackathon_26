import { useEffect, useMemo, useState } from 'react'
import {
  Home, Pause, ClipboardList, Package, Bell, LayoutGrid,
  Sun, Moon, Factory, Gauge, PanelLeft,
} from 'lucide-react'
import { api } from './api.js'
import HomeView from './components/HomeView.jsx'
import ParetoChart from './components/ParetoChart.jsx'
import WhatIfPanel from './components/WhatIfPanel.jsx'
import AlarmlarView from './components/AlarmlarView.jsx'
import WorkOrdersView from './components/WorkOrdersView.jsx'
import StockView from './components/StockView.jsx'
import FleetView from './components/FleetView.jsx'
import StoppageTrendChart from './components/StoppageTrendChart.jsx'
import StoppageKpiCards from './components/StoppageKpiCards.jsx'
import OeeTrendChart from './components/OeeTrendChart.jsx'
import DateRangePicker from './components/DateRangePicker.jsx'

const TABS = [
  { id: 'home', label: 'Ana Sayfa', Icon: Home },
  { id: 'duruslar', label: 'Duruşlar', Icon: Pause },
  { id: 'workorders', label: 'İş Emirleri', Icon: ClipboardList },
  { id: 'stock', label: 'Stok', Icon: Package },
  { id: 'alarmlar', label: 'Alarmlar', Icon: Bell },
  { id: 'fleet', label: 'Filo', Icon: LayoutGrid },
]

export default function App() {
  const [machines, setMachines] = useState([])
  const [machine, setMachine] = useState('')
  const [dates, setDates] = useState([])
  const [range, setRange] = useState({ start: '', end: '' })  // ana sayfa OEE trendi için
  const [date, setDate] = useState('')                         // Duruşlar/İş Emirleri: tek aktif gün
  const [stockRange, setStockRange] = useState({ start: '', end: '' })  // Stok: tarih aralığı
  const [tab, setTab] = useState('home')

  const [baseline, setBaseline] = useState(null)
  const [pareto, setPareto] = useState(null)
  const [alarmDates, setAlarmDates] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])
  const dark = theme === 'dark'

  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar') === '1')
  useEffect(() => { localStorage.setItem('sidebar', collapsed ? '1' : '0') }, [collapsed])

  // Bir sınıra göre <= olan en son VERİ gününü çözer (verisiz uca denk gelirse bozulmasın)
  const resolveDay = (bound) => {
    if (!dates.length || !bound) return bound
    const within = dates.filter((d) => d <= bound)
    return within.length ? within[within.length - 1] : dates[0]
  }

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
      const end = ds.includes('2025-11-10') ? '2025-11-10' : ds[ds.length - 1] || ''
      const endIdx = ds.indexOf(end)
      const start = ds[Math.max(0, endIdx - 29)] || end
      setRange({ start, end })
      setDate(end)
      // Stok: varsayılan 2 günlük aralık (gün + sonraki gün) — boş bitiş gösterilmez
      setStockRange({ start: end, end: ds[Math.min(ds.length - 1, endIdx + 1)] || end })
    }).catch((e) => setErr(e.message))
    api.alerts(machine).then((res) => {
      const uniq = [...new Set(res.alerts.map((a) => a.started_on.slice(0, 10)))].sort()
      setAlarmDates(uniq)
    }).catch(() => setAlarmDates([]))
  }, [machine])

  useEffect(() => {
    if (!machine || !date) return
    setLoading(true); setErr(null)
    Promise.all([api.baseline(machine, date), api.pareto(machine, date, 6)])
      .then(([b, p]) => { setBaseline(b); setPareto(p) })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [machine, date])

  const reasons = useMemo(() => (pareto?.items || []).map((i) => i.reason), [pareto])

  return (
    <div className={`shell ${collapsed ? 'collapsed' : ''}`}>
      <header className="tc-header">
        <button className="tc-ico-btn" title="Menüyü aç/kapat" onClick={() => setCollapsed((c) => !c)}>
          <PanelLeft size={18} />
        </button>
        <div className="tc-logo"><Gauge className="mark" size={24} /><span className="t1">OEE</span><span className="t2">Panosu</span></div>
        <div style={{ flex: 1 }} />
        <button className="tc-ico-btn" title="Tema değiştir" onClick={() => setTheme(dark ? 'light' : 'dark')}>
          {dark ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </header>

      <div className="body">
        <aside className="sidebar">
          <nav className="side-nav">
            {TABS.map((t) => (
              <button key={t.id} title={t.label}
                      className={`side-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
                <t.Icon size={18} /><span className="side-label">{t.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        <main className="content">
          {/* Ortalanmış: makine seçici + tarih aralığı takvimi */}
          <div className="topcenter">
            <div className="field">
              <Factory size={17} className="ic" />
              <select value={machine} onChange={(e) => setMachine(e.target.value)}>
                {machines.map((m) => <option key={m.unit_uid} value={m.name}>{m.name}</option>)}
              </select>
            </div>
            {tab === 'home' ? (
              <DateRangePicker availableDates={dates} start={range.start} end={range.end}
                onChange={(r) => { setRange(r); setDate(resolveDay(r.end || r.start)) }} />
            ) : tab === 'stock' ? (
              <DateRangePicker availableDates={dates} start={stockRange.start} end={stockRange.end}
                onChange={(r) => setStockRange({ start: r.start, end: r.end || r.start })} />
            ) : tab !== 'alarmlar' ? (
              <DateRangePicker single availableDates={dates} start={date} end={date}
                onChange={(r) => setDate(r.end)} />
            ) : null}
            {loading && <span className="muted small">yükleniyor…</span>}
          </div>

          {err && <div className="err" style={{ marginBottom: 16 }}>{err}</div>}

          {tab === 'home' && (
            <>
              <HomeView baseline={baseline} dark={dark} onGoStoppages={() => setTab('duruslar')} />
              <div style={{ marginTop: 18 }}>
                <OeeTrendChart machine={machine} start={range.start} end={range.end} dark={dark} />
              </div>
            </>
          )}
          {tab === 'duruslar' && (
            <>
              <StoppageKpiCards machine={machine} date={date} />
              <div style={{ marginTop: 18 }}>
                <StoppageTrendChart machine={machine} date={date} dark={dark} />
              </div>
              <div className="grid cols-2" style={{ marginTop: 18 }}>
                <ParetoChart data={pareto} dark={dark} />
                <WhatIfPanel machine={machine} date={date} reasons={reasons} dark={dark} />
              </div>
            </>
          )}
          {tab === 'workorders' && <WorkOrdersView machine={machine} date={date} />}
          {tab === 'stock' && <StockView machine={machine} start={stockRange.start} end={stockRange.end} dark={dark} />}
          {tab === 'alarmlar' && <AlarmlarView machine={machine} alarmDates={alarmDates} />}
          {tab === 'fleet' && <FleetView date={date} />}

          <footer className="small muted" style={{ marginTop: 28, textAlign: 'center' }}>
            OEE What-If & Kök Neden · RCA → What-If → ROI
          </footer>
        </main>
      </div>
    </div>
  )
}
