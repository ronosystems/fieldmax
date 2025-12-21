# sales/forms.py - FIXED VERSION

from django import forms
from .models import Sale, SaleItem











class SaleForm(forms.ModelForm):
    """
    Form for Sale model (transaction-level, not item-level)
    ✅ FIXED: Only includes fields that exist on Sale model
    """
    
    class Meta:
        model = Sale
        fields = [
            'buyer_name',
            'buyer_phone',
            'buyer_id_number',
            'nok_name',
            'nok_phone',
        ]
        widgets = {
            'buyer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Customer name'
            }),
            'buyer_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '0712345678'
            }),
            'buyer_id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID number'
            }),
            'nok_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Next of kin name'
            }),
            'nok_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Next of kin phone'
            }),
        }









class SaleItemForm(forms.ModelForm):
    """
    Form for individual sale items
    Use this when adding items to a sale
    """
    
    class Meta:
        model = SaleItem
        fields = [
            'product',
            'quantity',
            'unit_price',
        ]
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-control'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': 0
            }),
        }













# ============================================
# FORMSETS FOR INLINE ITEM EDITING
# ============================================

from django.forms import inlineformset_factory

# Create formset for adding multiple items to a sale
SaleItemFormSet = inlineformset_factory(
    Sale,  # Parent model
    SaleItem,  # Child model
    form=SaleItemForm,
    extra=1,  # Number of empty forms to display
    can_delete=True,
    min_num=1,  # At least one item required
    validate_min=True
)













# ============================================
# ALTERNATIVE: Simple form for quick sale entry
# ============================================

class QuickSaleForm(forms.Form):
    """
    Simplified form for quick single-item sales
    Used in POS-style interfaces
    """
    
    product_code = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Scan or enter product code',
            'autofocus': True
        }),
        label='Product Code / SKU / IMEI'
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1
        }),
        label='Quantity'
    )
    
    unit_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Auto-filled from product'
        }),
        label='Unit Price (Optional)'
    )
    
    # Client details (optional)
    buyer_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Customer name'
        }),
        label='Customer Name'
    )
    
    buyer_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0712345678'
        }),
        label='Phone Number'
    )
    
    buyer_id_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ID number'
        }),
        label='ID Number'
    )
    
    nok_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Next of kin name'
        }),
        label='Next of Kin'
    )
    
    nok_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Next of kin phone'
        }),
        label='Next of Kin Phone'
    )










# ============================================
# ADMIN FORMS (Optional)
# ============================================

class SaleAdminForm(forms.ModelForm):
    """
    Form for Django admin
    Includes all fields including read-only ones
    """
    
    class Meta:
        model = Sale
        fields = '__all__'
        widgets = {
            'sale_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local'
            }),
        }


class SaleItemInlineForm(forms.ModelForm):
    """
    Inline form for editing sale items in admin
    """
    
    class Meta:
        model = SaleItem
        fields = [
            'product',
            'product_code',
            'product_name',
            'sku_value',
            'quantity',
            'unit_price',
            'total_price',
        ]
        widgets = {
            'product_code': forms.TextInput(attrs={'readonly': True}),
            'product_name': forms.TextInput(attrs={'readonly': True}),
            'sku_value': forms.TextInput(attrs={'readonly': True}),
            'total_price': forms.NumberInput(attrs={'readonly': True}),
        }