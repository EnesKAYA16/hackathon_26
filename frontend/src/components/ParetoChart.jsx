import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell,
} from 'recharts'
import Card from './Card.jsx'

const COLORS = ['#e2483d', '#f0a52b', '#8b5cf6', '#2b6cf0', '#25b06b']

export default function ParetoChart({ data, dark }) {
  if (!data) return null
  const ax = dark ? '#93a1b2' : '#6b7686'
  const grid = dark ? '#28323f' : '#eef1f6'
  const tip = dark
    ? { background: '#1e2733', border: '1px solid #28323f', borderRadius: 10, color: '#e6edf3' }
    : { background: '#fff', border: '1px solid #e6eaf1', borderRadius: 10, color: '#1f2a37', boxShadow: '0 4px 16px rgba(16,24,40,.1)' }
  const rows = data.items.map((i) => ({
    reason: i.reason,
    hours: Number(i.total_hours.toFixed(2)),
    cum: Number(i.cumulative_pct.toFixed(1)),
  }))

  return (
    <Card title="Plansız Duruş Pareto'su"
          action={<span className="muted small">Toplam {data.total_unplanned_h.toFixed(1)} saat</span>}>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={rows} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid stroke={grid} strokeDasharray="3 3" />
          <XAxis dataKey="reason" tick={{ fill: ax, fontSize: 11 }} interval={0} />
          <YAxis yAxisId="l" tick={{ fill: ax, fontSize: 11 }} label={{ value: 'saat', angle: -90, position: 'insideLeft', fill: ax, fontSize: 11 }} />
          <YAxis yAxisId="r" orientation="right" domain={[0, 100]} tick={{ fill: ax, fontSize: 11 }} unit="%" />
          <Tooltip contentStyle={tip} />
          <Bar yAxisId="l" dataKey="hours" name="Süre (saat)" radius={[6, 6, 0, 0]}>
            {rows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Bar>
          <Line yAxisId="r" dataKey="cum" name="Kümülatif %" stroke="#2b6cf0" strokeWidth={2.5} dot={{ r: 3, fill: '#2b6cf0' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  )
}
