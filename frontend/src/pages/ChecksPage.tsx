import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ShieldCheck, TriangleAlert } from 'lucide-react'

import { getKnowledge } from '@/api/client'
import type { KnowledgeBase, PciCheck, RbiCheck } from '@/api/types'
import { Badge, Card, SEVERITY_VARIANT, Spinner, cn } from '@/components/ui'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-overline uppercase text-text-tertiary">{title}</p>
      <div className="mt-1">{children}</div>
    </div>
  )
}

function Chips({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="rounded border border-surface-border bg-surface-raised px-1.5 py-0.5 font-mono text-caption text-text-secondary"
        >
          {item}
        </span>
      ))}
    </div>
  )
}

function RbiCard({ check }: { check: RbiCheck }) {
  const q = check.quality_criteria ?? {}
  const s = check.search ?? {}
  const variants = Object.entries(check.business_type_variations ?? {})

  return (
    <Card id={check.id} className="scroll-mt-20">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-caption text-text-tertiary">{check.id}</p>
          <h3 className="text-h3 text-text-primary">{check.name}</h3>
        </div>
        <Badge variant={SEVERITY_VARIANT[check.severity] ?? 'neutral'}>{check.severity}</Badge>
      </div>

      <p className="mb-4 text-body-sm text-text-secondary">{check.description}</p>

      <div className="space-y-3">
        {s.url_patterns?.length ? (
          <Section title="Pages searched">
            <Chips items={s.url_patterns} />
          </Section>
        ) : null}

        {s.body_keywords?.length ? (
          <Section title="Keywords that identify the page">
            <Chips items={s.body_keywords} />
          </Section>
        ) : null}

        {q.must_contain_topics?.length ? (
          <Section title="Topics the policy must cover">
            <Chips items={q.must_contain_topics} />
          </Section>
        ) : null}

        {variants.length > 0 && (
          <Section title="Extra topics by business type">
            <ul className="space-y-1">
              {variants.map(([type, v]) => (
                <li key={type} className="flex flex-wrap items-baseline gap-2">
                  <span className="font-mono text-caption text-accent">{type}</span>
                  <span className="text-caption text-text-secondary">
                    {(v.extra_topics ?? []).join(', ')}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {q.min_word_count ? (
          <Section title="Minimum length">
            <span className="text-body-sm text-text-secondary">{q.min_word_count} words</span>
          </Section>
        ) : null}

        {q.red_flags?.length ? (
          <Section title="Red flags that cap the score at 2">
            <Chips items={q.red_flags} />
          </Section>
        ) : null}

        {q.gst_pattern && (
          <Section title="GSTIN format">
            <code className="break-all font-mono text-caption text-text-secondary">
              {q.gst_pattern}
            </code>
          </Section>
        )}

        {q.known_mismatch_patterns?.length ? (
          <Section title="Name mismatches detected">
            <Chips items={q.known_mismatch_patterns} />
          </Section>
        ) : null}

        {q.min_similarity_threshold != null && (
          <Section title="Similarity threshold">
            <span className="text-body-sm text-text-secondary">
              {Math.round(q.min_similarity_threshold * 100)}% after normalisation
            </span>
          </Section>
        )}
      </div>
    </Card>
  )
}

function PciCard({ check }: { check: PciCheck }) {
  const deductions = check.scoring?.deductions ?? []
  return (
    <Card id={check.id} className="scroll-mt-20">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-caption text-text-tertiary">
            {check.id} · Requirement {check.requirement}
          </p>
          <h3 className="text-h3 text-text-primary">{check.name}</h3>
        </div>
        <div className="flex items-center gap-2">
          {check.scoring?.max_points != null && (
            <span className="font-mono text-caption text-text-tertiary">
              {check.scoring.max_points} pts
            </span>
          )}
          <Badge variant={SEVERITY_VARIANT[check.severity] ?? 'neutral'}>{check.severity}</Badge>
        </div>
      </div>

      <p className="mb-4 text-body-sm text-text-secondary">{check.description}</p>

      {deductions.length > 0 && (
        <Section title="How points are lost">
          <ul className="divide-y divide-surface-border-subtle">
            {deductions.map((d, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-2 py-1.5">
                <code className="font-mono text-caption text-accent">{d.condition}</code>
                <span className="font-mono text-caption text-status-danger">-{d.points}</span>
                <span className="text-caption text-text-secondary">{d.reason}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </Card>
  )
}

export function ChecksPage() {
  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    getKnowledge().then(setKb).catch(() => setError(true))
  }, [])

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-surface-border">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-5">
          <Link to="/" className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <span className="text-body font-semibold text-text-primary">MCIE</span>
          </Link>
          <Link
            to="/"
            className="ml-auto inline-flex items-center gap-1.5 text-body-sm text-text-secondary hover:text-text-primary"
          >
            <ArrowLeft className="h-4 w-4" />
            Home
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 py-10">
        <h1 className="text-h1 text-text-primary">What the engine checks</h1>
        <p className="mt-2 max-w-3xl text-body text-text-secondary">
          Every rule below is read from{' '}
          <code className="font-mono text-text-primary">backend/knowledge</code> at request time,
          by the same loader the agents use. This page cannot describe a rule the engine does not
          apply, and a test fails the build if any declared rule stops being read.
        </p>

        {error && (
          <Card className="mt-6 border-status-danger/40 bg-status-danger-muted">
            <div className="flex gap-3">
              <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-status-danger" />
              <p className="text-body-sm text-text-secondary">
                The compliance engine is not reachable, so the rules cannot be loaded. Start the
                backend on port 8000 and reload.
              </p>
            </div>
          </Card>
        )}

        {!kb && !error && (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        )}

        {kb && (
          <div className="mt-8 space-y-10">
            <section>
              <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-h2 text-text-primary">
                  RBI Merchant Due Diligence
                  <span className="ml-2 text-body-sm text-text-tertiary">
                    {kb.rbi.checks.length} checks
                  </span>
                </h2>
                <p className="text-caption text-text-tertiary">{kb.rbi.source}</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {kb.rbi.checks.map((c) => (
                  <RbiCard key={c.id} check={c} />
                ))}
              </div>
            </section>

            <section>
              <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-h2 text-text-primary">
                  PCI DSS surface
                  <span className="ml-2 text-body-sm text-text-tertiary">
                    {kb.pci.checks.length} checks
                  </span>
                </h2>
                <p className="text-caption text-text-tertiary">{kb.pci.source}</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {kb.pci.checks.map((c) => (
                  <PciCard key={c.id} check={c} />
                ))}
              </div>
              <p className="mt-3 text-caption text-text-tertiary">
                Headers are graded on a payment page where one exists, matched on:{' '}
                {kb.pci.payment_page_patterns.join(', ')}.
              </p>
            </section>

            <section>
              <h2 className="mb-4 text-h2 text-text-primary">How the score is built</h2>
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <p className="mb-3 text-overline uppercase text-text-tertiary">Weights</p>
                  <ul className="space-y-2">
                    {Object.entries(kb.scoring.weights).map(([label, weight]) => (
                      <li key={label} className="flex items-center gap-3">
                        <span className="w-40 shrink-0 text-body-sm text-text-primary">
                          {label}
                        </span>
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-border">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{ width: `${weight * 100}%` }}
                          />
                        </div>
                        <span className="w-10 shrink-0 text-right font-mono text-caption text-text-secondary">
                          {Math.round(weight * 100)}%
                        </span>
                      </li>
                    ))}
                  </ul>
                </Card>

                <Card>
                  <p className="mb-3 text-overline uppercase text-text-tertiary">Grades</p>
                  <ul className="space-y-1.5">
                    {kb.scoring.grades.map((g) => (
                      <li key={g.grade} className="flex items-center gap-3">
                        <span
                          className={cn(
                            'w-6 text-body font-bold',
                            g.grade === 'A' && 'text-grade-a',
                            g.grade === 'B' && 'text-grade-b',
                            g.grade === 'C' && 'text-grade-c',
                            g.grade === 'D' && 'text-grade-d',
                            g.grade === 'F' && 'text-grade-f',
                          )}
                        >
                          {g.grade}
                        </span>
                        <span className="text-body-sm text-text-secondary">
                          {g.min_score === 0 ? 'below 25' : `${g.min_score} and above`}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-4 text-caption text-text-tertiary">
                    Policy quality is scored 0 to 10 by rules first. Where credentials are
                    configured the model refines that score against the topic list above; where
                    they are not, the rule based score stands and the report says so.
                  </p>
                </Card>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}
