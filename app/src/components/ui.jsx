import { useEffect } from 'react'
import { X } from 'lucide-react'
import { STATUS } from '../lib/fmt'

export function Toggle({ on, onChange, size = 'md', disabled }) {
  const w = size === 'lg' ? 'w-14 h-8' : 'w-11 h-6'
  const k = size === 'lg' ? 'w-6 h-6' : 'w-4 h-4'
  const tx = size === 'lg' ? 'translate-x-6' : 'translate-x-5'
  return (
    <button type="button" disabled={disabled} onClick={(e) => { e.stopPropagation(); onChange(!on) }}
      className={`${w} shrink-0 rounded-full p-1 transition-colors ${on ? 'bg-up' : 'bg-line'} disabled:opacity-40`}>
      <span className={`${k} block rounded-full bg-white transition-transform ${on ? tx : ''}`} />
    </button>
  )
}

export function Segmented({ value, onChange, options }) {
  return (
    <div className="flex bg-bg border border-line rounded-xl p-1 gap-1">
      {options.map(([v, l]) => (
        <button key={v} type="button" onClick={() => onChange(v)}
          className={`flex-1 rounded-lg py-1.5 text-xs font-medium transition ${value === v ? 'bg-line text-white' : 'text-mute'}`}>
          {l}
        </button>
      ))}
    </div>
  )
}

export function Badge({ status }) {
  const [l, c] = STATUS[status] || [status, 'bg-line text-mute']
  return <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${c}`}>{l}</span>
}

export function Dot({ ok, label }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-mute">
      <span className={`w-2 h-2 rounded-full ${ok ? 'bg-up' : 'bg-down'}`} />{label}
    </span>
  )
}

export function Sheet({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', k); document.body.style.overflow = '' }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full md:max-w-lg max-h-[90vh] overflow-y-auto bg-card border border-line rounded-t-3xl md:rounded-3xl safe-b">
        <div className="sticky top-0 bg-card flex items-center justify-between px-5 pt-4 pb-3 border-b border-line">
          <h3 className="font-semibold truncate pr-4">{title}</h3>
          <button onClick={onClose} className="text-mute p-1"><X size={20} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-mute/80 mt-1">{hint}</span>}
    </label>
  )
}

export function Row({ title, hint, children }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <div className="text-sm">{title}</div>
        {hint && <div className="text-xs text-mute">{hint}</div>}
      </div>
      {children}
    </div>
  )
}

export function Empty({ children }) {
  return <div className="text-center text-sm text-mute py-16">{children}</div>
}
