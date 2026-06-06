import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '../api.js'
import Card from './Card.jsx'

// Vardiya günü boyunca saatlik planlı (yeşil) / plansız (kırmızı) duruş — slayt 005.
export default function StoppageTrendChart({ machine, date, dark }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!machine || !date) return
    setErr(null); setData(null)
    api.stoppageTrend(machine, date).then(setData).catch((e) => setErr(e.message))
  }, [machine, date])

  const ax = dark ? '#93a1b2' : '#6b7686'
  const grid = dark ? '#28323f' : '#eef1f6'
  const tip = dark
    ? { background: '#1e2733', border: '1px solid #28323f', borderRadius: 10, color: '#e6edf3' }
    : { background: '#fff', border: '1px solid #e6eaf1', borderRadius: 10, color: '#1f2a37' }

  return (
    <Card title="Duruş Zaman Serisi (saatlik)"
          action={<span className="muted small">{date} · planlı vs plansız</span>}>
      {err && <div className="err">{err}</div>}
      {!data && !err && <div className="spin">Yükleniyor…</div>}
      {data && (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data.buckets} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid stroke={grid} strokeDasharray="3 3" />
            <XAxis dataKey="hour" tick={{ fill: ax, fontSize: 10 }} interval={1} />
            <YAxis tick={{ fill: ax, fontSize: 11 }} unit="s" />
            <Tooltip contentStyle={tip} formatter={(v, n) => [`${Number(v).toFixed(2)} sa`, n]} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="planned_h" stackId="s" name="Planlı" fill="#25b06b" radius={[0, 0, 0, 0]} />
            <Bar dataKey="unplanned_h" stackId="s" name="Plansız" fill="#e2483d" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}
