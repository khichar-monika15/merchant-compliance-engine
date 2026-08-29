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
          // The cap-at-2 rule lives in the policy quality scorer, which only the page-searched
          // checks use. RBI-004 and RBI-005 score differently, so claiming it for them was wrong.
          <Section
            title={
              check.detection_strategy === 'page_search'
                ? 'Red flags that cap the score at 2'
                : 'Placeholder values that do not count as compliant'
            }
          >
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
  const s = check.scoring ?? {}
  const deductions = s.deductions ?? []
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

      <div className="space-y-3">
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

        {/* Only PCI-001 uses `deductions`. Rendering that shape alone left four of five checks
            looking like they had no scoring model at all. */}
        {s.per_script_without_sri_deduction != null && (
          <Section title="How points are lost">
            <p className="text-caption text-text-secondary">
              {s.per_script_without_sri_deduction} points per third-party script without an
              integrity hash, capped at {s.max_deduction}.
            </p>
          </Section>
        )}

        {s.no_csp_deduction != null && (
          <Section title="How points are lost">
            <ul className="space-y-1">
              {[
                ['No CSP header', s.no_csp_deduction],
                ['Weak CSP', s.weak_csp_deduction],
                ['Moderate CSP', s.moderate_csp_deduction],
                ['Strong CSP', s.strong_csp_deduction],
              ].map(([label, points]) => (
                <li key={String(label)} className="flex items-baseline gap-2">
                  <span className="font-mono text-caption text-status-danger">-{points}</span>
                  <span className="text-caption text-text-secondary">{label}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {s.headers?.length ? (
          <Section title="Headers scored, and what each is worth">
            <ul className="space-y-1">
              {s.headers.map((h) => (
                <li key={h.name} className="flex flex-wrap items-baseline gap-2">
                  <code className="font-mono text-caption text-accent">{h.name}</code>
                  <span className="font-mono text-caption text-text-tertiary">{h.points} pts</span>
                  {h.requirement && (
                    <span className="text-caption text-text-secondary">{h.requirement}</span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {check.grading && (
          <Section title="Strength bands">
            <ul className="space-y-1">
              {Object.entries(check.grading).map(([band, g]) => (
                <li key={band} className="flex flex-wrap items-baseline gap-2">
                  <span className="font-mono text-caption text-accent">{band}</span>
                  <span className="font-mono text-caption text-text-tertiary">
                    score &ge; {g.score_min}
                  </span>
                  <span className="text-caption text-text-secondary">{g.description}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {check.known_exemptions?.length ? (
          <Section title="Exempt from this check">
            <Chips items={check.known_exemptions} />
            {check.notes && (
              <p className="mt-1 text-caption text-text-tertiary">{check.notes}</p>
            )}
          </Section>
        ) : null}

        {!check.scoring && (
          <p className="text-caption text-text-tertiary">
            Classification only. This check labels every third-party script by risk and category
            and raises no deduction of its own.
          </p>
        )}
      </div>
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
              <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-h2 text-text-primary">
                  Script risk taxonomy
                  <span className="ml-2 text-body-sm text-text-tertiary">
                    behind PCI-003
                  </span>
                </h2>
                <p className="text-caption text-text-tertiary">
                  updated {kb.script_risk.last_updated}
                </p>
              </div>
              <Card>
                <p className="mb-4 text-body-sm text-text-secondary">{kb.script_risk.notes}</p>
                <div className="space-y-3">
                  <Section title="Low risk domains">
                    <Chips items={kb.script_risk.low_risk.flatMap((e) => e.domains)} />
                  </Section>
                  <Section title="Medium risk domains">
                    <Chips items={kb.script_risk.medium_risk.flatMap((e) => e.domains)} />
                  </Section>
                  <Section title="Substrings that mark a script high risk">
                    <Chips items={kb.script_risk.high_risk_indicators} />
                  </Section>
                </div>
              </Card>
            </section>

            <section>
              <h2 className="mb-4 text-h2 text-text-primary">
                Stacks detected, and what each one gets recommended
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                {Object.entries(kb.stacks).map(([key, stack]) => (
                  <Card key={key}>
                    <div className="mb-2">
                      <code className="font-mono text-caption text-text-tertiary">{key}</code>
                    </div>
                    <p className="text-body-sm text-accent">
                      {stack.razorpay_recommendation.product}
                    </p>
                    <p className="mt-1 text-caption text-text-secondary">
                      {stack.razorpay_recommendation.reason}
                    </p>
                    <a
                      href={stack.razorpay_recommendation.docs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-block text-caption text-accent hover:underline"
                    >
                      Documentation
                    </a>
                  </Card>
                ))}
              </div>
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
                    {kb.scoring.grades.map((g, i) => (
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
                          {/* The bottom band is "below the one above it". Deriving it keeps the
                              number out of this file, which is the whole claim of this page. */}
                          {g.min_score === 0
                            ? `below ${kb.scoring.grades[i - 1]?.min_score ?? 0}`
                            : `${g.min_score} and above`}
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
