import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import BaselineCard from './components/BaselineCard.jsx'
import ParetoChart from './components/ParetoChart.jsx'
import WhatIfPanel from './components/WhatIfPanel.jsx'
import RootCauseCard from './components/RootCauseCard.jsx'

export default function App() {
  const [machines, setMachines] = useState([])
  const [machine, setMachine] = useState('')
  const [dates, setDates] = useState([])
  const [date, setDate] = useState('')

  const [baseline, setBaseline] = useState(null)
  const [pareto, setPareto] = useState(null)
  const [alarmDates, setAlarmDates] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  // 1) Makineleri yükle (yalnızca etkin olanlar), varsayılan Makine 1
  useEffect(() => {
    api.machines().then((ms) => {
      const enabled = ms.filter((m) => m.is_enabled)
      setMachines(enabled)
      setMachine(enabled.find((m) => m.name === 'Makine 1')?.name || enabled[0]?.name || '')
    }).catch((e) => setErr(e.message))
  }, [])

  // 2) Makine değişince: günler + alarm günleri
  useEffect(() => {
    if (!machine) return
    api.dates(machine).then((ds) => {
      setDates(ds)
      // Yüksek duruşlu örnek gün varsa onu seç, yoksa sonuncuyu
      setDate(ds.includes('2025-11-10') ? '2025-11-10' : ds[ds.length - 1] || '')
    }).catch((e) => setErr(e.message))

    api.alerts(machine).then((res) => {
      const uniq = [...new Set(res.alerts.map((a) => a.started_on.slice(0, 10)))].sort()
      setAlarmDates(uniq)
    }).catch(() => setAlarmDates([]))
  }, [machine])

  // 3) Makine+gün değişince: baz OEE + Pareto
  useEffect(() => {
    if (!machine || !date) return
    setLoading(true); setErr(null)
    Promise.all([api.baseline(machine, date), api.pareto(machine, date, 5)])
      .then(([b, p]) => { setBaseline(b); setPareto(p) })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [machine, date])

  const reasons = useMemo(() => (pareto?.items || []).map((i) => i.reason), [pareto])

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>⚙️ OEE What-If & Kök Neden Panosu</h1>
          <div className="sub">Endüstriyel üretim verimliliği · trexCloud verisi</div>
        </div>
        <div className="controls">
          <div>
            <label>Makine</label>
            <select value={machine} onChange={(e) => setMachine(e.target.value)}>
              {machines.map((m) => <option key={m.unit_uid} value={m.name}>{m.name}</option>)}
            </select>
          </div>
        </div>
      </header>

      {err && <div className="err">{err}</div>}

      {/* ---- OEE & WHAT-IF ---- */}
      <div className="section-title">OEE Bazı & What-If (vardiya günü)</div>
      <div className="controls" style={{ marginBottom: 14 }}>
        <div>
          <label>Vardiya günü</label>
          <select value={date} onChange={(e) => setDate(e.target.value)}>
            {dates.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        {loading && <span className="spin">Yükleniyor…</span>}
      </div>

      <div className="grid cols-2">
        <BaselineCard data={baseline} />
        <WhatIfPanel machine={machine} date={date} reasons={reasons} />
      </div>
      <div style={{ marginTop: 16 }}>
        <ParetoChart data={pareto} />
      </div>

      {/* ---- RCA ---- */}
      <div className="section-title">Kök Neden Analizi (alarm günü)</div>
      <RootCauseCard machine={machine} alarmDates={alarmDates} />

      <footer className="small muted" style={{ marginTop: 28, textAlign: 'center' }}>
        Backend: FastAPI · /api → :8000 · RCA → What-If → ROI
      </footer>
    </div>
  )
}
