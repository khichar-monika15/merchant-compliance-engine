// pages/api/create-order.ts
import type { NextApiRequest, NextApiResponse } from 'next';
import Razorpay from 'razorpay';

const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID!,
  key_secret: process.env.RAZORPAY_KEY_SECRET!,
});

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end();
  const { amount, currency = 'INR' } = req.body;
  const order = await razorpay.orders.create({ amount, currency });
  res.json(order);
}

// ---- components/PayButton.tsx ----
'use client';
import { useCallback } from 'react';

declare global {
  interface Window { Razorpay: any }
}

export function PayButton({ amount }: { amount: number }) {
  const handlePay = useCallback(async () => {
    const order = await fetch('/api/create-order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount }),
    }).then(r => r.json());

    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    document.body.appendChild(script);

    script.onload = () => {
      const rzp = new window.Razorpay({
        key: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID,
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
    };
  }, [amount]);

  return <button onClick={handlePay}>Pay ₹{amount / 100}</button>;
}
