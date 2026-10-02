export default function Pagination({ page, pages, pageSize, onPage, onPageSize }) {
  return (
    <div className="pagination">
      <label className="muted small">
        Rows per page{' '}
        <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))}>
          {[5, 10, 25, 50, 100].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </label>
      <div className="pager">
        <button className="btn btn-sm btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          ‹ Prev
        </button>
        <span className="muted small">
          Page {pages === 0 ? 0 : page} of {pages}
        </span>
        <button className="btn btn-sm btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next ›
        </button>
      </div>
    </div>
  )
}
