# ====================================
# INVENTORY IMPORTS
# ====================================
from django.db import models
from django.db.models import Max
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from cloudinary.models import CloudinaryField
from decimal import Decimal
import logging









logger = logging.getLogger(__name__)









# ====================================
# CATEGORY  MODELS
# ====================================

class Category(models.Model):
    """Product categories that define item types"""
    
    SKU_TYPE_CHOICES = [
        ('imei', 'IMEI NUMBER'),
        ('serial', 'SERIAL NUMBER'),
    ]
    
    ITEM_TYPE_CHOICES = [
        ('single', 'Single Item'),
        ('bulk', 'Bulk Item'),
    ]

    name = models.CharField(max_length=100, unique=True)
    item_type = models.CharField(
        max_length=10, 
        choices=ITEM_TYPE_CHOICES,
        help_text="Single: Unique items (phones). Bulk: Stock items (cables)"
    )
    sku_type = models.CharField(
        max_length=10, 
        choices=SKU_TYPE_CHOICES,
        help_text="Type of identifier for this category"
    )
    category_code = models.CharField(max_length=10, unique=True, blank=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.category_code:
            first_letter = self.name.strip()[0].upper()
            self.category_code = f"{first_letter}FSL"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.category_code}) - {self.get_item_type_display()}"

    @property
    def is_single_item(self):
        return self.item_type == 'single'
    
    @property
    def is_bulk_item(self):
        return self.item_type == 'bulk'














# ====================================
#  PRODUCT MODELS
# ====================================

class Product(models.Model):
    """
    Represents inventory items.
    - Single items: Each phone gets its own Product record with unique SKU
    - Bulk items: Multiple units share one Product record with same SKU
    """
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('lowstock', 'Low Stock'),
        ('outofstock', 'Out of Stock'),
    ]

    # Basic Information
    name = models.CharField(max_length=255, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    product_code = models.CharField(max_length=20, unique=True, blank=True, db_index=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2) 
    image = CloudinaryField('image', blank=True, null=True)

    # New fields
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)

    # SKU (IMEI/Serial/Barcode)
    sku_value = models.CharField(
        max_length=200, 
        help_text="IMEI, Serial Number, or Barcode",
        db_index=True,
        blank=True,    
        null=True 
    )
    
    # Quantity
    quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="1 for single items, multiple for bulk items"
    )
    
    # Pricing
    buying_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Cost price"
    )
    selling_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Retail price"
    )
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['sku_value']),
            models.Index(fields=['-created_at']),
        ]

    def save(self, *args, **kwargs):
        # Auto-generate unique product_code
        if not self.product_code:
            self.product_code = self._generate_product_code()

        # ✅ SET PRICE (THIS WAS MISSING)
        self.price = self.selling_price
        
        # Enforce single item quantity = 1
        if self.category.is_single_item:
            self.quantity = 1
        
        # Auto-update status based on item type and quantity
        self._update_status()
        
        super().save(*args, **kwargs)

    def _generate_product_code(self):
        """Generate unique sequential product code"""
        category_code = self.category.category_code
        
        # Get the highest existing number for this category
        max_code = Product.objects.filter(
            product_code__startswith=category_code
        ).aggregate(Max('product_code'))['product_code__max']

        if max_code:
            last_number = int(max_code.replace(category_code, ''))
            new_number = last_number + 1
        else:
            new_number = 1

        return f"{category_code}{str(new_number).zfill(3)}"

    def _update_status(self):
        """
        ✅ FIXED: Auto-update status with sold protection
        
        SINGLE ITEMS:
        - Once sold, stays sold (unless explicitly restored via return)
        - quantity = 1 → status = 'available'
        - quantity = 0 → status = 'sold'
    
        BULK ITEMS:
        - quantity > 5 → status = 'available'
        - 1 ≤ quantity ≤ 5 → status = 'lowstock'
        - quantity = 0 → status = 'outofstock'
        """
        if self.category.is_single_item:
            # ✅ CRITICAL: Once sold, NEVER go back to available
            # This prevents sold items from being resold
            if self.status == 'sold':
                # Sold items stay sold unless explicitly restored via return
                return
            
            # Single items: available or sold (cannot restock)
            if self.quantity > 0:
                self.status = 'available' 
            else:
                self.status = 'sold'
        else: 
            # Bulk items: can be restocked
            if self.quantity > 5:
                self.status = 'available'
            elif 1 <= self.quantity <= 5:
                self.status = 'lowstock'
            else:
                self.status = 'outofstock'

    def clean(self):
        """Validation before saving"""
        # Validate pricing
        if not self.buying_price or not self.selling_price:
            return
        if self.buying_price > self.selling_price:
            raise ValidationError("Buying price cannot exceed selling price")
        
        # Single items must have quantity = 1
        if self.category.is_single_item and self.quantity != 1:
            raise ValidationError("Single items must have quantity = 1")
        
        # Bulk items must have quantity >= 0
        if self.category.is_bulk_item and self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")

    def __str__(self):
        return f"{self.name} ({self.product_code}) - SKU: {self.sku_value}"

    @property
    def can_restock(self):
        """Check if this product can be restocked"""
        return self.category.is_bulk_item

    @property
    def profit_margin(self):
        buying = self.buying_price or Decimal('0.00')
        selling = self.selling_price or Decimal('0.00')
        return selling - buying

    @property
    def profit_percentage(self):
        buying = self.buying_price or Decimal('0.00')
        selling = self.selling_price or Decimal('0.00')
        if buying == 0:
            return Decimal('0.0')
        return (selling - buying) / buying * 100











# ====================================
# STOCK ENTRY MODELS
# ====================================

class StockEntry(models.Model):
    """
    Tracks all inventory movements:
    - Purchase: Add new stock (bulk items) or new single item
    - Sale: Sell items (reduces quantity or marks single item as sold)
    - Return: Customer returns item (reverses sale)
    - Adjustment: Manual correction (damage, theft, etc.)
    """
    
    ENTRY_TYPE_CHOICES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('reversal', 'Reversal'),
        ('adjustment', 'Adjustment'),
    ]

    # Links
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_entries',
        help_text="Product this entry affects"
    )
    
    # Transaction Details
    quantity = models.IntegerField(
        help_text="Positive for stock IN, Negative for stock OUT"
    )
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Price per unit at time of transaction"
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total transaction value"
    )
    
    # Reference
    reference_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Invoice/Receipt/Order number"
    )
    notes = models.TextField(blank=True, null=True)
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Stock Entry'
        verbose_name_plural = 'Stock Entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['entry_type']),
            models.Index(fields=['product', '-created_at']),
        ]

    def save(self, *args, **kwargs):
        # Calculate total amount if not provided
        if not self.total_amount:
            self.total_amount = abs(self.quantity) * self.unit_price
        
        # Validate before saving
        self.clean()
        
        # Determine if new entry
        is_new = self.pk is None

        # Store product quantity before update
        old_quantity = self.product.quantity

        # Save the stock entry
        super().save(*args, **kwargs)

        if is_new:
            # Update product quantity
            self._update_product_stock()

            # Log detailed stock movement
            direction = "IN" if self.quantity > 0 else "OUT"
            logger.info(
                f"[STOCK MOVEMENT] Type: {self.get_entry_type_display()} | "
                f"Product: {self.product.product_code} ({self.product.name}) | "
                f"Quantity: {self.quantity} | "
                f"Old Stock: {old_quantity} | New Stock: {self.product.quantity} | "
                f"Status: {self.product.status} | "
                f"Unit Price: {self.unit_price} | Total: {self.total_amount} | "
                f"User: {self.created_by.username if self.created_by else 'System'}"
            )

    def _update_product_stock(self):
        """
        ✅ FIXED: Update product quantity with explicit sold status
        """
        product = self.product
        
        if self.entry_type == 'purchase':
            # Stock IN: Add quantity
            if product.category.is_single_item:
                product.quantity = 1
                product.status = 'available'
            else:
                product.quantity += abs(self.quantity)
        
        elif self.entry_type  in ('return','reversal'):
            # Returns: restore availability
            if product.category.is_single_item:
                product.quantity = 1
                product.status = 'available'
            else:
                product.quantity += abs(self.quantity)
        
        elif self.entry_type == 'sale':
            # ✅ CRITICAL FIX: Explicitly handle single item sales
            if product.category.is_single_item:
                product.quantity = 0
                product.status = 'sold'
                logger.info(f"[SOLD] Single item {product.product_code} marked as SOLD")
            else:
                # Bulk items: reduce quantity
                product.quantity -= abs(self.quantity)
                if product.quantity < 0:
                    product.quantity = 0
        
        elif self.entry_type == 'adjustment':
            # Can be positive or negative
            product.quantity += self.quantity
            if product.quantity < 0:
                product.quantity = 0
        
        # Save product (will trigger _update_status)
        product.save()

    def clean(self):
        """Validation"""
        # Quantity cannot be zero
        if self.quantity == 0:
            raise ValidationError("Quantity cannot be zero")
        
        # Check if this is the initial stock entry
        is_initial_entry = not self.pk and not self.product.stock_entries.exists()
        
        # Single items: purchases and returns must be quantity 1
        if self.product.category.is_single_item:
            if self.entry_type in ['purchase', 'return'] and abs(self.quantity) != 1:
                raise ValidationError("Single items must have quantity = 1")
        
        # Sales cannot exceed available stock
        if self.entry_type == 'sale':
            if abs(self.quantity) > self.product.quantity:
                raise ValidationError(
                    f"Cannot sell {abs(self.quantity)} units. Only {self.product.quantity} available."
                )
        
        # Single items cannot be restocked EXCEPT for initial entry
        if self.product.category.is_single_item:
            if self.entry_type == 'purchase' and not is_initial_entry and self.product.quantity > 0:
                raise ValidationError("Single items cannot be restocked. Create a new product instead.")

    def __str__(self):
        direction = "IN" if self.quantity > 0 else "OUT"
        return f"{self.entry_type.title()} {direction} - {self.product.product_code} - {abs(self.quantity)} units"

    @property
    def is_stock_in(self):
        return self.quantity > 0

    @property
    def is_stock_out(self):
        return self.quantity < 0

    @property
    def absolute_quantity(self):
        return abs(self.quantity)
    
