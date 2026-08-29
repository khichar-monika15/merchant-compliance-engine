import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CircleAlert, RotateCcw } from 'lucide-react'

import { Button, Card, CardHeader, Progress, Spinner } from '@/components/ui'
import { AgentTimeline } from '@/features/scan/AgentTimeline'
import { attachToJob } from '@/scan/scanSocket'
import { useScan, useScanStore, useScanTimeline } from '@/scan/scanStore'

export function ScanProgressPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const record = useScan(jobId)
  const timeline = useScanTimeline(jobId)
  const startScan = useScanStore((s) => s.startScan)

  // Recover a scan this page did not start: a reload, or a pasted link.
  useEffect(() => {
    if (jobId) void attachToJob(jobId)
  }, [jobId])

  useEffect(() => {
    if (record?.status === 'completed' && jobId) {
      // Replace so Back skips the finished progress view and returns to the form.
      navigate(`/dashboard/report/${jobId}`, { replace: true })
    }
  }, [record?.status, jobId, navigate])

  if (!jobId) return null

  const failed = record?.status === 'failed'
  const reason = record?.error ?? timeline.failure?.message ?? null

  async function runAgain() {
    if (!record?.merchant.website_url) return
    const next = await startScan(record.merchant)
    if (next) navigate(`/dashboard/scan/${next}`, { replace: true })
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-h2 text-text-primary">
            {failed ? 'Scan failed' : 'Scanning merchant website'}
          </h1>
          <p className="mt-1 truncate font-mono text-caption text-text-secondary">
            {record?.merchant.website_url || jobId}
          </p>
        </div>
        {!failed && <Spinner />}
      </div>

      <Progress
        value={timeline.percent}
        tone={failed ? 'danger' : 'accent'}
        indeterminate={!failed && timeline.parallelGroupActive}
        label="Scan progress"
      />

      {failed && (
        <Card className="border-status-danger/40 bg-status-danger-muted">
          <div className="flex gap-3">
            <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-status-danger" />
            <div className="min-w-0 flex-1">
              <p className="text-body-sm font-medium text-text-primary">
                {reason ? 'The engine could not complete this scan' : 'This scan failed'}
              </p>
              <p className="mt-1 break-words text-caption text-text-secondary">
                {reason ??
                  'The engine no longer has the failure details. They are kept for the current server session only.'}
              </p>
              {record?.merchant.website_url && (
                <Button
                  className="mt-3"
                  size="sm"
                  variant="secondary"
                  leadingIcon={<RotateCcw className="h-3.5 w-3.5" />}
                  onClick={runAgain}
                >
                  Run again
                </Button>
              )}
            </div>
          </div>
        </Card>
      )}

      <Card padded={false}>
        <div className="px-5 pt-5">
          <CardHeader
            title="Agent pipeline"
            subtitle="Four of the seven run concurrently inside a single graph node."
            className="mb-2"
          />
        </div>
        <div className="px-5 pb-3">
          <AgentTimeline timeline={timeline} />
        </div>
      </Card>
    </div>
  )
}
