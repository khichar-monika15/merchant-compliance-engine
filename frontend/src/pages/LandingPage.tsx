import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Code2,
  FileText,
  Lock,
  Radar,
  ScrollText,
  ShieldCheck,
  Users,
} from 'lucide-react'

import { Badge, Button, Card, cn } from '@/components/ui'

/**
 * Every number here is measured, not aspirational, and the countable ones are asserted against
 * the backend by `backend/tests/test_frontend_claims.py`. The timing is a real measurement of
 * the four local sites on the rule path; an LLM-refined run adds model round trips and is
 * slower, which is why the detail names the path rather than quoting one number for both.
 */
const METRICS = [
  { value: '7', label: 'specialist agents', detail: 'four running concurrently' },
  { value: '12', label: 'compliance checks', detail: '7 RBI, 5 PCI DSS' },
  { value: '5 to 9s', label: 'per full audit', detail: 'four local sites, rule path' },
  { value: 'A to F', label: 'readiness grade', detail: 'weighted across four axes' },
]

const FEATURES = [
  {
    icon: ScrollText,
    title: 'RBI due diligence',
    body: 'Refund, privacy, terms, contact, GSTIN display and, for merchants who ship goods, delivery terms. Checked against the Master Directions checklist rather than model memory.',
  },
  {
    icon: Lock,
    title: 'PCI DSS surface scan',
    body: 'Requirements 6.4.3 and 11.6.1: every script inventoried and risk classified, SRI verified, and the security header suite graded on the checkout page.',
  },
  {
    icon: Users,
    title: 'KYC name consistency',
    body: 'PAN, GST and bank names normalised then compared pairwise, so Pvt versus Private is not a mismatch but a genuine spacing difference is.',
  },
  {
    icon: FileText,
    title: 'Policy drafting',
    body: 'Where a policy is missing or too thin, the engine drafts a replacement tailored to the detected business type.',
  },
  {
    icon: Code2,
    title: 'Integration advice',
    body: 'Detects the merchant stack and returns the matching Razorpay path with working starter code, from the Shopify app to Standard Checkout.',
  },
  {
    icon: ShieldCheck,
    title: 'Full audit trail',
    body: 'Every agent records what it did, what it found and how long it took. Nothing in the score is unexplained.',
  },
]

const STEPS = [
  { n: '01', title: 'Give it a URL and three names', body: 'The website, plus the business name as it appears on PAN, GST and the bank account.' },
  { n: '02', title: 'Seven agents audit in parallel', body: 'A crawler feeds four analysers running concurrently, then policy drafting and scoring.' },
  { n: '03', title: 'Read the graded report', body: 'A score out of 100, a grade, and every gap with a specific fix. Anything found on the site links to the page it came from.' },
]

function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  const [ref, setRef] = useState<HTMLDivElement | null>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    if (!ref) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true)
          io.disconnect()
        }
      },
      { rootMargin: '-40px' },
    )
    io.observe(ref)
    return () => io.disconnect()
  }, [ref])

  return (
    <div
      ref={setRef}
      className={cn('transition-all duration-500', shown ? 'opacity-100' : 'translate-y-4 opacity-0', className)}
    >
      {children}
    </div>
  )
}

export function LandingPage() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="min-h-screen bg-surface">
      <header
        className={cn(
          'fixed inset-x-0 top-0 z-50 transition-colors duration-200',
          scrolled && 'border-b border-surface-border bg-surface-raised/90 backdrop-blur',
        )}
      >
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-5">
          <ShieldCheck className="h-5 w-5 text-accent" />
          <span className="text-body font-semibold text-text-primary">MCIE</span>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/login">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link to="/signup">
              <Button size="sm">Start a scan</Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden px-5 pb-20 pt-32">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(13,148,251,0.14), transparent), linear-gradient(rgba(28,37,54,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(28,37,54,0.35) 1px, transparent 1px)',
            backgroundSize: '100% 100%, 48px 48px, 48px 48px',
          }}
        />
        <div className="relative mx-auto max-w-3xl text-center">
          <Badge variant="info">Razorpay AI Buildathon 2026 · Track 05</Badge>
          <h1 className="mt-5 bg-gradient-to-r from-text-primary to-accent bg-clip-text text-display text-transparent">
            Is this merchant ready to go live?
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-body text-text-secondary">
            Payment aggregators reject merchants for missing refund policies, mismatched KYC names
            and unsafe checkout pages, and they find out late. MCIE audits all of it from a URL and
            three names, and returns a graded report with the specific fix for every gap.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/signup">
              <Button size="lg" trailingIcon={<ArrowRight className="h-4 w-4" />}>
                Run a compliance scan
              </Button>
            </Link>
            <Link to="/checks">
              <Button size="lg" variant="secondary">
                See every check
              </Button>
            </Link>
          </div>
        </div>

        <Reveal className="relative mx-auto mt-16 max-w-4xl">
          <div className="grid grid-cols-2 gap-4 rounded-xl border border-surface-border bg-surface-card p-6 sm:grid-cols-4">
            {METRICS.map((m) => (
              <div key={m.label} className="text-center">
                <p className="text-h1 text-text-primary">{m.value}</p>
                <p className="text-body-sm text-text-secondary">{m.label}</p>
                <p className="mt-0.5 text-caption text-text-tertiary">{m.detail}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <section className="border-t border-surface-border px-5 py-20">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <h2 className="text-h1 text-text-primary">How it works</h2>
          </Reveal>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {STEPS.map((s) => (
              <Reveal key={s.n}>
                <div className="border-l-2 border-accent pl-4">
                  <p className="font-mono text-caption text-accent">{s.n}</p>
                  <h3 className="mt-1 text-h3 text-text-primary">{s.title}</h3>
                  <p className="mt-1.5 text-body-sm text-text-secondary">{s.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-surface-border px-5 py-20">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <h2 className="text-h1 text-text-primary">What gets checked</h2>
            <p className="mt-2 max-w-2xl text-body-sm text-text-secondary">
              Deterministic rules do the checking and hold the source of truth. The model is used
              in two places where judgement is needed: rating how substantive a policy document
              is, and drafting a replacement when one is missing. It never decides whether a
              check passes, and every score it produces has a rule based fallback.
            </p>
          </Reveal>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <Reveal key={title}>
                <Card interactive className="h-full">
                  <Icon className="h-5 w-5 text-accent" />
                  <h3 className="mt-3 text-h3 text-text-primary">{title}</h3>
                  <p className="mt-1.5 text-body-sm text-text-secondary">{body}</p>
                </Card>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-surface-border px-5 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <Radar className="mx-auto h-8 w-8 text-accent" />
          <h2 className="mt-4 text-h1 text-text-primary">Stop guessing. Start knowing.</h2>
          <p className="mt-3 text-body text-text-secondary">
            Four synthetic merchant sites ship with the repo, graded F, D, C and B, so you can
            reproduce every number in this report yourself.
          </p>
          <Link to="/signup" className="mt-6 inline-block">
            <Button size="lg" trailingIcon={<ArrowRight className="h-4 w-4" />}>
              Start a scan
            </Button>
          </Link>
        </div>
      </section>

      <footer className="border-t border-surface-border px-5 py-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 text-caption text-text-tertiary sm:flex-row sm:items-center sm:justify-between">
          <span className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            Merchant Compliance Intelligence Engine
          </span>
          <span>
            Authentication is a UI shell. The compliance engine has no user model.
          </span>
        </div>
      </footer>
    </div>
  )
}
