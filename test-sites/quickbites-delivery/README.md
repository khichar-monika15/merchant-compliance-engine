# QuickBites Delivery — Synthetic Test Site (Grade D)

Deliberately non-compliant food delivery site used to test MCIE gap detection.

## Planted compliance gaps

| Gap | Location | Expected finding |
|-----|----------|-----------------|
| Copy-paste privacy policy | privacy.html | Mentions "FoodZapp Private Limited" instead of QuickBites |
| US address (not India) | contact.html | RBI requires Indian address; this has a San Francisco address |
| No refund policy | (missing) | RBI-001 fails — food delivery must publish refund/cancellation policy |
| No T&C | (missing) | RBI-003 fails |
| No GST number | index.html footer | RBI-005 fails |
| 8 scripts without SRI | index.html | PCI-001/PCI-002 fail — including Facebook, Hotjar, Intercom, Amplitude |
| Minimal security headers | vercel.json | Only X-Content-Type-Options; missing CSP, HSTS, X-Frame-Options |

## Expected score range

Score: 15–40 | Grade: D

## To serve locally

```bash
npx serve . -p 4004
```
