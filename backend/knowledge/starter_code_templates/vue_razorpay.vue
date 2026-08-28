<template>
  <button @click="handlePay">Pay ₹{{ amount / 100 }}</button>
</template>

<script setup lang="ts">
import { defineProps } from 'vue';

const props = defineProps<{ amount: number }>();

declare global {
  interface Window { Razorpay: any }
}

function loadRazorpay(): Promise<boolean> {
  return new Promise(resolve => {
    if (window.Razorpay) return resolve(true);
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

async function handlePay() {
  const loaded = await loadRazorpay();
  if (!loaded) { alert('Razorpay failed to load'); return; }

  const order = await fetch('/api/create-order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount: props.amount, currency: 'INR' }),
  }).then(r => r.json());

  const rzp = new window.Razorpay({
    key: 'rzp_test_YOUR_KEY_ID',
    amount: order.amount,
    currency: order.currency,
    name: 'Your Store',
    order_id: order.id,
    handler: async (response: any) => {
      await fetch('/api/verify-payment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(response),
      });
    },
  });
  rzp.open();
}
</script>
