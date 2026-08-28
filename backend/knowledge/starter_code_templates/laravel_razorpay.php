<?php
// routes/api.php
use App\Http\Controllers\PaymentController;
Route::post('/create-order', [PaymentController::class, 'createOrder']);
Route::post('/verify-payment', [PaymentController::class, 'verifyPayment']);

// app/Http/Controllers/PaymentController.php
namespace App\Http\Controllers;

use Illuminate\Http\Request;

class PaymentController extends Controller
{
    private $razorpay;

    public function __construct()
    {
        $api = new \Razorpay\Api\Api(
            config('services.razorpay.key_id'),
            config('services.razorpay.key_secret')
        );
        $this->razorpay = $api;
    }

    public function createOrder(Request $request)
    {
        $order = $this->razorpay->order->create([
            'amount'   => $request->input('amount'),   // in paise
            'currency' => $request->input('currency', 'INR'),
            'notes'    => ['created_by' => auth()->id()],
        ]);
        return response()->json($order);
    }

    public function verifyPayment(Request $request)
    {
        $signature = hash_hmac(
            'sha256',
            $request->razorpay_order_id . '|' . $request->razorpay_payment_id,
            config('services.razorpay.key_secret')
        );

        if (hash_equals($signature, $request->razorpay_signature)) {
            // Mark order as paid in your database
            return response()->json(['status' => 'ok']);
        }
        return response()->json(['status' => 'error', 'message' => 'Invalid signature'], 400);
    }
}

// config/services.php — add:
// 'razorpay' => [
//     'key_id'     => env('RAZORPAY_KEY_ID', 'rzp_test_YOUR_KEY_ID'),
//     'key_secret' => env('RAZORPAY_KEY_SECRET', ''),
// ],
