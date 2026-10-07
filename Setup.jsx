import { useState } from 'react'
import { setConn } from '../lib/supa'

export default function Setup({ onDone }) {
  const [url, setUrl] = useState('')
  const [anon, setAnon] = useState('')
  const ok = url.startsWith('https://') && anon.length > 30
  return (
    <div className="min-h-full flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <img src={import.meta.env.BASE_URL + "icon.svg"} className="w-12 h-12 mb-6" alt="" />
        <h1 className="text-xl font-semibold mb-1">Collega Supabase</h1>
        <p className="text-sm text-mute mb-6">Solo la prima volta. Li trovi in Supabase → Project Settings → API.</p>
        <div className="space-y-3">
          <input placeholder="Project URL (https://...supabase.co)" value={url} onChange={e => setUrl(e.target.value)} />
          <input placeholder="anon public key" value={anon} onChange={e => setAnon(e.target.value)} />
          <button disabled={!ok} className="btn-primary w-full" onClick={() => { setConn(url, anon); onDone() }}>Continua</button>
        </div>
      </div>
    </div>
  )
}
