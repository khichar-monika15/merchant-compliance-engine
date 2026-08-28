# Merchant Compliance Intelligence Engine (MCIE)

## Project overview

AI-powered multi-agent system for Razorpay AI Buildathon 2026 (Track 05 — Open Track).
Pre-qualifies merchants for payment gateway onboarding by auditing website compliance,
KYC consistency, PCI DSS surface security, and integration readiness.

## Architecture

- Supervisor-worker pattern using LangGraph (StateGraph)
- 7 specialist agents: WebCrawler, ComplianceAuditor, PCIScanner, KYCValidator, PolicyGenerator, IntegrationAdvisor, ReportGenerator
- Graph: validate → crawl → parallel_analysis (asyncio.gather) → conditional policy_gen → report
- LLM via OpenAI-compatible endpoint (AWS Bedrock mantle, qwen.qwen3-32b by default) or Anthropic direct API
- FastAPI backend, React+TypeScript+Tailwind frontend
- SQLite (aiosqlite) for audit trail persistence

## Key commands

```bash
# Install deps
cd merchant-compliance-engine && uv sync

# Backend
uv run uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Tests
uv run pytest backend/tests/ -v

# Playwright browsers
uv run playwright install chromium

# Full ground-truth validation (serve all 4 test sites first — see below)
uv run python -m backend.tests.validate_ground_truth
```

## Test sites (synthetic)

Serve on these ports — `validate_ground_truth.py` and the docs all assume them.

- `test-sites/freshkart-india/` — port 4001 — 24 / Grade F (every major gap planted)
- `test-sites/quickbites-delivery/` — port 4002 — 36 / Grade D (KYC mismatches, copy-paste policy)
- `test-sites/clouddesk-saas/` — port 4003 — 52 / Grade C (thin policies)
- `test-sites/artisan-weaves/` — port 4004 — 85 / Grade B (nearly ready)

Served locally the `vercel.json` security headers do not apply, so all four report their headers
as missing. Ground truth encodes the local-serving values.

## Environment

- Python 3.12 (uv-managed)
- Node 24+
- `.env` is optional. Without it the engine still runs: policy quality falls back to rule-based
  scoring and the report records that the LLM was unavailable.
  - `OPENAI_API_KEY` + `OPENAI_BASE_URL` (Bedrock mantle, default) + `LLM_MODEL=qwen.qwen3-32b`
  - or `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL` (direct Anthropic API)
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (test keys, `rzp_test_` prefix) are optional too —
  without them the test order fails and integration scores 70 instead of 100.

## Conventions

- All agents export `async run(state: EngineState) -> dict` returning partial state updates
- Every agent appends to `audit_log` with timestamps
- Compliance checks ground in `backend/knowledge/*.json` — never LLM memory alone. RBI checks read
  `rbi_mdd_checklist.json`; PCI scoring reads its deduction constants from
  `pci_dss_surface_checks.json`
- The LLM refines policy quality scores; it never gates them. Every score has a rule-based fallback
  so a run without credentials still produces an honest report
- Graceful failure: one agent error must not block others
- LangGraph parallel execution via `asyncio.gather()` inside a single `parallel_analysis` node
- Git identity: khichar-monika15
