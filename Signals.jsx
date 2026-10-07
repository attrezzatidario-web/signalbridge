import { useMemo, useState } from 'react'
import { useLiveTable, useTick } from '../lib/live'
import { ago, num, ACTION_LABEL } from '../lib/fmt'
import { Badge, Empty, Segmented } from '../components/ui'

const FILTERS = [['all', 'Tutti'], ['executed', 'Eseguiti'], ['skipped', 'Saltati'], ['error', 'Errori']]

export default function Signals() {
  useTick(15000)
  const [rows, loading] = useLiveTable('signals', { order: 'created_at', limit: 150 })
  const [f, setF] = useState('all')
  const [open, setOpen] = useState(null)

  const list = useMemo(() => rows.filter(r => {
    if (f === 'all') return r.status !== 'ignored'
    if (f === 'executed') return r.status === 'executed' || r.status === 'partial'
    return r.status === f
  }), [rows, f])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Segnali</h1>
      <Segmented value={f} onChange={setF} options={FILTERS} />
      {!loading && list.length === 0 && <Empty>Nessun segnale ancora</Empty>}
      <div className="space-y-2">
        {list.map(s => (
          <button key={s.id} onClick={() => setOpen(open === s.id ? null : s.id)} className="card w-full text-left p-4 block">
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <span className="text-xs text-mute truncate">{s.channel_title} · {ago(s.created_at)}{s.parser === 'ai' ? ' · AI' : ''}{s.edited ? ' · modificato' : ''}</span>
              <Badge status={s.status} />
            </div>
            <Summary s={s} />
            {s.reason && <div className="text-xs text-mute mt-1.5">{s.reason}</div>}
            {open === s.id && <pre className="mt-3 text-xs text-zinc-400 whitespace-pre-wrap font-sans bg-bg rounded-xl p-3 border border-line">{s.text}</pre>}
          </button>
        ))}
      </div>
    </div>
  )
}

function Summary({ s }) {
  const p = s.parsed || {}
  if (s.kind === 'update') {
    return (
      <div className="text-sm font-medium">
        {ACTION_LABEL[p.action] || p.action}
        {p.percent ? ` ${p.percent}%` : ''}{p.price ? ` → ${num(p.price)}` : ''}
        {p.symbol && <span className="text-mute font-normal"> · {p.symbol}</span>}
      </div>
    )
  }
  if (s.kind !== 'signal') return <div className="text-sm text-mute">—</div>
  const entry = p.entry_range ? `${num(p.entry_range[0])}–${num(p.entry_range[1])}` : p.entry ? num(p.entry) : 'mercato'
  return (
    <div>
      <div className="text-sm font-semibold">
        <span className={p.side === 'BUY' ? 'text-up' : 'text-down'}>{p.side}</span> {p.symbol}
        {p.order_type && p.order_type !== 'market' && <span className="text-mute font-normal"> {p.order_type}</span>}
        <span className="text-mute font-normal num"> @ {entry}</span>
      </div>
      <div className="text-xs text-mute num mt-0.5">
        SL {p.sl ? num(p.sl) : p.sl_pips ? `${p.sl_pips} pips` : '—'} · TP {(p.tps?.length ? p.tps.map(x => num(x)).join(' / ') : p.tp_pips?.length ? p.tp_pips.join('/') + ' pips' : '—')}
      </div>
    </div>
  )
}
