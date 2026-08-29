import { useNavigate } from 'react-router-dom'
import { TriangleAlert } from 'lucide-react'

import type { MerchantInput } from '@/api/types'
import { useBackendHealth } from '@/app/useBackendHealth'
import { Card } from '@/components/ui'
import { MerchantScanForm } from '@/features/scan/MerchantScanForm'
import { useScanStore, useSubmitState } from '@/scan/scanStore'

export function NewScanPage() {
  const navigate = useNavigate()
  const health = useBackendHealth()
  const { submitting, error } = useSubmitState()
  const startScan = useScanStore((s) => s.startScan)

  async function run(merchant: MerchantInput) {
    const jobId = await startScan(merchant)
    if (jobId) navigate(`/dashboard/scan/${jobId}`)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 text-text-primary">New compliance scan</h1>
        <p className="mt-1 text-body-sm text-text-secondary">
          Seven agents audit the site against RBI Merchant Due Diligence and PCI DSS v4.0.1, then
          cross check the three KYC names. A local test site takes about 20 seconds.
        </p>
      </div>

      {health === 'offline' && (
        <Card className="border-status-danger/40 bg-status-danger-muted" padded>
          <div className="flex gap-3">
            <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-status-danger" />
            <div>
              <p className="text-body-sm font-medium text-text-primary">
                The compliance engine is not reachable
              </p>
              <p className="mt-1 text-caption text-text-secondary">
                Start the backend with{' '}
                <code className="font-mono text-text-primary">
                  uv run uvicorn backend.main:app --port 8000
                </code>
                . No scan can run until it responds.
              </p>
            </div>
          </div>
        </Card>
      )}

      {error && (
        <Card className="border-status-danger/40 bg-status-danger-muted" padded>
          <p className="text-body-sm text-status-danger">{error}</p>
        </Card>
      )}

      <MerchantScanForm
        onSubmit={run}
        submitting={submitting}
        disabled={health === 'offline'}
        disabledReason="Start the backend to run a scan"
      />
    </div>
  )
}
