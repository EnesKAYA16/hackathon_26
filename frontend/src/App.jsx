import { useEffect, useMemo, useState } from 'react'
import {
  Home, Pause, ClipboardList, Package, Bell, LayoutGrid,
  Sun, Moon, Factory, Calendar, Gauge, PanelLeft,
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
import OeeTrendChart from './components/OeeTrendChart.jsx'

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
  const [date, setDate] = useState('')
  const [tab, setTab] = useState('home')

  const [baseline, setBaseline] = useState(null)
  const [pareto, setPareto] = useState(null)
  const [alarmDates, setAlarmDates] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [refreshedAt, setRefreshedAt] = useState('')

  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])
  const dark = theme === 'dark'

  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar') === '1')
  useEffect(() => { localStorage.setItem('sidebar', collapsed ? '1' : '0') }, [collapsed])

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
          <div className="side-machine" title="Makine seç">
            <Factory size={18} className="ic" />
            <select value={machine} onChange={(e) => setMachine(e.target.value)}>
              {machines.map((m) => <option key={m.unit_uid} value={m.name}>{m.name}</option>)}
            </select>
          </div>
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
          {showDatePill && (
            <div className="center">
              <div className="datepill">
                <div className="dt"><Calendar size={16} />
                  <select value={date} onChange={(e) => setDate(e.target.value)}
                          style={{ border: 'none', boxShadow: 'none', fontWeight: 700, padding: '2px 4px' }}>
                    {dates.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
                <div className="rf">SON YENİLEME<br />{refreshedAt || '—'}</div>
                {loading && <span className="muted small">yükleniyor…</span>}
              </div>
            </div>
          )}

          {err && <div className="err" style={{ marginBottom: 16 }}>{err}</div>}

          {tab === 'home' && (
            <>
              <HomeView baseline={baseline} dark={dark} onGoStoppages={() => setTab('duruslar')} />
              <div style={{ marginTop: 18 }}><OeeTrendChart machine={machine} dark={dark} /></div>
            </>
          )}
          {tab === 'duruslar' && (
            <>
              <StoppageTrendChart machine={machine} date={date} dark={dark} />
              <div className="grid cols-2" style={{ marginTop: 18 }}>
                <ParetoChart data={pareto} dark={dark} />
                <WhatIfPanel machine={machine} date={date} reasons={reasons} dark={dark} />
              </div>
            </>
          )}
          {tab === 'workorders' && <WorkOrdersView machine={machine} date={date} />}
          {tab === 'stock' && <StockView machine={machine} date={date} />}
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
