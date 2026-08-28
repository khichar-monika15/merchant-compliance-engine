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

- Grade: F
- Score: 10-25
- All 5 RBI checks: FAIL
- PCI score: near 0 (no headers, no SRI)
- KYC: overall_consistent = false
