import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'

// ΔOEE'yi A / P / Q katkılarına ayrıştıran "Etki Şelalesi".
export default function WaterfallChart({ waterfall, netPP, dark }) {
  const ax = dark ? '#93a1b2' : '#6b7686'
  const grid = dark ? '#28323f' : '#eef1f6'
  const tip = dark
    ? { background: '#1e2733', border: '1px solid #28323f', borderRadius: 10, color: '#e6edf3' }
    : { background: '#fff', border: '1px solid #e6eaf1', borderRadius: 10, color: '#1f2a37' }

  const data = [
    { name: 'A katkı', v: waterfall.a },
    { name: 'P katkı', v: waterfall.p },
    { name: 'Q katkı', v: waterfall.q },
    { name: 'Net ΔOEE', v: netPP, net: true },
  ]
  const color = (d) => (d.net ? '#2b6cf0' : d.v >= 0 ? '#25b06b' : '#e2483d')

  return (
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={data} margin={{ top: 10, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid stroke={grid} strokeDasharray="3 3" />
        <XAxis dataKey="name" tick={{ fill: ax, fontSize: 11 }} />
        <YAxis tick={{ fill: ax, fontSize: 11 }} unit="pp" />
        <Tooltip contentStyle={tip} formatter={(v) => [`${Number(v).toFixed(2)} pp`, 'katkı']} />
        <ReferenceLine y={0} stroke={ax} />
        <Bar dataKey="v" radius={[5, 5, 0, 0]}>
          {data.map((d, i) => <Cell key={i} fill={color(d)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
