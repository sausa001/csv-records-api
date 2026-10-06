// Thin client for the PeoplePulse API.
// All calls go to /api/... ; Vite (dev) or nginx (Kubernetes) forwards them to FastAPI.
import { buildQuery, errorMessage } from './utils.js'

const BASE = import.meta.env.VITE_API_BASE || '/api'
const KEY_STORAGE = 'csv-records-api-key'

export function getApiKey() {
  try {
    return localStorage.getItem(KEY_STORAGE) || ''
  } catch {
    return ''
  }
}

export function setApiKey(value) {
  try {
    if (value) localStorage.setItem(KEY_STORAGE, value)
    else localStorage.removeItem(KEY_STORAGE)
  } catch {
    /* storage unavailable: key only lives for this page load */
  }
}

async function request(path, { method = 'GET', body, query } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const key = getApiKey()
  if (key && method !== 'GET') headers['X-API-Key'] = key

  const res = await fetch(`${BASE}${path}${buildQuery(query)}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = new Error(errorMessage(data, res.status))
    err.status = res.status
    throw err
  }
  return data
}

export const api = {
  health: () => request('/health'),
  stats: () => request('/records/stats'),
  departments: () => request('/departments'),
  list: (query) => request('/records', { query }),
  get: (id) => request(`/records/${id}`),
  create: (record) => request('/records', { method: 'POST', body: record }),
  replace: (id, record) => request(`/records/${id}`, { method: 'PUT', body: record }),
  remove: (id) => request(`/records/${id}`, { method: 'DELETE' }),
  exportUrl: (query) => `${BASE}/records/export${buildQuery(query)}`,
}
