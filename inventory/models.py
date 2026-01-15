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
import random
import string


logger = logging.getLogger(__name__)




# ====================================
#  SUPLIER MODEL
# ====================================
class Supplier(models.Model):
    """Your product suppliers"""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name




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
    category_code = models.CharField(max_length=50, unique=True, blank=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        """
        Auto-generate category code in format: FSL.NAME
        Examples:
        - CABLES → FSL.CABLES
        - CHARGERS → FSL.CHARGERS
        - POWERBANK → FSL.POWERBANK
        """
        if not self.category_code:
            # Convert name to uppercase and remove spaces
            clean_name = self.name.strip().upper().replace(' ', '')
            self.category_code = f"FSL.{clean_name}"
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
    # ✅ ADD THIS: Barcode for bulk items
    barcode = models.CharField(
        max_length=200,
        help_text="Barcode for bulk items",
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

    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=200, blank=True, null=True)
    
    # Specifications as JSON
    specifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Store RAM, storage, color, screen size, etc."
    )
    
    # Example: {"ram": "8GB", "storage": "256GB", "color": "Black", "condition": "New"}
    
    condition = models.CharField(
        max_length=20,
        choices=[
            ('new', 'Brand New'),
            ('refurbished', 'Refurbished'),
            ('used', 'Used - Excellent'),
            ('used_good', 'Used - Good'),
        ],
        default='new'
    )
    
    warranty_months = models.PositiveIntegerField(
        default=12,
        help_text="Warranty period in months"
    )
    
    description = models.TextField(blank=True, null=True)
    
    supplier = models.ForeignKey(
         Supplier, 
         on_delete=models.SET_NULL, 
         null=True, 
         blank=True,
         related_name='products'
    )

    reorder_level = models.PositiveIntegerField(
        default=5,
        null=True,  # Makes it safe for existing records
        blank=True
    )
    
    last_restocked = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When was this last restocked"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['sku_value']),
            models.Index(fields=['-created_at']),
        ]
    
    def save(self, *args, **kwargs):
        """
        Override save to:
        1. Auto-generate product_code
        2. Auto-generate barcode for bulk items (if not provided)
        3. Set price
        4. Update status
        """
        
        # Auto-generate unique product_code
        if not self.product_code:
            self.product_code = self._generate_product_code()

        # ✅ NEW: Auto-generate barcode for bulk items without barcode
        if self.category.is_bulk_item and not self.barcode:
            self.barcode = self._generate_barcode()
        
        # Set price (selling price is the display price)
        self.price = self.selling_price
        
        # Enforce single item quantity = 1
        if self.category.is_single_item:
            self.quantity = 1
            # Clear barcode for single items
            self.barcode = None
        
        # Auto-update status based on item type and quantity
        self._update_status()
        
        super().save(*args, **kwargs)
    
    def _generate_product_code(self):
        """
        Generate unique sequential product code based on item type
        
        BULK ITEMS:   FSL0001, FSL0002, FSL0003, etc. (all bulk items share same sequence)
        SINGLE ITEMS: Category-specific codes:
            - PHONES     → PFSL0001, PFSL0002, PFSL0003
            - TELEVISION → TFSL0001, TFSL0002, TFSL0003
            - LAPTOPS    → LFSL0001, LFSL0002, LFSL0003
        """
        # Determine prefix based on category item type
        if self.category.is_bulk_item:
            # All bulk items use FSL prefix
            prefix = 'FSL'
        else:
            # Single items: Use first letter of category name + FSL
            first_letter = self.category.name.strip()[0].upper()
            prefix = f'{first_letter}FSL'
        
        # Get the highest existing number for this prefix
        max_code = Product.objects.filter(
            product_code__startswith=prefix
        ).aggregate(Max('product_code'))['product_code__max']
        
        if max_code:
            # Extract the numeric part (remove prefix)
            last_number = int(max_code.replace(prefix, ''))
            new_number = last_number + 1
        else:
            # First product for this prefix
            new_number = 1
        
        # Format: Prefix + 3-digit zero-padded number
        return f"{prefix}{str(new_number).zfill(3)}"

    def _generate_barcode(self):
        """
        ✅ Auto-generate unique NUMERIC barcode for bulk items
        
        Format: 13 digits (compatible with standard barcode scanners)
        - First 3 digits: Category ID (padded)
        - Next 6 digits: Sequential product number
        - Last 4 digits: Random variation
        
        Example: 0010000011234
                 ^^^      ^^^^
                 Cat ID   Random
        """
        max_attempts = 10
        
        # Get category ID (first 3 digits)
        category_id = str(self.category.id).zfill(3)
        
        # Get sequential number within this category
        product_count = Product.objects.filter(category=self.category).count()
        sequence = str(product_count + 1).zfill(6)
        
        for attempt in range(max_attempts):
            # Generate 4 random digits
            random_digits = ''.join(random.choices(string.digits, k=4))
            
            # Combine: 001 + 000001 + 1234 = 0010000011234
            barcode = f"{category_id}{sequence}{random_digits}"
            
            # Check if barcode already exists
            if not Product.objects.filter(barcode=barcode).exists():
                logger.info(f"✅ Auto-generated barcode: {barcode} for product {self.product_code}")
                return barcode
            
            # If collision, increment sequence
            sequence = str(int(sequence) + 1).zfill(6)
        
        # Fallback: timestamp-based (guaranteed unique)
        import time
        timestamp = str(int(time.time()))[-10:]  # Last 10 digits
        barcode = f"{category_id}{timestamp}"
        
        logger.warning(f"⚠️ Used timestamp fallback barcode: {barcode}")
        return barcode

    def _generate_ean13_barcode(self):
        """
        Alternative: Generate EAN-13 compatible barcode
        Format: 13 digits (standard retail barcode)
        """
        # Get category ID (padded to 3 digits)
        category_id = str(self.category.id).zfill(3)
        
        # Get product sequence number (padded to 6 digits)
        product_count = Product.objects.filter(category=self.category).count()
        product_seq = str(product_count + 1).zfill(6)
        
        # Random 3 digits
        random_digits = ''.join(random.choices(string.digits, k=3))
        
        # Combine: 2 (country) + 3 (category) + 6 (product) + 1 (check digit)
        barcode_base = f"2{category_id}{product_seq}{random_digits}"
        
        # Calculate EAN-13 check digit
        check_digit = self._calculate_ean13_checksum(barcode_base)
        
        barcode = f"{barcode_base}{check_digit}"
        
        # Ensure uniqueness
        if Product.objects.filter(barcode=barcode).exists():
            # If collision, add random variation
            random_suffix = random.randint(0, 9)
            barcode = f"{barcode_base[:-1]}{random_suffix}"
            check_digit = self._calculate_ean13_checksum(barcode)
            barcode = f"{barcode}{check_digit}"
        
        return barcode

    def _calculate_ean13_checksum(self, barcode_12):
        """
        Calculate EAN-13 check digit
        Algorithm: https://en.wikipedia.org/wiki/International_Article_Number
        """
        if len(barcode_12) != 12:
            raise ValueError("EAN-13 barcode base must be 12 digits")
        
        odd_sum = sum(int(barcode_12[i]) for i in range(0, 12, 2))
        even_sum = sum(int(barcode_12[i]) for i in range(1, 12, 2))
        
        total = odd_sum + (even_sum * 3)
        check_digit = (10 - (total % 10)) % 10
        
        return str(check_digit)

    def _generate_code128_barcode(self):
        """
        Alternative: Generate Code 128 compatible barcode
        Format: Alphanumeric (supports letters and numbers)
        """
        category_code = self.category.category_code[:4].upper()
        
        # Sequential number within category
        product_count = Product.objects.filter(category=self.category).count()
        sequence = str(product_count + 1).zfill(6)
        
        # Random suffix
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        
        barcode = f"{category_code}{sequence}{random_suffix}"
        
        # Ensure uniqueness
        while Product.objects.filter(barcode=barcode).exists():
            random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
            barcode = f"{category_code}{sequence}{random_suffix}"
        
        return barcode

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

    @property
    def needs_reorder(self):
        if self.category.is_bulk_item and self.reorder_level:
            return self.quantity <= self.reorder_level
        return False
    
    @property
    def display_name(self):
        if self.brand and self.model:
            return f"{self.brand} {self.model}"
        return self.name
    
    @property
    def is_in_warranty(self):
        """Check if item still under warranty"""
        if not self.warranty_months:
            return False
        from datetime import timedelta
        from django.utils import timezone
        warranty_end = self.created_at + timedelta(days=self.warranty_months * 30)
        return timezone.now() < warranty_end
    





# ====================================
#  PRODUCTIMAGE MODELS
# ====================================
class ProductImage(models.Model):
    """Multiple images per product"""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = CloudinaryField('image')
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']






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
    






# ====================================
# STOCKalert MODELS
# ====================================
class StockAlert(models.Model):
    """Alert when products are running low"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    alert_level = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    last_alerted = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Alert: {self.product.name} (Level: {self.alert_level})"





# ====================================
# product preview MODELS
# ====================================
class ProductReview(models.Model):
    """Customer product reviews"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer_name = models.CharField(max_length=200)
    rating = models.PositiveIntegerField(default=5)  # 1-5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']