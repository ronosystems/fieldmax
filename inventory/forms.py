from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from decimal import Decimal, InvalidOperation
from .models import Category, Product, StockEntry
from django.forms import inlineformset_factory


class CategoryForm(forms.ModelForm):
    """Form for creating/editing categories"""
    
    class Meta:
        model = Category
        fields = ['name', 'item_type', 'sku_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Phones, Accessories',
                'required': True
            }),
            'item_type': forms.Select(attrs={
                'class': 'form-select'}),
            'sku_type': forms.Select(attrs={
                'class': 'form-selct'}),
        }
        labels = {
            'name': 'Category Name',
            'item_type': 'Item Type',
            'sku_type': 'SKU Type',
        }
        help_texts = {
            'item_type': 'Single: Unique items like phones. Bulk: Stock items like cables.',
            'sku_type': 'Type of identifier for products in this category',
        }
    
    def clean_name(self):
        """Validate category name"""
        name = self.cleaned_data.get('name', '').strip()
        
        if not name:
            raise ValidationError("Category name is required")
        
        # Check for duplicates (case-insensitive)
        existing = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise ValidationError(f"Category '{name}' already exists")
        
        return name
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        
        # Ensure sku_type is provided
        if not cleaned_data.get('sku_type'):
            raise ValidationError({
                'sku_type': 'SKU type is required'
            })
        
        return cleaned_data




class ProductForm(forms.ModelForm):
    """Form for creating/editing products"""
    
    class Meta:
        model = Product
        fields = [
            'category',
            'name',
            'sku_value',
            'barcode',      # ✅ ADD THIS LINE
            'quantity',
            'buying_price',
            'selling_price',
            'image',
        ]
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'required': True
            }),
            'sku_value': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter SKU/IMEI/Serial'
            }),
            'barcode': forms.TextInput(attrs={      # ✅ ADD THIS WIDGET
                'class': 'form-control',
                'placeholder': 'Enter barcode for bulk items'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Enter quantity'
            }),
            'buying_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00',
                'required': True
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00',
                'required': True
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make sku_value, barcode, and quantity optional by default
        self.fields['sku_value'].required = False
        self.fields['barcode'].required = False    # ✅ ADD THIS LINE
        self.fields['quantity'].required = False
        
        # Set default quantity to 1 if not provided
        if not self.instance.pk and not self.data.get('quantity'):
            self.fields['quantity'].initial = 1

    def clean(self):
        cleaned_data = super().clean()
        
        category = cleaned_data.get('category')
        name = cleaned_data.get('name')
        sku_value = (cleaned_data.get('sku_value') or '').strip()
        barcode = (cleaned_data.get('barcode') or '').strip()  # ✅ ADD THIS LINE
        quantity = cleaned_data.get('quantity')
        buying_price = cleaned_data.get('buying_price')
        selling_price = cleaned_data.get('selling_price')
        
        # Validate category-specific requirements
        if category:
            # Single items require unique SKU
            if category.is_single_item:
                if not sku_value:
                    self.add_error('sku_value', f'{category.get_sku_type_display()} is required for single items')
                else:
                    # Check if SKU already exists (only for new products)
                    if not self.instance.pk:  # Only check on create, not edit
                        if Product.objects.filter(sku_value__iexact=sku_value, is_active=True).exists():
                            self.add_error('sku_value', f'This {category.get_sku_type_display()} already exists in inventory')
                
                # Single items always have quantity = 1
                cleaned_data['quantity'] = 1
                # Clear barcode for single items
                cleaned_data['barcode'] = None  # ✅ ADD THIS LINE
            
            # Bulk items require quantity > 0
            elif category.is_bulk_item:
                if not quantity or quantity <= 0:
                    self.add_error('quantity', 'Quantity must be greater than 0 for bulk items')
                
                # ✅ ADD THIS: Validate unique barcode for bulk items
                if barcode:
                    existing_barcode = Product.objects.filter(
                        barcode__iexact=barcode, 
                        is_active=True
                    )
                    # Exclude current instance if editing
                    if self.instance.pk:
                        existing_barcode = existing_barcode.exclude(pk=self.instance.pk)
                    
                    if existing_barcode.exists():
                        self.add_error('barcode', f'Barcode "{barcode}" already exists for another product')
                
                # Clear sku_value for bulk items
                cleaned_data['sku_value'] = None  # ✅ ADD THIS LINE
        
        # Validate pricing
        if buying_price and selling_price:
            if selling_price < buying_price:
                self.add_error('selling_price', 'Selling price must be greater than or equal to buying price')
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Ensure single items have quantity = 1 and no barcode
        if instance.category and instance.category.is_single_item:
            instance.quantity = 1
            instance.barcode = None  # ✅ ADD THIS LINE
        
        # Ensure bulk items have no sku_value (use barcode instead)
        if instance.category and instance.category.is_bulk_item:
            instance.sku_value = None  # ✅ ADD THIS LINE
        
        if commit:
            instance.save()
        
        return instance
    


class CustomProductFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make price fields not required for all forms in the formset
        for form in self.forms:
            form.fields['buying_price'].required = False
            form.fields['selling_price'].required = False
            # Set default values
            if not form.initial.get('buying_price'):
                form.fields['buying_price'].initial = 0
            if not form.initial.get('selling_price'):
                form.fields['selling_price'].initial = 0

ProductFormSet = inlineformset_factory(
    Category,
    Product,
    form=ProductForm,
    formset=CustomProductFormSet,  # Use custom formset
    extra=1,
    can_delete=True,
    validate_min=False
)




class ProductQuickEditForm(forms.ModelForm):
    """Lightweight form for quick product edits"""
    
    class Meta:
        model = Product
        fields = ['name', 'buying_price', 'selling_price', 'quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'buying_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
        }
    
    def clean_buying_price(self):
        """Validate buying price"""
        buying_price = self.cleaned_data.get('buying_price')
        if buying_price is None:
            return Decimal('0.00')
        return buying_price
    
    def clean_selling_price(self):
        """Validate selling price"""
        selling_price = self.cleaned_data.get('selling_price')
        if selling_price is None:
            return Decimal('0.00')
        return selling_price
    
    def clean(self):
        cleaned_data = super().clean()
        buying_price = cleaned_data.get('buying_price')
        selling_price = cleaned_data.get('selling_price')
        
        if buying_price and selling_price and buying_price > selling_price:
            raise ValidationError("Selling price must be greater than buying price")
        
        return cleaned_data


class StockEntryForm(forms.ModelForm):
    """Form for creating stock entries"""
    
    class Meta:
        model = StockEntry
        fields = [
            'product',
            'quantity',
            'entry_type',
            'unit_price',
            'reference_id',
            'notes',
        ]
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-control product-select',
                'required': True
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter quantity (positive for IN, negative for OUT)',
                'required': True
            }),
            'entry_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'required': True
            }),
            'reference_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Invoice/Receipt/Order number (optional)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes (optional)'
            }),
        }
        labels = {
            'product': 'Product',
            'quantity': 'Quantity',
            'entry_type': 'Entry Type',
            'unit_price': 'Unit Price',
            'reference_id': 'Reference Number',
            'notes': 'Notes',
        }
        help_texts = {
            'quantity': 'Positive for stock IN (purchase/return), Negative for stock OUT (sale)',
            'entry_type': 'Type of stock movement',
            'unit_price': 'Price per unit for this transaction',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show active products
        self.fields['product'].queryset = Product.objects.filter(
            is_active=True
        ).select_related('category')
        
        # Set initial unit_price from product if creating new entry
        if not self.instance.pk and 'initial' in kwargs:
            product_id = kwargs['initial'].get('product')
            if product_id:
                try:
                    product = Product.objects.get(id=product_id)
                    self.fields['unit_price'].initial = product.buying_price
                except Product.DoesNotExist:
                    pass
    
    def clean_quantity(self):
        """Validate quantity"""
        quantity = self.cleaned_data.get('quantity')
        
        if quantity == 0:
            raise ValidationError("Quantity cannot be zero")
        
        return quantity
    
    def clean(self):
        """Validate stock entry"""
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        entry_type = cleaned_data.get('entry_type')
        unit_price = cleaned_data.get('unit_price')
        
        if not all([product, quantity, entry_type, unit_price]):
            return cleaned_data
        
        # Validate single item quantities
        if hasattr(product.category, 'is_single_item') and product.category.is_single_item:
            if entry_type in ['purchase', 'return'] and abs(quantity) != 1:
                raise ValidationError({
                    'quantity': 'Single items must have quantity = 1 for purchases/returns'
                })
        
        # Validate sales don't exceed stock
        if entry_type == 'sale':
            if quantity > 0:
                raise ValidationError({
                    'quantity': 'Sales quantity must be negative (e.g., -5 to sell 5 units)'
                })
            
            product_qty = product.quantity or 0
            if abs(quantity) > product_qty:
                raise ValidationError({
                    'quantity': f'Cannot sell {abs(quantity)} units. Only {product_qty} available.'
                })
        
        # Validate purchases/returns are positive
        if entry_type in ['purchase', 'return']:
            if quantity < 0:
                raise ValidationError({
                    'quantity': 'Purchase/Return quantity must be positive'
                })
        
        # Validate single items cannot be restocked
        if hasattr(product.category, 'is_single_item') and product.category.is_single_item:
            product_qty = product.quantity or 0
            if entry_type == 'purchase' and product_qty > 0:
                raise ValidationError({
                    'entry_type': 'Single items cannot be restocked. They are already in stock.'
                })
        
        return cleaned_data


class SaleStockEntryForm(forms.Form):
    """Simplified form for creating sales from POS/checkout"""
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Product'
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'value': '1'
        }),
        label='Quantity to Sell'
    )
    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        }),
        label='Selling Price',
        help_text='Leave blank to use product selling price'
    )
    reference_id = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Receipt/Invoice number'
        }),
        label='Reference Number'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial unit_price from product if provided
        if 'initial' in kwargs and 'product' in kwargs['initial']:
            product = kwargs['initial']['product']
            if isinstance(product, Product):
                self.fields['unit_price'].initial = product.selling_price
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        if product and quantity:
            # Check stock availability
            product_qty = product.quantity or 0
            if quantity > product_qty:
                raise ValidationError(
                    f"Insufficient stock. Only {product_qty} units available."
                )
            
            # Set default unit_price if not provided
            if not cleaned_data.get('unit_price'):
                cleaned_data['unit_price'] = product.selling_price or Decimal('0.00')
        
        return cleaned_data
    
    def save(self, user=None):
        """Create sale stock entry"""
        product = self.cleaned_data['product']
        quantity = self.cleaned_data['quantity']
        unit_price = self.cleaned_data['unit_price']
        reference_id = self.cleaned_data.get('reference_id', '')
        
        stock_entry = StockEntry.objects.create(
            product=product,
            quantity=-quantity,  # Negative for sales
            entry_type='sale',
            unit_price=unit_price,
            total_amount=quantity * unit_price,
            reference_id=reference_id,
            created_by=user,
            notes=f"Sale of {quantity} units"
        )
        
        return stock_entry


class PurchaseStockEntryForm(forms.Form):
    """Simplified form for receiving/purchasing stock"""
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Product'
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'value': '1'
        }),
        label='Quantity Received'
    )
    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        }),
        label='Purchase Price',
        help_text='Cost per unit'
    )
    supplier_invoice = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Supplier invoice/PO number'
        }),
        label='Supplier Invoice'
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional notes'
        }),
        label='Notes'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        if product and quantity:
            # Validate single items cannot be restocked
            if hasattr(product.category, 'is_single_item') and product.category.is_single_item:
                product_qty = product.quantity or 0
                if product_qty > 0:
                    raise ValidationError(
                        "Single items cannot be restocked. Please create a new product."
                    )
            
            # Set default unit_price if not provided
            if not cleaned_data.get('unit_price'):
                cleaned_data['unit_price'] = product.buying_price or Decimal('0.00')
        
        return cleaned_data
    
    def save(self, user=None):
        """Create purchase stock entry"""
        product = self.cleaned_data['product']
        quantity = self.cleaned_data['quantity']
        unit_price = self.cleaned_data['unit_price']
        reference_id = self.cleaned_data.get('supplier_invoice', '')
        notes = self.cleaned_data.get('notes', '')
        
        stock_entry = StockEntry.objects.create(
            product=product,
            quantity=quantity,  # Positive for purchases
            entry_type='purchase',
            unit_price=unit_price,
            total_amount=quantity * unit_price,
            reference_id=reference_id,
            created_by=user,
            notes=notes or f"Purchase of {quantity} units"
        )
        
        return stock_entry


class ProductSearchForm(forms.Form):
    """Form for searching products"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, product code, or SKU...'
        }),
        label='Search'
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Category'
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Product.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status'
    )
    item_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Category.ITEM_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Item Type'
    )