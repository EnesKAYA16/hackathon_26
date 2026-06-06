import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell,
} from 'recharts'

const COLORS = ['#f85149', '#d29922', '#bc8cff', '#2f81f7', '#3fb950']

export default function ParetoChart({ data }) {
  if (!data) return null
  const rows = data.items.map((i) => ({
    reason: i.reason,
    hours: Number(i.total_hours.toFixed(2)),
    cum: Number(i.cumulative_pct.toFixed(1)),
  }))

  return (
    <div className="card">
      <h3>Plansız Duruş Pareto'su</h3>
      <div className="small muted" style={{ marginBottom: 8 }}>
        En çok süre kaybettiren nedenler · toplam {data.total_unplanned_h.toFixed(1)} saat
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={rows} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid stroke="#2d333b" strokeDasharray="3 3" />
          <XAxis dataKey="reason" tick={{ fill: '#8b949e', fontSize: 11 }} interval={0} />
          <YAxis yAxisId="l" tick={{ fill: '#8b949e', fontSize: 11 }} label={{ value: 'saat', angle: -90, position: 'insideLeft', fill: '#8b949e', fontSize: 11 }} />
          <YAxis yAxisId="r" orientation="right" domain={[0, 100]} tick={{ fill: '#8b949e', fontSize: 11 }} unit="%" />
          <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #2d333b', borderRadius: 8, color: '#e6edf3' }} />
          <Bar yAxisId="l" dataKey="hours" name="Süre (saat)" radius={[4, 4, 0, 0]}>
            {rows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Bar>
          <Line yAxisId="r" dataKey="cum" name="Kümülatif %" stroke="#e6edf3" strokeWidth={2} dot={{ r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
