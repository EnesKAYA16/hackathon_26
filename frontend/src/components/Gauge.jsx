// trexCloud tarzı yarım daire gösterge (kırmızı→sarı→yeşil gradyan).
// value: 0..1 oran.
export default function Gauge({ value, label = 'Kullanılabilirlik', size = 230 }) {
  const v = Math.max(0, Math.min(1, value || 0))
  const w = size
  const cx = w / 2, cy = w / 2, r = w / 2 - 20
  const polar = (frac) => {
    const ang = Math.PI - frac * Math.PI // 0->sol(π), 1->sağ(0)
    return [cx + r * Math.cos(ang), cy - r * Math.sin(ang)]
  }
  const [x0, y0] = polar(0)
  const [x1, y1] = polar(1)
  const [mx, my] = polar(v)
  const bg = `M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`

  return (
    <svg viewBox={`0 0 ${w} ${cy + 22}`} width="100%" style={{ maxWidth: size }}>
      <defs>
        <linearGradient id="gaugeg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#e0512f" />
          <stop offset="50%" stopColor="#ecc02a" />
          <stop offset="100%" stopColor="#34b35a" />
        </linearGradient>
      </defs>
      <path className="g-track" d={bg} fill="none" strokeWidth="20" strokeLinecap="round" />
      <path d={bg} fill="none" stroke="url(#gaugeg)" strokeWidth="20" strokeLinecap="round" />
      <circle cx={mx} cy={my} r="10" fill="#fff" stroke="#94a3b8" strokeWidth="3" />
      <text className="g-val" x={cx} y={cy - 4} textAnchor="middle" fontSize={w * 0.17} fontWeight="800">
        {Math.round(v * 100)}%
      </text>
      <text className="g-lbl" x={cx} y={cy + 16} textAnchor="middle" fontSize={w * 0.058}>{label}</text>
    </svg>
  )
}
