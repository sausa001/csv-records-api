import { formatCompactINR, formatDate } from '../utils.js'

const COLUMNS = [
  { key: 'id', label: 'ID', sortable: true },
  { key: 'name', label: 'Name', sortable: true },
  { key: 'department', label: 'Department', sortable: true },
  { key: 'role', label: 'Role' },
  { key: 'city', label: 'City', sortable: true },
  { key: 'salary', label: 'Salary', sortable: true, align: 'right' },
  { key: 'joining_date', label: 'Joined', sortable: true },
  { key: 'active', label: 'Status' },
]

export default function RecordsTable({ items, loading, sortBy, order, onSort, onView, onEdit, onDelete }) {
  return (
    <div className={`table-wrap ${loading ? 'is-loading' : ''}`}>
      <table>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} className={c.align === 'right' ? 'right' : ''} aria-sort={sortBy === c.key ? (order === 'asc' ? 'ascending' : 'descending') : undefined}>
                {c.sortable ? (
                  <button className="th-btn" onClick={() => onSort(c.key)}>
                    {c.label}
                    <span className="sort">{sortBy === c.key ? (order === 'asc' ? '▲' : '▼') : '↕'}</span>
                  </button>
                ) : (
                  c.label
                )}
              </th>
            ))}
            <th className="right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && !loading && (
            <tr>
              <td colSpan={COLUMNS.length + 1} className="empty">No records match these filters.</td>
            </tr>
          )}
          {items.map((r) => (
            <tr key={r.id}>
              <td className="muted">{r.id}</td>
              <td>
                <button className="link" onClick={() => onView(r)}>{r.name}</button>
                <div className="muted small">{r.email}</div>
              </td>
              <td>{r.department}</td>
              <td>{r.role}</td>
              <td>{r.city}</td>
              <td className="right mono">{formatCompactINR(r.salary)}</td>
              <td>{formatDate(r.joining_date)}</td>
              <td>
                <span className={`badge ${r.active ? 'ok' : 'off'}`}>{r.active ? 'Active' : 'Inactive'}</span>
              </td>
              <td className="right nowrap">
                <button className="btn btn-sm btn-ghost" onClick={() => onEdit(r)}>Edit</button>
                <button className="btn btn-sm btn-danger" onClick={() => onDelete(r)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
