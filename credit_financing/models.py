# ====================================
# CREDIT FINANCING MODELS
# Integration for Company X Credit Program
# ====================================
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from inventory.models import Product
import logging

logger = logging.getLogger(__name__)


# ====================================
# CREDIT PARTNER (Company X)
# ====================================
class CreditPartner(models.Model):
    """
    Credit financing companies (e.g., Company X, Lipa Later, etc.)
    """
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, help_text="e.g., COMPX, LIPA")
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField(blank=True)
    
    # Commission/Fee structure
    commission_type = models.CharField(
        max_length=20,
        choices=[
            ('percentage', 'Percentage'),
            ('fixed', 'Fixed Amount'),
        ],
        default='percentage'
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage (e.g., 5.00 for 5%) or Fixed Amount"
    )
    
    # Settlement terms
    settlement_days = models.PositiveIntegerField(
        default=7,
        help_text="Days after customer confirmation to receive payment"
    )
    
    # API/Integration details (for future automation)
    api_endpoint = models.URLField(blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


# ====================================
# CREDIT CUSTOMER
# ====================================
class CreditCustomer(models.Model):
    """
    Customers who buy on credit through Company X
    """
    # Personal Information
    full_name = models.CharField(max_length=200)
    id_number = models.CharField(max_length=50, unique=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    
    # Address
    county = models.CharField(max_length=100)
    sub_county = models.CharField(max_length=100, blank=True)
    location = models.TextField(blank=True)
    
    # Credit Partner
    credit_partner = models.ForeignKey(
        CreditPartner,
        on_delete=models.PROTECT,
        related_name='customers'
    )
    
    # Customer reference from partner (e.g., Company X customer ID)
    partner_customer_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="Customer ID in Company X's system"
    )
    
    # Credit status
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Maximum credit allowed by partner"
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['credit_partner', 'partner_customer_id']]
    
    def __str__(self):
        return f"{self.full_name} ({self.id_number}) - {self.credit_partner.code}"
    
    @property
    def outstanding_credit(self):
        """Calculate total outstanding credit"""
        return self.credit_transactions.filter(
            status__in=['pending', 'active']
        ).aggregate(
            total=models.Sum('phone_price')
        )['total'] or Decimal('0.00')
    
    @property
    def available_credit(self):
        """Calculate available credit limit"""
        return self.credit_limit - self.outstanding_credit


# ====================================
# CREDIT TRANSACTION
# ====================================
class CreditTransaction(models.Model):
    """
    Main credit transaction when you give phone to customer on credit
    FLOW: You → Customer → Company X → You
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending Confirmation'),      # Phone given, waiting for Company X confirmation
        ('confirmed', 'Confirmed by Partner'),    # Company X confirmed customer took phone
        ('active', 'Active - Customer Paying'),   # Customer making installments
        ('settled', 'Settled - You Paid'),        # Company X paid you full amount
        ('cancelled', 'Cancelled'),               # Transaction cancelled
        ('disputed', 'Disputed'),                 # Issue with transaction
    ]
    
    # Transaction ID
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Parties involved
    credit_partner = models.ForeignKey(
        CreditPartner,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    customer = models.ForeignKey(
        CreditCustomer,
        on_delete=models.PROTECT,
        related_name='credit_transactions'
    )
    dealer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='credit_transactions',
        help_text="You (the dealer)"
    )
    
    # Product Details
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='credit_transactions'
    )
    
    # Pricing
    phone_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Price you'll receive from Company X"
    )
    customer_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total amount customer pays to Company X (including interest)"
    )
    partner_commission = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Commission Company X charges"
    )
    
    # Installment details
    installment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Monthly installment customer pays"
    )
    installment_period = models.PositiveIntegerField(
        help_text="Number of months/installments"
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Important dates
    transaction_date = models.DateTimeField(default=timezone.now)
    confirmation_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When Company X confirmed customer took phone"
    )
    expected_settlement_date = models.DateField(
        null=True,
        blank=True,
        help_text="When you expect payment from Company X"
    )
    actual_settlement_date = models.DateField(
        null=True,
        blank=True,
        help_text="When Company X actually paid you"
    )
    
    # Reference numbers
    partner_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Company X's transaction reference"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['credit_partner', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-generate transaction ID and calculate dates"""
        if not self.transaction_id:
            self.transaction_id = self._generate_transaction_id()
        
        # Calculate expected settlement date
        if self.confirmation_date and not self.expected_settlement_date:
            from datetime import timedelta
            self.expected_settlement_date = (
                self.confirmation_date.date() + 
                timedelta(days=self.credit_partner.settlement_days)
            )
        
        super().save(*args, **kwargs)
    
    def _generate_transaction_id(self):
        """Generate unique transaction ID: CRX-YYYYMMDD-0001"""
        from django.db.models import Max
        import datetime
        
        today = datetime.date.today()
        prefix = f"CRX-{today.strftime('%Y%m%d')}"
        
        # Get last transaction for today
        last_trans = CreditTransaction.objects.filter(
            transaction_id__startswith=prefix
        ).aggregate(Max('transaction_id'))['transaction_id__max']
        
        if last_trans:
            last_num = int(last_trans.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}-{str(new_num).zfill(4)}"
    
    def confirm_transaction(self, confirmed_by=None):
        """Mark transaction as confirmed by Company X"""
        if self.status != 'pending':
            raise ValidationError("Only pending transactions can be confirmed")
        
        self.status = 'confirmed'
        self.confirmation_date = timezone.now()
        self.save()
        
        # Log confirmation
        logger.info(
            f"Credit transaction {self.transaction_id} confirmed. "
            f"Customer: {self.customer.full_name}, "
            f"Amount: KSH {self.phone_price}"
        )
    
    def mark_as_settled(self, settlement_date=None, settlement_reference='', settled_by=None):
        """Mark as settled when Company X pays you"""
        if self.status not in ['confirmed', 'active']:
            raise ValidationError("Only confirmed/active transactions can be settled")
        
        self.status = 'settled'
        self.actual_settlement_date = settlement_date or timezone.now().date()
        self.partner_reference = settlement_reference
        self.save()
        
        # Create StockEntry to record the sale in inventory
        from inventory.models import StockEntry
        
        StockEntry.objects.create(
            product=self.product,
            quantity=-1,  # Stock OUT (single item sold)
            entry_type='sale',
            unit_price=self.phone_price,
            total_amount=self.phone_price,
            reference_id=self.transaction_id,
            notes=f'Credit sale settled by {self.credit_partner.name}',
            created_by=settled_by or self.dealer
        )
        
        # Log settlement
        logger.info(
            f"Credit transaction {self.transaction_id} settled. "
            f"Amount received: KSH {self.phone_price}. "
            f"StockEntry created."
        )
    
    def cancel_transaction(self, reason=''):
        """Cancel transaction"""
        if self.status == 'settled':
            raise ValidationError("Cannot cancel settled transaction")
        
        self.status = 'cancelled'
        self.cancellation_reason = reason
        self.save()
        
        logger.warning(
            f"Credit transaction {self.transaction_id} cancelled. "
            f"Reason: {reason}"
        )
    
    def __str__(self):
        return (
            f"{self.transaction_id} - {self.customer.full_name} - "
            f"KSH {self.phone_price} ({self.get_status_display()})"
        )
    
    @property
    def days_until_settlement(self):
        """Days remaining until expected settlement"""
        if not self.expected_settlement_date:
            return None
        
        from datetime import date
        delta = self.expected_settlement_date - date.today()
        return delta.days
    
    @property
    def is_overdue(self):
        """Check if settlement is overdue"""
        if not self.expected_settlement_date or self.status == 'settled':
            return False
        
        from datetime import date
        return date.today() > self.expected_settlement_date


# ====================================
# CUSTOMER INSTALLMENT TRACKING
# ====================================
class CustomerInstallment(models.Model):
    """
    Track customer payments to Company X (optional - for your records)
    Company X should provide this data via API or reports
    """
    
    credit_transaction = models.ForeignKey(
        CreditTransaction,
        on_delete=models.CASCADE,
        related_name='installments'
    )
    
    installment_number = models.PositiveIntegerField(
        help_text="1st, 2nd, 3rd installment, etc."
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('late', 'Late'),
        ('missed', 'Missed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Reference from Company X
    payment_reference = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['installment_number']
        unique_together = [['credit_transaction', 'installment_number']]
    
    def __str__(self):
        return (
            f"{self.credit_transaction.transaction_id} - "
            f"Installment {self.installment_number} - KSH {self.amount}"
        )


# ====================================
# DEALER SETTLEMENT (Payment to You)
# ====================================
class DealerSettlement(models.Model):
    """
    Records when Company X pays you (can combine multiple transactions)
    """
    
    settlement_id = models.CharField(max_length=100, unique=True)
    credit_partner = models.ForeignKey(
        CreditPartner,
        on_delete=models.PROTECT,
        related_name='settlements'
    )
    
    # Transactions included in this settlement
    transactions = models.ManyToManyField(
        CreditTransaction,
        related_name='settlements'
    )
    
    # Payment details
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total amount Company X paid you"
    )
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('mpesa', 'M-Pesa'),
            ('cheque', 'Cheque'),
        ]
    )
    payment_reference = models.CharField(max_length=200)
    payment_date = models.DateField()
    
    # Bank details
    bank_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=100, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return (
            f"{self.settlement_id} - {self.credit_partner.code} - "
            f"KSH {self.total_amount}"
        )
    
    def save(self, *args, **kwargs):
        """Auto-generate settlement ID"""
        if not self.settlement_id:
            self.settlement_id = self._generate_settlement_id()
        super().save(*args, **kwargs)
    
    def _generate_settlement_id(self):
        """Generate settlement ID: STL-COMPX-YYYYMMDD-001"""
        from django.db.models import Max
        import datetime
        
        today = datetime.date.today()
        prefix = f"STL-{self.credit_partner.code}-{today.strftime('%Y%m%d')}"
        
        last_settlement = DealerSettlement.objects.filter(
            settlement_id__startswith=prefix
        ).aggregate(Max('settlement_id'))['settlement_id__max']
        
        if last_settlement:
            last_num = int(last_settlement.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}-{str(new_num).zfill(3)}"


# ====================================
# CREDIT TRANSACTION LOG
# ====================================
class CreditTransactionLog(models.Model):
    """
    Audit trail for all credit transaction changes
    """
    credit_transaction = models.ForeignKey(
        CreditTransaction,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    
    action = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Created'),
            ('confirmed', 'Confirmed'),
            ('settled', 'Settled'),
            ('cancelled', 'Cancelled'),
            ('updated', 'Updated'),
        ]
    )
    
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.credit_transaction.transaction_id} - {self.action}"