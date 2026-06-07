import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Card from './Card.jsx'
import RootCauseCard from './RootCauseCard.jsx'
import AlarmParetoChart from './AlarmParetoChart.jsx'

export default function AlarmlarView({ machine, alarmDates, dark }) {
  const [items, setItems] = useState([])
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!machine) return
    setErr(null)
    api.alertPareto(machine, 50).then((d) => setItems(d.items)).catch((e) => setErr(e.message))
  }, [machine])

  const total = items.reduce((s, i) => s + i.count, 0)
  const max = items.reduce((m, i) => Math.max(m, i.count), 0) || 1
  const top5 = items.slice(0, 5)

  return (
    <>
      {err && <div className="err" style={{ marginBottom: 16 }}>{err}</div>}

      <div className="rankcards">
        {top5.map((it, i) => (
          <div key={i} className={`rankcard t${i}`}>
            <div className="rk"><b>#{i + 1}</b> {it.message}</div>
            <div className="ct">{it.count}</div>
            <div className="pb"><span style={{ width: `${(it.count / max) * 100}%` }} /></div>
            <div className="pct">%{total ? ((it.count / total) * 100).toFixed(2) : '0'}</div>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 18 }}>
        <AlarmParetoChart items={items} dark={dark} />
      </div>

      <Card title={`Alarm Sıklığı · ${machine}`} noPad>
        <table className="atable">
          <thead>
            <tr><th>Alarm Detayı</th><th>Alarm Sıklığı</th><th>Adet</th><th style={{ width: 180 }} /></tr>
          </thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={i}>
                <td><span className="alink">{it.message}</span></td>
                <td>%{total ? ((it.count / total) * 100).toFixed(2) : '0'}</td>
                <td>{it.count}</td>
                <td><div className="freqbar"><span style={{ width: `${(it.count / max) * 100}%` }} /></div></td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={4} className="muted" style={{ padding: 20 }}>Alarm kaydı yok.</td></tr>}
          </tbody>
        </table>
      </Card>

      <div className="section-title">Kök Neden Analizi</div>
      <RootCauseCard machine={machine} alarmDates={alarmDates} />
    </>
  )
}
