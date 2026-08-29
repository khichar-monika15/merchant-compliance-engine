import { useEffect } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Download, FileText } from 'lucide-react'

import { Badge, Button, Card, Spinner, Tabs } from '@/components/ui'
import type { TabItem } from '@/components/ui'
import { ScoreRing } from '@/features/report/ScoreRing'
import { exportJson, exportMarkdown, siteFromReport } from '@/features/report/exportReport'
import { AuditTab } from '@/features/report/tabs/AuditTab'
import { ComplianceTab } from '@/features/report/tabs/ComplianceTab'
import { IntegrationTab } from '@/features/report/tabs/IntegrationTab'
import { KycTab } from '@/features/report/tabs/KycTab'
import { OverviewTab } from '@/features/report/tabs/OverviewTab'
import { PoliciesTab } from '@/features/report/tabs/PoliciesTab'
import { SecurityTab } from '@/features/report/tabs/SecurityTab'
import { attachToJob } from '@/scan/scanSocket'
import { useScan } from '@/scan/scanStore'

export function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const record = useScan(jobId)

  useEffect(() => {
    if (jobId) void attachToJob(jobId)
  }, [jobId])

  // A failed scan has no report to show, so the progress view with its error is the right place.
  useEffect(() => {
    if (record?.status === 'failed' && jobId) {
      navigate(`/dashboard/scan/${jobId}`, { replace: true })
    }
  }, [record?.status, jobId, navigate])

  if (!jobId) return null

  const report = record?.report
  if (!report) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <Spinner size="lg" />
        <p className="text-body-sm text-text-secondary">Loading report</p>
      </div>
    )
  }

  // Built from what the report actually contains: every details block is optional, and an agent
  // that failed still produces a report without its section.
  const tabs: TabItem[] = [
    { id: 'overview', label: 'Overview' },
    report.compliance_details && { id: 'compliance', label: 'RBI compliance' },
    report.pci_details && { id: 'security', label: 'Security' },
    report.kyc_details && { id: 'kyc', label: 'KYC' },
    report.integration_details && { id: 'integration', label: 'Integration' },
    report.generated_policies?.generated_policies?.length
      ? { id: 'policies', label: 'Policies', count: report.generated_policies.generated_policies.length }
      : null,
    { id: 'audit', label: 'Audit trail', count: report.audit_trail?.length },
  ].filter(Boolean) as TabItem[]

  const requested = params.get('tab') ?? 'overview'
  const active = tabs.some((t) => t.id === requested) ? requested : 'overview'
  // A report opened from a link has no merchant input in this tab, so fall back to the URL the
  // crawler recorded rather than showing the raw job id.
  const site = record.merchant.website_url || siteFromReport(report)
  const merchant = { ...record.merchant, website_url: site }

  return (
    <div className="space-y-5">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1.5 text-body-sm text-text-secondary hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to dashboard
      </Link>

      <Card>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <ScoreRing score={report.overall_score} grade={report.grade} />

          <div className="min-w-0 flex-1">
            <h1 className="break-all font-mono text-h3 text-text-primary">
              {site || jobId}
            </h1>
            <p className="mt-1 text-body-sm text-text-secondary">{report.estimated_fix_time}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge variant="critical">{report.critical_gaps?.length ?? 0} critical</Badge>
              <Badge variant="warning">{report.warnings?.length ?? 0} warnings</Badge>
              {merchant.business_type && (
                <Badge variant="neutral">{merchant.business_type}</Badge>
              )}
            </div>
          </div>

          <div className="flex shrink-0 gap-2">
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={<Download className="h-3.5 w-3.5" />}
              onClick={() => exportJson(report, merchant, jobId)}
            >
              JSON
            </Button>
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={<FileText className="h-3.5 w-3.5" />}
              onClick={() => exportMarkdown(report, merchant, jobId)}
            >
              Markdown
            </Button>
          </div>
        </div>
      </Card>

      <Tabs
        tabs={tabs}
        active={active}
        onChange={(id) => setParams(id === 'overview' ? {} : { tab: id }, { replace: true })}
      />

      <div className="animate-fade-in">
        {active === 'overview' && <OverviewTab report={report} />}
        {active === 'compliance' && report.compliance_details && (
          <ComplianceTab compliance={report.compliance_details} />
        )}
        {active === 'security' && report.pci_details && <SecurityTab pci={report.pci_details} />}
        {active === 'kyc' && report.kyc_details && <KycTab kyc={report.kyc_details} />}
        {active === 'integration' && report.integration_details && (
          <IntegrationTab integration={report.integration_details} />
        )}
        {active === 'policies' && report.generated_policies && (
          <PoliciesTab policies={report.generated_policies} />
        )}
        {active === 'audit' && <AuditTab log={report.audit_trail ?? []} />}
      </div>
    </div>
  )
}
