# FreshKart India — Grade F Test Site

Synthetic e-commerce site for MCIE ground-truth validation. Deliberately non-compliant.

## Planted violations

| Check | Violation |
|-------|-----------|
| RBI-001 Refund Policy | Missing entirely |
| RBI-002 Privacy Policy | Missing entirely |
| RBI-003 T&C | Missing entirely |
| RBI-004 Contact Info | Email only — no phone, no physical address |
| RBI-005 GST Display | No GSTIN shown anywhere |
| PCI-001 Script Inventory | 14+ third-party scripts |
| PCI-002 SRI | Zero scripts have integrity attribute |
| PCI-003 Script Risk | Facebook Pixel, Hotjar, Intercom, Segment, OneSignal, Mixpanel, Amplitude (all medium/high risk) |
| PCI-004 CSP Header | Not set (vercel.json has empty headers array) |
| PCI-005 Security Headers | None of HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |

## KYC inputs (for ground-truth test)

- PAN name: FreshKart Pvt. Ltd.
- GST legal name: FRESHKART PRIVATE LIMITED
- Bank account name: Fresh Kart Private Limited

All three diverge — "Pvt. Ltd." vs "PRIVATE LIMITED" vs extra space "Fresh Kart". KYC consistency should fail.

## Expected output

Served locally on port 4001:

- Grade: F
- Score: 19 (expected range 14-24)
- RBI: 8 — no policy page is found at all; the contact page is partial (4/10) and the sole
  GSTIN on the site sits inside an HTML
  comment and must not count as displayed
- PCI: 20 — no headers, 18 third-party scripts with 17 lacking SRI
- KYC: overall_consistent = false (5 mismatches)
- Critical gaps: 11
