import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '../api.js'
import Card from './Card.jsx'

// Seçilen tarih aralığında OEE / Availability / Performans trendi.
export default function OeeTrendChart({ machine, start, end, dark }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!machine) return
    setErr(null); setData(null)
    api.oeeTrend(machine, start && end ? { start, end } : { days: 30 })
      .then(setData).catch((e) => setErr(e.message))
  }, [machine, start, end])

  const ax = dark ? '#93a1b2' : '#6b7686'
  const grid = dark ? '#28323f' : '#eef1f6'
  const tip = dark
    ? { background: '#1e2733', border: '1px solid #28323f', borderRadius: 10, color: '#e6edf3' }
    : { background: '#fff', border: '1px solid #e6eaf1', borderRadius: 10, color: '#1f2a37' }

  return (
    <Card title="OEE Trendi"
          action={<span className="muted small">{start && end ? `${start} → ${end}` : machine}</span>}>
      {err && <div className="err">{err}</div>}
      {!data && !err && <div className="spin">Yükleniyor…</div>}
      {data && (
        <ResponsiveContainer width="100%" height={230}>
          <LineChart data={data.points} margin={{ top: 8, right: 10, left: -12, bottom: 0 }}>
            <CartesianGrid stroke={grid} strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: ax, fontSize: 10 }} interval="preserveStartEnd" minTickGap={28} />
            <YAxis tick={{ fill: ax, fontSize: 11 }} unit="%" />
            <Tooltip contentStyle={tip} formatter={(v, n) => [`${Number(v).toFixed(1)}%`, n]} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="availability" name="Availability" stroke="#f0a52b" strokeWidth={2} dot={false} />
            <Line dataKey="performance" name="Performans" stroke="#8b5cf6" strokeWidth={2} dot={false} />
            <Line dataKey="oee" name="OEE" stroke="#2b6cf0" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}
