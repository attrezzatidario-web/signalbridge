// Comunicazione con il motore sulla VPS (stesso indirizzo dell'app)
let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export async function api(method, path, body) {
  const r = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (r.status === 401 && path !== '/api/login') { onUnauthorized(); throw new Error('Sessione scaduta') }
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.error || `Errore ${r.status}`)
  return data
}

export const login = (password) => api('POST', '/api/login', { password })
export const logout = () => api('POST', '/api/logout')
export const isLogged = () => fetch('/api/me', { credentials: 'same-origin' }).then(r => r.ok).catch(() => false)

/** Esegue un comando sul motore e ritorna {status, result} */
export const command = (type, payload = {}) => api('POST', '/api/command', { type, payload })
