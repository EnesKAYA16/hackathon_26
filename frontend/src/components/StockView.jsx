import { useEffect, useState } from 'react'
import { Package, Repeat, Boxes } from 'lucide-react'
import { api, fmtHM, fmtCycle, fmtDate } from '../api.js'
import Card from './Card.jsx'

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

export default function StockView({ machine, start, end }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!machine || !start) return
    setErr(null); setData(null)
    api.stock(machine, start, end).then(setData).catch((e) => setErr(e.message))
  }, [machine, start, end])

  if (err) return <div className="err">{err}</div>
  if (!data) return <div className="spin">Yükleniyor…</div>

  const range = data.start === data.end ? fmtDate(data.start) : `${fmtDate(data.start)} → ${fmtDate(data.end)}`
  const totalMs = data.total_duration_ms || 1

  return (
    <>
      <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 18 }}>
        <Kpi Icon={Package} tone="blue" label="Program Sayısı" value={data.count} sub={range} />
        <Kpi Icon={Repeat} tone="amber" label="Toplam Çalışma (run)" value={data.total_runs}
             sub={`${fmtHM(data.total_duration_ms)} toplam süre`} />
        <Kpi Icon={Boxes} tone="green" label="Toplam Üretim (adet)" value={data.total_produced.toLocaleString()}
             sub="oee_summary ProductSum" />
      </div>

      <Card title={`Stok / Program Özeti · ${machine} · ${range}`} noPad>
        <table className="atable">
          <thead>
            <tr>
              <th>Program (İş Emri No)</th>
              <th>Çalışma Sayısı</th>
              <th>Toplam Süre</th>
              <th>Ort. Çevrim</th>
              <th>Üretilen Adet</th>
              <th style={{ width: 200 }}>Süre Payı (%)</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((it, i) => {
              const share = (it.total_duration_ms / totalMs) * 100
              return (
                <tr key={i}>
                  <td><span className="alink">#{it.order_no}</span></td>
                  <td>{it.runs}</td>
                  <td>{fmtHM(it.total_duration_ms)}</td>
                  <td>{fmtCycle(it.avg_cycle_ms)}</td>
                  <td><b>{it.produced != null ? it.produced.toLocaleString() : '—'}</b></td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div className="freqbar" style={{ flex: 1 }}>
                        <span style={{ width: `${share}%` }} />
                      </div>
                      <span style={{ width: 42, textAlign: 'right', fontWeight: 700 }}>%{share.toFixed(0)}</span>
                    </div>
                  </td>
                </tr>
              )
            })}
            {!data.items.length && (
              <tr><td colSpan={6} className="muted" style={{ padding: 20 }}>Bu aralıkta iş emri kaydı yok.</td></tr>
            )}
          </tbody>
        </table>
        {!data.has_program_counter && data.items.length > 0 && (
          <div className="small muted" style={{ padding: '10px 14px', borderTop: '1px solid var(--border)' }}>
            ℹ️ Bu makinede program-bazlı sayaç (COUNT) verisi yok (ör. Mitsubishi farklı kaydeder);
            "Üretilen Adet" satır bazında "—". Toplam üretim üstte gerçek <b>ProductSum</b>'dan gelir.
          </div>
        )}
      </Card>
    </>
  )
}
