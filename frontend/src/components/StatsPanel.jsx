import { formatCompactINR } from '../utils.js'

export default function StatsPanel({ stats }) {
  if (!stats) {
    return <section className="stats-grid skeleton" aria-busy="true">{[1, 2, 3, 4].map((i) => <div key={i} className="card stat" />)}</section>
  }

  const maxCount = Math.max(1, ...stats.by_department.map((d) => d.count))
  const cities = Object.entries(stats.by_city).sort((a, b) => b[1] - a[1])

  return (
    <>
      <section className="stats-grid">
        <Stat label="Total employees" value={stats.total_records} />
        <Stat label="Active" value={stats.active_records} hint={`${stats.inactive_records} inactive`} />
        <Stat label="Average salary" value={formatCompactINR(stats.avg_salary)} />
        <Stat
          label="Salary range"
          value={`${formatCompactINR(stats.min_salary)} – ${formatCompactINR(stats.max_salary)}`}
        />
      </section>

      <section className="breakdown">
        <div className="card">
          <h3>By department</h3>
          <ul className="bars">
            {stats.by_department.map((d) => (
              <li key={d.department}>
                <span className="bar-label">{d.department}</span>
                <span className="bar-track">
                  <span className="bar-fill" style={{ width: `${(d.count / maxCount) * 100}%` }} />
                </span>
                <span className="bar-value">{d.count}</span>
                <span className="bar-extra muted">avg {formatCompactINR(d.avg_salary)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h3>By city</h3>
          <div className="chips">
            {cities.map(([city, count]) => (
              <span key={city} className="chip">
                {city} <b>{count}</b>
              </span>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="card stat">
      <span className="muted small">{label}</span>
      <strong>{value}</strong>
      {hint && <span className="muted small">{hint}</span>}
    </div>
  )
}
