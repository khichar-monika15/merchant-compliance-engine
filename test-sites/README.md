# MCIE Synthetic Test Sites

Four synthetic merchant websites for ground-truth validation of the Merchant Compliance Intelligence Engine.

## Sites

| Site | Grade | URL (local) | Key violations |
|------|-------|-------------|----------------|
| `freshkart-india/` | F | :4001 | All 5 RBI checks fail, 14+ scripts no SRI, no security headers, KYC mismatch |
| `clouddesk-saas/` | C | :4002 | Missing T&C + GST, thin policies, only X-Frame-Options header |
| `artisan-weaves/` | B | :4003 | All policies present, only missing CSP header |
| `quickbites-delivery/` | D | :4004 | KYC name mismatch, no refund/T&C, copy-paste privacy, no headers |

## Serve locally

```bash
# Each site (from its directory)
npx serve test-sites/freshkart-india -p 4001
npx serve test-sites/clouddesk-saas   -p 4002
npx serve test-sites/artisan-weaves    -p 4003
npx serve test-sites/quickbites-delivery -p 4004
```

## Deploy to Vercel (for live URL testing)

```bash
cd test-sites/freshkart-india && vercel --prod
cd test-sites/clouddesk-saas   && vercel --prod
cd test-sites/artisan-weaves    && vercel --prod
cd test-sites/quickbites-delivery && vercel --prod
```

## Ground-truth validation

After deploying, update `backend/tests/validate_ground_truth.py` with the live Vercel URLs, then:

```bash
cd merchant-compliance-engine
uv run python -m backend.tests.validate_ground_truth
```

## Design principles

Each site plants specific violations precisely mapped to the RBI MDD and PCI DSS checks in
`backend/knowledge/*.json`. The violations are commented in the HTML source to make them
easy to verify. No violations are accidental — every missing policy, absent header, and
name mismatch is deliberate and documented in the site's README.
