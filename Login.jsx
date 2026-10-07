import { useState } from 'react'
import { sb, clearConn } from '../lib/supa'

export default function Login({ onReset }) {
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const go = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    const { error } = await sb().auth.signInWithPassword({ email, password: pw })
    if (error) setErr(error.message === 'Invalid login credentials' ? 'Email o password errati' : error.message)
    setBusy(false)
  }

  return (
    <div className="min-h-full flex items-center justify-center p-6">
      <form onSubmit={go} className="w-full max-w-sm">
        <img src={import.meta.env.BASE_URL + "icon.svg"} className="w-12 h-12 mb-6" alt="" />
        <h1 className="text-xl font-semibold mb-6">SignalBridge</h1>
        <div className="space-y-3">
          <input type="email" autoComplete="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
          <input type="password" autoComplete="current-password" placeholder="Password" value={pw} onChange={e => setPw(e.target.value)} />
          {err && <div className="text-sm text-down">{err}</div>}
          <button disabled={busy} className="btn-primary w-full">Entra</button>
        </div>
        <button type="button" onClick={() => { clearConn(); onReset() }} className="text-xs text-mute mt-8">Cambia progetto Supabase</button>
      </form>
    </div>
  )
}
