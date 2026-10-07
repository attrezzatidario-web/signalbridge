export const money = (v, cur = 'EUR') =>
  v == null ? '—' : new Intl.NumberFormat('it-IT', { style: 'currency', currency: cur || 'EUR', maximumFractionDigits: 2 }).format(v)

export const num = (v, d) => {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return d == null ? String(+n.toFixed(5)) : n.toFixed(d)
}

export const ago = (iso) => {
  if (!iso) return '—'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.floor(s)}s fa`
  if (s < 3600) return `${Math.floor(s / 60)}m fa`
  if (s < 86400) return `${Math.floor(s / 3600)}h fa`
  return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: 'short' })
}

export const time = (iso) => iso ? new Date(iso).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }) : ''

export const pnlClass = (v) => (v > 0 ? 'text-up' : v < 0 ? 'text-down' : 'text-mute')

export const ACTION_LABEL = {
  close_all: 'Chiudi tutto', close_partial: 'Chiusura parziale', move_sl_be: 'SL a pareggio',
  modify_sl: 'Modifica SL', modify_tp: 'Modifica TP', cancel: 'Annulla ordine', info: 'Report',
}

export const STATUS = {
  executed: ['Eseguito', 'bg-up/15 text-up'],
  partial: ['Parziale', 'bg-amber-500/15 text-amber-400'],
  skipped: ['Saltato', 'bg-zinc-500/15 text-zinc-400'],
  error: ['Errore', 'bg-down/15 text-down'],
  ignored: ['Ignorato', 'bg-zinc-500/10 text-zinc-500'],
  received: ['Ricevuto', 'bg-accent/15 text-accent'],
}
