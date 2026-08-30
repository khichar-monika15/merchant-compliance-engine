import { useEffect } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Download, FileJson, FileText, Printer } from 'lucide-react'

import { Badge, Button, Card, cn, Menu, Spinner, Tabs } from '@/components/ui'
import type { TabItem } from '@/components/ui'
import { ScoreRing } from '@/features/report/ScoreRing'
import { exportJson, exportMarkdown, exportPdf, siteFromReport } from '@/features/report/exportReport'
import { AuditTab } from '@/features/report/tabs/AuditTab'
import { ComplianceTab } from '@/features/report/tabs/ComplianceTab'
import { IntegrationTab } from '@/features/report/tabs/IntegrationTab'
import { KycTab } from '@/features/report/tabs/KycTab'
import { OverviewTab } from '@/features/report/tabs/OverviewTab'
import { PoliciesTab } from '@/features/report/tabs/PoliciesTab'
import { SecurityTab } from '@/features/report/tabs/SecurityTab'
import { attachToJob } from '@/scan/scanSocket'
import { useScan } from '@/scan/scanStore'

/** One tab's content. Mounted whether or not it is the open tab, so print gets all of them. */
function Panel({ id, active, children }: { id: string; active: string; children: React.ReactNode }) {
  return (
    <section className={cn(id !== active && 'hidden print:mb-6 print:block')} aria-hidden={id !== active}>
      {children}
    </section>
  )
}

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

          <div className="flex shrink-0 gap-2" data-print-hide>
            <Menu
              label="Download report"
              trigger={
                <Button
                  variant="secondary"
                  size="sm"
                  leadingIcon={<Download className="h-3.5 w-3.5" />}
                >
                  Download
                </Button>
              }
              items={[
                {
                  label: 'PDF',
                  description: 'Opens your print dialog, choose Save as PDF',
                  icon: <Printer className="h-4 w-4" />,
                  onSelect: exportPdf,
                },
                {
                  label: 'Markdown',
                  description: 'The full report as text',
                  icon: <FileText className="h-4 w-4" />,
                  onSelect: () => exportMarkdown(report, merchant, jobId),
                },
                {
                  label: 'JSON',
                  description: 'Every field, for another tool to read',
                  icon: <FileJson className="h-4 w-4" />,
                  onSelect: () => exportJson(report, merchant, jobId),
                },
              ]}
            />
          </div>
        </div>
      </Card>

      <div data-print-hide>
        <Tabs
          tabs={tabs}
          active={active}
          onChange={(id) => setParams(id === 'overview' ? {} : { tab: id }, { replace: true })}
        />
      </div>

      {/*
        Every panel stays mounted and the inactive ones are hidden, so printing reveals the whole
        report rather than whichever tab happened to be open. On screen this is unchanged.
      */}
      <div className="animate-fade-in">
        <Panel id="overview" active={active}>
          <OverviewTab report={report} />
        </Panel>
        {report.compliance_details && (
          <Panel id="compliance" active={active}>
            <ComplianceTab compliance={report.compliance_details} />
          </Panel>
        )}
        {report.pci_details && (
          <Panel id="security" active={active}>
            <SecurityTab pci={report.pci_details} />
          </Panel>
        )}
        {report.kyc_details && (
          <Panel id="kyc" active={active}>
            <KycTab kyc={report.kyc_details} />
          </Panel>
        )}
        {report.integration_details && (
          <Panel id="integration" active={active}>
            <IntegrationTab integration={report.integration_details} />
          </Panel>
        )}
        {report.generated_policies && (
          <Panel id="policies" active={active}>
            <PoliciesTab policies={report.generated_policies} />
          </Panel>
        )}
        <Panel id="audit" active={active}>
          <AuditTab log={report.audit_trail ?? []} />
        </Panel>
      </div>
    </div>
  )
}
