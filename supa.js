import { createClient } from '@supabase/supabase-js'

const KEY = 'sb_conn'
let client = null

export function getConn() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null') } catch { return null }
}
export function setConn(url, anon) {
  localStorage.setItem(KEY, JSON.stringify({ url: url.trim().replace(/\/$/, ''), anon: anon.trim() }))
  client = null
}
export function clearConn() { localStorage.removeItem(KEY); client = null }

export function sb() {
  if (client) return client
  const c = getConn()
  if (!c) return null
  client = createClient(c.url, c.anon, { auth: { persistSession: true, autoRefreshToken: true } })
  return client
}

/** Invia un comando al motore. Con wait=true attende il risultato (max 15s). */
export async function command(type, payload = {}, wait = false) {
  const { data, error } = await sb().from('commands').insert({ type, payload }).select().single()
  if (error) throw error
  if (!wait) return data
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 500))
    const { data: d } = await sb().from('commands').select('*').eq('id', data.id).single()
    if (d && d.status !== 'pending') return d
  }
  throw new Error('Il motore non risponde')
}
