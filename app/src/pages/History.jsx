import { useMemo, useState } from 'react'
import { useLiveTable, useRow } from '../lib/live'
import { money, num, ago, pnlClass } from '../lib/fmt'
import { Empty, Segmented } from '../components/ui'

const RANGES = [['1', 'Oggi'], ['7', '7 giorni'], ['30', '30 giorni'], ['all', 'Tutto']]

export default function History() {
  const [rows, loading] = useLiveTable('trades', { order: 'opened_at', limit: 2000 })
  const [st] = useRow('status')
  const [range, setRange] = useState('7')
  const [view, setView] = useState('groups')

  const closed = useMemo(() => {
    const from = range === 'all' ? 0 : range === '1' ? new Date().setHours(0, 0, 0, 0) : Date.now() - Number(range) * 86400000
    return rows.filter(t => t.status === 'closed' && new Date(t.closed_at || t.opened_at).getTime() >= from)
  }, [rows, range])

  const groups = useMemo(() => {
    const m = {}
    for (const t of closed) {
      const g = (m[t.channel_title || '—'] ||= { name: t.channel_title || '—', n: 0, win: 0, pnl: 0 })
      g.n++; g.pnl += Number(t.profit || 0); if (Number(t.profit) > 0) g.win++
    }
    return Object.values(m).sort((a, b) => b.pnl - a.pnl)
  }, [closed])

  const tot = closed.reduce((a, t) => a + Number(t.profit || 0), 0)
  const wins = closed.filter(t => Number(t.profit) > 0).length
  const cur = st?.currency

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Storico</h1>
      <Segmented value={range} onChange={setRange} options={RANGES} />

      <div className="grid grid-cols-3 gap-3">
        <div className="card p-4"><div className="text-xs text-mute">Risultato</div><div className={`text-lg font-semibold num ${pnlClass(tot)}`}>{money(tot, cur)}</div></div>
        <div className="card p-4"><div className="text-xs text-mute">Trade</div><div className="text-lg font-semibold num">{closed.length}</div></div>
        <div className="card p-4"><div className="text-xs text-mute">Vincenti</div><div className="text-lg font-semibold num">{closed.length ? Math.round(wins / closed.length * 100) : 0}%</div></div>
      </div>

      <Segmented value={view} onChange={setView} options={[['groups', 'Per gruppo'], ['trades', 'Operazioni']]} />

      {!loading && closed.length === 0 && <Empty>Nessuna operazione chiusa nel periodo</Empty>}

      {view === 'groups' ? (
        groups.length > 0 && (
          <div className="card divide-y divide-line">
            {groups.map(g => (
              <div key={g.name} className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="text-sm truncate">{g.name}</div>
                  <div className="text-[11px] text-mute">{g.n} trade · {Math.round(g.win / g.n * 100)}% vincenti</div>
                </div>
                <div className={`text-sm font-medium num ${pnlClass(g.pnl)}`}>{money(g.pnl, cur)}</div>
              </div>
            ))}
          </div>
        )
      ) : (
        closed.length > 0 && (
          <div className="card divide-y divide-line">
            {closed.slice(0, 300).map(t => (
              <div key={t.id} className="flex items-center gap-3 px-4 py-3">
                <div className={`text-[11px] font-semibold w-11 text-center rounded-md py-1 ${t.side === 'BUY' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'}`}>{t.side}</div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm">{t.symbol} <span className="text-mute num">{num(t.volume)}</span></div>
                  <div className="text-[11px] text-mute truncate num">{num(t.open_price)} → {num(t.close_price)} · {t.channel_title} · {ago(t.closed_at)}</div>
                </div>
                <div className={`text-sm font-medium num ${pnlClass(t.profit)}`}>{num(t.profit, 2)}</div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
