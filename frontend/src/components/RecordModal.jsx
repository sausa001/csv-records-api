import { useEffect, useState } from 'react'
import { EMPTY_RECORD, formatDate, formatINR, toPayload, validateRecord } from '../utils.js'

const FIELDS = [
  { name: 'name', label: 'Full name' },
  { name: 'email', label: 'Email', type: 'email' },
  { name: 'department', label: 'Department', list: 'department-options' },
  { name: 'role', label: 'Role' },
  { name: 'city', label: 'City' },
  { name: 'salary', label: 'Salary (₹ per year)', type: 'number', min: 0 },
  { name: 'joining_date', label: 'Joining date', type: 'date' },
]

export default function RecordModal({ mode, record, departments, onClose, onEdit, onSave }) {
  const [form, setForm] = useState(() => (record ? { ...EMPTY_RECORD, ...record, salary: String(record.salary) } : EMPTY_RECORD))
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const title = mode === 'create' ? 'Add employee' : mode === 'edit' ? `Edit ${record.name}` : record.name

  const submit = async (e) => {
    e.preventDefault()
    const v = validateRecord(form)
    setErrors(v)
    if (Object.keys(v).length) return
    setSaving(true)
    setServerError('')
    try {
      await onSave(toPayload(form))
    } catch (err) {
      setServerError(err.status === 401 ? 'API key required: set it with the "API key" button at the top.' : err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-head">
          <h2 id="modal-title">{title}</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {mode === 'view' ? (
          <>
            <dl className="details">
              <dt>ID</dt><dd>{record.id}</dd>
              <dt>Email</dt><dd>{record.email}</dd>
              <dt>Department</dt><dd>{record.department}</dd>
              <dt>Role</dt><dd>{record.role}</dd>
              <dt>City</dt><dd>{record.city}</dd>
              <dt>Salary</dt><dd>{formatINR(record.salary)}</dd>
              <dt>Joined</dt><dd>{formatDate(record.joining_date)}</dd>
              <dt>Status</dt>
              <dd><span className={`badge ${record.active ? 'ok' : 'off'}`}>{record.active ? 'Active' : 'Inactive'}</span></dd>
            </dl>
            <div className="modal-foot">
              <button className="btn btn-ghost" onClick={onClose}>Close</button>
              <button className="btn btn-primary" onClick={onEdit}>Edit</button>
            </div>
          </>
        ) : (
          <form onSubmit={submit} noValidate>
            <div className="form-grid">
              {FIELDS.map((f) => (
                <label key={f.name} className={errors[f.name] ? 'has-error' : ''}>
                  {f.label}
                  <input
                    name={f.name}
                    type={f.type || 'text'}
                    min={f.min}
                    list={f.list}
                    value={form[f.name]}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  />
                  {errors[f.name] && <span className="field-error">{errors[f.name]}</span>}
                </label>
              ))}
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm({ ...form, active: e.target.checked })}
                />
                Active employee
              </label>
            </div>
            <datalist id="department-options">
              {departments.map((d) => <option key={d} value={d} />)}
            </datalist>

            {serverError && <div className="alert">{serverError}</div>}

            <div className="modal-foot">
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : mode === 'edit' ? 'Save changes' : 'Add employee'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
