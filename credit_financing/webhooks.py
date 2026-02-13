# ====================================
# CREDIT FINANCING WEBHOOKS
# Receive notifications from Company X
# ====================================

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.mail import send_mail
from decimal import Decimal
import json
import logging
from .models import CreditTransaction, CreditTransactionLog, CustomerInstallment

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def company_x_webhook(request):
    """
    Receive notifications from Company X
    
    Endpoint: https://yoursite.com/credit/webhook/companyx/
    """
    try:
        # Verify webhook signature (important for security!)
        signature = request.headers.get('X-CompanyX-Signature')
        if not verify_webhook_signature(request.body, signature):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Parse webhook data
        data = json.loads(request.body)
        event_type = data.get('event')
        
        # Handle different event types
        if event_type == 'transaction.confirmed':
            handle_transaction_confirmed(data)
        
        elif event_type == 'transaction.approved':
            handle_transaction_approved(data)
        
        elif event_type == 'settlement.processed':
            handle_settlement_processed(data)
        
        elif event_type == 'installment.paid':
            handle_installment_paid(data)
        
        elif event_type == 'transaction.disputed':
            handle_transaction_disputed(data)
        
        else:
            logger.warning(f"Unknown event type: {event_type}")
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def verify_webhook_signature(payload, signature):
    """
    Verify webhook is from Company X
    """
    import hmac
    import hashlib
    from django.conf import settings
    
    # Company X webhook secret
    secret = getattr(settings, 'COMPANY_X_WEBHOOK_SECRET', 'default-secret-change-this')
    
    # Calculate expected signature
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature or '')


def handle_transaction_confirmed(data):
    """
    Company X confirmed customer took the phone
    """
    our_ref = data['dealer_reference']
    company_x_ref = data['transaction_id']
    
    try:
        transaction = CreditTransaction.objects.get(transaction_id=our_ref)
        
        # Update transaction
        transaction.partner_reference = company_x_ref
        transaction.confirm_transaction()
        
        # Log event
        CreditTransactionLog.objects.create(
            credit_transaction=transaction,
            action='confirmed',
            old_status='pending',
            new_status='confirmed',
            notes=f'Auto-confirmed via webhook. Company X ref: {company_x_ref}'
        )
        
        logger.info(f"✅ Transaction {our_ref} auto-confirmed")
        
        # Send email notification
        send_confirmation_email(transaction)
        
    except CreditTransaction.DoesNotExist:
        logger.error(f"Transaction not found: {our_ref}")


def handle_transaction_approved(data):
    """
    Company X approved the credit application (same as confirmed)
    """
    handle_transaction_confirmed(data)


def handle_settlement_processed(data):
    """
    Company X has processed payment to you
    """
    our_ref = data['dealer_reference']
    settlement_ref = data['settlement_reference']
    amount = Decimal(data['amount'])
    payment_date = data['payment_date']
    
    try:
        transaction = CreditTransaction.objects.get(transaction_id=our_ref)
        
        # Mark as settled (settled_by=None for automated webhooks)
        transaction.mark_as_settled(
            settlement_date=payment_date,
            settlement_reference=settlement_ref,
            settled_by=None  # Automated settlement via webhook
        )
        
        logger.info(f"✅ Transaction {our_ref} auto-settled: KSH {amount}. StockEntry created.")
        
        # Send email notification
        send_settlement_email(transaction, amount)
        
    except CreditTransaction.DoesNotExist:
        logger.error(f"Transaction not found: {our_ref}")


def handle_installment_paid(data):
    """
    Customer made an installment payment
    """
    our_ref = data['dealer_reference']
    installment_number = data['installment_number']
    amount = Decimal(data['amount'])
    payment_date = data['payment_date']
    
    try:
        transaction = CreditTransaction.objects.get(transaction_id=our_ref)
        
        # Update installment status
        installment = transaction.installments.get(
            installment_number=installment_number
        )
        installment.status = 'paid'
        installment.payment_date = payment_date
        installment.payment_reference = data.get('payment_reference', '')
        installment.save()
        
        logger.info(
            f"✅ Installment {installment_number} paid for {our_ref}: "
            f"KSH {amount}"
        )
        
    except (CreditTransaction.DoesNotExist, CustomerInstallment.DoesNotExist) as e:
        logger.error(f"Error updating installment: {str(e)}")


def handle_transaction_disputed(data):
    """
    Issue with transaction (e.g., customer didn't receive phone)
    """
    our_ref = data['dealer_reference']
    reason = data['reason']
    
    try:
        transaction = CreditTransaction.objects.get(transaction_id=our_ref)
        transaction.status = 'disputed'
        transaction.notes = f"DISPUTED: {reason}"
        transaction.save()
        
        # Alert staff
        send_dispute_alert(transaction, reason)
        
        logger.warning(f"⚠️ Transaction {our_ref} DISPUTED: {reason}")
        
    except CreditTransaction.DoesNotExist:
        logger.error(f"Transaction not found: {our_ref}")


# ================================
# EMAIL HELPER FUNCTIONS
# ================================

def send_confirmation_email(transaction):
    """
    Send email when transaction is confirmed
    """
    try:
        subject = f'Credit Transaction Confirmed: {transaction.transaction_id}'
        message = f"""
Transaction {transaction.transaction_id} has been confirmed by {transaction.credit_partner.name}.

Customer: {transaction.customer.full_name}
Product: {transaction.product.name}
Amount: KSH {transaction.phone_price:,}
Expected Settlement: {transaction.expected_settlement_date}

The customer has received the product and the credit agreement is active.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@fieldmax.com',
            recipient_list=['dealer@fieldmax.com'],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Error sending confirmation email: {str(e)}")


def send_settlement_email(transaction, amount):
    """
    Send email when settlement is received
    """
    try:
        subject = f'Settlement Received: {transaction.transaction_id}'
        message = f"""
Settlement has been processed for transaction {transaction.transaction_id}.

Customer: {transaction.customer.full_name}
Product: {transaction.product.name}
Amount Received: KSH {amount:,}
Settlement Reference: {transaction.partner_reference}

The transaction has been marked as settled.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@fieldmax.com',
            recipient_list=['dealer@fieldmax.com'],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"Error sending settlement email: {str(e)}")


def send_dispute_alert(transaction, reason):
    """
    Send urgent alert when transaction is disputed
    """
    try:
        subject = f'⚠️ URGENT: Transaction Disputed - {transaction.transaction_id}'
        message = f"""
URGENT: A transaction has been disputed!

Transaction ID: {transaction.transaction_id}
Customer: {transaction.customer.full_name}
Product: {transaction.product.name}
Amount: KSH {transaction.phone_price:,}

Reason: {reason}

Please contact {transaction.credit_partner.name} immediately to resolve this issue.
Contact: {transaction.credit_partner.phone} / {transaction.credit_partner.email}
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@fieldmax.com',
            recipient_list=['dealer@fieldmax.com'],
            fail_silently=False,  # Don't fail silently for disputes
        )
    except Exception as e:
        logger.error(f"Error sending dispute alert: {str(e)}")