from django.contrib import admin
from .models import PendingOrder, PendingOrderItem
from django.contrib import admin
from django.utils.html import format_html
from .models import  Customer, Order, OrderItem, Cart, CartItem

@admin.register(PendingOrder)
class PendingOrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'buyer_name', 'buyer_phone', 'total_amount', 
                    'status', 'created_at']
    list_filter = ['status', 'created_at', 'payment_method']
    search_fields = ['order_id', 'buyer_name', 'buyer_phone']
    readonly_fields = ['order_id', 'created_at', 'updated_at']
    
@admin.register(PendingOrderItem)
class PendingOrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'quantity', 'unit_price', 'total_price']
    list_filter = ['created_at']
    search_fields = ['product_name', 'order__order_id']

    
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'city', 'is_active', 'order_count', 'created_at']
    list_filter = ['is_active', 'city', 'created_at']
    search_fields = ['full_name', 'email', 'phone', 'address']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'full_name', 'email', 'phone')
        }),
        ('Address', {
            'fields': ('address', 'city', 'postal_code')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def order_count(self, obj):
        count = obj.orders.count()
        return format_html(
            '<span style="background-color: #667eea; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            count
        )
    order_count.short_description = 'Orders'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'product_code', 'product_name', 'product_price', 'quantity', 'subtotal']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'customer_name', 'customer_phone', 
        'status_badge', 'payment_status_badge', 'total_amount', 
        'created_at'
    ]
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'customer_name', 'customer_email', 'customer_phone']
    readonly_fields = [
        'order_number', 'subtotal', 'total_amount', 
        'created_at', 'updated_at', 'completed_at'
    ]
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'status', 'payment_status')
        }),
        ('Customer Details', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('Delivery Address', {
            'fields': ('delivery_address', 'delivery_city', 'delivery_postal_code')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'delivery_fee', 'total_amount')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_confirmed', 'mark_as_completed', 'mark_as_cancelled']
    
    def status_badge(self, obj):
        colors = {
            'pending': '#6b7280',
            'confirmed': '#3b82f6',
            'processing': '#f59e0b',
            'shipped': '#8b5cf6',
            'delivered': '#10b981',
            'completed': '#059669',
            'cancelled': '#ef4444'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6b7280'),
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def payment_status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'paid': '#10b981',
            'failed': '#ef4444',
            'refunded': '#6b7280'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.payment_status, '#6b7280'),
            obj.get_payment_status_display().upper()
        )
    payment_status_badge.short_description = 'Payment'
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f'{updated} orders marked as confirmed.')
    mark_as_confirmed.short_description = 'Mark as confirmed'
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        for order in queryset:
            order.status = 'completed'
            order.completed_at = timezone.now()
            order.save()
        self.message_user(request, f'{queryset.count()} orders marked as completed.')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} orders marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark as cancelled'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'session_key', 'item_count', 'cart_total', 'created_at']
    list_filter = ['created_at']
    search_fields = ['customer__full_name', 'session_key']
    readonly_fields = ['created_at', 'updated_at', 'cart_total']
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'
    
    def cart_total(self, obj):
        return f"KSh {obj.get_total():,.2f}"
    cart_total.short_description = 'Total'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'quantity', 'subtotal', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'cart__customer__full_name']
    readonly_fields = ['subtotal', 'created_at', 'updated_at']