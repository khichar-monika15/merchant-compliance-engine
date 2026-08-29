# MCIE Synthetic Test Sites

Four synthetic merchant websites for ground-truth validation of the Merchant Compliance
Intelligence Engine.

## Sites

Ports match `backend/tests/validate_ground_truth.py`. Scores are what the engine actually
produces when the sites are served locally.

| Site | Port | Stack | Score | Grade | Key violations |
|------|------|-------|-------|-------|----------------|
| `freshkart-india/` | 4001 | static HTML | 19 | F | No policy pages, 18 third-party scripts (15 without SRI, two Razorpay scripts are exempt), no security headers, GSTIN only in an HTML comment, KYC mismatch |
| `quickbites-delivery/` | 4002 | Nuxt | 28 | D | KYC name mismatch, no refund or T&C, thin boilerplate privacy policy, US-only address, no GSTIN |
| `clouddesk-saas/` | 4003 | Next.js | 55 | C | Refund and privacy pages are 40-60 word stubs, missing T&C and GSTIN |
| `artisan-weaves/` | 4004 | Shopify | 81 | B | Nearly compliant — policies substantive but not exhaustive, GSTIN shown, KYC clean; missing a CSP header |

## Serve locally

```bash
npx serve test-sites/freshkart-india      -p 4001
npx serve test-sites/quickbites-delivery  -p 4002
npx serve test-sites/clouddesk-saas       -p 4003
npx serve test-sites/artisan-weaves       -p 4004
```

## Ground-truth validation

With all four served, from the repo root:

```bash
uv run python -m backend.tests.validate_ground_truth
```

Expect `4/4 test sites passed`.

## A note on security headers

Artisan declares four security headers in its `vercel.json` and CloudDesk declares one;
FreshKart and QuickBites declare a rule with no headers in it, which is the planted fault. A
static local server does not apply any of them either way, so served locally **every** site
reports CSP, HSTS, X-Frame-Options, X-Content-Type-Options and Referrer-Policy as missing, and
the four PCI scores compress toward each other. The
ground-truth files encode the local-serving values. Deploy to Vercel to exercise the header
differences:

```bash
cd test-sites/freshkart-india && vercel --prod   # and likewise for the other three
```

Then point `validate_ground_truth.py` at the live URLs and update the `*_present` expectations in
`backend/tests/ground_truth/*.json`.

## Design principles

Each site plants specific violations mapped to the RBI MDD and PCI DSS checks in
`backend/knowledge/*.json`. The violations are commented in the HTML source to make them easy to
verify. No violation is accidental — every missing policy, absent header, and name mismatch is
deliberate and documented in the site's own README.
