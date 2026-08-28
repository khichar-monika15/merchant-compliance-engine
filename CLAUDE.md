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

# Full ground-truth validation
uv run python -m backend.tests.validate_ground_truth
```

## Test sites (synthetic)

- `test-sites/freshkart-india/` — Grade F (every major gap planted)
- `test-sites/clouddesk-saas/` — Grade C (thin policies)
- `test-sites/artisan-weaves/` — Grade B (nearly ready)
- `test-sites/quickbites-delivery/` — Grade D (KYC mismatches, copy-paste policy)

## Environment

- Python 3.12 (uv-managed)
- Node 24+
- Needs `.env` with either:
  - `OPENAI_API_KEY` + `OPENAI_BASE_URL` (Bedrock mantle, default) + `LLM_MODEL=qwen.qwen3-32b`
  - or `ANTHROPIC_API_KEY` (direct Anthropic API)
- Also set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (test keys with `rzp_test_` prefix)

## Conventions

- All agents export `async run(state: EngineState) -> dict` returning partial state updates
- Every agent appends to `audit_log` with timestamps
- Compliance checks ground in `backend/knowledge/*.json` — never LLM memory alone
- Graceful failure: one agent error must not block others
- LangGraph parallel execution via `asyncio.gather()` inside a single `parallel_analysis` node
- Git identity: khichar-monika15
