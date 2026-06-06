import { useEffect, useMemo, useRef, useState } from 'react'
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react'

const DOW = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
const MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

// Tarih ARALIĞI seçici. Verisi olmayan günler soluk + tıklanamaz.
export default function DateRangePicker({ availableDates, start, end, onChange }) {
  const avail = useMemo(() => new Set(availableDates), [availableDates])
  const [open, setOpen] = useState(false)
  const [view, setView] = useState(() => new Date((end || availableDates?.[availableDates.length - 1] || iso(new Date())) + 'T00:00'))
  const ref = useRef(null)

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  useEffect(() => { if (end) setView(new Date(end + 'T00:00')) }, [end, open])

  const y = view.getFullYear(), mo = view.getMonth()
  const startDow = (new Date(y, mo, 1).getDay() + 6) % 7
  const daysInMonth = new Date(y, mo + 1, 0).getDate()
  const cells = [...Array(startDow).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => new Date(y, mo, i + 1))]

  const inRange = (s) => start && end && s > start && s < end
  const click = (d) => {
    const s = iso(d)
    // Soluk (verisiz) günler de seçilebilir; sadece görsel olarak soluk.
    if (!start || end) {
      onChange({ start: s, end: null })            // 1. tık: yeni başlangıç (bitişi boşalt)
    } else if (s >= start) {
      onChange({ start, end: s }); setOpen(false)  // 2. tık: bitiş -> aralık tamam
    } else {
      onChange({ start: s, end: null })            // başlangıçtan önce -> yeni başlangıç
    }
  }

  return (
    <div className="rangepick" ref={ref}>
      <button className="rangepick-btn" onClick={() => setOpen((o) => !o)}>
        <Calendar size={16} /> <b>{start || '—'}</b><span className="arr">→</span><b>{end || '—'}</b>
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
              if (!has) cls.push('nodata')  // verisiz: soluk ama yine de seçilebilir
              if (s === start || s === end) cls.push('sel')
              else if (inRange(s)) cls.push('inrange')
              return (
                <button key={i} type="button" className={cls.join(' ')} onClick={() => click(d)}>
                  {d.getDate()}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
