import { useMemo, useState } from 'react'
import { RefreshCw, Search, ChevronRight } from 'lucide-react'
import { useLiveTable } from '../lib/live'
import { api, command } from '../lib/api'
import { ago } from '../lib/fmt'
import { Toggle, Sheet, Segmented, Field, Row, Empty } from '../components/ui'

const RISK = [['fixed_lot', 'Lotto fisso'], ['risk_pct', '% saldo'], ['fixed_money', '€ fissi']]
const RISK_UNIT = { fixed_lot: 'lotti', risk_pct: '% del saldo a rischio', fixed_money: '€ a rischio per segnale' }
const TPM = [['split', 'Dividi sui TP'], ['first', 'Solo TP1'], ['last', 'Solo ultimo']]

export default function Groups() {
  const [rows, loading, setRows] = useLiveTable('channels', { order: 'title', asc: true, limit: 1000 })
  const [q, setQ] = useState('')
  const [onlyOn, setOnlyOn] = useState(false)
  const [sel, setSel] = useState(null)
  const [busy, setBusy] = useState(false)

  const save = async (id, patch) => {
    setRows(r => r.map(c => (c.id === id ? { ...c, ...patch } : c)))
    try { await api('PATCH', `/api/channels/${id}`, patch) } catch (e) { alert(e.message) }
  }

  const list = useMemo(() => {
    const s = q.trim().toLowerCase()
    return rows
      .filter(c => (!onlyOn || c.enabled) && (!s || c.title.toLowerCase().includes(s)))
      .sort((a, b) => (b.enabled - a.enabled) || a.title.localeCompare(b.title))
  }, [rows, q, onlyOn])
  const active = rows.filter(c => c.enabled).length
  const cur = rows.find(c => c.id === sel)

  const refresh = async () => {
    setBusy(true)
    try { const r = await command('refresh_channels', {}); alert(`Lista aggiornata. Nuovi: ${r.result?.new ?? 0}`) } catch (e) { alert(e.message) }
    setBusy(false)
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Gruppi</h1>
          <div className="text-xs text-mute">{active} attivi su {rows.length}</div>
        </div>
        <button onClick={refresh} disabled={busy} className="btn-ghost !px-3"><RefreshCw size={16} className={busy ? 'animate-spin' : ''} /></button>
      </header>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
          <input className="!pl-9" placeholder="Cerca gruppo" value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <button onClick={() => setOnlyOn(!onlyOn)} className={`btn !px-3 text-xs border ${onlyOn ? 'border-up/50 text-up' : 'border-line text-mute'}`}>Attivi</button>
      </div>

      {!loading && rows.length === 0 && <Empty>Nessun gruppo. Avvia il motore: la lista dei tuoi gruppi Telegram comparirà qui.</Empty>}

      <div className="card divide-y divide-line">
        {list.map(c => (
          <div key={c.id} onClick={() => setSel(c.id)} className="flex items-center gap-3 px-4 py-3 cursor-pointer active:bg-line/30">
            <div className="min-w-0 flex-1">
              <div className={`text-sm truncate ${c.enabled ? 'text-white' : 'text-zinc-400'}`}>{c.title}</div>
              <div className="text-[11px] text-mute truncate">
                {c.enabled ? `${RISK.find(r => r[0] === c.risk_mode)?.[1]} ${c.risk_value} · ${c.trades_count} trade` : c.kind === 'channel' ? 'Canale' : 'Gruppo'}
                {c.last_message_at ? ` · ${ago(c.last_message_at)}` : ''}
              </div>
            </div>
            <Toggle on={c.enabled} onChange={(v) => save(c.id, { enabled: v })} />
            <ChevronRight size={16} className="text-mute" />
          </div>
        ))}
      </div>

      <Sheet open={!!cur} onClose={() => setSel(null)} title={cur?.title}>
        {cur && <GroupForm c={cur} save={(p) => save(cur.id, p)} />}
      </Sheet>
    </div>
  )
}

function NumInput({ value, onSave, step = 'any' }) {
  const [v, setV] = useState(value ?? '')
  return (
    <input type="number" inputMode="decimal" step={step} value={v}
      onChange={e => setV(e.target.value)}
      onBlur={() => { const n = parseFloat(String(v).replace(',', '.')); if (!isNaN(n) && n !== Number(value)) onSave(n) }} />
  )
}

function GroupForm({ c, save }) {
  return (
    <div className="space-y-5">
      <Row title="Copia i segnali di questo gruppo"><Toggle on={c.enabled} onChange={v => save({ enabled: v })} /></Row>

      <div className="space-y-3">
        <span className="label">Dimensione ordini</span>
        <Segmented value={c.risk_mode} onChange={v => save({ risk_mode: v, risk_value: v === 'fixed_lot' ? 0.01 : v === 'risk_pct' ? 1 : 50 })} options={RISK} />
        <div className="grid grid-cols-2 gap-3">
          <Field label={RISK_UNIT[c.risk_mode]}><NumInput key={c.risk_mode} value={c.risk_value} onSave={n => save({ risk_value: n })} /></Field>
          <Field label="Lotto massimo totale"><NumInput value={c.max_lot} onSave={n => save({ max_lot: n })} /></Field>
        </div>
      </div>

      <div className="space-y-2">
        <span className="label">Take profit multipli</span>
        <Segmented value={c.tp_mode} onChange={v => save({ tp_mode: v })} options={TPM} />
        <p className="text-[11px] text-mute">“Dividi” apre una posizione per ogni TP con il lotto diviso.</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="SL d'emergenza (pips)" hint="Se il segnale non ha SL. 0 = non aprire">
          <NumInput value={c.default_sl_pips} onSave={n => save({ default_sl_pips: n })} />
        </Field>
        <Field label="Scostamento max (pips)" hint="Oltre: ordine limit al prezzo del segnale. 0 = off">
          <NumInput value={c.max_slippage_pips} onSave={n => save({ max_slippage_pips: n })} />
        </Field>
      </div>

      <div className="divide-y divide-line">
        <Row title="SL a pareggio dopo TP1" hint="Automatico quando chiude il primo TP"><Toggle on={c.be_after_tp1} onChange={v => save({ be_after_tp1: v })} /></Row>
        <Row title="Segui aggiornamenti" hint="Chiudi, chiudi metà, BE, modifica SL/TP"><Toggle on={c.follow_updates} onChange={v => save({ follow_updates: v })} /></Row>
      </div>
    </div>
  )
}
