import { InputForm } from './components/InputForm'
import { ProgressTracker } from './components/ProgressTracker'
import { ScoreCard } from './components/ScoreCard'
import { GapAnalysis } from './components/GapAnalysis'
import { KYCPanel } from './components/KYCPanel'
import { PCIReport } from './components/PCIReport'
import { PolicyViewer } from './components/PolicyViewer'
import { CodeBlock } from './components/CodeBlock'
import { AuditTrail } from './components/AuditTrail'
import { ReportExport } from './components/ReportExport'
import { useComplianceCheck } from './hooks/useComplianceCheck'

export default function App() {
  const { status, report, progress, error, submit } = useComplianceCheck()

  const isActive = status === 'queued' || status === 'running'
  const allGaps = report
    ? [...(report.critical_gaps ?? []), ...(report.warnings ?? []), ...(report.info_items ?? [])]
    : []

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <span className="text-2xl">🛡️</span>
          <div>
            <h1 className="text-lg font-bold text-gray-900">Merchant Compliance Intelligence Engine</h1>
            <p className="text-xs text-gray-500">Razorpay AI Buildathon 2026 — Track 05</p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-base font-semibold mb-4">Merchant Details</h2>
          <InputForm onSubmit={submit} disabled={isActive} />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {isActive && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <ProgressTracker progress={progress} status={status} />
          </div>
        )}

        {report && (() => {
          return (
            <>
              <ScoreCard
                score={report.overall_score}
                grade={report.grade}
                breakdown={report.score_breakdown ?? []}
              />

              <GapAnalysis gaps={allGaps} estimatedFixTime={report.estimated_fix_time} />

              {report.kyc_details && <KYCPanel kyc={report.kyc_details} />}

              {report.pci_details && <PCIReport pci={report.pci_details} />}

              {report.generated_policies && report.generated_policies.generated_policies.length > 0 && (
                <PolicyViewer policyGen={report.generated_policies} />
              )}

              {report.integration_details && <CodeBlock integration={report.integration_details} />}

              <AuditTrail log={report.audit_trail} />

              <div className="flex justify-end">
                <ReportExport report={report} gaps={allGaps} />
              </div>
            </>
          )
        })()}
      </main>
    </div>
  )
}
