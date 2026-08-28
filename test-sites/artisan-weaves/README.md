# Artisan Weaves — Grade B Test Site

Synthetic handloom e-commerce site for MCIE ground-truth validation. Nearly compliant — missing CSP.

## Compliance summary

| Check | Result | Notes |
|-------|--------|-------|
| RBI-001 Refund Policy | PASS | 7-day return window, clear process, timeline specified |
| RBI-002 Privacy Policy | PASS | Comprehensive, mentions DPDP Act 2023 |
| RBI-003 T&C | PASS | Full terms page including governing law |
| RBI-004 Contact Info | PASS | Full address (Lucknow UP), phone, email |
| RBI-005 GST Display | PASS | GSTIN: 09ABCAW1234A1Z5 visible on multiple pages |
| PCI-002 SRI | PARTIAL | GTM and jQuery have SRI; Facebook Pixel does not |
| PCI-004 CSP Header | FAIL | Not set (the only major gap) |
| PCI-005 Security Headers | PASS | HSTS, X-Frame-Options: DENY, X-Content-Type-Options, Referrer-Policy all set |

## KYC inputs (for ground-truth test)

- PAN name: Artisan Weaves Private Limited
- GST legal name: ARTISAN WEAVES PRIVATE LIMITED
- Bank account name: Artisan Weaves Private Limited

KYC: PASS (all three normalize to the same name).

## Expected output

Served locally on port 4004:

- Grade: B
- Score: 85 (expected range 76-89)
- RBI: 5/5 pass
- PCI: 52 — deductions for the missing CSP and the Facebook Pixel without SRI
- KYC: overall_consistent = true
- Critical gaps: 3

Note: served locally the `vercel.json` headers do not apply, so HSTS, X-Frame-Options,
X-Content-Type-Options and Referrer-Policy also report as missing. Deployed to Vercel only the
CSP is absent.
