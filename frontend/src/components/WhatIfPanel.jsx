import { useEffect, useState } from 'react'
import { api, pct, fmtHM } from '../api.js'
import Card from './Card.jsx'

export default function WhatIfPanel({ machine, date, reasons }) {
  const [reason, setReason] = useState('')
  const [reduction, setReduction] = useState(20) // %
  const [fin, setFin] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  // Varsayılan finansal varsayımları yükle
  useEffect(() => { api.financeDefaults().then(setFin).catch(() => {}) }, [])
  // Pareto nedenleri değişince ilk nedeni seç
  useEffect(() => { if (reasons?.length) setReason(reasons[0]) }, [reasons])
  // Girdi değişince eski sonucu temizle
  useEffect(() => { setResult(null); setErr(null) }, [machine, date, reason, reduction])

  const setFinField = (k, v) => setFin((f) => ({ ...f, [k]: v === '' ? null : Number(v) }))

  async function simulate() {
    setLoading(true); setErr(null)
    try {
      const body = {
        machine, date, durus_nedeni: reason, azaltma_yuzdesi: reduction / 100,
        finance: fin,
      }
      setResult(await api.whatif(body))
    } catch (e) { setErr(e.message) } finally { setLoading(false) }
  }

  if (!reasons?.length) return (
    <Card title="What-If Simülasyonu">
      <div className="muted small">Bu gün için plansız duruş nedeni yok.</div>
    </Card>
  )

  return (
    <Card title="What-If Simülasyonu">
      <div style={{ marginBottom: 10 }}>
        <label>Duruş nedeni</label>
        <select value={reason} onChange={(e) => setReason(e.target.value)} style={{ width: '100%' }}>
          {reasons.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      <div style={{ marginBottom: 10 }}>
        <label>Azaltma: <b>%{reduction}</b></label>
        <div className="slider-row">
          <input type="range" min="0" max="100" value={reduction}
                 onChange={(e) => setReduction(Number(e.target.value))} />
        </div>
      </div>

      <details>
        <summary>Finansal varsayımlar (₺)</summary>
        {fin && (
          <div className="fin-inputs">
            <div><label>Parça başı marj</label>
              <input type="number" value={fin.contribution_margin_per_piece}
                     onChange={(e) => setFinField('contribution_margin_per_piece', e.target.value)} /></div>
            <div><label>Saatlik duruş maliyeti</label>
              <input type="number" value={fin.downtime_cost_per_hour}
                     onChange={(e) => setFinField('downtime_cost_per_hour', e.target.value)} /></div>
            <div><label>Müdahale maliyeti</label>
              <input type="number" value={fin.intervention_cost}
                     onChange={(e) => setFinField('intervention_cost', e.target.value)} /></div>
            <div><label>Parça/saat (override)</label>
              <input type="number" placeholder="otomatik tahmin"
                     value={fin.pieces_per_hour_override ?? ''}
                     onChange={(e) => setFinField('pieces_per_hour_override', e.target.value)} /></div>
            <div><label>ROI ufku (gün)</label>
              <input type="number" value={fin.horizon_days}
                     onChange={(e) => setFinField('horizon_days', e.target.value)} /></div>
          </div>
        )}
      </details>

      <button style={{ marginTop: 12, width: '100%' }} onClick={simulate} disabled={loading}>
        {loading ? 'Hesaplanıyor…' : 'Simüle Et'}
      </button>

      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
      {result && <Result r={result} />}
    </Card>
  )
}

function Result({ r }) {
  const f = r.financial
  const up = r.delta.oee_pp >= 0
  return (
    <div style={{ marginTop: 14 }}>
      <div className="grid cols-2">
        <Stat label="OEE (önce → sonra)"
              value={`${pct(r.before.oee)} → ${pct(r.after.oee)}`}
              delta={`${up ? '+' : ''}${r.delta.oee_pp.toFixed(2)} pp`} up={up} />
        <Stat label="Availability (önce → sonra)"
              value={`${pct(r.before.availability)} → ${pct(r.after.availability)}`}
              delta={`+${r.delta.availability_pp.toFixed(2)} pp`} up />
      </div>

      <div className="section-title" style={{ marginTop: 16 }}>Finansal Etki (varsayımsal)</div>
      <div className="fin-grid">
        <div className="kv"><span className="k">Geri kazanılan saat</span><span className="v">{f.recovered_hours.toFixed(2)} sa</span></div>
        <div className="kv"><span className="k">Ekstra parça</span><span className="v">{f.extra_pieces.toFixed(1)}</span></div>
        <div className="kv"><span className="k">Brüt fayda</span><span className="v">{f.currency}{Math.round(f.gross_benefit).toLocaleString()}</span></div>
        <div className="kv"><span className="k">Duruş tasarrufu</span><span className="v">{f.currency}{Math.round(f.downtime_saving).toLocaleString()}</span></div>
        <div className="kv"><span className="k">Günlük fayda</span><span className="v">{f.currency}{Math.round(f.daily_benefit).toLocaleString()}</span></div>
        <div className="kv"><span className="k">Müdahale maliyeti</span><span className="v">{f.currency}{Math.round(f.intervention_cost).toLocaleString()}</span></div>
        <div className="kv"><span className="k">Geri ödeme</span><span className="v">{f.payback_days ? `${f.payback_days.toFixed(1)} gün` : '-'}</span></div>
        <div className="kv"><span className="k">ROI ({f.horizon_days} gün)</span><span className="v delta-up">{f.roi != null ? `%${Math.round(f.roi * 100).toLocaleString()}` : '-'}</span></div>
      </div>
      <div className="small muted" style={{ marginTop: 6 }}>
        Parça/saat: {f.pieces_per_hour.toFixed(2)} {f.pieces_per_hour_is_estimated ? '(baz günden tahmin)' : '(override)'}
      </div>
    </div>
  )
}

function Stat({ label, value, delta, up }) {
  return (
    <div className="statbox">
      <div className="lbl">{label}</div>
      <div className="big">{value}</div>
      <div className={up ? 'delta-up' : 'delta-down'}>{delta}</div>
    </div>
  )
}
