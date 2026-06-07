import { useEffect, useMemo, useRef, useState } from 'react'
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react'
import { fmtDate } from '../api.js'

const DOW = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
const MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

// Tarih ARALIĞI seçici. Verisi olmayan günler soluk + tıklanamaz.
export default function DateRangePicker({ availableDates, start, end, onChange, single = false }) {
  const avail = useMemo(() => new Set(availableDates), [availableDates])
  const [open, setOpen] = useState(false)
  const [anchor, setAnchor] = useState(null)  // aralık seçiminde 1. tık (iç state)
  const [view, setView] = useState(() => new Date((end || availableDates?.[availableDates.length - 1] || iso(new Date())) + 'T00:00'))
  const ref = useRef(null)

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  useEffect(() => { if (end) setView(new Date(end + 'T00:00')) }, [end, open])
  useEffect(() => { if (!open) setAnchor(null) }, [open])  // kapanınca seçimi sıfırla

  const y = view.getFullYear(), mo = view.getMonth()
  const startDow = (new Date(y, mo, 1).getDay() + 6) % 7
  const daysInMonth = new Date(y, mo + 1, 0).getDate()
  const cells = [...Array(startDow).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => new Date(y, mo, i + 1))]

  // Hızlı ön ayarlar — en son mevcut tarihe göre geriye doğru (aralık modu).
  const applyPreset = (kind) => {
    const dates = availableDates || []
    if (!dates.length) return
    const last = dates[dates.length - 1]          // mevcut en son gün
    const first = dates[0]                          // mevcut en eski gün
    const e = new Date(last + 'T00:00')
    const s = new Date(last + 'T00:00')
    if (kind === '7d') s.setDate(s.getDate() - 6)
    else if (kind === '1m') s.setMonth(s.getMonth() - 1)
    else if (kind === '3m') s.setMonth(s.getMonth() - 3)
    else if (kind === '6m') s.setMonth(s.getMonth() - 6)
    let si = iso(s)
    if (si < first) si = first                      // mevcut aralığın dışına taşma
    onChange({ start: si, end: iso(e) })
    setAnchor(null); setOpen(false)
  }

  const inRange = (s) => !single && start && end && s > start && s < end
  const click = (d) => {
    const s = iso(d)
    if (single) {
      if (!avail.has(s)) return                    // tek-gün: verisiz gün seçilemez
      onChange({ start: s, end: s }); setOpen(false)
      return
    }
    // Aralık modu — soluk (verisiz) günler de seçilebilir.
    // Aralık modu — iç "anchor" ile (bitiş ASLA null olmaz -> '-> -' bug'ı yok).
    if (anchor === null) {
      setAnchor(s); onChange({ start: s, end: s })          // 1. tık: başlangıç (end=start)
    } else if (s >= anchor) {
      onChange({ start: anchor, end: s }); setAnchor(null); setOpen(false)  // 2. tık: tamam
    } else {
      setAnchor(s); onChange({ start: s, end: s })          // başlangıçtan önce -> yeni başlangıç
    }
  }

  return (
    <div className="rangepick" ref={ref}>
      <button className="rangepick-btn" onClick={() => setOpen((o) => !o)}>
        <Calendar size={16} />
        {single
          ? <b>{start ? fmtDate(start) : '—'}</b>
          : <><b>{start ? fmtDate(start) : '—'}</b><span className="arr">→</span><b>{end ? fmtDate(end) : '—'}</b></>}
      </button>
      {open && (
        <div className="rangepick-pop">
          <div className="rp-head">
            <button type="button" onClick={() => setView(new Date(y, mo - 1, 1))}><ChevronLeft size={16} /></button>
            <span>{MONTHS[mo]} {y}</span>
            <button type="button" onClick={() => setView(new Date(y, mo + 1, 1))}><ChevronRight size={16} /></button>
          </div>
          <div className="rp-grid">
            {DOW.map((d) => <div key={d} className="rp-dow">{d}</div>)}
            {cells.map((d, i) => {
              if (!d) return <div key={i} />
              const s = iso(d), has = avail.has(s)
              const cls = ['rp-day']
              if (!has) cls.push('nodata')  // verisiz: soluk
              if (s === start || s === end) cls.push('sel')
              else if (inRange(s)) cls.push('inrange')
              return (
                <button key={i} type="button" className={cls.join(' ')}
                        disabled={single && !has} onClick={() => click(d)}>
                  {d.getDate()}
                </button>
              )
            })}
          </div>
          {!single && (
            <div className="rp-presets">
              <button type="button" onClick={() => applyPreset('7d')}>Son 7 Gün</button>
              <button type="button" onClick={() => applyPreset('1m')}>Son 1 Ay</button>
              <button type="button" onClick={() => applyPreset('3m')}>Son 3 Ay</button>
              <button type="button" onClick={() => applyPreset('6m')}>Son 6 Ay</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
