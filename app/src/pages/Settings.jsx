import { useState } from 'react'
import { LogOut, FlaskConical } from 'lucide-react'
import { useRow } from '../lib/live'
import { command, logout } from '../lib/api'
import { Toggle, Field, Row, Segmented } from '../components/ui'

export default function Settings() {
  const [s, update] = useRow('settings')
  if (!s) return null
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Impostazioni</h1>

      <section className="card px-4 divide-y divide-line">
        <Row title="Consenti conto REALE" hint="Spento = il bot opera solo su conti demo">
          <Toggle on={s.allow_real_account} onChange={v => {
            if (v && !confirm('Attenzione: il bot potrà aprire ordini con soldi veri. Confermi?')) return
            update({ allow_real_account: v })
          }} />
        </Row>
        <Row title="Usa Gemini AI" hint="Per i messaggi che le regole non capiscono"><Toggle on={s.ai_enabled} onChange={v => update({ ai_enabled: v })} /></Row>
      </section>

      <section className="card p-4 space-y-4">
        <h2 className="text-sm font-medium">Sicurezza</h2>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Max posizioni aperte"><Num value={s.max_open_positions} onSave={n => update({ max_open_positions: Math.round(n) })} /></Field>
          <Field label="Stop perdita giornaliera %" hint="0 = disattivato"><Num value={s.daily_loss_limit_pct} onSave={n => update({ daily_loss_limit_pct: n })} /></Field>
        </div>
      </section>

      <section className="card p-4 space-y-4">
        <h2 className="text-sm font-medium">Broker</h2>
        <Field label="Suffisso simboli" hint="Es. XAUUSD.m → scrivi .m (vuoto se non serve)">
          <Text value={s.symbol_suffix} onSave={v => update({ symbol_suffix: v })} />
        </Field>
        <Aliases value={s.symbol_aliases} onSave={v => update({ symbol_aliases: v })} />
      </section>

      <section className="card p-4 space-y-3">
        <h2 className="text-sm font-medium">Default per nuovi gruppi</h2>
        <Segmented value={s.default_risk_mode} onChange={v => update({ default_risk_mode: v })}
          options={[['fixed_lot', 'Lotto fisso'], ['risk_pct', '% saldo'], ['fixed_money', '€ fissi']]} />
        <Field label="Valore"><Num value={s.default_risk_value} onSave={n => update({ default_risk_value: n })} /></Field>
      </section>

      <Tester />

      <button onClick={async () => { await logout().catch(() => {}); location.reload() }} className="btn-ghost w-full"><LogOut size={16} />Esci</button>
      <p className="text-center text-[11px] text-mute pb-4">SignalBridge 1.1</p>
    </div>
  )
}

function Num({ value, onSave }) {
  const [v, setV] = useState(value ?? '')
  return <input type="number" inputMode="decimal" value={v} onChange={e => setV(e.target.value)}
    onBlur={() => { const n = parseFloat(String(v).replace(',', '.')); if (!isNaN(n) && n !== Number(value)) onSave(n) }} />
}
function Text({ value, onSave }) {
  const [v, setV] = useState(value ?? '')
  return <input value={v} onChange={e => setV(e.target.value)} onBlur={() => v !== value && onSave(v.trim())} />
}

function Aliases({ value, onSave }) {
  const toText = (o) => Object.entries(o || {}).map(([k, v]) => `${k}=${v}`).join('\n')
  const [t, setT] = useState(toText(value))
  const save = () => {
    const o = {}
    t.split('\n').forEach(l => { const [k, v] = l.split('=').map(x => x?.trim().toUpperCase()); if (k && v) o[k] = v })
    onSave(o)
  }
  return (
    <Field label="Nomi alternativi (uno per riga: NOME=SIMBOLO)" hint="Es. GOLD=XAUUSD, NASDAQ=NAS100">
      <textarea rows={5} className="font-mono text-xs" value={t} onChange={e => setT(e.target.value)} onBlur={save} />
    </Field>
  )
}

function Tester() {
  const [text, setText] = useState('')
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true); setRes(null)
    try { const r = await command('parse_test', { text }); setRes(r.result) } catch (e) { setRes({ error: e.message }) }
    setBusy(false)
  }
  return (
    <section className="card p-4 space-y-3">
      <h2 className="text-sm font-medium flex items-center gap-2"><FlaskConical size={16} />Prova un segnale</h2>
      <p className="text-xs text-mute">Incolla un messaggio di un gruppo per vedere come lo legge il bot (nessun ordine viene aperto).</p>
      <textarea rows={5} value={text} onChange={e => setText(e.target.value)} placeholder={'XAUUSD BUY 2650\nSL 2640\nTP 2660'} />
      <button onClick={run} disabled={!text.trim() || busy} className="btn-primary w-full">{busy ? 'Analisi…' : 'Analizza'}</button>
      {res && (
        <pre className="text-xs bg-bg border border-line rounded-xl p-3 overflow-x-auto whitespace-pre-wrap">
          {res.error ? res.error : res.parsed ? `Letto con: ${res.parser === 'ai' ? 'Gemini AI' : 'regole'}\n\n${JSON.stringify(res.parsed, null, 2)}` : 'Non riconosciuto come segnale o aggiornamento.'}
        </pre>
      )}
    </section>
  )
}
