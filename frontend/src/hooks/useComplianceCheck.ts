import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { MerchantInput, ScanResponse, ProgressEvent } from '../types'

type Status = 'idle' | 'queued' | 'running' | 'completed' | 'failed'

export function useComplianceCheck() {
  const [status, setStatus] = useState<Status>('idle')
  const [jobId, setJobId] = useState<string | null>(null)
  const [report, setReport] = useState<ScanResponse['report'] | null>(null)
  const [progress, setProgress] = useState<ProgressEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const connectWebSocket = useCallback((id: string) => {
    const ws = new WebSocket(`ws://localhost:8000/ws/scan/${id}`)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data: ProgressEvent = JSON.parse(event.data)
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

    ws.onerror = () => {
      // fall back to polling if WebSocket fails
      pollRef.current = setInterval(() => fetchResult(id), 3000)
    }
  }, [cleanup]) // eslint-disable-line react-hooks/exhaustive-deps

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

  const submit = useCallback(async (merchant: MerchantInput) => {
    cleanup()
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
      setStatus('failed')
      setError(err instanceof Error ? err.message : 'Scan failed')
    }
  }, [cleanup, connectWebSocket])

  useEffect(() => () => cleanup(), [cleanup])

  return { status, jobId, report, progress, error, submit }
}
