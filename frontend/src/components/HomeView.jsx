import Card from './Card.jsx'
import Gauge from './Gauge.jsx'
import Donut from './Donut.jsx'
import { fmtHM, pct } from '../api.js'

function Metric({ name, v }) {
  return (
    <div className="metric3">
      <div className="nm">{name}</div>
      <div className="pc">{Math.round(v * 100)}%</div>
      <div className="pb"><span style={{ width: `${Math.min(v * 100, 100)}%` }} /></div>
    </div>
  )
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
        <div className="center"><Gauge value={a.A} label="Kullanılabilirlik" /></div>
        <div className="three">
          <Metric name="OEE" v={baseline.oee} />
          <Metric name="Performans" v={baseline.performance.P} />
          <Metric name="Kalite" v={baseline.quality.Q} />
        </div>
        <div className="kv" style={{ marginTop: 16 }}>
          <span className="k">● OEE Dahil · Üretilen parça</span>
          <span className="v">{baseline.quality.product_sum} Ad</span>
        </div>
      </Card>

      <Card title="Makine Kullanılabilirliği"
            action={<span className="link" onClick={onGoStoppages}>Duruşlar →</span>}>
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

        <div className="section-sub">🕐 Zaman Dağılımı</div>
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
