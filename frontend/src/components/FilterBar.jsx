export default function FilterBar({ filters, departments, onChange, onReset }) {
  const set = (field) => (e) => onChange({ [field]: e.target.value })

  return (
    <div className="filters">
      <input
        className="grow"
        type="search"
        placeholder="Search name, email or role…"
        value={filters.search}
        onChange={set('search')}
        aria-label="Search"
      />
      <select value={filters.department} onChange={set('department')} aria-label="Department">
        <option value="">All departments</option>
        {departments.map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
      <input type="text" placeholder="City" value={filters.city} onChange={set('city')} aria-label="City" />
      <select value={filters.active} onChange={set('active')} aria-label="Status">
        <option value="">Any status</option>
        <option value="true">Active</option>
        <option value="false">Inactive</option>
      </select>
      <input
        type="number"
        min="0"
        placeholder="Min salary"
        value={filters.min_salary}
        onChange={set('min_salary')}
        aria-label="Minimum salary"
      />
      <input
        type="number"
        min="0"
        placeholder="Max salary"
        value={filters.max_salary}
        onChange={set('max_salary')}
        aria-label="Maximum salary"
      />
      <button className="btn btn-ghost" onClick={onReset}>Reset</button>
    </div>
  )
}
