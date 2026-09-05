import { Check, X } from 'lucide-react'

import type { KYCMatch, KYCResult } from '@/api/types'
import { Badge, Card, cn } from '@/components/ui'

function NameRow({ label, raw }: { label: string; raw: string }) {
  return (
    <div>
      <p className="text-overline uppercase text-text-tertiary">{label} as typed</p>
      <p className="break-words font-mono text-caption text-text-primary">{raw}</p>
    </div>
  )
}

function MatchCard({ label, match }: { label: string; match: KYCMatch }) {
  const [a, b] = label.split(' vs ')
  // The case that reads as a contradiction without a sentence: the two normalised names are the
  // same string, similarity is 100%, and the verdict is still mismatch.
  const sameAfterNormalising = !match.match && match.normalized_a === match.normalized_b
  return (
    <Card className={cn(match.match ? 'border-surface-border' : 'border-status-danger/40')}>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-body-sm text-text-primary">{label}</span>
        <Badge variant={match.match ? 'success' : 'critical'}>
          {match.match ? 'match' : 'mismatch'}
        </Badge>
      </div>

      <div className="space-y-2">
        <NameRow label={a} raw={match.raw_a} />
        <NameRow label={b} raw={match.raw_b} />
      </div>

      {sameAfterNormalising && (
        <p className="mt-3 text-caption text-text-secondary">
          Both names mean the same company. The two documents word it differently, and the check
          at onboarding compares the wording.
        </p>
      )}

      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-border">
          <div
            className={cn(
              'h-full rounded-full',
              match.match ? 'bg-status-success' : 'bg-status-danger',
            )}
            style={{ width: `${Math.round(match.similarity * 100)}%` }}
          />
        </div>
        <span className="font-mono text-caption text-text-secondary">
          {Math.round(match.similarity * 100)}%
        </span>
      </div>

      {match.issues.length > 0 && (
        <ul className="mt-3 space-y-1">
          {match.issues.map((issue, i) => (
            <li key={i} className="text-caption text-status-danger">
              {issue}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function KycTab({ kyc }: { kyc: KYCResult }) {
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {kyc.overall_consistent ? (
              <Check className="h-6 w-6 text-status-success" />
            ) : (
              <X className="h-6 w-6 text-status-danger" />
            )}
            <div>
              <h3 className="text-h3 text-text-primary">
                {kyc.overall_consistent
                  ? 'The three documents agree'
                  : 'The three documents do not agree'}
              </h3>
              <p className="text-caption text-text-tertiary">
                RBI-006. Different wording across two documents is still reported, because the
                check at onboarding compares what each document says.
              </p>
            </div>
          </div>
          <span className="font-mono text-body-sm text-text-secondary">
            confidence {Math.round(kyc.confidence * 100)}%
          </span>
        </div>

        {kyc.common_mismatches.length > 0 && (
          <ul className="mt-4 space-y-1 rounded border border-status-danger/30 bg-status-danger-muted p-3">
            {kyc.common_mismatches.map((m, i) => (
              <li key={i} className="text-body-sm text-text-secondary">
                {m}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <MatchCard label="PAN vs GST" match={kyc.pan_gst_match} />
        <MatchCard label="GST vs Bank" match={kyc.gst_bank_match} />
        <MatchCard label="PAN vs Bank" match={kyc.pan_bank_match} />
      </div>
    </div>
  )
}
