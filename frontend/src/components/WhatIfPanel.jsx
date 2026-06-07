import { useEffect, useRef, useState } from 'react'
import { TrendingUp, Clock } from 'lucide-react'
import { api, pct } from '../api.js'
import Card from './Card.jsx'
import WaterfallChart from './WaterfallChart.jsx'

// Slider + senkron sayısal input (ayarlanabilir kontrol)
function SliderInput({ value, onChange, min = 0, max = 100, unit = '%' }) {
  const clamp = (v) => Math.max(min, Math.min(max, Number.isNaN(v) ? 0 : v))
  return (
    <div className="wf-si">
      <input type="range" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <div className="wf-si-num">
        <input type="number" min={min} max={max} value={value} onChange={(e) => onChange(clamp(Number(e.target.value)))} />
        <span>{unit}</span>
      </div>
    </div>
  )
}

export default function WhatIfPanel({ machine, date, reasons, dark }) {
  const [reason, setReason] = useState('')
  const [reduction, setReduction] = useState(20)      // W1 %
  const [reclassifyPct, setReclassifyPct] = useState(0) // W2 %
  const [cycleImp, setCycleImp] = useState(0)         // W3 %
  const [scrap, setScrap] = useState(0)               // W4 %
  const [fin, setFin] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const seq = useRef(0)

  useEffect(() => { api.financeDefaults().then(setFin).catch(() => {}) }, [])
  useEffect(() => { if (reasons?.length && !reason) setReason(reasons[0]) }, [reasons])

  // Parametre değişince ANINDA (debounce 300ms) yeniden hesapla
  useEffect(() => {
    if (!machine || !date || !reason) return
    const my = ++seq.current
    setBusy(true)
    const t = setTimeout(() => {
      api.whatif({
        machine, date, durus_nedeni: reason,
        azaltma_yuzdesi: reduction / 100, reclassify_pct: reclassifyPct / 100,
        cycle_improvement_pct: cycleImp / 100, scrap_rate: scrap / 100, finance: fin,
      }).then((r) => { if (my === seq.current) { setResult(r); setErr(null) } })
        .catch((e) => { if (my === seq.current) setErr(e.message) })
        .finally(() => { if (my === seq.current) setBusy(false) })
    }, 300)
    return () => clearTimeout(t)
  }, [machine, date, reason, reduction, reclassifyPct, cycleImp, scrap, fin])

  if (!reasons?.length) return (
    <Card title="What-If Simülasyonu">
      <div className="muted small">Bu gün için plansız duruş nedeni yok.</div>
    </Card>
  )

  const r = result
  const up = r ? r.delta.oee_pp >= 0 : true
  const f = r?.financial

  return (
    <Card title="What-If Simülasyonu"
          action={<span className="muted small">{busy ? 'hesaplanıyor…' : 'anlık'}</span>}>
      {/* Büyük canlı KPI kartları */}
      <div className="wf-kpis">
        <div className={`wf-kpi ${up ? 'good' : 'bad'}`}>
          <div className="wf-kpi-l"><TrendingUp size={14} /> Öngörülen OEE Artışı</div>
          <div className="wf-kpi-v">{r ? `${up ? '+' : ''}${r.delta.oee_pp.toFixed(2)} pp` : '—'}</div>
          <div className="wf-kpi-s">{r ? `${pct(r.before.oee)} → ${pct(r.after.oee)}` : ''}</div>
        </div>
        <div className="wf-kpi blue">
          <div className="wf-kpi-l"><Clock size={14} /> Kazanılan Saat</div>
          <div className="wf-kpi-v">{f ? `${f.recovered_hours.toFixed(1)} sa` : '—'}</div>
          <div className="wf-kpi-s">{f ? `~${f.extra_pieces.toFixed(0)} ekstra parça` : ''}</div>
        </div>
      </div>

      {/* A kaldıracı: neden + W1 azalt + W2 planlıya çevir (ikisi de ayarlanabilir %) */}
      <div className="wf-lever">
        <div className="wf-lever-tag a">A · Kullanılabilirlik</div>
        <label style={{ marginTop: 8 }}>Duruş nedeni</label>
        <select value={reason} onChange={(e) => setReason(e.target.value)} style={{ width: '100%' }}>
          {reasons.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
        <div className="wf-lever-row"><span className="wf-lever-label">W1 · Plansızı azalt</span></div>
        <SliderInput value={reduction} onChange={setReduction} />
        <div className="wf-lever-row"><span className="wf-lever-label">W2 · Planlıya çevir</span></div>
        <SliderInput value={reclassifyPct} onChange={setReclassifyPct} />
      </div>

      <div className="wf-lever">
        <div className="wf-lever-tag p">P · Performans</div>
        <div className="wf-lever-row"><span className="wf-lever-label">W3 · Çevrim iyileştirme</span></div>
        <SliderInput value={cycleImp} onChange={setCycleImp} max={50} />
      </div>

      <div className="wf-lever">
        <div className="wf-lever-tag q">Q · Kalite</div>
        <div className="wf-lever-row"><span className="wf-lever-label">W4 · Sentetik fire</span></div>
        <SliderInput value={scrap} onChange={setScrap} max={10} />
      </div>

      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}

      {r && (
        <>
          <div className="apq" style={{ marginTop: 16 }}>
            {[['Availability', r.before.availability, r.after.availability, r.delta.availability_pp],
              ['Performance', r.before.performance, r.after.performance, r.delta.performance_pp],
              ['Quality', r.before.quality, r.after.quality, r.delta.quality_pp]].map(([n, b, a, dpp]) => (
              <div key={n} className="apq-cell">
                <div className="small muted">{n}</div>
                <div style={{ fontWeight: 700 }}>{pct(b)}→{pct(a)}</div>
                <div className={dpp >= 0 ? 'delta-up' : 'delta-down'} style={{ fontSize: 12 }}>
                  {dpp >= 0 ? '+' : ''}{dpp.toFixed(2)} pp
                </div>
              </div>
            ))}
          </div>

          <div className="section-sub">Etki Şelalesi</div>
          <WaterfallChart waterfall={r.waterfall} netPP={r.delta.oee_pp} dark={dark} />

          <details>
            <summary>Finansal varsayımlar & ROI detayı (₺)</summary>
            {fin && (
              <div className="fin-inputs">
                <div><label>Parça başı marj</label>
                  <input type="number" value={fin.contribution_margin_per_piece}
                         onChange={(e) => setFin({ ...fin, contribution_margin_per_piece: Number(e.target.value) })} /></div>
                <div><label>Saatlik duruş maliyeti</label>
                  <input type="number" value={fin.downtime_cost_per_hour}
                         onChange={(e) => setFin({ ...fin, downtime_cost_per_hour: Number(e.target.value) })} /></div>
                <div><label>Müdahale maliyeti</label>
                  <input type="number" value={fin.intervention_cost}
                         onChange={(e) => setFin({ ...fin, intervention_cost: Number(e.target.value) })} /></div>
                <div><label>ROI ufku (gün)</label>
                  <input type="number" value={fin.horizon_days}
                         onChange={(e) => setFin({ ...fin, horizon_days: Number(e.target.value) })} /></div>
              </div>
            )}
            {f && (
              <div className="fin-grid" style={{ marginTop: 10 }}>
                <div className="kv"><span className="k">Brüt fayda</span><span className="v">{f.currency}{Math.round(f.gross_benefit).toLocaleString()}</span></div>
                <div className="kv"><span className="k">Günlük fayda</span><span className="v">{f.currency}{Math.round(f.daily_benefit).toLocaleString()}</span></div>
                <div className="kv"><span className="k">Geri ödeme</span><span className="v">{f.payback_days ? `${f.payback_days.toFixed(1)} gün` : '-'}</span></div>
                <div className="kv"><span className="k">ROI ({f.horizon_days} gün)</span><span className="v delta-up">{f.roi != null ? `%${Math.round(f.roi * 100).toLocaleString()}` : '-'}</span></div>
              </div>
            )}
          </details>
        </>
      )}
    </Card>
  )
}
