import { create } from 'zustand'
import { useShallow } from 'zustand/react/shallow'

import { postScan } from '@/api/client'
import { describeError } from '@/api/errors'
import type { MerchantInput, ProgressEvent, ReadinessReport, ScanStatus } from '@/api/types'

import { buildTimeline } from './agentTimeline'
import { closeAllSockets, connectSocket } from './scanSocket'

export type ErrorSource = 'submit' | 'stream' | 'fetch' | 'unavailable'

export interface ScanRecord {
  jobId: string
  merchant: MerchantInput
  status: ScanStatus
  startedAt: string
  events: ProgressEvent[]
  report: ReadinessReport | null
  error: string | null
  errorSource: ErrorSource | null
}

interface ScanState {
  scans: Record<string, ScanRecord>
  order: string[]
  submitting: boolean
  submitError: string | null
  startScan: (merchant: MerchantInput) => Promise<string | null>
  applyEvent: (jobId: string, event: ProgressEvent) => void
  settle: (jobId: string, patch: Partial<ScanRecord>) => void
  clearSubmitError: () => void
  reset: () => void
}

export function blankMerchant(): MerchantInput {
  return { website_url: '', pan_name: '', gst_legal_name: '', bank_account_name: '' }
}

function blankRecord(jobId: string, merchant: MerchantInput): ScanRecord {
  return {
    jobId,
    merchant,
    status: 'queued',
    startedAt: new Date().toISOString(),
    events: [],
    report: null,
    error: null,
    errorSource: null,
  }
}

export const useScanStore = create<ScanState>((set) => ({
  scans: {},
  order: [],
  submitting: false,
  submitError: null,

  async startScan(merchant) {
    set({ submitting: true, submitError: null })
    try {
      const res = await postScan(merchant)
      const jobId = res.job_id
      set((s) => ({
        submitting: false,
        scans: { ...s.scans, [jobId]: { ...blankRecord(jobId, merchant), status: 'running' } },
        order: [jobId, ...s.order.filter((id) => id !== jobId)],
      }))
      connectSocket(jobId)
      return jobId
    } catch (err) {
      set({ submitting: false, submitError: describeError(err) })
      return null
    }
  },

  applyEvent(jobId, event) {
    set((s) => {
      const existing = s.scans[jobId]
      if (!existing) return s
      return {
        scans: { ...s.scans, [jobId]: { ...existing, events: [...existing.events, event] } },
      }
    })
  },

  settle(jobId, patch) {
    set((s) => {
      // A reload or a pasted link settles a job this tab never started, so synthesise a shell.
      const base = s.scans[jobId] ?? blankRecord(jobId, blankMerchant())
      return {
        scans: { ...s.scans, [jobId]: { ...base, ...patch } },
        order: s.order.includes(jobId) ? s.order : [jobId, ...s.order],
      }
    })
  },

  clearSubmitError() {
    set({ submitError: null })
  },

  reset() {
    closeAllSockets()
    set({ scans: {}, order: [], submitting: false, submitError: null })
  },
}))

// --- selectors -------------------------------------------------------------
// Exported as hooks so no component inlines a selector that returns a fresh object each render.

export const useScan = (jobId: string | undefined) =>
  useScanStore((s) => (jobId ? s.scans[jobId] : undefined))

export const useScanTimeline = (jobId: string | undefined) => {
  const record = useScan(jobId)
  return buildTimeline(record?.events ?? [], record?.status ?? 'queued')
}

/** `useShallow` matters: without it this returns a new array every render and loops forever. */
export const useScanList = () =>
  useScanStore(useShallow((s) => s.order.map((id) => s.scans[id]).filter(Boolean)))

export const useSubmitState = () =>
  useScanStore(useShallow((s) => ({ submitting: s.submitting, error: s.submitError })))

export const useRunningCount = () =>
  useScanStore(
    (s) =>
      s.order.filter((id) => {
        const status = s.scans[id]?.status
        return status === 'queued' || status === 'running'
      }).length,
  )
