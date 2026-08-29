import { getScan, scanSocketUrl } from '@/api/client'
import { describeError } from '@/api/errors'
import type { ProgressEvent } from '@/api/types'

import { useScanStore } from './scanStore'

interface JobController {
  ws: WebSocket | null
  poll: number | null
  settled: boolean
  openedAt: number
}

/**
 * Controllers live here, not in a component, so navigating between the progress page and the
 * report page cannot tear down a running scan. The old hook cleaned up on unmount, which is
 * exactly what would have killed a scan the moment routing existed.
 */
const controllers = new Map<string, JobController>()

const POLL_INTERVAL_MS = 3000
const MAX_CONCURRENT = 3

export function cleanupJob(jobId: string): void {
  const c = controllers.get(jobId)
  if (!c) return
  if (c.ws) {
    // Null the handlers before closing. close() fires onclose synchronously, which would
    // otherwise start a poller for a scan that just finished.
    c.ws.onclose = null
    c.ws.onerror = null
    c.ws.onmessage = null
    try {
      c.ws.close()
    } catch {
      // Already closing
    }
    c.ws = null
  }
  if (c.poll !== null) {
    window.clearInterval(c.poll)
    c.poll = null
  }
  c.settled = true
  controllers.delete(jobId)
}

export function closeAllSockets(): void {
  for (const jobId of [...controllers.keys()]) cleanupJob(jobId)
}

if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', closeAllSockets)
}

async function fetchResult(jobId: string): Promise<void> {
  const store = useScanStore.getState()
  try {
    const res = await getScan(jobId)
    if (res.status === 'completed') {
      store.settle(jobId, { status: 'completed', report: res.report ?? null })
      cleanupJob(jobId)
    } else if (res.status === 'failed') {
      store.settle(jobId, {
        status: 'failed',
        error: res.error ?? null,
      })
      // Keep the socket open when the reason is missing: the server replays the error event.
      if (res.error) cleanupJob(jobId)
    }
  } catch (err) {
    store.settle(jobId, { status: 'failed', error: describeError(err) })
    cleanupJob(jobId)
  }
}

function startPolling(jobId: string): void {
  const c = controllers.get(jobId)
  if (!c || c.settled || c.poll !== null) return

  // The poll exists so a dropped socket does not strand the UI on "running". If the record is
  // already terminal there is nothing to poll for, which is the case when the server closes the
  // socket deliberately after replaying a finished job.
  const record = useScanStore.getState().scans[jobId]
  if (record && (record.status === 'completed' || record.status === 'failed')) {
    cleanupJob(jobId)
    return
  }

  c.poll = window.setInterval(() => void fetchResult(jobId), POLL_INTERVAL_MS)
}

function evictOldestIfNeeded(): void {
  if (controllers.size < MAX_CONCURRENT) return
  const oldest = [...controllers.entries()].sort((a, b) => a[1].openedAt - b[1].openedAt)[0]
  if (oldest) cleanupJob(oldest[0])
}

export function connectSocket(jobId: string): void {
  if (controllers.has(jobId)) return
  evictOldestIfNeeded()

  const controller: JobController = { ws: null, poll: null, settled: false, openedAt: Date.now() }
  controllers.set(jobId, controller)

  let ws: WebSocket
  try {
    ws = new WebSocket(scanSocketUrl(jobId))
  } catch {
    startPolling(jobId)
    return
  }
  controller.ws = ws

  ws.onmessage = (event) => {
    let data: ProgressEvent
    try {
      data = JSON.parse(event.data)
    } catch {
      return
    }
    if (data.type === 'ping') return

    const store = useScanStore.getState()
    store.applyEvent(jobId, data)

    if (data.type === 'complete') {
      void fetchResult(jobId)
    } else if (data.type === 'error') {
      store.settle(jobId, {
        status: 'failed',
        error: (data.message ?? 'Scan failed').replace(/^Error:\s*/, ''),
      })
      cleanupJob(jobId)
    }
  }

  ws.onerror = () => startPolling(jobId)
  ws.onclose = () => startPolling(jobId)
}

/**
 * Recover a scan the current page did not start: a reload, or a pasted report link.
 *
 * The server replays a job's full event history on connect and then closes immediately if the
 * job already finished, so reopening the socket is what recovers a failure reason that the REST
 * response cannot supply.
 */
export async function attachToJob(jobId: string): Promise<void> {
  if (controllers.has(jobId)) return
  const store = useScanStore.getState()

  try {
    const res = await getScan(jobId)
    store.settle(jobId, {
      status: res.status,
      report: res.report ?? null,
      error: res.error ?? null,
    })
    if (res.status === 'completed') return
    if (res.status === 'failed' && res.error) return
  } catch (err) {
    const notFound =
      typeof err === 'object' && err !== null && (err as { response?: { status?: number } }).response?.status === 404
    store.settle(jobId, {
      status: 'failed',
      error: notFound
        ? 'This scan is no longer available. The engine keeps recent scans only.'
        : describeError(err),
    })
    return
  }

  connectSocket(jobId)
}
