import { useEffect, useState } from 'react'
import { Clock, ArrowRight, Trophy } from 'lucide-react'
import Card from './Card.jsx'
import Donut from './Donut.jsx'
import { api, fmtHM, pct } from '../api.js'

function color(v) {
  if (v >= 0.6) return 'var(--green)'
  if (v >= 0.3) return 'var(--amber)'
  return 'var(--red)'
}

function Chip({ tone, label, value }) {
  return (
    <div className={`chip ${tone}`}>
      <div className="cl"><span className="dot" />{label}</div>
      <div className="cv">{value}</div>
    </div>
  )
}

function TdRow({ color, name, p, v }) {
  return (
    <div className="tdrow">
      <span className="dot" style={{ background: color }} />
      <span className="nm">{name}</span>
      <span className="vv">{v}</span>
      <span className="pp">{p}</span>
    </div>
  )
}

// Üstte yatay Kullanılabilirlik, altta OEE/Performans/Kalite dikey sütunlar.
function OeeBars({ A, oee, P, Q }) {
  const cols = [
    { name: 'OEE', v: oee, c: 'var(--accent)' },
    { name: 'Performans', v: P, c: '#8b5cf6' },
    { name: 'Kalite', v: Q, c: 'var(--green)' },
  ]
  return (
    <div>
      <div className="hbar-top"><span>Kullanılabilirlik (A)</span><b>{pct(A)}</b></div>
      <div className="hbar"><span style={{ width: `${Math.min(A * 100, 100)}%`, background: color(A) }} /></div>
      <div className="vbars">
        {cols.map((c) => (
          <div className="vbar" key={c.name}>
            <div className="vbar-pct">{Math.round(c.v * 100)}%</div>
            <div className="vbar-track"><div className="vbar-fill" style={{ height: `${Math.min(c.v * 100, 100)}%`, background: c.c }} /></div>
            <div className="vbar-name">{c.name}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Top3({ date }) {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    if (!date) return
    api.fleetOverview(date)
      .then((f) => setRows([...f.machines].sort((a, b) => b.oee - a.oee).slice(0, 3)))
      .catch(() => setRows([]))
  }, [date])
  if (!rows || !rows.length) return null
  const medal = ['#e0a72b', '#9aa7b4', '#cd7f43']
  return (
    <div className="top3">
      <div className="top3-head"><Trophy size={15} /> En İyi 3 Makine ({date})</div>
      {rows.map((m, i) => (
        <div className="top3-row" key={m.unit_uid}>
          <span className="top3-rk" style={{ background: medal[i] }}>{i + 1}</span>
          <span className="top3-nm">{m.machine}</span>
          <span className="top3-oee" style={{ color: color(m.oee) }}>{pct(m.oee)}</span>
        </div>
      ))}
    </div>
  )
}

export default function HomeView({ baseline, onGoStoppages, dark }) {
  if (!baseline) return <div className="spin">Yükleniyor…</div>
  const a = baseline.availability
  const wt = a.work_total_ms, ps = a.planned_stop_ms, us = a.unplanned_stop_ms, rt = a.run_time_ms
  const p = (x) => (wt > 0 ? `${(x / wt * 100).toFixed(1)}%` : '0%')
  const segs = [
    { name: 'Net Çalışma', value: rt, color: '#25b06b' },
    { name: 'Planlı Duruş', value: ps, color: '#f0a52b' },
    { name: 'Plansız Duruş', value: us, color: '#e2483d' },
  ]

  return (
    <div className="grid cols-2">
      <Card title="Makine OEE">
        <OeeBars A={a.A} oee={baseline.oee} P={baseline.performance.P} Q={baseline.quality.Q} />
        <Top3 date={baseline.date} />
      </Card>

      <Card title="Makine Kullanılabilirliği"
            action={<span className="link" onClick={onGoStoppages} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>Duruşlar <ArrowRight size={13} /></span>}>
        <div className="avail-row">
          <div className="chips">
            <Chip tone="blue" label="Çalışma Süresi" value={fmtHM(wt)} />
            <Chip tone="amber" label="Toplam Duruş" value={fmtHM(ps + us)} />
            <Chip tone="green" label="Net Çalışma Süresi" value={fmtHM(rt)} />
          </div>
          <Donut segments={segs} centerValue={p(rt)} centerLabel="Net Çalışma Süresi" dark={dark} />
          <div className="chips">
            <Chip tone="amber" label="Planlı Duruş" value={fmtHM(ps)} />
            <Chip tone="red" label="Plansız Duruş" value={fmtHM(us)} />
          </div>
        </div>

        <div className="section-sub"><Clock size={15} /> Zaman Dağılımı</div>
        <div className="timedist">
          <span style={{ width: p(rt), background: '#25b06b' }} />
          <span style={{ width: p(ps), background: '#f0a52b' }} />
          <span style={{ width: p(us), background: '#e2483d' }} />
        </div>
        <div className="tdlegend">
          <TdRow color="#25b06b" name="Net Çalışma Süresi" p={p(rt)} v={fmtHM(rt)} />
          <TdRow color="#f0a52b" name="Planlı Duruş" p={p(ps)} v={fmtHM(ps)} />
          <TdRow color="#e2483d" name="Plansız Duruş" p={p(us)} v={fmtHM(us)} />
        </div>
      </Card>
    </div>
  )
}
