import requests
import uuid
import logging
import re
from django.conf import settings
from apps.management.models import ManagementLog
from django.core.mail import send_mail
from twilio.rest import TwilioClient

logger = logging.getLogger(__name__)

def initialize_payment(job, user, amount):
    tx_ref = f"job-{job.id}-client-{user.id}-{uuid.uuid4().hex[:6]}"
    
    description = re.sub(r'[^a-zA-Z0-9\-_\s.]', '', job.title)[:100] 
    payload = {
        'amount': str(amount),
        'currency': 'ETB',
        'email': user.email or 'lily.yishak',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'phone_number': user.phone_number or '',
        'tx_ref': tx_ref,
        'callback_url': 'https://api.skillconnect.wisewaytech.com/jobs/payment-callback/',
        'return_url': '',
        'customization': {
            'title': f'Job {job.id} Payment'[:16], 
            'description': description
        }
    }
    headers = {
        'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY.strip()}',
        'Content-Type': 'application/json'
    }
    try:
        logger.info(f"Sending Chapa request: {payload}")
        response = requests.post(
            f"{settings.CHAPA_BASE_URL}/transaction/initialize",
            json=payload,
            headers=headers,
            timeout=10,
            verify=True
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"Chapa response: {data}")
        if data.get('status') == 'success':
            return data['data']['checkout_url'], tx_ref
        else:
            logger.error(f"Chapa initialization failed: {data}")
            raise ValueError(f"Chapa initialization failed: {data.get('message', 'Unknown error')}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Chapa HTTP error: {str(e)}, Response: {response.text}")
        raise ValueError(f"Invalid payment request: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Chapa request failed: {str(e)}, Response: {response.text if 'response' in locals() else 'No response'}")
        raise
    except ValueError as e:
        logger.error(f"Chapa payload error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in initialize_payment: {str(e)}")
        raise

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

def send_notification(user, subject, email_message, sms_message):
    """
    Send notifications to users via email and SMS.
    
    Args:
        user: User object to send notification to
        subject: Email subject
        email_message: Email message content
        sms_message: SMS message content
    """
    try:
        # Send email if user has email
        if user.email:
            send_mail(
                subject=subject,
                message=email_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
            logger.info(f"Email notification sent to {user.email}")

        # Send SMS if user has phone number
        if user.phone_number:
            try:
                client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                message = client.messages.create(
                    body=sms_message,
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=user.phone_number
                )
                logger.info(f"SMS notification sent to {user.phone_number}")
            except Exception as e:
                logger.error(f"Failed to send SMS to {user.phone_number}: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
        raise