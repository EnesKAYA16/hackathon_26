import { useEffect, useState } from 'react'
import { Play } from 'lucide-react'
import { api, pct } from '../api.js'
import Card from './Card.jsx'
import WaterfallChart from './WaterfallChart.jsx'

export default function WhatIfPanel({ machine, date, reasons, dark }) {
  const [reason, setReason] = useState('')
  const [reduction, setReduction] = useState(20)   // W1 %
  const [reclassify, setReclassify] = useState(false) // W2
  const [cycleImp, setCycleImp] = useState(0)      // W3 %
  const [scrap, setScrap] = useState(0)            // W4 %
  const [fin, setFin] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => { api.financeDefaults().then(setFin).catch(() => {}) }, [])
  useEffect(() => { if (reasons?.length) setReason(reasons[0]) }, [reasons])
  useEffect(() => { setResult(null); setErr(null) }, [machine, date, reason, reduction, reclassify, cycleImp, scrap])

  const setFinField = (k, v) => setFin((f) => ({ ...f, [k]: v === '' ? null : Number(v) }))

  async function simulate() {
    setLoading(true); setErr(null)
    try {
      setResult(await api.whatif({
        machine, date,
        durus_nedeni: reason || null,
        azaltma_yuzdesi: reclassify ? 0 : reduction / 100,
        reclassify,
        cycle_improvement_pct: cycleImp / 100,
        scrap_rate: scrap / 100,
        finance: fin,
      }))
    } catch (e) { setErr(e.message) } finally { setLoading(false) }
  }

  return (
    <Card title="What-If Simülasyonu">
      {/* A kaldıracı */}
      <div className="lever">
        <div className="lever-head">A · Kullanılabilirlik</div>
        {reasons?.length ? (
          <>
            <label>Duruş nedeni</label>
            <select value={reason} onChange={(e) => setReason(e.target.value)} style={{ width: '100%' }}>
              {reasons.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <label className="chk">
              <input type="checkbox" checked={reclassify} onChange={(e) => setReclassify(e.target.checked)} />
              W2: Plansız → Planlı yeniden sınıflandır
            </label>
            {!reclassify && (
              <div style={{ marginTop: 6 }}>
                <label>W1 · Azaltma: <b>%{reduction}</b></label>
                <input type="range" min="0" max="100" value={reduction} onChange={(e) => setReduction(+e.target.value)} />
              </div>
            )}
          </>
        ) : <div className="muted small">Bu gün için plansız duruş nedeni yok.</div>}
      </div>

      {/* P kaldıracı */}
      <div className="lever">
        <div className="lever-head">P · Performans</div>
        <label>W3 · Çevrim süresi iyileştirme: <b>%{cycleImp}</b></label>
        <input type="range" min="0" max="50" value={cycleImp} onChange={(e) => setCycleImp(+e.target.value)} />
      </div>

      {/* Q kaldıracı */}
      <div className="lever">
        <div className="lever-head">Q · Kalite</div>
        <label>W4 · Sentetik fire oranı: <b>%{scrap}</b></label>
        <input type="range" min="0" max="10" value={scrap} onChange={(e) => setScrap(+e.target.value)} />
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
              <input type="number" placeholder="otomatik" value={fin.pieces_per_hour_override ?? ''}
                     onChange={(e) => setFinField('pieces_per_hour_override', e.target.value)} /></div>
            <div><label>ROI ufku (gün)</label>
              <input type="number" value={fin.horizon_days}
                     onChange={(e) => setFinField('horizon_days', e.target.value)} /></div>
          </div>
        )}
      </details>

      <button style={{ marginTop: 14, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              onClick={simulate} disabled={loading}>
        <Play size={16} />{loading ? 'Hesaplanıyor…' : 'Simüle Et'}
      </button>

      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
      {result && <Result r={result} dark={dark} />}
    </Card>
  )
}

function Result({ r, dark }) {
  const f = r.financial
  const up = r.delta.oee_pp >= 0
  const APQ = [
    ['Availability', r.before.availability, r.after.availability, r.delta.availability_pp],
    ['Performance', r.before.performance, r.after.performance, r.delta.performance_pp],
    ['Quality', r.before.quality, r.after.quality, r.delta.quality_pp],
  ]
  return (
    <div style={{ marginTop: 16 }}>
      <div className="statbox" style={{ textAlign: 'center', marginBottom: 12 }}>
        <div className="lbl">OEE (önce → sonra)</div>
        <div style={{ fontSize: 22, fontWeight: 800, margin: '4px 0' }}>
          {pct(r.before.oee)} → {pct(r.after.oee)}
        </div>
        <div className={up ? 'delta-up' : 'delta-down'}>
          {up ? '+' : ''}{r.delta.oee_pp.toFixed(2)} pp · göreceli {up ? '+' : ''}%{r.delta.oee_relative_pct.toFixed(0)}
        </div>
      </div>

      <div className="apq">
        {APQ.map(([n, b, a, d]) => (
          <div key={n} className="apq-cell">
            <div className="small muted">{n}</div>
            <div style={{ fontWeight: 700 }}>{pct(b)}→{pct(a)}</div>
            <div className={d >= 0 ? 'delta-up' : 'delta-down'} style={{ fontSize: 12 }}>
              {d >= 0 ? '+' : ''}{d.toFixed(2)} pp
            </div>
          </div>
        ))}
      </div>

      <div className="section-sub">Etki Şelalesi (ΔOEE = A + P + Q)</div>
      <WaterfallChart waterfall={r.waterfall} netPP={r.delta.oee_pp} dark={dark} />

      <div className="section-sub">Finansal Etki (varsayımsal)</div>
      <div className="fin-grid">
        <div className="kv"><span className="k">Geri kazanılan saat</span><span className="v">{f.recovered_hours.toFixed(2)} sa</span></div>
        <div className="kv"><span className="k">Ekstra parça</span><span className="v">{f.extra_pieces.toFixed(1)}</span></div>
        <div className="kv"><span className="k">Brüt fayda</span><span className="v">{f.currency}{Math.round(f.gross_benefit).toLocaleString()}</span></div>
        <div className="kv"><span className="k">Günlük fayda</span><span className="v">{f.currency}{Math.round(f.daily_benefit).toLocaleString()}</span></div>
        <div className="kv"><span className="k">Geri ödeme</span><span className="v">{f.payback_days ? `${f.payback_days.toFixed(1)} gün` : '-'}</span></div>
        <div className="kv"><span className="k">ROI ({f.horizon_days} gün)</span><span className="v delta-up">{f.roi != null ? `%${Math.round(f.roi * 100).toLocaleString()}` : '-'}</span></div>
      </div>
    </div>
  )
}
