import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

// trexCloud tarzı donut + ortada büyük değer.
export default function Donut({ segments, centerValue, centerLabel, size = 200, dark }) {
  const stroke = dark ? '#161c24' : '#fff'
  const tip = dark
    ? { background: '#1e2733', border: '1px solid #28323f', borderRadius: 10, fontSize: 12, color: '#e6edf3' }
    : { background: '#fff', border: '1px solid #e6eaf1', borderRadius: 10, fontSize: 12 }
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={segments} dataKey="value" nameKey="name"
               innerRadius={size * 0.33} outerRadius={size * 0.47}
               startAngle={90} endAngle={-270} stroke={stroke} strokeWidth={2} paddingAngle={1}>
            {segments.map((s, i) => <Cell key={i} fill={s.color} />)}
          </Pie>
          <Tooltip contentStyle={tip} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
        <div style={{ fontSize: 24, fontWeight: 800 }}>{centerValue}</div>
        <div className="small muted">{centerLabel}</div>
      </div>
    </div>
  )
}
