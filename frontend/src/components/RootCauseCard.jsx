import { useEffect, useState } from 'react'
import { AlertTriangle, Activity, PauseCircle, Ban, Lightbulb, TrendingUp, Sparkles } from 'lucide-react'
import { api, fmtHM } from '../api.js'
import Card from './Card.jsx'

const time = (iso) => (iso ? new Date(iso).toLocaleTimeString('tr-TR', { hour12: false }) : '')
const likeClass = (l) => (l === 'Yüksek' ? 'good' : l === 'Orta' ? 'warn' : 'bad')

// Basit markdown render (## başlık, - madde, **kalın**) — güvenli (HTML yok).
function bold(s) {
  return s.split('**').map((p, i) => (i % 2 ? <b key={i}>{p}</b> : p))
}
function MdLite({ text }) {
  return (
    <div className="ai-md">
      {text.split('\n').map((ln, i) => {
        const t = ln.trim()
        if (!t) return <div key={i} style={{ height: 6 }} />
        if (t.startsWith('## ')) return <div key={i} className="ai-h">{t.slice(3)}</div>
        if (t.startsWith('# ')) return <div key={i} className="ai-h">{t.slice(2)}</div>
        if (t.startsWith('- ') || t.startsWith('* ')) return <div key={i} className="ai-li">• {bold(t.slice(2))}</div>
        return <div key={i}>{bold(t)}</div>
      })}
    </div>
  )
}

export default function RootCauseCard({ machine, alarmDates }) {
  const [date, setDate] = useState('')
  const [card, setCard] = useState(null)
  const [dev, setDev] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [ai, setAi] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)

  useEffect(() => { if (alarmDates?.length) setDate((d) => d || alarmDates[0]) }, [alarmDates])

  useEffect(() => {
    if (!machine || !date) return
    setLoading(true); setErr(null); setCard(null); setDev(null); setAi(null)
    api.rootCause(machine, date)
      .then((c) => {
        setCard(c)
        if (c.has_alarm && c.primary_time) {
          api.deviation(machine, c.primary_time).then(setDev).catch(() => {})
        }
      })
      .catch((e) => setErr(e.message)).finally(() => setLoading(false))
  }, [machine, date])

  async function runAi() {
    setAiLoading(true); setAi(null)
    try { setAi(await api.analyzeRootCause(machine, date)) }
    catch (e) { setAi({ analysis: `Analiz başarısız: ${e.message}`, source: 'error' }) }
    finally { setAiLoading(false) }
  }

  const dateSelect = (
    <select value={date} onChange={(e) => setDate(e.target.value)}>
      {(alarmDates || []).map((d) => <option key={d} value={d}>{d}</option>)}
    </select>
  )

  return (
    <Card title="Kök Neden Kartı (RCA)" action={dateSelect}>
      {loading && <div className="spin">Telemetri sorgulanıyor…</div>}
      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}

      {card && !card.has_alarm && (
        <div className="muted small" style={{ marginTop: 12 }}>{card.summary}</div>
      )}

      {card && card.has_alarm && (
        <>
          <div style={{ margin: '12px 0' }}>
            {card.run_stopped_at_alarm
              ? <span className="badge bad">Telemetri doğruladı: makine durdu</span>
              : <span className="badge warn">Telemetri: net duruş kanıtı yok</span>}
          </div>
          <p style={{ marginTop: 0 }}>{card.summary}</p>

          {/* AI Detaylı Analiz (Gemini) */}
          <div className="ai-box">
            <div className="ai-bar">
              <button className="ai-btn" onClick={runAi} disabled={aiLoading}>
                <Sparkles size={16} />{aiLoading ? 'Analiz ediliyor…' : 'Yapay Zeka ile Detaylı Analiz'}
              </button>
              {ai && ai.source && (
                <span className={`badge ${ai.source === 'gemini' ? 'good' : ai.source === 'error' ? 'bad' : 'warn'}`}>
                  {ai.source === 'gemini' ? `Gemini · ${ai.model || ''}` : ai.source === 'error' ? 'Hata' : 'Yerel özet'}
                </span>
              )}
            </div>
            {aiLoading && <div className="spin">Gemini olay verisini analiz ediyor…</div>}
            {ai && ai.note && <div className="ai-note">⚠️ {ai.note}</div>}
            {ai && ai.analysis && <div className="ai-panel"><MdLite text={ai.analysis} /></div>}
          </div>

          <div className="section-sub">Alarmlar (tekrar sayısı + öneri)</div>
          {card.alarms.map((a, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <b>{a.message}</b>
                <span className="badge warn">×{a.recurrence_total} kez</span>
              </div>
              <div className="recommend"><Lightbulb size={14} style={{ verticalAlign: -2 }} /> {a.recommendation}</div>
            </div>
          ))}

          {dev && dev.available && (
            <>
              <div className="section-sub"><TrendingUp size={15} /> Referans Sapması (Teknik 3)</div>
              <div className="recommend">{dev.summary}</div>
            </>
          )}

          {card.hypotheses && (
            <>
              <div className="section-sub">Hipotez & Doğrulama</div>
              <table className="tl">
                <thead><tr><th>Hipotez</th><th>Beklenen Kanıt</th><th>Veri Sonucu</th><th>İhtimal</th></tr></thead>
                <tbody>
                  {card.hypotheses.map((h, i) => (
                    <tr key={i}>
                      <td>{h.hypothesis}</td>
                      <td className="muted">{h.expected}</td>
                      <td>{h.data_result}</td>
                      <td><span className={`badge ${likeClass(h.likelihood)}`}>{h.likelihood}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <div className="section-sub">Olay Çizelgesi (±{card.timeline.window_min} dk)</div>
          <Timeline tl={card.timeline} />

          {card.downtime_context && (
            <>
              <div className="section-sub">Downtime Köprüsü → What-If/ROI</div>
              <div className="kv"><span className="k">Vardiya günü</span><span className="v">{card.downtime_context.shift_date}</span></div>
              <div className="kv"><span className="k">Toplam plansız duruş</span><span className="v" style={{ color: 'var(--red)' }}>{card.downtime_context.total_unplanned_h.toFixed(1)} saat</span></div>
              <div className="small muted" style={{ marginTop: 6 }}>{card.downtime_context.note}</div>
            </>
          )}
        </>
      )}
    </Card>
  )
}

function TlIcon({ type }) {
  if (type === 'alarm') return <AlertTriangle size={15} color="#e2483d" />
  if (type === 'tel') return <Activity size={15} color="#2b6cf0" />
  if (type === 'planli') return <PauseCircle size={15} color="#f0a52b" />
  return <Ban size={15} color="#e2483d" />
}

function Timeline({ tl }) {
  const rows = []
  tl.alerts.forEach((a) => rows.push({ t: a.time, type: 'alarm', label: 'Alarm', detail: a.message }))
  tl.telemetry.forEach((x) => rows.push({ t: x.time, type: 'tel', label: 'Telemetri', detail: `${x.signal} = ${x.value}` }))
  tl.stoppages.forEach((s) => rows.push({
    t: s.started_on, type: s.is_planned ? 'planli' : 'plansiz',
    label: s.is_planned ? 'Planlı duruş' : 'Plansız duruş',
    detail: `${s.reason} (${fmtHM(s.duration_ms)})`,
  }))
  rows.sort((a, b) => new Date(a.t) - new Date(b.t))

  if (!rows.length) return <div className="muted small">Pencerede olay yok.</div>
  return (
    <table className="tl">
      <thead><tr><th>Saat</th><th>Tür</th><th>Detay</th></tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td className="t">{time(r.t)}</td>
            <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><TlIcon type={r.type} />{r.label}</span></td>
            <td>{r.detail}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
