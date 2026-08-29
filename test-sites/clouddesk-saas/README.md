# CloudDesk SaaS — Synthetic Test Site (Grade C)

Partially compliant SaaS customer support platform. Has some policies but they're thin/placeholder-quality and key items are missing.

## Planted compliance gaps

| Gap | Location | Expected finding |
|-----|----------|-----------------|
| No Terms & Conditions | (missing) | RBI-003 fails — no T&C page linked anywhere |
| No GST number | index.html, contact.html | RBI-005 fails — SaaS company with no GST |
| Thin privacy policy | privacy.html | About 56 words, no data category detail, no DPDP Act mention |
| Thin refund policy | refund.html | About 43 words, vague "case-by-case" language |
| 3 scripts without SRI | index.html | GTM, Facebook Pixel, Intercom — no integrity attributes |
| Minimal security headers | vercel.json | Only X-Frame-Options:SAMEORIGIN; missing CSP, HSTS, X-Content-Type-Options, Referrer-Policy |

## What is correct

- Contact page: has Indian address (Bengaluru), phone number, email
- Company name consistent: "CloudDesk Solutions Private Limited" throughout
- Some security headers present (partial credit)

## Expected output

Served locally on port 4003:

- Grade: C
- Score: 55 (expected range 50-62)
- RBI: 26 — refund (2/10) and privacy (1/10) exist but are 40-60 word stubs,
  not missing; T&C and GSTIN are absent
- PCI: 46 — 3 third-party scripts, none with SRI
- KYC: overall_consistent = true
- Critical gaps: 5

## To serve locally

```bash
npx serve . -p 4003
```
