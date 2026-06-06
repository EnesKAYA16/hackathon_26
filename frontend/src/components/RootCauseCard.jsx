import { useEffect, useState } from 'react'
import { api, fmtHM } from '../api.js'

const time = (iso) => (iso ? new Date(iso).toLocaleTimeString('tr-TR', { hour12: false }) : '')
const day = (iso) => (iso ? iso.slice(0, 10) : '')

export default function RootCauseCard({ machine, alarmDates }) {
  const [date, setDate] = useState('')
  const [card, setCard] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  // Alarm günleri gelince ilkini seç
  useEffect(() => { if (alarmDates?.length) setDate((d) => d || alarmDates[0]) }, [alarmDates])

  useEffect(() => {
    if (!machine || !date) return
    setLoading(true); setErr(null); setCard(null)
    api.rootCause(machine, date)
      .then(setCard).catch((e) => setErr(e.message)).finally(() => setLoading(false))
  }, [machine, date])

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ margin: 0 }}>Kök Neden Kartı (RCA)</h3>
        <div>
          <label>Alarm günü</label>
          <select value={date} onChange={(e) => setDate(e.target.value)}>
            {(alarmDates || []).map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
      </div>

      {loading && <div className="spin">Telemetri sorgulanıyor…</div>}
      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}

      {card && !card.has_alarm && (
        <div className="muted small" style={{ marginTop: 12 }}>{card.summary}</div>
      )}

      {card && card.has_alarm && (
        <>
          <div style={{ margin: '12px 0' }}>
            {card.run_stopped_at_alarm
              ? <span className="badge bad">Telemetri doğruladı: makine durdu</span>
              : <span className="badge warn">Telemetri: net duruş kanıtı yok</span>}
          </div>
          <p style={{ marginTop: 0 }}>{card.summary}</p>

          <div className="section-title">Alarmlar (tekrar sayısı + öneri)</div>
          {card.alarms.map((a, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <b>{a.message}</b>
                <span className="badge warn">×{a.recurrence_total} kez</span>
              </div>
              <div className="recommend">💡 {a.recommendation}</div>
            </div>
          ))}

          <div className="section-title">Olay Çizelgesi (±{card.timeline.window_min} dk)</div>
          <Timeline tl={card.timeline} />

          {card.downtime_context && (
            <>
              <div className="section-title">Downtime Köprüsü → What-If/ROI</div>
              <div className="kv"><span className="k">Vardiya günü</span><span className="v">{card.downtime_context.shift_date}</span></div>
              <div className="kv"><span className="k">Toplam plansız duruş</span><span className="v" style={{ color: 'var(--bad)' }}>{card.downtime_context.total_unplanned_h.toFixed(1)} saat</span></div>
              <div className="small muted" style={{ marginTop: 6 }}>{card.downtime_context.note}</div>
            </>
          )}
        </>
      )}
    </div>
  )
}

function Timeline({ tl }) {
  const rows = []
  tl.alerts.forEach((a) => rows.push({ t: a.time, type: '🚨 Alarm', detail: a.message }))
  tl.telemetry.forEach((x) => rows.push({ t: x.time, type: '📈 Telemetri', detail: `${x.signal} = ${x.value}` }))
  tl.stoppages.forEach((s) => rows.push({
    t: s.started_on, type: s.is_planned ? '⏸ Planlı duruş' : '⛔ Plansız duruş',
    detail: `${s.reason} (${fmtHM(s.duration_ms)})`,
  }))
  rows.sort((a, b) => new Date(a.t) - new Date(b.t))

  if (!rows.length) return <div className="muted small">Pencerede olay yok.</div>
  return (
    <table className="tl">
      <thead><tr><th>Saat</th><th>Tür</th><th>Detay</th></tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}><td className="t">{time(r.t)}</td><td>{r.type}</td><td>{r.detail}</td></tr>
        ))}
      </tbody>
    </table>
  )
}
