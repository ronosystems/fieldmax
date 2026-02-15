# ====================================
# CREDIT FINANCING ADMIN
# ====================================
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count, Q
from decimal import Decimal
from .models import (
    CreditCompany,
    CreditCustomer,
    CreditTransaction,
    CompanyPayment,
    CreditTransactionLog
)


# ====================================
# CREDIT COMPANY ADMIN (was CreditPartner)
# ====================================
@admin.register(CreditCompany)
class CreditCompanyAdmin(admin.ModelAdmin):
    """
    Admin for Credit Companies - companies you work with (e.g., M-Kopa, Company X)
    """
    list_display = [
        'name',
        'code',
        'email',
        'phone',
        'contact_person',
        'transaction_count',
        'pending_amount_display',
        'paid_amount_display',
        'is_active',
        'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'email', 'contact_person', 'phone']
    readonly_fields = ['code', 'created_at', 'updated_at', 'transaction_count', 
                       'total_pending', 'total_paid', 'transactions_list']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'email', 'phone', 'contact_person', 'address')
        }),
        ('Payment Terms', {
            'fields': ('payment_terms',),
            'description': 'Optional - for your reference only'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('transaction_count', 'total_pending', 'total_paid'),
            'classes': ('collapse',)
        }),
        ('Related Transactions', {
            'fields': ('transactions_list',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def transaction_count(self, obj):
        """Number of transactions for this company"""
        count = obj.transactions.count()
        return format_html(
            '<span style="font-weight: bold;">{}</span>',
            count
        )
    transaction_count.short_description = 'Transactions'
    
    def pending_amount_display(self, obj):
        """Amount this company owes you"""
        total = obj.transactions.filter(
            payment_status='pending'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00')
        
        if total > 0:
            return format_html(
                '<span style="color: orange; font-weight: bold;">KSH {:,.2f}</span>',
                total
            )
        return format_html('<span style="color: gray;">KSH 0.00</span>')
    pending_amount_display.short_description = 'Pending Payment'
    
    def paid_amount_display(self, obj):
        """Amount this company has paid you"""
        total = obj.transactions.filter(
            payment_status='paid'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00')
        
        if total > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">KSH {:,.2f}</span>',
                total
            )
        return format_html('<span style="color: gray;">KSH 0.00</span>')
    paid_amount_display.short_description = 'Paid Amount'
    
    def total_pending(self, obj):
        """Total pending amount (for readonly fields)"""
        return obj.transactions.filter(
            payment_status='pending'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00')
    total_pending.short_description = 'Total Pending (KSH)'
    
    def total_paid(self, obj):
        """Total paid amount (for readonly fields)"""
        return obj.transactions.filter(
            payment_status='paid'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00')
    total_paid.short_description = 'Total Paid (KSH)'
    
    def transactions_list(self, obj):
        """List of related transactions"""
        transactions = obj.transactions.all().order_by('-transaction_date')[:10]
        if not transactions:
            return "No transactions yet"
        
        html = '<ul style="margin: 0; padding-left: 20px;">'
        for t in transactions:
            status_color = 'green' if t.payment_status == 'paid' else 'orange'
            html += f'''
                <li>
                    <a href="{reverse('admin:credit_financing_credittransaction_change', args=[t.id])}">
                        {t.transaction_id}
                    </a> - 
                    {t.customer.full_name} - 
                    KSH {t.ceiling_price:,.2f} - 
                    <span style="color: {status_color};">{t.get_payment_status_display()}</span>
                </li>
            '''
        html += '</ul>'
        if obj.transactions.count() > 10:
            html += f'<p>... and {obj.transactions.count() - 10} more</p>'
        return format_html(html)
    transactions_list.short_description = 'Recent Transactions'


# ====================================
# CREDIT CUSTOMER ADMIN
# ====================================
@admin.register(CreditCustomer)
class CreditCustomerAdmin(admin.ModelAdmin):
    """
    Admin for Credit Customers - people who buy phones on credit
    """
    list_display = [
        'full_name',
        'id_number',
        'phone_number',
        'transaction_count',
        'total_credit_display',
        'pending_count',
        'is_active',
        'created_at',
    ]
    list_filter = ['is_active', 'county', 'created_at']
    search_fields = [
        'full_name',
        'id_number',
        'phone_number',
        'email',
        'nok_name',
    ]
    readonly_fields = ['created_at', 'updated_at', 'total_credit', 'transactions_list']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('full_name', 'id_number', 'phone_number', 'alternate_phone', 'email')
        }),
        ('Address', {
            'fields': ('county', 'town', 'physical_address'),
            'classes': ('collapse',)
        }),
        ('Next of Kin', {
            'fields': ('nok_name', 'nok_phone'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'notes')
        }),
        ('Statistics', {
            'fields': ('total_credit', 'transactions_list'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def transaction_count(self, obj):
        """Number of transactions for this customer"""
        count = obj.transactions.count()
        return format_html(
            '<span style="font-weight: bold;">{}</span>',
            count
        )
    transaction_count.short_description = 'Transactions'
    
    def total_credit_display(self, obj):
        """Total credit taken by customer"""
        total = obj.transactions.aggregate(
            Sum('ceiling_price')
        )['ceiling_price__sum'] or Decimal('0.00')
        
        if total > 0:
            return format_html(
                '<span style="color: #0dcaf0; font-weight: bold;">KSH {:,.2f}</span>',
                total
            )
        return format_html('<span style="color: gray;">KSH 0.00</span>')
    total_credit_display.short_description = 'Total Credit'
    
    def pending_count(self, obj):
        """Number of pending transactions"""
        count = obj.transactions.filter(payment_status='pending').count()
        if count > 0:
            return format_html(
                '<span style="color: orange; font-weight: bold;">{}</span>',
                count
            )
        return count
    pending_count.short_description = 'Pending'
    
    def total_credit(self, obj):
        """Total credit (for readonly fields)"""
        return obj.transactions.aggregate(
            Sum('ceiling_price')
        )['ceiling_price__sum'] or Decimal('0.00')
    total_credit.short_description = 'Total Credit (KSH)'
    
    def transactions_list(self, obj):
        """List of customer's transactions"""
        transactions = obj.transactions.all().order_by('-transaction_date')[:10]
        if not transactions:
            return "No transactions yet"
        
        html = '<ul style="margin: 0; padding-left: 20px;">'
        for t in transactions:
            status_color = 'green' if t.payment_status == 'paid' else 'orange'
            html += f'''
                <li>
                    <a href="{reverse('admin:credit_financing_credittransaction_change', args=[t.id])}">
                        {t.transaction_id}
                    </a> - 
                    {t.credit_company.name} - 
                    KSH {t.ceiling_price:,.2f} - 
                    <span style="color: {status_color};">{t.get_payment_status_display()}</span>
                </li>
            '''
        html += '</ul>'
        return format_html(html)
    transactions_list.short_description = 'Recent Transactions'


# ====================================
# TRANSACTION LOG INLINE
# ====================================
class CreditTransactionLogInline(admin.TabularInline):
    model = CreditTransactionLog
    extra = 0
    readonly_fields = ['action', 'performed_by', 'notes', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


# ====================================
# CREDIT TRANSACTION ADMIN
# ====================================
@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    """
    Admin for Credit Transactions - records of phones given on credit
    """
    list_display = [
        'transaction_id',
        'customer_link',
        'company_link',
        'product_info',
        'ceiling_price_display',
        'status_badge',
        'transaction_date',
        'days_since',
    ]
    list_filter = [
        'payment_status',
        'credit_company',
        'transaction_date',
        'paid_date',
    ]
    search_fields = [
        'transaction_id',
        'customer__full_name',
        'customer__id_number',
        'product__name',
        'product__product_code',
        'company_reference',
    ]
    readonly_fields = [
        'transaction_id',
        'created_at',
        'updated_at',
        'product_name',
        'product_code',
        'logs_list',
    ]
    
    date_hierarchy = 'transaction_date'
    
    inlines = [CreditTransactionLogInline]
    
    fieldsets = (
        ('Transaction Information', {
            'fields': (
                'transaction_id',
                'payment_status',
                'transaction_date',
            )
        }),
        ('Parties', {
            'fields': (
                'credit_company',
                'customer',
                'dealer',
            )
        }),
        ('Product', {
            'fields': (
                'product',
                'product_name',
                'product_code',
                'imei',
            )
        }),
        ('Pricing', {
            'fields': ('ceiling_price',)
        }),
        ('Payment Tracking', {
            'fields': (
                'paid_date',
                'payment_reference',
            )
        }),
        ('References', {
            'fields': ('company_reference',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Activity Log', {
            'fields': ('logs_list',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_paid',
        'mark_as_pending',
        'export_selected',
    ]
    
    def customer_link(self, obj):
        """Link to customer admin"""
        url = reverse('admin:credit_financing_creditcustomer_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.full_name)
    customer_link.short_description = 'Customer'
    customer_link.admin_order_field = 'customer__full_name'
    
    def company_link(self, obj):
        """Link to company admin"""
        url = reverse('admin:credit_financing_creditcompany_change', args=[obj.credit_company.id])
        return format_html('<a href="{}">{}</a>', url, obj.credit_company.name)
    company_link.short_description = 'Company'
    company_link.admin_order_field = 'credit_company__name'
    
    def product_info(self, obj):
        """Product information"""
        if obj.imei:
            return f"{obj.product_name} ({obj.imei})"
        return obj.product_name
    product_info.short_description = 'Product'
    
    def ceiling_price_display(self, obj):
        """Display ceiling price with formatting"""
        return format_html(
            '<span style="font-weight: bold;">KSH {:,.2f}</span>',
            obj.ceiling_price
        )
    ceiling_price_display.short_description = 'Ceiling Price'
    ceiling_price_display.admin_order_field = 'ceiling_price'
    
    def status_badge(self, obj):
        """Colored status badge"""
        colors = {
            'pending': 'orange',
            'paid': 'green',
            'cancelled': 'red',
        }
        color = colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    status_badge.short_description = 'Status'
    
    def days_since(self, obj):
        """Days since transaction was created"""
        days = obj.days_since_given
        if days == 0:
            return 'Today'
        elif days == 1:
            return 'Yesterday'
        else:
            return f'{days} days'
    days_since.short_description = 'Given'
    
    def logs_list(self, obj):
        """Display transaction logs"""
        logs = obj.logs.all().order_by('-created_at')[:10]
        if not logs:
            return "No logs yet"
        
        html = '<ul style="margin: 0; padding-left: 20px;">'
        for log in logs:
            html += f'<li>{log.created_at.strftime("%Y-%m-%d %H:%M")} - {log.action} - {log.performed_by} - {log.notes}</li>'
        html += '</ul>'
        return format_html(html)
    logs_list.short_description = 'Recent Activity'
    
    # Admin actions
    def mark_as_paid(self, request, queryset):
        """Mark selected transactions as paid"""
        count = 0
        for transaction in queryset.filter(payment_status='pending'):
            try:
                transaction.mark_as_paid(paid_by=request.user)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error marking {transaction.transaction_id} as paid: {str(e)}",
                    level='error'
                )
        
        self.message_user(
            request,
            f"Successfully marked {count} transaction(s) as paid"
        )
    mark_as_paid.short_description = "Mark selected as PAID"
    
    def mark_as_pending(self, request, queryset):
        """Revert selected transactions to pending"""
        count = queryset.filter(payment_status='paid').update(
            payment_status='pending',
            paid_date=None,
            payment_reference=''
        )
        self.message_user(
            request,
            f"Reverted {count} transaction(s) to pending"
        )
    mark_as_pending.short_description = "Revert to PENDING"
    
    def export_selected(self, request, queryset):
        """Export selected transactions (you can implement CSV export)"""
        count = queryset.count()
        self.message_user(
            request,
            f"Selected {count} transaction(s) for export. Implement CSV export here."
        )
    export_selected.short_description = "Export selected"


# ====================================
# COMPANY PAYMENT ADMIN
# ====================================
@admin.register(CompanyPayment)
class CompanyPaymentAdmin(admin.ModelAdmin):
    """
    Admin for Company Payments - bulk payments received from companies
    """
    list_display = [
        'payment_id',
        'credit_company',
        'amount_display',
        'payment_method',
        'payment_reference',
        'payment_date',
        'transaction_count',
        'created_at',
    ]
    list_filter = ['credit_company', 'payment_method', 'payment_date']
    search_fields = ['payment_id', 'payment_reference', 'bank_name']
    readonly_fields = ['payment_id', 'created_at', 'transactions_list']
    date_hierarchy = 'payment_date'
    
    filter_horizontal = ['transactions']
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('payment_id', 'credit_company', 'transactions')
        }),
        ('Payment Details', {
            'fields': (
                'amount',
                'payment_method',
                'payment_reference',
                'payment_date',
            )
        }),
        ('Bank Details', {
            'fields': ('bank_name', 'account_number'),
            'classes': ('collapse',)
        }),
        ('Related Transactions', {
            'fields': ('transactions_list',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def amount_display(self, obj):
        """Display amount with formatting"""
        return format_html(
            '<span style="font-weight: bold; color: green;">KSH {:,.2f}</span>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def transaction_count(self, obj):
        """Number of transactions in this payment"""
        count = obj.transactions.count()
        return format_html(
            '<span style="font-weight: bold;">{} transaction(s)</span>',
            count
        )
    transaction_count.short_description = 'Transactions'
    
    def transactions_list(self, obj):
        """List of transactions in this payment"""
        transactions = obj.transactions.all()
        if not transactions:
            return "No transactions in this payment"
        
        html = '<ul style="margin: 0; padding-left: 20px;">'
        for t in transactions:
            html += f'''
                <li>
                    <a href="{reverse('admin:credit_financing_credittransaction_change', args=[t.id])}">
                        {t.transaction_id}
                    </a> - 
                    {t.customer.full_name} - 
                    KSH {t.ceiling_price:,.2f}
                </li>
            '''
        html += '</ul>'
        return format_html(html)
    transactions_list.short_description = 'Transactions'
    
    actions = ['process_payment']
    
    def process_payment(self, request, queryset):
        """Process selected payments (mark all transactions as paid)"""
        count = 0
        for payment in queryset.filter():
            try:
                payment.process_payment()
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error processing payment {payment.payment_id}: {str(e)}",
                    level='error'
                )
        
        self.message_user(
            request,
            f"Successfully processed {count} payment(s)"
        )
    process_payment.short_description = "Process selected payments"


# ====================================
# TRANSACTION LOG ADMIN
# ====================================
@admin.register(CreditTransactionLog)
class CreditTransactionLogAdmin(admin.ModelAdmin):
    """
    Admin for Transaction Logs - audit trail
    """
    list_display = [
        'transaction_link',
        'action',
        'performed_by',
        'notes_short',
        'created_at',
    ]
    list_filter = ['action', 'created_at']
    search_fields = ['transaction__transaction_id', 'notes', 'performed_by__username']
    readonly_fields = [
        'transaction',
        'action',
        'performed_by',
        'notes',
        'created_at',
    ]
    date_hierarchy = 'created_at'
    
    def transaction_link(self, obj):
        """Link to transaction"""
        url = reverse('admin:credit_financing_credittransaction_change', args=[obj.transaction.id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.transaction_id)
    transaction_link.short_description = 'Transaction'
    
    def notes_short(self, obj):
        """Truncate long notes"""
        if len(obj.notes) > 50:
            return obj.notes[:50] + '...'
        return obj.notes
    notes_short.short_description = 'Notes'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False