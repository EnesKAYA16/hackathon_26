import { useEffect, useState } from 'react'
import { Clock, Percent, Timer, Wrench } from 'lucide-react'
import { api, fmtHM } from '../api.js'

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

export default function StoppageKpiCards({ machine, date }) {
  const [k, setK] = useState(null)
  useEffect(() => {
    if (!machine || !date) return
    setK(null)
    api.stoppageKpis(machine, date).then(setK).catch(() => setK(null))
  }, [machine, date])

  if (!k) return <div className="kpi-row"><div className="spin">Yükleniyor…</div></div>
  return (
    <div className="kpi-row">
      <Kpi Icon={Clock} tone="blue" label="Toplam Duruş Süresi" value={fmtHM(k.total_stop_ms)} />
      <Kpi Icon={Percent} tone="red" label="Plansız Duruş Oranı" value={`%${k.unplanned_ratio_pct.toFixed(1)}`} />
      <Kpi Icon={Timer} tone="green" label="MTBF (Arıza Arası)" value={fmtHM(k.mtbf_ms)}
           sub={`${k.unplanned_events} plansız olay`} />
      <Kpi Icon={Wrench} tone="amber" label="MTTR (Ort. Tamir)" value={fmtHM(k.mttr_ms)} />
    </div>
  )
}
