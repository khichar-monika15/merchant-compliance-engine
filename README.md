# Merchant Compliance Intelligence Engine (MCIE)

**Razorpay AI Buildathon 2026 · Track 05 — Open Track**

An AI-powered multi-agent pipeline that pre-qualifies merchants for payment gateway onboarding. Given a merchant website URL and KYC details (PAN name, GST legal name, bank account name), the engine:

1. Crawls the website with Playwright
2. Audits RBI Merchant Due Diligence requirements
3. Scans PCI DSS v4.0.1 surface compliance
4. Validates KYC document name consistency
5. Generates missing policy documents
6. Recommends a Razorpay integration path with starter code
7. Produces a readiness report scored 0–100 (grade A–F)

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/khichar-monika15/merchant-compliance-engine
cd merchant-compliance-engine
uv sync
uv run playwright install chromium

# 2. Configure
cp .env.example .env
# LLM — choose one:
#   Option A (AWS Bedrock mantle, default)
#     OPENAI_API_KEY=<bearer token>
#     OPENAI_BASE_URL=https://bedrock-mantle.us-east-1.api.aws/v1
#     LLM_MODEL=qwen.qwen3-32b
#   Option B (Anthropic direct)
#     ANTHROPIC_API_KEY=<api key>
# Payment (test keys)
#   RAZORPAY_KEY_ID=rzp_test_...
#   RAZORPAY_KEY_SECRET=...

# 3. Run backend
uv run uvicorn backend.main:app --reload --port 8000

# 4. Run frontend
cd frontend && npm install && npm run dev

# 5. Run tests
uv run pytest backend/tests/ -v
```

## Architecture

Supervisor-worker pattern (LangGraph StateGraph):

```
validate → crawl → [compliance + pci + kyc + integration] → policy_gen? → report
```

The parallel analysis phase runs all four agents concurrently via `asyncio.gather()`.

## Test sites

Four synthetic merchant sites with planted compliance gaps for repeatable demos:

| Site | Grade | Key issues |
|------|-------|-----------|
| FreshKart India | F | No policies, 14+ scripts without SRI, no GST |
| QuickBites Delivery | D | KYC name mismatches, copy-paste privacy policy |
| CloudDesk SaaS | C | Thin/placeholder policies, missing T&C |
| Artisan Weaves | B | Nearly compliant — missing Referrer-Policy only |

## Tech stack

- **Backend**: Python 3.12, FastAPI, LangGraph 0.2.60, Playwright, SQLite (aiosqlite)
- **LLM**: AWS Bedrock mantle (OpenAI-compat endpoint) or Anthropic direct API
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite, Recharts
- **Payment**: Razorpay Python SDK (test mode)

## Running the demo locally

```bash
# Serve test sites (needs 4 terminals or background processes)
npx serve test-sites/artisan-weaves -p 4001
npx serve test-sites/freshkart-india -p 4002
npx serve test-sites/clouddesk-saas -p 4003
npx serve test-sites/quickbites-delivery -p 4004

# Submit via frontend at http://localhost:5173
# or run the e2e script directly
uv run python backend/tests/e2e_artisan.py
```
