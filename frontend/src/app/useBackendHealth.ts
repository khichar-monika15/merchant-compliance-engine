import { useEffect, useState } from 'react'

import { getHealth } from '@/api/client'

export type BackendHealth = 'checking' | 'online' | 'offline'

const POLL_MS = 30_000

/**
 * Tells the user the engine is unreachable before they fill in five fields, rather than after
 * via an axios failure. Replaces the react-query dependency that was installed but never used.
 */
export function useBackendHealth(): BackendHealth {
  const [health, setHealth] = useState<BackendHealth>('checking')

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        await getHealth()
        if (!cancelled) setHealth('online')
      } catch {
        if (!cancelled) setHealth('offline')
      }
    }

    void check()
    const id = window.setInterval(check, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  return health
}
