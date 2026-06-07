import { useEffect, useState } from 'react'
import { api, fmtHM, fmtCycle, fmtDateTime, fmtDate } from '../api.js'
import Card from './Card.jsx'

const time = (iso) => fmtDateTime(iso)  // UTC + DD.MM.YYYY HH:mm:ss

export default function WorkOrdersView({ machine, date }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!machine || !date) return
    setErr(null); setData(null)
    api.workorders(machine, date).then(setData).catch((e) => setErr(e.message))
  }, [machine, date])

  if (err) return <div className="err">{err}</div>
  if (!data) return <div className="spin">Yükleniyor…</div>

  return (
    <Card title={`İş Emirleri · ${machine} · ${fmtDate(date)}`}
          action={<span className="muted small">{data.count} kayıt</span>} noPad>
      <table className="atable">
        <thead>
          <tr>
            <th>İş Emri</th><th>Tür</th><th>Başlangıç</th><th>Bitiş</th>
            <th>Süre</th><th>Çevrim (cycle)</th><th>Planlı Adet</th>
          </tr>
        </thead>
        <tbody>
          {data.orders.map((o, i) => (
            <tr key={i}>
              <td><span className="alink">#{o.order_no}</span></td>
              <td>{o.is_stock
                ? <span className="badge good">Stok</span>
                : <span className="badge warn">İş Emri</span>}</td>
              <td className="t">{time(o.started_on)}</td>
              <td className="t">{time(o.ended_on)}</td>
              <td>{fmtHM(o.duration_ms)}</td>
              <td>{fmtCycle(o.stock_cycle_ms)}</td>
              <td>{o.planned_quantity != null ? o.planned_quantity : '—'}</td>
            </tr>
          ))}
          {!data.orders.length && (
            <tr><td colSpan={7} className="muted" style={{ padding: 20 }}>Bu vardiya gününde iş emri kaydı yok.</td></tr>
          )}
        </tbody>
      </table>
    </Card>
  )
}
