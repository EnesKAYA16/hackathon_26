import { pct, fmtHM } from '../api.js'

function color(v) {
  if (v >= 0.6) return 'var(--good)'
  if (v >= 0.3) return 'var(--warn)'
  return 'var(--bad)'
}

function Metric({ name, value }) {
  return (
    <div className="metric">
      <div className="row">
        <span className="name">{name}</span>
        <span className="val">{pct(value)}</span>
      </div>
      <div className="bar">
        <span style={{ width: `${Math.min(value * 100, 100)}%`, background: color(value) }} />
      </div>
    </div>
  )
}

export default function BaselineCard({ data }) {
  if (!data) return null
  const a = data.availability, p = data.performance, q = data.quality
  return (
    <div className="card">
      <h3>Baz OEE (A × P × Q)</h3>
      <div className="bigoee">
        <div className="num" style={{ color: color(data.oee) }}>{pct(data.oee)}</div>
        <div className="lbl">OEE · {data.machine} · {data.date}</div>
      </div>
      <Metric name="Availability (A)" value={a.A} />
      <Metric name="Performance (P)" value={p.P} />
      <Metric name="Quality (Q)" value={q.Q} />
      <div style={{ marginTop: 12 }}>
        <div className="kv"><span className="k">Çalışma (WorkTotal)</span><span className="v">{fmtHM(a.work_total_ms)}</span></div>
        <div className="kv"><span className="k">Planlı duruş</span><span className="v">{fmtHM(a.planned_stop_ms)}</span></div>
        <div className="kv"><span className="k">Plansız duruş</span><span className="v" style={{ color: 'var(--bad)' }}>{fmtHM(a.unplanned_stop_ms)}</span></div>
        <div className="kv"><span className="k">Üretilen parça</span><span className="v">{q.product_sum}</span></div>
      </div>
      <div className="small muted" style={{ marginTop: 8 }}>
        Doğrulama Δ: {data.validation_delta.toExponential(1)} (trexCloud ile birebir)
      </div>
    </div>
  )
}
