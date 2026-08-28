import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { MerchantInput, ScanResponse, ProgressEvent } from '../types'

type Status = 'idle' | 'queued' | 'running' | 'completed' | 'failed'

const POLL_INTERVAL_MS = 3000

export function useComplianceCheck() {
  const [status, setStatus] = useState<Status>('idle')
  const [jobId, setJobId] = useState<string | null>(null)
  const [report, setReport] = useState<ScanResponse['report'] | null>(null)
  const [progress, setProgress] = useState<ProgressEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const settledRef = useRef(false)

  const cleanup = useCallback(() => {
    settledRef.current = true
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.close()
      wsRef.current = null
    }
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const fetchResult = useCallback(async (id: string) => {
    try {
      const { data } = await axios.get<ScanResponse>(`/api/scan/${id}`)
      if (data.status === 'completed') {
        setStatus('completed')
        setReport(data.report ?? null)
        cleanup()
      } else if (data.status === 'failed') {
        setStatus('failed')
        setError('Scan failed')
        cleanup()
      }
    } catch {
      setStatus('failed')
      setError('Failed to fetch result')
      cleanup()
    }
  }, [cleanup])

  // Only one poller may exist, and never after the scan has settled
  const startPolling = useCallback((id: string) => {
    if (settledRef.current || pollRef.current) return
    pollRef.current = setInterval(() => fetchResult(id), POLL_INTERVAL_MS)
  }, [fetchResult])

  const connectWebSocket = useCallback((id: string) => {
    // Same-origin so the Vite dev proxy and any reverse proxy both work, and so an
    // HTTPS page does not open a blocked insecure socket
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/scan/${id}`)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data: ProgressEvent = JSON.parse(event.data)
        if (data.type === 'ping') return
        setProgress((prev) => [...prev, data])
        if (data.type === 'complete') {
          setStatus('completed')
          fetchResult(id)
          cleanup()
        } else if (data.type === 'error') {
          setStatus('failed')
          setError(data.message ?? 'Scan error')
          cleanup()
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => startPolling(id)
    // A dropped socket must not leave the UI stuck on "running" forever
    ws.onclose = () => startPolling(id)
  }, [cleanup, fetchResult, startPolling])

  const submit = useCallback(async (merchant: MerchantInput) => {
    cleanup()
    settledRef.current = false
    setStatus('queued')
    setProgress([])
    setReport(null)
    setError(null)

    try {
      const { data } = await axios.post<ScanResponse>('/api/scan', merchant)
      setJobId(data.job_id)
      setStatus('running')
      connectWebSocket(data.job_id)
    } catch (err) {
      settledRef.current = true
      setStatus('failed')
      setError(describeError(err))
    }
  }, [cleanup, connectWebSocket])

  useEffect(() => () => cleanup(), [cleanup])

  return { status, jobId, report, progress, error, submit }
}

/** Surface FastAPI's validation detail instead of a bare "status code 422". */
function describeError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => `${d.loc?.slice(1).join('.') ?? 'field'}: ${d.msg}`).join('; ')
    }
  }
  return err instanceof Error ? err.message : 'Scan failed'
}
