# Merchant Compliance Intelligence Engine (MCIE)

**Razorpay AI Buildathon 2026 · Track 05 — Open Track**

An AI-powered multi-agent pipeline that pre-qualifies merchants for payment gateway onboarding.
Given a merchant website URL and KYC details (PAN name, GST legal name, bank account name), the
engine crawls the site, audits it against RBI Merchant Due Diligence and PCI DSS v4.0.1 surface
requirements, checks that the three KYC documents actually agree, writes the policy documents that
are missing, recommends a Razorpay integration path with working starter code, and scores the whole
thing 0-100 with a grade from A to F.

## Quickstart

```bash
git clone https://github.com/khichar-monika15/merchant-compliance-engine
cd merchant-compliance-engine
uv sync
uv run playwright install chromium

cp .env.example .env      # see Configuration below
uv run pytest backend/tests/            # 532 tests, no credentials needed
uv run uvicorn backend.main:app --reload --port 8000
cd frontend && npm install && npm run dev   # http://localhost:5173
```

To run it the way it would be deployed, build the frontend once and let the backend serve it, so
the whole app is one process on one origin with no proxy involved:

```bash
cd frontend && npm run build && cd ..
uv run uvicorn backend.main:app --port 8000   # http://localhost:8000
```

## Configuration

Everything is optional. With no `.env` at all the engine still runs end to end — it falls back to
rule-based policy scoring and records in the report that the LLM was unavailable.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` + `OPENAI_BASE_URL` + `LLM_MODEL` | OpenAI-compatible endpoint (AWS Bedrock mantle). The default path. |
| `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL` | Anthropic direct API. Used when the `OPENAI_*` vars are empty. |
| `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` | Test-mode keys. Without them the live test order fails and the integration sub-score is 70 instead of 100; scans are unaffected. |
| `CRAWLER_TIMEOUT`, `CRAWLER_MAX_PAGES` | Crawl budget. Defaults 30s and 20 pages. |

## Architecture

Supervisor-worker pattern on a LangGraph `StateGraph`. The four independent analysis agents run
concurrently inside a single node via `asyncio.gather()`, which keeps the graph linear and avoids
LangGraph 0.2's fragile fan-out/join convergence.

```mermaid
graph LR
  A[validate_input] --> B[crawl_website]
  B -->|pages found| C[parallel_analysis]
  B -->|site unreachable| G([END])
  C -->|gaps found| E[generate_policies]
  C -->|no gaps| F[generate_report]
  E --> F
  F --> G([END])

  subgraph C [parallel_analysis · asyncio.gather]
    C1[ComplianceAuditor<br/>RBI MDD]
    C2[PCIScanner<br/>PCI DSS v4.0.1]
    C3[KYCValidator<br/>name matching]
    C4[IntegrationAdvisor<br/>stack detection]
  end
```

Every agent exports `async run(state: EngineState) -> dict` returning a partial state update, so
each is independently testable. An agent that raises is caught and recorded in `errors` and the
audit log without blocking the others.

### Scoring

| Axis | Weight | Source |
|---|---|---|
| RBI compliance | 40% | The applicable checks in `backend/knowledge/rbi_mdd_checklist.json`: five for every merchant, plus RBI-007 shipping for those who deliver physical goods. RBI-006 name consistency is scored under KYC |
| KYC consistency | 25% | How many of the 3 document pairs agree |
| PCI DSS surface | 20% | 4 of the 5 checks in `backend/knowledge/pci_dss_surface_checks.json` carry points; PCI-003 classifies every third-party script and raises warnings, notably session recorders that can capture card entry, without taking points from the other four |
| Integration readiness | 15% | Stack detected + starter code, with a live test order as a bonus |

Grades: A ≥ 90, B ≥ 75, C ≥ 50, D ≥ 25, F below that.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness check |
| `GET /api/knowledge` | Every rule the engine applies, served from the files the agents load. Backs the public `/checks` page. No auth |
| `POST /api/scan` | Start a scan. Body: `website_url`, `pan_name`, `gst_legal_name`, `bank_account_name`, optional `business_type`. Returns `{job_id, status}` |
| `GET /api/scan/{job_id}` | Poll status and fetch the report once complete |
| `WS /ws/scan/{job_id}` | Live agent progress. Replays history on connect, so a client that joins mid-scan or after it still sees every event |
| `POST /api/assistant` | Ask a question about a report. Body: `question`, optional `job_id`, optional `history`. Returns the answer plus `cited_checks`, the check ids it cites |

Interactive docs at `http://localhost:8000/docs`.

## Test sites

Four synthetic merchant sites with deliberately planted gaps, for a repeatable demo. Scores below
are what the engine actually produces when the sites are served locally.

| Site | Port | Stack | Score | Grade | Planted gaps |
|---|---|---|---|---|---|
| FreshKart India | 4001 | static HTML | 19 | F | No policy pages, 18 third-party scripts of which 15 count against SRI (two Razorpay scripts are exempt and one reCAPTCHA script carries a real integrity hash), GSTIN only in an HTML comment, KYC mismatches |
| QuickBites Delivery | 4002 | Nuxt | 26 | D | Thin boilerplate privacy policy, no refund or T&C, US registered office and no Indian address, no GSTIN, KYC mismatches |
| CloudDesk SaaS | 4003 | Next.js | 56 | C | Refund and privacy pages are 40-60 word stubs, no T&C, no GSTIN |
| Artisan Weaves | 4004 | Shopify | 86 | B | Nearly compliant — policies substantive but not exhaustive, GSTIN shown, KYC clean; missing a CSP header |

Each site carries a different stack signature, so the integration advisor is exercised across
three of its nine stack profiles: Shopify gets the Payment Button, static HTML gets Payment Links,
and both Next.js and Nuxt get Standard Checkout with different starter code. Two of the four land
on the same product, which is correct rather than a gap: the recommendation follows the stack.

The table shows the no-credentials numbers, so a reviewer cloning without an `.env` sees exactly
these. With an LLM configured the model refines the policy quality scores and the totals move by a
point or two. Measured on both paths against `qwen.qwen3-32b`: FreshKart 19 F either way,
QuickBites 26 then 27, CloudDesk 56 then 58, Artisan 86 then 84. No grade moves, and the bounds in
`ground_truth/*.json` hold on both. One run exercises one path, so checking both means running the
harness twice; it prints which path it actually took, says so when a configured provider turns out
to be unreachable, and asserts the exact recorded score only on the deterministic rule path.

Serve them and run the full comparison against ground truth:

```bash
uv run python test-sites/serve.py     # all four, on 4001-4004

uv run python -m backend.tests.validate_ground_truth
```

Artisan's `vercel.json` sets four security headers and CloudDesk's sets one; FreshKart and
QuickBites declare a header rule with nothing in it, which is the planted fault. `serve.py` reads
each site's `vercel.json` and actually sends those headers, so the header checks grade the site
rather than the serving method. Under `npx serve`, which ignores `vercel.json`, all four reported
every header missing, PCI-004 and PCI-005 could not tell them apart, and 25 of the 100 PCI points
were decided by how the site was served. That is why Artisan scores 86 rather than 81 and
CloudDesk 56 rather than 55.

## The assistant

A merchant who reads "PCI: CSP header missing" and does not know what a Content Security Policy is
gets nothing from the report. The chat panel closes that gap.

It is handed a digest built from `backend/knowledge/*.json` and, when a report is open, that
merchant's own findings, so the rules it explains are the rules the engine applied. Answers that
come from the knowledge base cite the check id, and the response carries those ids separately, so
the panel can badge them. An id the knowledge base does not declare is filtered out rather than
rendered, which means a model that invents `PCI-009` cannot make it look like a citation.

It will also answer wider questions, and says so rather than pretending everything is grounded.
That is the reason the panel carries a disclaimer, and why the citation badges matter: they are
what separates "this is your RBI-001 finding" from the model talking.

Unlike every score in this engine, this has no rule-based fallback, because a conversation cannot
have one. With no credential configured it says so plainly instead of rendering an apology as
though it were an answer.

## Tech stack

- **Backend**: Python 3.12, FastAPI, LangGraph 0.2.60, Playwright, SQLite (aiosqlite)
- **LLM**: AWS Bedrock mantle (OpenAI-compatible) or Anthropic direct — both optional
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite, Zustand, React Router
- **Payment**: Razorpay Python SDK (test mode)

## Known limitations

- The four test sites are synthetic and written by us, so the ground-truth numbers measure the
  engine against a corpus we control. They demonstrate that the engine discriminates between
  compliance levels; they are not a claim about accuracy on real merchant websites.
- Ground truth is recorded on the deterministic rule-based path so it reproduces on a clean clone
  with no credentials. With an LLM configured, policy quality scores can move a point or two and
  the totals shift with them.
- Generated policy documents are drafts for a merchant to review, not legal advice. Nothing checks
  them for legal accuracy.
- A site with no checkout or cart page has its security headers graded on the homepage.
- `verify_payment_signature` in `backend/tools/razorpay_client.py` is written and tested but
  not wired to a webhook route, because there is no webhook route yet.
- The assistant needs a language model. Everything else in the engine runs without one.
- Accounts are a demo shell held in the browser tab. The API is unauthenticated, and the UI says
  so with a "Demo mode" badge rather than implying otherwise.
