# Razorpay on Shopify

Shopify does not allow custom payment code in the checkout. Razorpay integrates through the
official app, not through a snippet you paste into your theme.

## Steps

1. Install **Razorpay Secure (Payment Gateway)** from the Shopify App Store.
2. In the Razorpay Dashboard, go to **Settings → API Keys** and generate a key pair.
   Use the `rzp_test_` pair while you are testing.
3. In Shopify, go to **Settings → Payments → Add payment method** and select Razorpay.
4. Paste the Key ID and Key Secret, then save.
5. Set your store to **Test mode** in the Razorpay app and place a test order using the
   test card `4111 1111 1111 1111`, any future expiry, any CVV.
6. Switch the app to Live mode and replace the keys with your `rzp_live_` pair once the test
   order settles.

## What to check before going live

- Razorpay appears as a payment option on the checkout page, not only in the admin.
- Your Shopify store currency is INR. Razorpay settles in INR for domestic merchants.
- Refunds initiated from the Shopify admin reach the Razorpay Dashboard. Test one refund
  end to end before your first real order.
- Webhooks are enabled in **Razorpay Dashboard → Settings → Webhooks** so order status stays
  in sync if a customer closes the browser mid-payment.

## Notes

- Shopify Payments and Razorpay cannot both be active for the same currency. Deactivate
  Shopify Payments first.
- Shopify Plus merchants can additionally use Razorpay in the checkout extensibility flow.
- Docs: https://razorpay.com/integrations/shopify/
