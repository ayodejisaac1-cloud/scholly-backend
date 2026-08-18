import requests
from ..config import settings

def initialize_payment(email, amount, reference):
    """Initialize Paystack payment"""
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "email": email,
        "amount": int(amount * 100),  # Convert to kobo
        "reference": reference,
        "callback_url": "https://yourdomain.com/payment-callback"
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def verify_payment(reference):
    """Verify Paystack payment"""
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }
    
    response = requests.get(url, headers=headers)
    return response.json()