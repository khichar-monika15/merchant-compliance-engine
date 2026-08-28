# MCIE Synthetic Test Sites

Four synthetic merchant websites for ground-truth validation of the Merchant Compliance
Intelligence Engine.

## Sites

Ports match `backend/tests/validate_ground_truth.py`. Scores are what the engine actually
produces when the sites are served locally.

| Site | Port | Score | Grade | Key violations |
|------|------|-------|-------|----------------|
| `freshkart-india/` | 4001 | 24 | F | No policy pages, 18 third-party scripts (17 without SRI), no security headers, GSTIN only in an HTML comment, KYC mismatch |
| `quickbites-delivery/` | 4002 | 36 | D | KYC name mismatch, no refund or T&C, copy-paste privacy policy naming another company, no GSTIN |
| `clouddesk-saas/` | 4003 | 52 | C | Refund and privacy pages are 40-60 word stubs, missing T&C and GSTIN |
| `artisan-weaves/` | 4004 | 85 | B | Nearly compliant — all policies substantive, GSTIN shown, KYC clean; missing a CSP header |

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

Each site declares its security headers in `vercel.json`. A static local server does not apply
them, so served locally **every** site reports CSP, HSTS, X-Frame-Options, X-Content-Type-Options
and Referrer-Policy as missing, and the four PCI scores compress toward each other. The
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
