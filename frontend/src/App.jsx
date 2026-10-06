import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Header from './components/Header.jsx'
import StatsPanel from './components/StatsPanel.jsx'
import FilterBar from './components/FilterBar.jsx'
import RecordsTable from './components/RecordsTable.jsx'
import Pagination from './components/Pagination.jsx'
import RecordModal from './components/RecordModal.jsx'
import ConfirmDialog from './components/ConfirmDialog.jsx'
import Toast from './components/Toast.jsx'

const INITIAL_FILTERS = {
  search: '',
  department: '',
  city: '',
  active: '',
  min_salary: '',
  max_salary: '',
  sort_by: 'id',
  order: 'asc',
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [departments, setDepartments] = useState([])
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [search, setSearch] = useState('') // debounced copy of filters.search
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [result, setResult] = useState({ items: [], total: 0, pages: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modal, setModal] = useState(null) // { mode: 'create' | 'edit' | 'view', record? }
  const [toDelete, setToDelete] = useState(null)
  const [toast, setToast] = useState(null)
  const [version, setVersion] = useState(0) // bump to reload everything

  const notify = useCallback((message, kind = 'success') => setToast({ message, kind, id: Date.now() }), [])
  const refresh = useCallback(() => setVersion((v) => v + 1), [])

  // Debounce the search box so we don't call the API on every keystroke
  useEffect(() => {
    const t = setTimeout(() => setSearch(filters.search.trim()), 300)
    return () => clearTimeout(t)
  }, [filters.search])

  // Health, stats and departments
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'down' }))
    api.stats().then(setStats).catch(() => setStats(null))
    api.departments().then(setDepartments).catch(() => setDepartments([]))
  }, [version])

  // The table
  const query = {
    ...filters,
    search,
    page,
    page_size: pageSize,
  }
  const queryKey = JSON.stringify(query)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    api
      .list(JSON.parse(queryKey))
      .then((data) => !cancelled && setResult(data))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [queryKey, version])

  const updateFilters = (patch) => {
    setFilters((f) => ({ ...f, ...patch }))
    setPage(1)
  }

  const handleSort = (field) => {
    setFilters((f) => ({
      ...f,
      sort_by: field,
      order: f.sort_by === field && f.order === 'asc' ? 'desc' : 'asc',
    }))
  }

  const handleSave = async (payload) => {
    if (modal.mode === 'edit') {
      const saved = await api.replace(modal.record.id, payload)
      notify(`Updated ${saved.name}`)
    } else {
      const saved = await api.create(payload)
      notify(`Added ${saved.name} (id ${saved.id})`)
    }
    setModal(null)
    refresh()
  }

  const handleDelete = async () => {
    try {
      await api.remove(toDelete.id)
      notify(`Deleted ${toDelete.name}`)
      if (result.items.length === 1 && page > 1) setPage(page - 1)
      refresh()
    } catch (e) {
      notify(e.message, 'error')
    } finally {
      setToDelete(null)
    }
  }

  const { page: _p, page_size: _s, ...exportQuery } = query

  return (
    <div className="app">
      <Header health={health} onRefresh={refresh} />

      <main className="container">
        <StatsPanel stats={stats} />

        <section className="card">
          <div className="section-head">
            <div>
              <h2>Employees</h2>
              <p className="muted">
                {loading ? 'Loading…' : `${result.total} record${result.total === 1 ? '' : 's'} match`}
              </p>
            </div>
            <div className="actions">
              <a className="btn btn-ghost" href={api.exportUrl(exportQuery)} download>
                Export CSV
              </a>
              <button className="btn btn-primary" onClick={() => setModal({ mode: 'create' })}>
                + Add employee
              </button>
            </div>
          </div>

          <FilterBar
            filters={filters}
            departments={departments}
            onChange={updateFilters}
            onReset={() => {
              setFilters(INITIAL_FILTERS)
              setPage(1)
            }}
          />

          {error ? (
            <div className="alert">
              <strong>Could not load records.</strong> {error}
              <button className="btn btn-ghost" onClick={refresh}>Retry</button>
            </div>
          ) : (
            <RecordsTable
              items={result.items}
              loading={loading}
              sortBy={filters.sort_by}
              order={filters.order}
              onSort={handleSort}
              onView={(record) => setModal({ mode: 'view', record })}
              onEdit={(record) => setModal({ mode: 'edit', record })}
              onDelete={setToDelete}
            />
          )}

          <Pagination
            page={page}
            pages={result.pages}
            pageSize={pageSize}
            onPage={setPage}
            onPageSize={(s) => {
              setPageSize(s)
              setPage(1)
            }}
          />
        </section>
      </main>

      {modal && (
        <RecordModal
          mode={modal.mode}
          record={modal.record}
          departments={departments}
          onClose={() => setModal(null)}
          onEdit={() => setModal({ mode: 'edit', record: modal.record })}
          onSave={handleSave}
        />
      )}

      {toDelete && (
        <ConfirmDialog
          title="Delete employee?"
          message={`${toDelete.name} (id ${toDelete.id}) will be permanently deleted.`}
          confirmLabel="Delete"
          onConfirm={handleDelete}
          onCancel={() => setToDelete(null)}
        />
      )}

      {toast && <Toast key={toast.id} {...toast} onDone={() => setToast(null)} />}
    </div>
  )
}
