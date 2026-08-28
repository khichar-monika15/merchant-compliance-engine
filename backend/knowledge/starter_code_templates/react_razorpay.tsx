import { useCallback } from 'react';

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

export function PayButton({ amount }: { amount: number }) {
  const handlePay = useCallback(async () => {
    const loaded = await loadRazorpay();
    if (!loaded) { alert('Razorpay SDK failed to load'); return; }

    // Create order on your backend
    const order = await fetch('/api/create-order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount, currency: 'INR' }),
    }).then(r => r.json());

    const rzp = new window.Razorpay({
      key: 'rzp_test_YOUR_KEY_ID',
      amount: order.amount,
      currency: order.currency,
      name: 'Your Store',
      description: 'Purchase',
      order_id: order.id,
      handler: async (response: any) => {
        await fetch('/api/verify-payment', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(response),
        });
        alert('Payment successful!');
      },
      prefill: { name: '', email: '', contact: '' },
      theme: { color: '#528FF0' },
    });
    rzp.open();
  }, [amount]);

  return <button onClick={handlePay}>Pay ₹{amount / 100}</button>;
}
