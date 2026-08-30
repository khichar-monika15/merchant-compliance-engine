import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

import type { PolicyGenResult } from '@/api/types'
import { Badge, Card, CardHeader, EmptyState, cn } from '@/components/ui'
import { businessTypeLabel } from '@/api/labels'

export function PoliciesTab({ policies }: { policies: PolicyGenResult }) {
  const generated = policies.generated_policies ?? []
  const [active, setActive] = useState(0)
  const [copied, setCopied] = useState(false)

  if (generated.length === 0) {
    // `policies_needed` is what the auditor actually decided. Asserting "nothing was needed"
    // without reading it was true only because the generator happens to draft one document per
    // needed policy; the claim did not depend on the field that carries the answer.
    const needed = policies.policies_needed ?? []
    return needed.length === 0 ? (
      <EmptyState
        title="No policies needed"
        description="Every required policy was found on the site and scored well enough that the engine did not draft a replacement."
      />
    ) : (
      <EmptyState
        title="Drafts unavailable"
        description={`The audit flagged ${needed.join(', ')} as missing or too thin, but no draft was produced. The audit trail records why.`}
      />
    )
  }

  // Clamp rather than index blindly: a later scan can return fewer policies than the last one.
  const index = Math.min(active, generated.length - 1)
  const policy = generated[index]

  async function copy() {
    if (!navigator.clipboard) return
    try {
      await navigator.clipboard.writeText(policy.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard denied, nothing to recover
    }
  }

  return (
    <Card padded={false}>
      <div className="px-5 pt-5">
        <CardHeader
          title="Generated policy drafts"
          subtitle="Drafts for the merchant to review, not legal advice."
          action={
            <button
              data-print-hide
              type="button"
              onClick={copy}
              className="inline-flex items-center gap-1.5 rounded px-2 py-1 text-caption text-text-secondary hover:bg-surface-hover hover:text-text-primary"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-status-success" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
              {copied ? 'Copied' : 'Copy'}
            </button>
          }
          className="mb-3"
        />
      </div>

      <div className="flex flex-wrap gap-2 border-b border-surface-border px-5 pb-3">
        {generated.map((p, i) => (
          <button
            key={p.policy_type}
            type="button"
            onClick={() => setActive(i)}
            className={cn(
              'rounded px-3 py-1.5 text-body-sm capitalize transition-colors',
              i === index
                ? 'bg-accent-muted text-accent'
                : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
            )}
          >
            {p.policy_type}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3 px-5 py-3">
        <Badge variant="info">{policy.policy_type}</Badge>
        <span className="text-caption text-text-tertiary">
          {policy.word_count} words, tailored to {businessTypeLabel(policy.tailored_to).toLowerCase()}
        </span>
      </div>

      <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap border-t border-surface-border bg-surface px-5 py-4 font-mono text-caption leading-relaxed text-text-secondary">
        {policy.content}
      </pre>
    </Card>
  )
}
