import { useEffect, useState } from 'react'
import { api } from './api'

// ---------- un'unica connessione WebSocket condivisa ----------
const subs = new Set()        // fn({t,row}) | fn({reconnect:true})
let ws = null
let retry = 0

function connect() {
  if (ws && ws.readyState <= 1) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws`)
  ws.onopen = () => { if (retry > 0) subs.forEach(fn => fn({ reconnect: true })); retry = 0 }
  ws.onmessage = (e) => { try { const m = JSON.parse(e.data); subs.forEach(fn => fn(m)) } catch { /* */ } }
  ws.onclose = () => { ws = null; if (subs.size) setTimeout(connect, Math.min(10000, 1000 * 2 ** retry++)) }
}
function subscribe(fn) {
  subs.add(fn); connect()
  return () => { subs.delete(fn); if (!subs.size && ws) { ws.close(); ws = null } }
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && subs.size) { connect(); subs.forEach(fn => fn({ reconnect: true })) }
})

const sortRows = (rows, order, asc) => [...rows].sort((a, b) => {
  const x = a[order], y = b[order]
  const c = x == null ? -1 : y == null ? 1 : typeof x === 'string' ? x.localeCompare(y) : x - y
  return asc ? c : -c
})

/** Tabella con aggiornamenti live */
export function useLiveTable(table, { order = 'id', asc = false, limit = 200, key = 'id' } = {}) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    const load = () => api('GET', `/api/${table}?limit=${limit}`)
      .then(d => { if (alive) { setRows(sortRows(d, order, asc).slice(0, limit)); setLoading(false) } })
      .catch(() => alive && setLoading(false))
    load()
    const off = subscribe((m) => {
      if (m.reconnect) return load()
      if (m.t !== table || !m.row) return
      setRows(prev => {
        const i = prev.findIndex(r => r[key] === m.row[key])
        const next = i >= 0 ? prev.map((r, j) => (j === i ? { ...r, ...m.row } : r)) : [m.row, ...prev]
        return sortRows(next, order, asc).slice(0, limit)
      })
    })
    return () => { alive = false; off() }
  }, [table, order, asc, limit, key])

  return [rows, loading, setRows]
}

/** Oggetto singolo: 'settings' o 'status' */
export function useRow(table) {
  const [row, setRow] = useState(null)
  useEffect(() => {
    let alive = true
    const load = () => api('GET', `/api/${table}`).then(d => alive && setRow(d)).catch(() => {})
    load()
    const off = subscribe((m) => {
      if (m.reconnect) return load()
      if (m.t === table && m.row) setRow(m.row)
    })
    return () => { alive = false; off() }
  }, [table])
  const update = async (patch) => {
    setRow(r => ({ ...r, ...patch }))
    try { setRow(await api('PATCH', `/api/${table}`, patch)) } catch (e) { alert(e.message) }
  }
  return [row, update]
}

/** Forza un re-render periodico (per "x secondi fa") */
export function useTick(ms = 5000) {
  const [, set] = useState(0)
  useEffect(() => { const t = setInterval(() => set(x => x + 1), ms); return () => clearInterval(t) }, [ms])
}
