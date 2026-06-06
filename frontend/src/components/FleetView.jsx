import { useEffect, useState } from 'react'
import { api, pct, fmtHM } from '../api.js'
import Card from './Card.jsx'

function oeeColor(v) {
  if (v >= 0.4) return 'var(--green)'
  if (v >= 0.15) return 'var(--amber)'
  return 'var(--red)'
}

export default function FleetView({ date }) {
  const [fleet, setFleet] = useState(null)
  const [patterns, setPatterns] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!date) return
    setErr(null); setFleet(null)
    api.fleetOverview(date).then(setFleet).catch((e) => setErr(e.message))
    api.fleetAlarmPatterns().then(setPatterns).catch(() => {})
  }, [date])

  if (err) return <div className="err">{err}</div>
  if (!fleet) return <div className="spin">Yükleniyor…</div>

  return (
    <>
      <Card title={`Öncelik Panosu · ${date} (en kötü OEE üstte)`}
            action={<span className="muted small">{fleet.count} makine</span>} noPad>
        <table className="atable">
          <thead>
            <tr><th>#</th><th>Makine</th><th>OEE</th><th>Availability</th>
              <th>Performans</th><th>Kalite</th><th>Plansız Duruş</th></tr>
          </thead>
          <tbody>
            {fleet.machines.map((m, i) => (
              <tr key={m.unit_uid}>
                <td className="muted">{i + 1}</td>
                <td><b>{m.machine}</b></td>
                <td><span className="badge" style={{ background: 'transparent', color: oeeColor(m.oee), fontWeight: 800 }}>{pct(m.oee)}</span></td>
                <td>{pct(m.availability)}</td>
                <td>{pct(m.performance)}</td>
                <td>{pct(m.quality)}</td>
                <td style={{ color: 'var(--red)' }}>{m.unplanned_stop_h.toFixed(1)} sa</td>
              </tr>
            ))}
            {!fleet.machines.length && <tr><td colSpan={7} className="muted" style={{ padding: 20 }}>Bu gün için veri yok.</td></tr>}
          </tbody>
        </table>
      </Card>

      <div className="section-title">Çapraz-Makine Alarm Örüntüleri</div>
      <Card title="Birden Fazla Makinede Görülen Alarmlar" noPad>
        <table className="atable">
          <thead><tr><th>Alarm</th><th>Makine Sayısı</th><th>Toplam</th><th>Makineler</th></tr></thead>
          <tbody>
            {(patterns?.items || []).map((p, i) => (
              <tr key={i}>
                <td><span className="alink">{p.message}</span></td>
                <td><span className="badge warn">{p.machine_count}</span></td>
                <td>{p.total}</td>
                <td className="muted small">{p.machines.join(', ')}</td>
              </tr>
            ))}
            {patterns && !patterns.items.length && (
              <tr><td colSpan={4} className="muted" style={{ padding: 20 }}>Birden fazla makinede ortak alarm bulunamadı.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </>
  )
}
