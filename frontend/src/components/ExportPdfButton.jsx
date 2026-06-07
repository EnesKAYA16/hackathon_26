import { useState } from 'react'
import { FileDown, Loader2 } from 'lucide-react'
import { exportToPdf } from '../pdf.js'

// Tarih seçicinin yanına hizalı "PDF Aktar" butonu. Aktif görünümü PDF'e döker.
export default function ExportPdfButton({ pageTitle, machine, dateLabel }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const onClick = async () => {
    if (busy) return
    setBusy(true)
    setErr(null)
    try {
      // Grafiklerin tam çizilmesi için bir kare bekle.
      await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 60)))
      await exportToPdf({ pageTitle, machine, dateLabel })
    } catch (e) {
      setErr(e.message || 'PDF oluşturulamadı')
    } finally {
      setBusy(false)
    }
  }

  return (
    <button className="pdf-btn" onClick={onClick} disabled={busy}
            title={err ? `Hata: ${err}` : 'Bu sayfayı PDF olarak indir'}>
      {busy ? <Loader2 size={16} className="spin-ic" /> : <FileDown size={16} />}
      <span>{busy ? 'Hazırlanıyor…' : 'PDF Aktar'}</span>
    </button>
  )
}
