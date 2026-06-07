import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import Card from './Card.jsx'

const COLORS = ['#e2483d', '#ec7a2f', '#f0a52b', '#d9b920', '#8b5cf6', '#2b6cf0', '#25b06b']

// Alarm Pareto (80/20): sıklığa göre azalan sütunlar + kümülatif % çizgisi.
export default function AlarmParetoChart({ items, dark }) {
  if (!items || !items.length) return null
  const top = items.slice(0, 8)
  const total = items.reduce((s, i) => s + i.count, 0) || 1
  let cum = 0
  const rows = top.map((i) => {
    cum += i.count
    return { name: i.message.length > 16 ? i.message.slice(0, 15) + '…' : i.message,
             full: i.message, count: i.count, cum: Number((cum / total * 100).toFixed(1)) }
  })

  const ax = dark ? '#93a1b2' : '#6b7686'
  const grid = dark ? '#28323f' : '#eef1f6'
  const tip = dark
    ? { background: '#1e2733', border: '1px solid #28323f', borderRadius: 10, color: '#e6edf3' }
    : { background: '#fff', border: '1px solid #e6eaf1', borderRadius: 10, color: '#1f2a37' }

  return (
    <Card title="Alarm Pareto Analizi (80/20)"
          action={<span className="muted small">sıklığa göre · kümülatif %</span>}>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={rows} margin={{ top: 10, right: 8, left: -12, bottom: 40 }}>
          <CartesianGrid stroke={grid} strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fill: ax, fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={60} />
          <YAxis yAxisId="l" tick={{ fill: ax, fontSize: 11 }} allowDecimals={false} label={{ value: 'adet', angle: -90, position: 'insideLeft', fill: ax, fontSize: 11 }} />
          <YAxis yAxisId="r" orientation="right" domain={[0, 100]} tick={{ fill: ax, fontSize: 11 }} unit="%" />
          <Tooltip contentStyle={tip}
                   formatter={(v, n) => (n === 'Kümülatif %' ? [`${v}%`, n] : [`${v} kez`, 'Sıklık'])}
                   labelFormatter={(l, p) => (p && p[0] ? p[0].payload.full : l)} />
          <ReferenceLine yAxisId="r" y={80} stroke="#e2483d" strokeDasharray="4 4"
                         label={{ value: '%80', fill: '#e2483d', fontSize: 10, position: 'right' }} />
          <Bar yAxisId="l" dataKey="count" name="Sıklık" radius={[5, 5, 0, 0]}>
            {rows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Bar>
          <Line yAxisId="r" dataKey="cum" name="Kümülatif %" stroke="#2b6cf0" strokeWidth={2.5} dot={{ r: 3, fill: '#2b6cf0' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  )
}
