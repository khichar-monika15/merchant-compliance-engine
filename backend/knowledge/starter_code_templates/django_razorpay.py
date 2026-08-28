# views.py
import hashlib
import hmac
import json

import razorpay
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@require_POST
def create_order(request):
    data = json.loads(request.body)
    order = client.order.create({
        "amount": data["amount"],   # in paise
        "currency": data.get("currency", "INR"),
        "notes": {"created_by": str(request.user)},
    })
    return JsonResponse(order)


@csrf_exempt
@require_POST
def verify_payment(request):
    data = json.loads(request.body)
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{data['razorpay_order_id']}|{data['razorpay_payment_id']}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(expected, data["razorpay_signature"]):
        # Mark order as paid in your database here
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error", "message": "Invalid signature"}, status=400)


# settings.py — add these:
# RAZORPAY_KEY_ID = "rzp_test_YOUR_KEY_ID"
# RAZORPAY_KEY_SECRET = "YOUR_KEY_SECRET"

# urls.py
# from django.urls import path
# from . import views
# urlpatterns = [
#     path("api/create-order/", views.create_order),
#     path("api/verify-payment/", views.verify_payment),
# ]
