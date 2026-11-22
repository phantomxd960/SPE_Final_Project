import { useCallback, useEffect, useRef, useState } from 'react'

// Load data from the API. While `poll(data)` returns true the data refreshes
// every `intervalMs` (job status, UI-5). `refresh()` reloads and restarts polling.
export function useApi(loader, deps, { poll, intervalMs = 2500 } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [nonce, setNonce] = useState(0)
  const loaderRef = useRef(loader)
  const pollRef = useRef(poll)
  loaderRef.current = loader
  pollRef.current = poll

  useEffect(() => {
    let cancelled = false
    let timer
    const run = async () => {
      try {
        const data = await loaderRef.current()
        if (cancelled) return
        setState({ data, error: null, loading: false })
        if (pollRef.current?.(data)) timer = setTimeout(run, intervalMs)
      } catch (error) {
        if (!cancelled) setState((previous) => ({ ...previous, error, loading: false }))
      }
    }
    run()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, intervalMs])

  const refresh = useCallback(() => setNonce((n) => n + 1), [])
  return { ...state, refresh }
}
