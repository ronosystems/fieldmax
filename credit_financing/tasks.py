# credit_financing/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import CreditTransaction
from .api_client import CompanyXAPIClient
import logging

logger = logging.getLogger(__name__)


@shared_task
def sync_transaction_statuses():
    """
    Sync pending transactions with Company X
    Run every hour
    """
    pending = CreditTransaction.objects.filter(
        status='pending'
    ).select_related('credit_partner')
    
    for transaction in pending:
        try:
            client = CompanyXAPIClient(transaction.credit_partner)
            status = client.get_transaction_status(transaction.partner_reference)
            
            # Auto-confirm if Company X says confirmed
            if status['status'] == 'confirmed':
                transaction.confirm_transaction()
                logger.info(f"✅ Auto-confirmed: {transaction.transaction_id}")
        
        except Exception as e:
            logger.error(
                f"Error syncing {transaction.transaction_id}: {str(e)}"
            )


@shared_task
def check_overdue_settlements():
    """
    Alert on overdue settlements
    Run daily at 9 AM
    """
    overdue = [
        t for t in CreditTransaction.objects.filter(
            status__in=['confirmed', 'active']
        ) if t.is_overdue
    ]
    
    if overdue:
        # Send email alert
        from django.core.mail import send_mail
        
        message = f"You have {len(overdue)} overdue settlements:\n\n"
        for t in overdue:
            message += (
                f"- {t.transaction_id}: {t.customer.full_name} "
                f"(KSH {t.phone_price}) - {abs(t.days_until_settlement)} days overdue\n"
            )
        
        send_mail(
            subject=f'⚠️ {len(overdue)} Overdue Settlements',
            message=message,
            from_email='noreply@fieldmax.com',
            recipient_list=['dealer@fieldmax.com'],
        )
        
        logger.warning(f"⚠️ Sent overdue alert for {len(overdue)} transactions")


@shared_task
def sync_installment_payments():
    """
    Sync customer payment status from Company X
    Run daily
    """
    from .models import CustomerInstallment
    
    active_transactions = CreditTransaction.objects.filter(
        status='active'
    )
    
    for transaction in active_transactions:
        try:
            client = CompanyXAPIClient(transaction.credit_partner)
            schedule = client.get_installment_schedule(transaction.partner_reference)
            
            # Update each installment
            for item in schedule:
                installment = transaction.installments.get(
                    installment_number=item['number']
                )
                
                if item['status'] == 'paid' and installment.status != 'paid':
                    installment.status = 'paid'
                    installment.payment_date = item['payment_date']
                    installment.save()
                    
                    logger.info(
                        f"✅ Updated installment {item['number']} for "
                        f"{transaction.transaction_id}"
                    )
        
        except Exception as e:
            logger.error(f"Error syncing installments: {str(e)}")


@shared_task
def fetch_pending_settlements():
    """
    Check Company X for settlements ready to process
    Run daily
    """
    from .models import CreditPartner
    
    for partner in CreditPartner.objects.filter(is_active=True):
        try:
            client = CompanyXAPIClient(partner)
            settlements = client.get_pending_settlements()
            
            for settlement in settlements:
                # Find our transaction
                our_ref = settlement['dealer_reference']
                
                try:
                    transaction = CreditTransaction.objects.get(
                        transaction_id=our_ref
                    )
                    
                    if transaction.status == 'confirmed':
                        # Mark as ready for settlement
                        transaction.notes += f"\n\nSettlement ready: {settlement['settlement_id']}"
                        transaction.save()
                        
                        logger.info(
                            f"✅ Settlement ready for {our_ref}: "
                            f"KSH {settlement['amount']}"
                        )
                
                except CreditTransaction.DoesNotExist:
                    logger.error(f"Transaction not found: {our_ref}")
        
        except Exception as e:
            logger.error(f"Error fetching settlements from {partner.name}: {str(e)}")


# ================================
# CELERY SCHEDULE CONFIG
# ================================
# Add to settings.py:

"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'sync-transaction-statuses': {
        'task': 'credit_financing.tasks.sync_transaction_statuses',
        'schedule': 3600,  # Every hour
    },
    'check-overdue-settlements': {
        'task': 'credit_financing.tasks.check_overdue_settlements',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'sync-installment-payments': {
        'task': 'credit_financing.tasks.sync_installment_payments',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'fetch-pending-settlements': {
        'task': 'credit_financing.tasks.fetch_pending_settlements',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
}
"""