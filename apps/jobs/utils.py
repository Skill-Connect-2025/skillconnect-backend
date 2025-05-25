# apps/jobs/utils.py
import uuid
import requests
import logging
from django.conf import settings
from django.core.mail import send_mail
import environ

logger = logging.getLogger(__name__)

def initialize_payment(job, client, amount):
    """
    Initialize a Chapa payment for a job.
    Returns (checkout_url, tx_ref) or raises an exception.
    """
    tx_ref = f"job-{job.id}-client-{client.id}-{uuid.uuid4().hex[:10]}"
    data = {
        'amount': str(amount),
        'currency': 'ETB',
        'email': client.email,
        'first_name': client.first_name or 'Anonymous',
        'last_name': client.last_name or '',
        'phone_number': client.worker_profile.phone_number or '0912345678',
        'tx_ref': tx_ref,
        'callback_url': 'https://api.skillconnect.wisewaytech.com/jobs/payment-callback/',
        'return_url': 'https://frontend-placeholder.com/payment/complete/',  # Placeholder for frontend
        'customization': {
            'title': f'SkillConnect Payment for {job.title}',
            'description': f'Payment for job ID {job.id}'
        }
    }
    headers = {
        'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(
            f'{settings.CHAPA_BASE_URL}/transaction/initialize',
            json=data,
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        if result.get('status') == 'success':
            return result['data']['checkout_url'], tx_ref
        else:
            logger.error(f'Chapa initialization failed: {result}')
            raise Exception(f'Chapa initialization failed: {result.get("message")}')
    except requests.RequestException as e:
        logger.error(f'Chapa request failed: {str(e)}')
        raise Exception(f'Payment service unavailable: {str(e)}')

def verify_payment(tx_ref):
    """
    Verify a Chapa payment transaction.
    Returns the verification result or raises an exception.
    """
    headers = {
        'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY}'
    }
    try:
        response = requests.get(
            f'{settings.CHAPA_BASE_URL}/transaction/verify/{tx_ref}',
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f'Chapa verification failed: {str(e)}')
        raise Exception(f'Verification failed: {str(e)}')