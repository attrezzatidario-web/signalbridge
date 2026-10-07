import { useEffect, useRef, useState } from 'react'
import { sb } from './supa'

let chanSeq = 0

/** Tabella con aggiornamenti realtime. key = colonna chiave. */
export function useLiveTable(table, { select = '*', order = 'id', asc = false, limit = 200, filter, key = 'id' } = {}) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const filterRef = useRef(filter)
  filterRef.current = filter

  useEffect(() => {
    let alive = true
    const load = async () => {
      let q = sb().from(table).select(select).order(order, { ascending: asc }).limit(limit)
      if (filterRef.current) q = filterRef.current(q)
      const { data } = await q
      if (alive) { setRows(data || []); setLoading(false) }
    }
    load()
    const ch = sb().channel(`${table}-${++chanSeq}`)
      .on('postgres_changes', { event: '*', schema: 'public', table }, (p) => {
        setRows(prev => {
          if (p.eventType === 'DELETE') return prev.filter(r => r[key] !== p.old[key])
          const i = prev.findIndex(r => r[key] === p.new[key])
          if (i >= 0) { const c = prev.slice(); c[i] = { ...c[i], ...p.new }; return c }
          return asc ? [...prev, p.new] : [p.new, ...prev].slice(0, limit)
        })
      })
      .subscribe()
    const onVis = () => document.visibilityState === 'visible' && load()
    document.addEventListener('visibilitychange', onVis)
    return () => { alive = false; sb().removeChannel(ch); document.removeEventListener('visibilitychange', onVis) }
  }, [table, select, order, asc, limit, key])

  return [rows, loading, setRows]
}

/** Riga singola (settings / status, id=1) */
export function useRow(table) {
  const [rows, loading, setRows] = useLiveTable(table, { limit: 1 })
  const row = rows[0] || null
  const update = async (patch) => {
    setRows(r => r.length ? [{ ...r[0], ...patch }] : r)
    const { error } = await sb().from(table).update(patch).eq('id', 1)
    if (error) alert(error.message)
  }
  return [row, update, loading]
}

/** Forza un re-render periodico (per "x secondi fa") */
export function useTick(ms = 5000) {
  const [, set] = useState(0)
  useEffect(() => { const t = setInterval(() => set(x => x + 1), ms); return () => clearInterval(t) }, [ms])
}
