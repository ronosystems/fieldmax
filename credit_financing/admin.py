# ====================================
# CREDIT FINANCING ADMIN
# ====================================
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from .models import (
    CreditPartner,
    CreditCustomer,
    CreditTransaction,
    CustomerInstallment,
    DealerSettlement,
    CreditTransactionLog
)


# ====================================
# CREDIT PARTNER ADMIN
# ====================================
@admin.register(CreditPartner)
class CreditPartnerAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'code',
        'commission_display',
        'settlement_days',
        'total_transactions',
        'total_value',
        'is_active',
    ]
    list_filter = ['is_active', 'commission_type']
    search_fields = ['name', 'code', 'email', 'phone']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'is_active')
        }),
        ('Contact Details', {
            'fields': ('contact_person', 'phone', 'email', 'address')
        }),
        ('Commission Structure', {
            'fields': ('commission_type', 'commission_rate', 'settlement_days')
        }),
        ('API Integration', {
            'fields': ('api_endpoint', 'api_key'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def commission_display(self, obj):
        if obj.commission_type == 'percentage':
            return f"{obj.commission_rate}%"
        return f"KSH {obj.commission_rate}"
    commission_display.short_description = 'Commission'
    
    def total_transactions(self, obj):
        count = obj.transactions.count()
        return format_html(
            '<span style="font-weight: bold;">{}</span>',
            count
        )
    total_transactions.short_description = 'Transactions'
    
    def total_value(self, obj):
        total = obj.transactions.filter(
            status__in=['confirmed', 'active', 'settled']
        ).aggregate(Sum('phone_price'))['phone_price__sum'] or 0
        return format_html(
            '<span style="color: green; font-weight: bold;">KSH {:,}</span>',
            total
        )
    total_value.short_description = 'Total Value'


# ====================================
# CREDIT CUSTOMER ADMIN
# ====================================
@admin.register(CreditCustomer)
class CreditCustomerAdmin(admin.ModelAdmin):
    list_display = [
        'full_name',
        'id_number',
        'phone',
        'credit_partner',
        'credit_limit',
        'outstanding_credit',
        'available_credit',
        'total_transactions',
        'is_active',
    ]
    list_filter = ['is_active', 'credit_partner', 'county']
    search_fields = [
        'full_name',
        'id_number',
        'phone',
        'email',
        'partner_customer_id'
    ]
    readonly_fields = ['created_at', 'updated_at', 'outstanding_credit', 'available_credit']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('full_name', 'id_number', 'phone', 'email')
        }),
        ('Location', {
            'fields': ('county', 'sub_county', 'location')
        }),
        ('Credit Details', {
            'fields': (
                'credit_partner',
                'partner_customer_id',
                'credit_limit',
                'outstanding_credit',
                'available_credit',
                'is_active'
            )
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_transactions(self, obj):
        count = obj.credit_transactions.count()
        url = reverse('admin:credit_financing_credittransaction_changelist') + f'?customer__id__exact={obj.id}'
        return format_html(
            '<a href="{}" style="font-weight: bold;">{} transactions</a>',
            url,
            count
        )
    total_transactions.short_description = 'Transactions'


# ====================================
# INSTALLMENT INLINE
# ====================================
class CustomerInstallmentInline(admin.TabularInline):
    model = CustomerInstallment
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'installment_number',
        'amount',
        'due_date',
        'payment_date',
        'status',
        'payment_reference',
    ]


# ====================================
# TRANSACTION LOG INLINE
# ====================================
class CreditTransactionLogInline(admin.TabularInline):
    model = CreditTransactionLog
    extra = 0
    readonly_fields = ['action', 'old_status', 'new_status', 'performed_by', 'timestamp', 'notes']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


# ====================================
# CREDIT TRANSACTION ADMIN
# ====================================
@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id',
        'customer_name',
        'product_name',
        'phone_price',
        'status_badge',
        'credit_partner',
        'transaction_date',
        'settlement_status',
    ]
    list_filter = [
        'status',
        'credit_partner',
        'transaction_date',
        'confirmation_date',
        'actual_settlement_date',
    ]
    search_fields = [
        'transaction_id',
        'customer__full_name',
        'customer__id_number',
        'product__name',
        'product__product_code',
        'partner_reference',
    ]
    readonly_fields = [
        'transaction_id',
        'created_at',
        'updated_at',
        'confirmation_date',
        'expected_settlement_date',
        'days_until_settlement_display',
        'is_overdue',
    ]
    
    date_hierarchy = 'transaction_date'
    
    inlines = [CustomerInstallmentInline, CreditTransactionLogInline]
    
    fieldsets = (
        ('Transaction Information', {
            'fields': (
                'transaction_id',
                'status',
                'transaction_date',
            )
        }),
        ('Parties', {
            'fields': (
                'credit_partner',
                'customer',
                'dealer',
            )
        }),
        ('Product', {
            'fields': ('product',)
        }),
        ('Pricing', {
            'fields': (
                'phone_price',
                'customer_total',
                'partner_commission',
            )
        }),
        ('Installment Plan', {
            'fields': (
                'installment_amount',
                'installment_period',
            )
        }),
        ('Settlement Tracking', {
            'fields': (
                'confirmation_date',
                'expected_settlement_date',
                'actual_settlement_date',
                'days_until_settlement_display',
                'is_overdue',
            )
        }),
        ('References', {
            'fields': ('partner_reference',)
        }),
        ('Notes', {
            'fields': ('notes', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'confirm_transactions',
        'mark_as_settled',
        'cancel_transactions',
    ]
    
    def customer_name(self, obj):
        return obj.customer.full_name
    customer_name.short_description = 'Customer'
    
    def product_name(self, obj):
        return f"{obj.product.name} ({obj.product.product_code})"
    product_name.short_description = 'Product'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'confirmed': 'blue',
            'active': 'green',
            'settled': 'darkgreen',
            'cancelled': 'red',
            'disputed': 'purple',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def settlement_status(self, obj):
        if obj.status == 'settled':
            return format_html(
                '<span style="color: green;">✓ Settled</span>'
            )
        elif obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ OVERDUE</span>'
            )
        elif obj.expected_settlement_date:
            return format_html(
                '<span style="color: orange;">Due: {}</span>',
                obj.expected_settlement_date
            )
        return '-'
    settlement_status.short_description = 'Settlement'
    
    def days_until_settlement_display(self, obj):
        days = obj.days_until_settlement
        if days is None:
            return 'N/A'
        if days < 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">{} days overdue</span>',
                abs(days)
            )
        return format_html('{} days', days)
    days_until_settlement_display.short_description = 'Days Until Settlement'
    
    # Admin actions
    def confirm_transactions(self, request, queryset):
        count = 0
        for transaction in queryset.filter(status='pending'):
            try:
                transaction.confirm_transaction(confirmed_by=request.user)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error confirming {transaction.transaction_id}: {str(e)}",
                    level='error'
                )
        
        self.message_user(
            request,
            f"Successfully confirmed {count} transaction(s)"
        )
    confirm_transactions.short_description = "Confirm selected transactions"
    
    def mark_as_settled(self, request, queryset):
        count = 0
        for transaction in queryset.filter(status__in=['confirmed', 'active']):
            try:
                transaction.mark_as_settled(settled_by=request.user)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error settling {transaction.transaction_id}: {str(e)}",
                    level='error'
                )
        
        self.message_user(
            request,
            f"Successfully settled {count} transaction(s). StockEntry created for each."
        )
    mark_as_settled.short_description = "Mark as settled"
    
    def cancel_transactions(self, request, queryset):
        count = queryset.exclude(status='settled').update(
            status='cancelled',
            cancellation_reason='Cancelled via admin action'
        )
        self.message_user(
            request,
            f"Successfully cancelled {count} transaction(s)"
        )
    cancel_transactions.short_description = "Cancel selected transactions"


# ====================================
# CUSTOMER INSTALLMENT ADMIN
# ====================================
@admin.register(CustomerInstallment)
class CustomerInstallmentAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id',
        'customer_name',
        'installment_number',
        'amount',
        'due_date',
        'payment_date',
        'status_badge',
    ]
    list_filter = ['status', 'due_date', 'payment_date']
    search_fields = [
        'credit_transaction__transaction_id',
        'credit_transaction__customer__full_name',
        'payment_reference',
    ]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'due_date'
    
    def transaction_id(self, obj):
        return obj.credit_transaction.transaction_id
    transaction_id.short_description = 'Transaction'
    
    def customer_name(self, obj):
        return obj.credit_transaction.customer.full_name
    customer_name.short_description = 'Customer'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'paid': 'green',
            'late': 'red',
            'missed': 'darkred',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


# ====================================
# DEALER SETTLEMENT ADMIN
# ====================================
@admin.register(DealerSettlement)
class DealerSettlementAdmin(admin.ModelAdmin):
    list_display = [
        'settlement_id',
        'credit_partner',
        'total_amount',
        'payment_method',
        'payment_date',
        'transaction_count',
    ]
    list_filter = ['credit_partner', 'payment_method', 'payment_date']
    search_fields = ['settlement_id', 'payment_reference', 'bank_name']
    readonly_fields = ['created_at']
    date_hierarchy = 'payment_date'
    
    filter_horizontal = ['transactions']
    
    fieldsets = (
        ('Settlement Information', {
            'fields': ('settlement_id', 'credit_partner', 'transactions')
        }),
        ('Payment Details', {
            'fields': (
                'total_amount',
                'payment_method',
                'payment_reference',
                'payment_date',
            )
        }),
        ('Bank Details', {
            'fields': ('bank_name', 'account_number'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def transaction_count(self, obj):
        count = obj.transactions.count()
        return format_html(
            '<span style="font-weight: bold;">{} transactions</span>',
            count
        )
    transaction_count.short_description = 'Transactions'


# ====================================
# TRANSACTION LOG ADMIN
# ====================================
@admin.register(CreditTransactionLog)
class CreditTransactionLogAdmin(admin.ModelAdmin):
    list_display = [
        'credit_transaction',
        'action',
        'old_status',
        'new_status',
        'performed_by',
        'timestamp',
    ]
    list_filter = ['action', 'timestamp']
    search_fields = ['credit_transaction__transaction_id', 'notes']
    readonly_fields = [
        'credit_transaction',
        'action',
        'old_status',
        'new_status',
        'performed_by',
        'notes',
        'timestamp',
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False