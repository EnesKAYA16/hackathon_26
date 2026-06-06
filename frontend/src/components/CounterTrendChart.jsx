import { useEffect, useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import { api } from '../api.js'
import Card from './Card.jsx'

// Vardiya günü boyunca saatlik üretilen parça (sayaç) — slayt 'Counters'.
export default function CounterTrendChart({ machine, date, dark }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!machine || !date) return
    setErr(null); setData(null)
    api.counterTrend(machine, date).then(setData).catch((e) => setErr(e.message))
  }, [machine, date])

  const ax = dark ? '#93a1b2' : '#6b7686'
  const grid = dark ? '#28323f' : '#eef1f6'
  const tip = dark
    ? { background: '#1e2733', border: '1px solid #28323f', borderRadius: 10, color: '#e6edf3' }
    : { background: '#fff', border: '1px solid #e6eaf1', borderRadius: 10, color: '#1f2a37' }

  return (
    <Card title="Üretim Sayacı (saatlik)"
          action={<span className="muted small">{data ? `${data.total_pieces.toFixed(0)} parça` : ''}</span>}>
      {err && <div className="err">{err}</div>}
      {!data && !err && <div className="spin">Yükleniyor…</div>}
      {data && (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data.buckets} margin={{ top: 8, right: 10, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="cnt" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2b6cf0" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#2b6cf0" stopOpacity={0.04} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={grid} strokeDasharray="3 3" />
            <XAxis dataKey="hour" tick={{ fill: ax, fontSize: 10 }} interval={1} />
            <YAxis tick={{ fill: ax, fontSize: 11 }} allowDecimals={false} unit=" Ad" />
            <Tooltip contentStyle={tip} formatter={(v) => [`${Number(v).toFixed(0)} Ad`, 'Parça']} />
            <Area dataKey="pieces" name="Parça" stroke="#2b6cf0" strokeWidth={2} fill="url(#cnt)" />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}
