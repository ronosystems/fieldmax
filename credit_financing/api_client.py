# ====================================
# COMPANY X API CLIENT
# Client for interacting with Company X API
# ====================================

import requests
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class CompanyXAPIClient:
    """
    Client for interacting with Company X API
    """
    
    def __init__(self, partner):
        """
        Initialize client with partner credentials
        
        Args:
            partner: CreditPartner instance
        """
        self.base_url = partner.api_endpoint
        self.api_key = partner.api_key
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
    
    def _make_request(self, method, endpoint, data=None):
        """
        Make API request with error handling
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise
    
    # ================================
    # CREATE TRANSACTION
    # ================================
    def create_transaction(self, transaction_data):
        """
        Submit new credit transaction to Company X
        
        Args:
            transaction_data: dict with transaction details
            
        Returns:
            dict: Response from Company X
        """
        endpoint = '/transactions/create'
        
        payload = {
            'dealer_id': getattr(settings, 'DEALER_ID', 'DEALER001'),
            'customer': {
                'id_number': transaction_data['customer_id_number'],
                'name': transaction_data['customer_name'],
                'phone': transaction_data['customer_phone'],
            },
            'product': {
                'name': transaction_data['product_name'],
                'imei': transaction_data['product_imei'],
                'price': str(transaction_data['product_price']),
            },
            'payment_plan': {
                'total_amount': str(transaction_data['customer_total']),
                'installment_amount': str(transaction_data['installment_amount']),
                'installment_period': transaction_data['installment_period'],
            },
            'reference': transaction_data['our_transaction_id'],
        }
        
        response = self._make_request('POST', endpoint, payload)
        
        logger.info(
            f"Transaction submitted to Company X: "
            f"{transaction_data['our_transaction_id']} -> "
            f"{response.get('transaction_id')}"
        )
        
        return response
    
    # ================================
    # CHECK TRANSACTION STATUS
    # ================================
    def get_transaction_status(self, company_x_transaction_id):
        """
        Get current status of transaction from Company X
        
        Args:
            company_x_transaction_id: Transaction ID from Company X
            
        Returns:
            dict: Transaction status and details
        """
        endpoint = f'/transactions/{company_x_transaction_id}/status'
        return self._make_request('GET', endpoint)
    
    # ================================
    # GET CUSTOMER INSTALLMENTS
    # ================================
    def get_installment_schedule(self, company_x_transaction_id):
        """
        Get customer's payment schedule and status
        
        Args:
            company_x_transaction_id: Transaction ID from Company X
            
        Returns:
            list: Installment schedule with payment status
        """
        endpoint = f'/transactions/{company_x_transaction_id}/installments'
        return self._make_request('GET', endpoint)
    
    # ================================
    # GET SETTLEMENTS
    # ================================
    def get_pending_settlements(self):
        """
        Get list of transactions ready for settlement
        
        Returns:
            list: Transactions awaiting settlement
        """
        endpoint = '/settlements/pending'
        return self._make_request('GET', endpoint)
    
    # ================================
    # CONFIRM SETTLEMENT RECEIVED
    # ================================
    def confirm_settlement_received(self, settlement_id, amount, reference):
        """
        Confirm you received settlement from Company X
        
        Args:
            settlement_id: Settlement batch ID
            amount: Amount received
            reference: Payment reference (M-Pesa, bank transfer)
            
        Returns:
            dict: Confirmation response
        """
        endpoint = f'/settlements/{settlement_id}/confirm'
        
        payload = {
            'amount': str(amount),
            'payment_reference': reference,
            'received_date': str(timezone.now().date()),
        }
        
        return self._make_request('POST', endpoint, payload)


# ================================
# USAGE EXAMPLES
# ================================

def example_create_transaction():
    """
    Example: Submit transaction to Company X API
    """
    from credit_financing.models import CreditTransaction
    
    # Get transaction and partner
    transaction = CreditTransaction.objects.get(transaction_id='CRX-20260213-0001')
    partner = transaction.credit_partner
    
    # Initialize API client
    client = CompanyXAPIClient(partner)
    
    # Prepare transaction data
    transaction_data = {
        'customer_id_number': transaction.customer.id_number,
        'customer_name': transaction.customer.full_name,
        'customer_phone': transaction.customer.phone,
        'product_name': transaction.product.name,
        'product_imei': transaction.product.sku_value,
        'product_price': transaction.phone_price,
        'customer_total': transaction.customer_total,
        'installment_amount': transaction.installment_amount,
        'installment_period': transaction.installment_period,
        'our_transaction_id': transaction.transaction_id,
    }
    
    try:
        # Submit to Company X
        response = client.create_transaction(transaction_data)
        
        # Save Company X's transaction ID
        transaction.partner_reference = response['transaction_id']
        transaction.save()
        
        print(f"✅ Transaction submitted: {response['transaction_id']}")
        
    except Exception as e:
        print(f"❌ Error submitting transaction: {str(e)}")


def example_check_status():
    """
    Example: Check transaction status
    """
    from credit_financing.models import CreditTransaction
    
    transaction = CreditTransaction.objects.get(transaction_id='CRX-20260213-0001')
    client = CompanyXAPIClient(transaction.credit_partner)
    
    try:
        status = client.get_transaction_status(transaction.partner_reference)
        
        print(f"Status: {status['status']}")
        print(f"Confirmation Date: {status.get('confirmation_date')}")
        print(f"Settlement Status: {status.get('settlement_status')}")
        
        # Auto-update our system
        if status['status'] == 'confirmed' and transaction.status == 'pending':
            transaction.confirm_transaction()
            print("✅ Transaction auto-confirmed in our system")
        
    except Exception as e:
        print(f"❌ Error checking status: {str(e)}")