import { useState } from 'react'
import { Power, X } from 'lucide-react'
import { useRow, useTick } from '../lib/live'
import { command } from '../lib/api'
import { money, num, ago, pnlClass } from '../lib/fmt'
import { Dot, Toggle, Empty } from '../components/ui'

export default function Home() {
  useTick(3000)
  const [st] = useRow('status')
  const [set, updateSet] = useRow('settings')
  const [busy, setBusy] = useState(null)

  const online = st?.last_seen && Date.now() - new Date(st.last_seen).getTime() < 20000 && st.engine_online
  const pos = st?.positions || []
  const floating = pos.reduce((a, p) => a + (p.profit || 0), 0)
  const today = st?.equity != null && st?.day_start_balance ? st.equity - st.day_start_balance : null
  const cur = st?.currency

  const close = async (ticket) => {
    if (!confirm('Chiudere questa posizione?')) return
    setBusy(ticket); try { await command('close_ticket', { ticket }) } catch (e) { alert(e.message) } setBusy(null)
  }
  const closeAll = async () => {
    if (!confirm(`Chiudere TUTTE le ${pos.length} posizioni/ordini del bot?`)) return
    setBusy('all'); try { await command('close_all', {}) } catch (e) { alert(e.message) } setBusy(null)
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Home</h1>
        <span className="text-xs text-mute">{st?.last_seen ? `agg. ${ago(st.last_seen)}` : ''}</span>
      </header>

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <Dot ok={online} label="Motore" />
        <Dot ok={online && st?.mt5_connected} label="MT5" />
        <Dot ok={online && st?.tg_connected} label="Telegram" />
        {st?.account_login && (
          <span className={`text-xs ${st.account_demo ? 'text-mute' : 'text-amber-400'}`}>
            {st.account_demo ? 'DEMO' : 'REALE'} · {st.account_login} · {st.account_server}
          </span>
        )}
      </div>
      {st?.message && <div className="text-xs text-amber-400">{st.message}</div>}
      {!online && <div className="card p-4 text-sm text-mute">Il motore non è attivo. Controlla che AVVIA.bat sia aperto sulla VPS.</div>}

      {/* interruttore generale */}
      <div className={`card p-5 flex items-center justify-between ${set?.trading_enabled ? 'border-up/40' : ''}`}>
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${set?.trading_enabled ? 'bg-up/15 text-up' : 'bg-line text-mute'}`}>
            <Power size={20} />
          </div>
          <div>
            <div className="font-semibold">{set?.trading_enabled ? 'Trading attivo' : 'Trading spento'}</div>
            <div className="text-xs text-mute">{set?.trading_enabled ? 'I segnali vengono eseguiti' : 'I segnali vengono solo registrati'}</div>
          </div>
        </div>
        <Toggle size="lg" on={!!set?.trading_enabled} onChange={(v) => updateSet({ trading_enabled: v })} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Saldo" value={money(st?.balance, cur)} />
        <Stat label="Equity" value={money(st?.equity, cur)} />
        <Stat label="Oggi" value={money(today, cur)} cls={pnlClass(today)} />
        <Stat label="Flottante" value={money(floating, cur)} cls={pnlClass(floating)} />
      </div>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-medium">Posizioni aperte <span className="text-mute">({pos.length})</span></h2>
          {pos.length > 0 && <button onClick={closeAll} disabled={busy === 'all'} className="btn-danger !py-1.5 !px-3 text-xs">Chiudi tutto</button>}
        </div>
        {pos.length === 0 ? <div className="card"><Empty>Nessuna posizione aperta</Empty></div> : (
          <div className="card divide-y divide-line">
            {pos.map(p => (
              <div key={p.ticket} className="flex items-center gap-3 px-4 py-3">
                <div className={`text-[11px] font-semibold w-11 text-center rounded-md py-1 ${p.kind === 'order' ? 'bg-line text-mute' : p.side === 'BUY' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'}`}>
                  {p.kind === 'order' ? 'PEND' : p.side}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{p.symbol} <span className="text-mute font-normal num">{num(p.volume)}</span></div>
                  <div className="text-[11px] text-mute truncate num">
                    {num(p.price_open)} · SL {num(p.sl) || '—'} · TP {p.tp ? num(p.tp) : '—'}{p.channel ? ` · ${p.channel}` : ''}
                  </div>
                </div>
                {p.kind !== 'order' && <div className={`text-sm font-medium num ${pnlClass(p.profit)}`}>{num(p.profit, 2)}</div>}
                <button onClick={() => close(p.ticket)} disabled={busy === p.ticket} className="text-mute hover:text-down p-1"><X size={18} /></button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function Stat({ label, value, cls = '' }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-mute mb-1">{label}</div>
      <div className={`text-lg font-semibold num ${cls}`}>{value}</div>
    </div>
  )
}
