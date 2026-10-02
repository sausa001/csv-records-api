// Pure helpers (unit-tested in utils.test.js)

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })

export function formatINR(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return inr.format(Number(value))
}

/** Compact salary: 8450000 -> "₹84.5L", 21950000 -> "₹2.2Cr" */
export function formatCompactINR(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  if (n >= 1e7) return `₹${trim(n / 1e7)}Cr`
  if (n >= 1e5) return `₹${trim(n / 1e5)}L`
  return formatINR(n)
}

function trim(n) {
  return n.toFixed(1).replace(/\.0$/, '')
}

export function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** Build a query string, skipping empty values. */
export function buildQuery(params = {}) {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    qs.append(key, String(value))
  }
  const s = qs.toString()
  return s ? `?${s}` : ''
}

/** Turn FastAPI error bodies into one readable message. */
export function errorMessage(body, status) {
  if (!body) return `Request failed (${status})`
  const { detail } = body
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== 'body' && p !== 'query').join('.') : ''
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  return `Request failed (${status})`
}

export const EMPTY_RECORD = {
  name: '',
  email: '',
  department: '',
  role: '',
  city: '',
  salary: '',
  joining_date: '',
  active: true,
}

/** Form state (strings) -> API payload (typed). */
export function toPayload(form) {
  return {
    name: form.name.trim(),
    email: form.email.trim(),
    department: form.department.trim(),
    role: form.role.trim(),
    city: form.city.trim(),
    salary: form.salary === '' ? null : Number(form.salary),
    joining_date: form.joining_date,
    active: Boolean(form.active),
  }
}

/** Client-side checks that mirror the API's validation rules. */
export function validateRecord(form) {
  const errors = {}
  for (const f of ['name', 'department', 'role', 'city']) {
    if (!String(form[f] ?? '').trim()) errors[f] = 'Required'
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(form.email ?? '').trim())) errors.email = 'Enter a valid email'
  const salary = Number(form.salary)
  if (form.salary === '' || !Number.isInteger(salary) || salary < 0) errors.salary = 'Whole number, 0 or more'
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.joining_date ?? '')) errors.joining_date = 'Pick a date'
  return errors
}
