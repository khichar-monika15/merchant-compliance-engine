# Razorpay on WooCommerce

WooCommerce integrates through the official Razorpay plugin. You do not need to write
checkout code, but you do need to configure webhooks correctly or orders will stay pending.

## Steps

1. In WordPress admin, go to **Plugins → Add New**, search for **Razorpay for WooCommerce**,
   install and activate it.
2. In the Razorpay Dashboard, go to **Settings → API Keys** and generate a key pair.
   Use the `rzp_test_` pair while you are testing.
3. Go to **WooCommerce → Settings → Payments → Razorpay** and enable it.
4. Paste the Key ID and Key Secret.
5. Copy the webhook URL shown on that settings page. In the Razorpay Dashboard under
   **Settings → Webhooks**, add it and subscribe to `payment.authorized` and `payment.failed`.
   Set the same webhook secret in both places.
6. Place a test order with the test card `4111 1111 1111 1111`, any future expiry, any CVV.

## What to check before going live

- The order status moves from `pending` to `processing` after payment. If it stays `pending`,
  the webhook is not reaching WordPress — check that the URL is publicly accessible and not
  blocked by a security plugin.
- Refunds issued from **WooCommerce → Orders** appear in the Razorpay Dashboard.
- Your WooCommerce store currency is INR.
- If you use a caching plugin, exclude the checkout and order-received pages.

## Notes

- The plugin supports both the hosted checkout and the newer embedded Magic Checkout.
- Switch to your `rzp_live_` keys and turn off test mode only after one successful test refund.
- Docs: https://razorpay.com/integrations/woocommerce/
