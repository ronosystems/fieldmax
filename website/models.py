from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json









# ============================================
# PEMDING ORDER
# ============================================

class PendingOrder(models.Model):
    """
    Orders submitted by customers that need staff approval
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    # Order ID
    order_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Customer Details
    buyer_name = models.CharField(max_length=200)
    buyer_phone = models.CharField(max_length=20)
    buyer_email = models.CharField(max_length=255, blank=True, null=True)
    buyer_id_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Order Details (stored as JSON)
    cart_data = models.TextField(help_text="JSON data of cart items")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    item_count = models.PositiveIntegerField(default=0)
    
    # Payment Details
    payment_method = models.CharField(max_length=50, default='cash')
    notes = models.TextField(blank=True, null=True)
    
    # Status Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Staff Actions
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reviewed_orders'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Link to actual Sale (once approved)
    sale_id = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        db_table = 'pending_orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['buyer_phone']),
        ]
    
    def __str__(self):
        return f"Order {self.order_id} - {self.buyer_name} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        if not self.order_id:
            # Generate order ID: PO-YYYYMMDD-XXXX
            from django.db.models import Max
            today = timezone.now().strftime('%Y%m%d')
            prefix = f"PO-{today}"
            
            last_order = PendingOrder.objects.filter(
                order_id__startswith=prefix
            ).aggregate(Max('order_id'))['order_id__max']
            
            if last_order:
                last_num = int(last_order.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.order_id = f"{prefix}-{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    @property
    def cart_items(self):
        """Parse and return cart items from cart_data JSON"""
        try:
            return json.loads(self.cart_data)
        except:
            return []
    
    @property
    def can_be_approved(self):
        return self.status == 'pending'
    
    @property
    def can_be_rejected(self):
        return self.status == 'pending'








# ============================================
# PENDING ORDER ITEM 
# ============================================

class PendingOrderItem(models.Model):
    """
    Individual items in a pending order
    """
    order = models.ForeignKey(
        PendingOrder, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pending_order_items'
        ordering = ['id']
    
    def __str__(self):
        return f"{self.product_name} x{self.quantity} - {self.order.order_id}"
    
    @property
    def total_price(self):
        return self.unit_price * self.quantity