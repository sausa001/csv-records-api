import { useState } from 'react'
import { getApiKey, setApiKey } from '../api.js'

export default function Header({ health, onRefresh }) {
  const [showKey, setShowKey] = useState(false)
  const [key, setKey] = useState(getApiKey())
  const up = health?.status === 'ok'

  return (
    <header className="topbar">
      <div className="container topbar-inner">
        <div className="brand">
          <span className="logo" aria-hidden="true">▤</span>
          <div>
            <h1>CSV Records</h1>
            <p className="muted small">React · FastAPI · Kubernetes</p>
          </div>
        </div>

        <div className="topbar-right">
          <span className={`status ${health ? (up ? 'up' : 'down') : ''}`} title="API health">
            <span className="dot" />
            {health ? (up ? `API v${health.version} · ${health.records_loaded} records` : 'API unreachable') : 'Checking…'}
          </span>
          <button className="btn btn-ghost" onClick={onRefresh}>Refresh</button>
          <button className="btn btn-ghost" onClick={() => setShowKey((s) => !s)} aria-expanded={showKey}>
            API key
          </button>
        </div>
      </div>

      {showKey && (
        <div className="container keybar">
          <label>
            X-API-Key for add / edit / delete (only needed when the API sets <code>APP_API_KEY</code>)
            <input
              type="password"
              value={key}
              placeholder="leave empty if not required"
              onChange={(e) => setKey(e.target.value)}
            />
          </label>
          <button
            className="btn btn-primary"
            onClick={() => {
              setApiKey(key.trim())
              setShowKey(false)
            }}
          >
            Save
          </button>
        </div>
      )}
    </header>
  )
}
