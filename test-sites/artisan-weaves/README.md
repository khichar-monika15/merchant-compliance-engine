# Artisan Weaves — Synthetic Test Site (Grade B)

Nearly-compliant Shopify-style handcraft e-commerce site. Has most compliance requirements in place with one deliberate gap.

## Planted compliance gap

| Gap | Location | Expected finding |
|-----|----------|-----------------|
| Missing Referrer-Policy header | vercel.json | Has CSP + HSTS + X-Frame-Options:DENY + X-Content-Type-Options, but NO Referrer-Policy |
| Facebook Pixel without SRI | index.html | fbevents.js has no integrity attribute; 3 other scripts DO have SRI |

## What is correct

- Refund policy: clear 7-day return window, condition requirements, process steps
- Privacy policy: DPDP Act 2023 compliant, data categories, third-party disclosure
- Terms and conditions: governing law (Karnataka), dispute resolution, liability cap
- Contact page: full Indian address (Bengaluru), +91 phone, email, working hours
- GST number: 29ABCAW1234F1Z7 in footer (valid format for Karnataka)
- Tech stack: Shopify detected via shopify-section classes and cdn.shopify.com scripts

## Expected score range

Score: 70–90 | Grade: B

## To serve locally

```bash
npx serve . -p 4001
```
