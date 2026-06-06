import { useEffect, useState } from 'react'
import { api, fmtHM } from '../api.js'
import Card from './Card.jsx'

export default function StockView({ machine, date }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!machine || !date) return
    setErr(null); setData(null)
    api.stock(machine, date).then(setData).catch((e) => setErr(e.message))
  }, [machine, date])

  if (err) return <div className="err">{err}</div>
  if (!data) return <div className="spin">Yükleniyor…</div>

  const totalRuns = data.items.reduce((s, i) => s + i.runs, 0)
  const totalMs = data.items.reduce((s, i) => s + i.total_duration_ms, 0)

  return (
    <>
      <div className="grid cols-2" style={{ marginBottom: 18 }}>
        <Card title="Program Sayısı"><div style={{ fontSize: 34, fontWeight: 800 }}>{data.count}</div>
          <div className="muted small">{date} vardiyasında çalışan farklı program</div></Card>
        <Card title="Toplam Çalışma">
          <div style={{ fontSize: 34, fontWeight: 800 }}>{fmtHM(totalMs)}</div>
          <div className="muted small">{totalRuns} çalışma (run)</div></Card>
      </div>

      <Card title={`Stok / Program Özeti · ${machine} · ${date}`} noPad>
        <table className="atable">
          <thead>
            <tr><th>Program (İş Emri No)</th><th>Çalışma Sayısı</th><th>Toplam Süre</th>
              <th>Ort. Çevrim</th><th style={{ width: 180 }} /></tr>
          </thead>
          <tbody>
            {data.items.map((it, i) => (
              <tr key={i}>
                <td><span className="alink">#{it.order_no}</span></td>
                <td>{it.runs}</td>
                <td>{fmtHM(it.total_duration_ms)}</td>
                <td>{it.avg_cycle_ms != null ? fmtHM(it.avg_cycle_ms) : '—'}</td>
                <td><div className="freqbar"><span style={{ width: `${totalMs ? (it.total_duration_ms / totalMs) * 100 : 0}%` }} /></div></td>
              </tr>
            ))}
            {!data.items.length && (
              <tr><td colSpan={5} className="muted" style={{ padding: 20 }}>Bu vardiya gününde program kaydı yok.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </>
  )
}
