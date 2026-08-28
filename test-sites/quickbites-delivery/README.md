# QuickBites Delivery — Grade D Test Site

Synthetic food delivery site for MCIE ground-truth validation. KYC mismatches + missing policies.

## Compliance summary

| Check | Result | Notes |
|-------|--------|-------|
| RBI-001 Refund Policy | FAIL | Missing entirely |
| RBI-002 Privacy Policy | PARTIAL | Exists but copy-paste boilerplate, quality < 3/10 |
| RBI-003 T&C | FAIL | Missing |
| RBI-004 Contact Info | PARTIAL | Email + phone but NO physical address |
| RBI-005 GST Display | FAIL | No GSTIN shown |
| PCI-002 SRI | FAIL | 6+ scripts without SRI |
| PCI-004 CSP Header | FAIL | Not set |
| PCI-005 Security Headers | FAIL | None set |

## KYC inputs (for ground-truth test)

- PAN name: QuickBites Pvt. Ltd.
- GST legal name: QUICKBITES PRIVATE LIMITED
- Bank account name: Quick Bites Private Limited

KYC mismatches:
1. "QuickBites" vs "Quick Bites" — spacing difference in bank name
2. "Pvt. Ltd." vs "PRIVATE LIMITED" — abbreviation mismatch (known pattern, forces match=False even at high similarity)

KYC: overall_consistent = false, issues_count >= 2

## Expected output

- Grade: D
- Score: 15-40
- RBI: 0-1/5 (contact partial at best)
- KYC: overall_consistent = false
- Critical gaps: 3+
