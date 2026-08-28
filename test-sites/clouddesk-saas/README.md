# CloudDesk SaaS — Synthetic Test Site (Grade C)

Partially compliant SaaS customer support platform. Has some policies but they're thin/placeholder-quality and key items are missing.

## Planted compliance gaps

| Gap | Location | Expected finding |
|-----|----------|-----------------|
| No Terms & Conditions | (missing) | RBI-003 fails — no T&C page linked anywhere |
| No GST number | index.html, contact.html | RBI-005 fails — SaaS company with no GST |
| Thin privacy policy | privacy.html | Under 150 words, no data category detail, no DPDP Act mention |
| Thin refund policy | refund.html | Only 80 words, vague "case-by-case" language |
| 3 scripts without SRI | index.html | GTM, Facebook Pixel, Intercom — no integrity attributes |
| Minimal security headers | vercel.json | Only X-Frame-Options:SAMEORIGIN; missing CSP, HSTS, X-Content-Type-Options, Referrer-Policy |

## What is correct

- Contact page: has Indian address (Bengaluru), phone number, email
- Company name consistent: "CloudDesk Solutions Private Limited" throughout
- Some security headers present (partial credit)

## Expected score range

Score: 35–60 | Grade: C

## To serve locally

```bash
npx serve . -p 4003
```
