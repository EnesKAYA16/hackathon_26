import { useEffect, useState } from 'react'
import { Gauge, Power, Boxes, ClipboardList, Bell } from 'lucide-react'
import { api, pct, fmtDate } from '../api.js'
import Card from './Card.jsx'

function oeeColor(v) {            // v: yüzde (0-100)
  if (v >= 40) return 'var(--green)'
  if (v >= 15) return 'var(--amber)'
  return 'var(--red)'
}

// Eksensiz mini çizgi grafik (sparkline) — son 7 gün OEE gidişatı.
function Sparkline({ values, w = 96, h = 26 }) {
  if (!values || values.length < 2) return <span className="muted small">yetersiz veri</span>
  const min = Math.min(...values), max = Math.max(...values), rng = (max - min) || 1
  const pts = values.map((v, i) =>
    `${(i / (values.length - 1)) * w},${h - 2 - ((v - min) / rng) * (h - 4)}`).join(' ')
  const up = values[values.length - 1] >= values[0]
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={up ? '#25b06b' : '#e2483d'} strokeWidth="1.8"
                strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

function Kpi({ Icon, tone, label, value, sub }) {
  return (
    <div className="kpi">
      <div className={`kpi-ic ${tone}`}><Icon size={20} /></div>
      <div>
        <div className="kpi-val">{value}</div>
        <div className="kpi-label">{label}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
      </div>
    </div>
  )
}

export default function FleetView({ date }) {
  const [d, setD] = useState(null)
  const [pat, setPat] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!date) return
    setErr(null); setD(null)
    api.fleetDashboard(date).then(setD).catch((e) => setErr(e.message))
    api.fleetAlarmPatterns().then(setPat).catch(() => {})
  }, [date])

  if (err) return <div className="err">{err}</div>
  if (!d) return <div className="spin">Yükleniyor…</div>
  const k = d.kpi

  return (
    <>
      {/* 1) Filo KPI'ları */}
      <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 18 }}>
        <Kpi Icon={Gauge} tone="blue" label="Filonun Ortalama OEE'si" value={`%${k.avg_oee}`}
             sub={`${fmtDate(date)} · 7 günlük ortalama`} />
        <Kpi Icon={Power} tone="green" label="Aktif Çalışan Makine" value={`${k.active}/${k.total}`}
             sub="vardiyada çalışan / toplam" />
        <Kpi Icon={Boxes} tone="amber" label="Toplam Günlük Üretim" value={k.total_production.toLocaleString()}
             sub="adet (tüm makineler)" />
      </div>

      {/* 2) Makine Durum Matrisi */}
      <div className="section-title">Makine Durum Matrisi</div>
      <div className="mx-grid">
        {d.machines.map((m) => {
          const nodata = m.status === 'nodata' || m.has_data === false
          return (
            <div key={m.unit_uid} className={`mx-card ${m.status}`}>
              <div className="mx-top">
                <span className="mx-name">{m.machine}</span>
                <span className="mx-badge">
                  {nodata ? 'Veri Yok' : (m.status === 'running' ? 'Çalışıyor' : 'Durdu')}
                </span>
              </div>
              {nodata ? (
                <>
                  <div className="mx-oee" style={{ color: 'var(--muted)' }}>—</div>
                  <div className="mx-oee-l">bu aralıkta veri yok</div>
                </>
              ) : (
                <>
                  <div className="mx-oee" style={{ color: oeeColor(m.oee) }}>%{m.oee}</div>
                  <div className="mx-oee-l">anlık OEE</div>
                </>
              )}
              <div className="mx-meta">
                <span><ClipboardList size={13} /> {m.workorders} iş emri</span>
                <span><Bell size={13} /> {m.alarms} alarm</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* 3) Öncelik Panosu + 7 günlük trend */}
      <div className="section-title" style={{ marginTop: 24 }}>Öncelik Panosu (7 günlük ort. OEE — en kötü üstte)</div>
      <Card title={`Filo · ${fmtDate(date)}`} noPad>
        <table className="atable">
          <thead>
            <tr><th>#</th><th>Makine</th><th>OEE (7g ort.)</th><th>Availability</th>
              <th>Performans</th><th>Plansız Duruş</th><th style={{ width: 120 }}>Trend (Son 7 Gün)</th></tr>
          </thead>
          <tbody>
            {d.board.map((m, i) => {
              const nd = m.avg_oee_7d == null
              return (
                <tr key={m.unit_uid} className={nd ? 'row-nodata' : ''}>
                  <td className="muted">{i + 1}</td>
                  <td><b>{m.machine}</b></td>
                  {nd
                    ? <td className="muted">Veri Yok</td>
                    : <td style={{ color: oeeColor(m.avg_oee_7d), fontWeight: 800 }}>%{m.avg_oee_7d}</td>}
                  <td>{nd ? '—' : `%${m.availability}`}</td>
                  <td>{nd ? '—' : `%${m.performance}`}</td>
                  <td style={{ color: 'var(--red)' }}>{nd ? '—' : `${m.unplanned_h.toFixed(1)} sa`}</td>
                  <td><Sparkline values={m.oee_7d} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>

      {/* 4) Çapraz-Makine Alarm Örüntüleri + şiddet */}
      <div className="section-title" style={{ marginTop: 24 }}>Çapraz-Makine Alarm Örüntüleri</div>
      <Card title="Birden Fazla Makinede Görülen Alarmlar" noPad>
        <table className="atable">
          <thead><tr><th>Alarm</th><th>Şiddet</th><th>Makine Sayısı</th><th>Toplam</th><th>Makineler</th></tr></thead>
          <tbody>
            {(pat?.items || []).map((p, i) => (
              <tr key={i}>
                <td><span className="alink">{p.message}</span></td>
                <td><span className={`badge ${p.severity === 'Kritik' ? 'bad' : 'warn'}`}>{p.severity}</span></td>
                <td><span className="badge warn">{p.machine_count}</span></td>
                <td>{p.total}</td>
                <td className="muted small">{p.machines.join(', ')}</td>
              </tr>
            ))}
            {pat && !pat.items.length && (
              <tr><td colSpan={5} className="muted" style={{ padding: 20 }}>Birden fazla makinede ortak alarm yok.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </>
  )
}
