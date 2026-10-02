import { useEffect } from 'react'

export default function Toast({ message, kind = 'success', onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 3500)
    return () => clearTimeout(t)
  }, [onDone])

  return (
    <div className={`toast ${kind}`} role="status" aria-live="polite">
      {message}
    </div>
  )
}
