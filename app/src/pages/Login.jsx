import { useState } from 'react'
import { login } from '../lib/api'

export default function Login({ onDone }) {
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const go = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try { await login(pw); onDone() } catch (x) { setErr(x.message) }
    setBusy(false)
  }

  return (
    <div className="min-h-full flex items-center justify-center p-6">
      <form onSubmit={go} className="w-full max-w-sm">
        <img src={import.meta.env.BASE_URL + 'icon.svg'} className="w-12 h-12 mb-6" alt="" />
        <h1 className="text-xl font-semibold mb-6">SignalBridge</h1>
        <div className="space-y-3">
          <input type="password" autoComplete="current-password" placeholder="Password" value={pw} onChange={e => setPw(e.target.value)} autoFocus />
          {err && <div className="text-sm text-down">{err}</div>}
          <button disabled={busy || !pw} className="btn-primary w-full">Entra</button>
        </div>
      </form>
    </div>
  )
}
