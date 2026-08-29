import axios from 'axios'

import type { KnowledgeBase, MerchantInput, ScanResponse } from './types'

/**
 * Same origin on purpose. The Vite dev server proxies `/api` and `/ws` to port 8000, and the
 * backend's CORS list only contains the two localhost:5173 origins, so a direct cross origin
 * call would hit a wall the proxy currently hides.
 */
export const http = axios.create({ baseURL: '', timeout: 20_000 })

export async function postScan(merchant: MerchantInput): Promise<ScanResponse> {
  const { data } = await http.post<ScanResponse>('/api/scan', merchant)
  return data
}

export async function getScan(jobId: string): Promise<ScanResponse> {
  const { data } = await http.get<ScanResponse>(`/api/scan/${jobId}`)
  return data
}

export interface HealthResponse {
  status: string
  timestamp: string
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/api/health', { timeout: 5_000 })
  return data
}

/** The WebSocket URL for a job, derived same origin so the `/ws` proxy applies. */
export function scanSocketUrl(jobId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/scan/${jobId}`
}

export async function getKnowledge(): Promise<KnowledgeBase> {
  const { data } = await http.get<KnowledgeBase>('/api/knowledge')
  return data
}
