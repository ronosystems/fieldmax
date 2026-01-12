from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from decimal import Decimal
from django.http import HttpResponse
import csv
from cloudinary import CloudinaryImage
from .models import Category, Product, StockEntry

# ============================================
# CUSTOM ACTIONS
# ============================================

def export_to_csv(modeladmin, request, queryset):
    """Export selected items to CSV"""
    opts = modeladmin.model._meta
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={opts.verbose_name_plural}.csv'

    writer = csv.writer(response)
    fields = [field for field in opts.get_fields() if not field.many_to_many and not field.one_to_many]

    # Write headers
    writer.writerow([field.verbose_name for field in fields])

    # Write data
    for obj in queryset:
        writer.writerow([getattr(obj, field.name) for field in fields])

    return response
export_to_csv.short_description = "Export to CSV"


def mark_as_active(modeladmin, request, queryset):
    queryset.update(is_active=True)
mark_as_active.short_description = "Mark as active"


def mark_as_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)
mark_as_inactive.short_description = "Mark as inactive"


# ============================================
# INLINE ADMINS
# ============================================

class StockEntryInline(admin.TabularInline):
    model = StockEntry
    extra = 0
    can_delete = False
    readonly_fields = [
        'quantity',
        'entry_type',
        'unit_price',
        'total_amount',
        'reference_id',
        'created_by',
        'created_at',
        'notes'
    ]
    fields = [
        'entry_type',
        'quantity',
        'unit_price',
        'total_amount',
        'reference_id',
        'created_by',
        'created_at'
    ]

    def has_add_permission(self, request, obj=None):
        return False


class ProductInline(admin.TabularInline):
    model = Product
    extra = 0
    fields = ['product_code', 'name', 'sku_value', 'quantity', 'status', 'image', 'is_active']
    readonly_fields = ['product_code', 'status']
    show_change_link = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_active=True)


# ============================================
# CATEGORY ADMIN
# ============================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'category_code',
        'item_type_badge',
        'sku_type_badge',
        'product_count',
        'total_inventory_value',
    ]
    list_filter = ['item_type', 'sku_type']
    search_fields = ['name', 'category_code']
    readonly_fields = ['category_code', 'created_info']
    fieldsets = (
        ('Basic Information', {'fields': ('name', 'category_code')}),
        ('Configuration', {'fields': ('item_type', 'sku_type')}),
        ('Statistics', {'fields': ('created_info',), 'classes': ('collapse',)}),
    )
    inlines = [ProductInline]
    actions = [export_to_csv]

    def item_type_badge(self, obj):
        colors = {'single': '#007bff', 'bulk': '#28a745'}
        color = colors.get(obj.item_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_item_type_display()
        )
    item_type_badge.short_description = 'Item Type'

    def sku_type_badge(self, obj):
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            obj.get_sku_type_display()
        )
    sku_type_badge.short_description = 'SKU Type'

    def product_count(self, obj):
        count = obj.products.filter(is_active=True).count()
        url = reverse('admin:inventory_product_changelist') + f'?category__id__exact={obj.id}'
        return format_html('<a href="{}">{} products</a>', url, count)
    product_count.short_description = 'Products'

    def total_inventory_value(self, obj):
        total = sum(
            (Decimal(p.buying_price or 0) * Decimal(p.quantity or 0))
            for p in obj.products.filter(is_active=True)
        )
        formatted_value = '${:,.2f}'.format(float(total))
        return format_html('<strong>{}</strong>', formatted_value)
    total_inventory_value.short_description = 'Inventory Value'

    def created_info(self, obj):
        products = obj.products.filter(is_active=True)
        if getattr(obj, 'is_single_item', False):
            available = sum(1 for p in products if p.status == 'available')
            sold = sum(1 for p in products if p.status == 'sold')
            info = f"Available: {available} | Sold: {sold}"
        else:
            total_qty = sum(p.quantity or 0 for p in products)
            available = sum(1 for p in products if p.status == 'available')
            lowstock = sum(1 for p in products if p.status == 'lowstock')
            outofstock = sum(1 for p in products if p.status == 'outofstock')
            info = (
                f"Total Units: {total_qty} | "
                f"Available: {available} | "
                f"Low Stock: {lowstock} | "
                f"Out: {outofstock}"
            )
        return info
    created_info.short_description = 'Category Statistics'


# ============================================
# PRODUCT ADMIN
# ============================================
# ============================================
# PRODUCT ADMIN - WITH BARCODE SUPPORT
# ============================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'show_image',
        'product_code',
        'name',
        'category_link',
        'identifier_display',  # ✅ CHANGED: Shows SKU or Barcode based on item type
        'quantity_display',
        'status_badge',
        'pricing_info',
        'profit_display',
        'owner_link',
        'is_active',
    ]
    list_filter = [
        'is_active',
        'status',
        'category',
        'category__item_type',
        'created_at',
    ]
    search_fields = [
        'product_code',
        'name',
        'sku_value',
        'barcode',  # ✅ ADD: Search by barcode
        'owner__username'
    ]
    readonly_fields = [
        'product_code',
        'status',
        'created_at',
        'updated_at',
        'live_image_preview',
        'inventory_summary',
        'profit_margin',
        'profit_percentage',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'product_code',
                'name',
                'category',
            )
        }),
        ('Identifiers', {  # ✅ NEW SECTION
            'fields': (
                'sku_value',
                'barcode',
            ),
            'description': 'SKU for single items (IMEI/Serial), Barcode for bulk items'
        }),
        ('Product Image', {
            'fields': (
                'image',
                'live_image_preview',
            ),
            'description': 'Upload an image to see it instantly below'
        }),
        ('Inventory', {
            'fields': (
                'quantity',
                'status',
            )
        }),
        ('Pricing', {
            'fields': (
                'buying_price',
                'selling_price',
                'profit_margin',
                'profit_percentage',
            )
        }),
        ('Ownership & Status', {
            'fields': (
                'owner',
                'is_active',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
        ('Summary', {
            'fields': ('inventory_summary',),
            'classes': ('collapse',)
        }),
    )

    inlines = [StockEntryInline]
    actions = [export_to_csv, mark_as_active, mark_as_inactive]
    date_hierarchy = 'created_at'
    list_per_page = 50

    # ============================================
    # MEDIA FOR LIVE IMAGE PREVIEW
    # ============================================
    
    class Media:
        js = ('admin/js/vendor/jquery/jquery.js', 'admin/js/jquery.init.js')
        css = {
            'all': ('admin/css/base.css',)
        }

    # ============================================
    # ✅ NEW: IDENTIFIER DISPLAY (SKU OR BARCODE)
    # ============================================

    def identifier_display(self, obj):
        """Display SKU for single items, Barcode for bulk items"""
        if obj.category.is_single_item:
            # Single items: Show SKU (IMEI/Serial)
            if obj.sku_value:
                sku_short = obj.sku_value[:15] + '...' if len(obj.sku_value) > 15 else obj.sku_value
                return format_html(
                    '<div style="display: flex; align-items: center; gap: 4px;">'
                    '<span style="background: #e0f7ff; color: #0369a1; padding: 2px 6px; '
                    'border-radius: 4px; font-size: 11px; font-weight: 600;">'
                    '📱 SKU</span>'
                    '<code style="font-size: 11px;">{}</code>'
                    '</div>',
                    sku_short
                )
            else:
                return format_html(
                    '<span style="color: #999; font-size: 11px;">No SKU</span>'
                )
        else:
            # Bulk items: Show Barcode
            if obj.barcode:
                barcode_short = obj.barcode[:15] + '...' if len(obj.barcode) > 15 else obj.barcode
                return format_html(
                    '<div style="display: flex; align-items: center; gap: 4px;">'
                    '<span style="background: #fef3c7; color: #92400e; padding: 2px 6px; '
                    'border-radius: 4px; font-size: 11px; font-weight: 600;">'
                    '🔍 BARCODE</span>'
                    '<code style="font-size: 11px;">{}</code>'
                    '</div>',
                    barcode_short
                )
            else:
                return format_html(
                    '<span style="color: #999; font-size: 11px;">No Barcode</span>'
                )
    
    identifier_display.short_description = 'SKU / Barcode'
    identifier_display.admin_order_field = 'sku_value'  # Default sort by SKU

    # ============================================
    # EXISTING METHODS (KEEP AS IS)
    # ============================================

    def show_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" />', obj.image.url)
        return "-"
    show_image.short_description = 'Image'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('category', 'owner')
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return True

    # ============================================
    # LIVE IMAGE PREVIEW (KEEP AS IS)
    # ============================================

    def live_image_preview(self, obj):
        """Live preview that updates when image is uploaded"""
        
        current_image_html = ''
        if obj and obj.image:
            try:
                public_id = obj.image.name
                img_url = CloudinaryImage(public_id).build_url(
                    width=400,
                    height=400,
                    crop='limit',
                    quality='auto',
                    fetch_format='auto'
                )
                current_image_html = f'''
                <img src="{img_url}" 
                     style="max-width: 400px; max-height: 400px; border-radius: 8px; 
                            box-shadow: 0 2px 8px rgba(0,0,0,0.1);" 
                     loading="lazy" 
                     alt="Product preview" />
                <div style="margin-top: 0.5rem; font-size: 0.75rem; color: #28a745;">
                    ✅ Image loaded from Cloudinary
                </div>
                '''
            except:
                current_image_html = '''
                <div style="padding: 10px; background: #fff3cd; border: 1px solid #ffc107; 
                            border-radius: 8px; text-align: center;">
                    <strong style="color: #856404;">⚠️ Error loading current image</strong>
                </div>
                '''
        else:
            current_image_html = '''
            <div style="padding: 20px; background: #f8f9fa; border: 2px dashed #dee2e6; 
                        border-radius: 8px; text-align: center;">
                <span style="font-size: 3rem; color: #adb5bd;">📷</span><br>
                <span style="color: #6c757d; font-size: 0.875rem;">No image yet - upload one above</span>
            </div>
            '''

        return format_html('''
            <div style="text-align: center;">
                <div id="image-preview-container" style="min-height: 200px;">
                    {current_image}
                </div>
                
                <script>
                (function() {{
                    if (document.readyState === 'loading') {{
                        document.addEventListener('DOMContentLoaded', initImagePreview);
                    }} else {{
                        initImagePreview();
                    }}
                    
                    function initImagePreview() {{
                        const imageInput = document.querySelector('input[name="image"]');
                        const clearCheckbox = document.querySelector('input[name="image-clear"]');
                        const previewContainer = document.getElementById('image-preview-container');
                        
                        if (!imageInput || !previewContainer) return;
                        
                        imageInput.addEventListener('change', function(e) {{
                            const file = e.target.files[0];
                            
                            if (file && file.type.startsWith('image/')) {{
                                const reader = new FileReader();
                                
                                reader.onload = function(event) {{
                                    previewContainer.innerHTML = `
                                        <div style="position: relative;">
                                            <img src="${{event.target.result}}" 
                                                 style="max-width: 400px; max-height: 400px; 
                                                        border-radius: 8px; 
                                                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);" 
                                                 alt="Preview" />
                                            <div style="margin-top: 0.5rem; padding: 8px; 
                                                        background: #d1ecf1; border: 1px solid #bee5eb; 
                                                        border-radius: 4px; font-size: 0.875rem; 
                                                        color: #0c5460;">
                                                <strong>📤 Ready to upload to Cloudinary</strong><br>
                                                <small>Image will be uploaded when you save</small>
                                            </div>
                                        </div>
                                    `;
                                }};
                                
                                reader.readAsDataURL(file);
                            }}
                        }});
                        
                        if (clearCheckbox) {{
                            clearCheckbox.addEventListener('change', function(e) {{
                                if (e.target.checked) {{
                                    previewContainer.innerHTML = `
                                        <div style="padding: 40px; background: #f8d7da; 
                                                    border: 2px dashed #f5c6cb; 
                                                    border-radius: 8px; text-align: center;">
                                            <span style="font-size: 3rem; color: #721c24;">🗑️</span><br>
                                            <strong style="color: #721c24;">Image will be removed</strong><br>
                                            <small style="color: #721c24;">Uncheck to keep current image</small>
                                        </div>
                                    `;
                                }} else {{
                                    location.reload();
                                }}
                            }});
                        }}
                    }}
                }})();
                </script>
            </div>
        ''', current_image=current_image_html)
    
    live_image_preview.short_description = '📸 Live Image Preview'

    # ============================================
    # OTHER DISPLAY METHODS (KEEP AS IS)
    # ============================================

    def category_link(self, obj):
        if obj.category:
            url = reverse('admin:inventory_category_change', args=[obj.category.id])
            return format_html('<a href="{}">{}</a>', url, obj.category.name)
        return '-'
    category_link.short_description = 'Category'
    category_link.admin_order_field = 'category__name'

    def quantity_display(self, obj):
        qty = obj.quantity or 0
        if getattr(obj.category, 'is_single_item', False):
            color = '#28a745' if qty > 0 else '#dc3545'
            text = 'Available' if qty > 0 else 'Sold'
        else:
            if qty > 5:
                color = '#28a745'
            elif qty > 0:
                color = '#ffc107'
            else:
                color = '#dc3545'
            text = str(qty)
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, text)
    quantity_display.short_description = 'Quantity'
    quantity_display.admin_order_field = 'quantity'

    def status_badge(self, obj):
        colors = {
            'available': '#28a745',
            'sold': '#6c757d',
            'lowstock': '#ffc107',
            'outofstock': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            (obj.get_status_display() or '').upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def pricing_info(self, obj):
        buy_price = float(Decimal(obj.buying_price or 0))
        sell_price = float(Decimal(obj.selling_price or 0))
        formatted_buy = 'KSH {:,.2f}'.format(buy_price)
        formatted_sell = 'KSH {:,.2f}'.format(sell_price)
        return format_html(
            'Buy: <strong>{}</strong><br>Sell: <strong>{}</strong>',
            formatted_buy,
            formatted_sell
        )
    pricing_info.short_description = 'Pricing'

    def profit_display(self, obj):
        margin = float(Decimal(obj.profit_margin or 0))
        percentage = float(Decimal(obj.profit_percentage or 0))
        color = '#28a745' if margin > 0 else '#dc3545'
        formatted_margin = 'KSH {:,.2f}'.format(margin)
        formatted_percentage = '{:.1f}%'.format(percentage)
        return format_html('<span style="color: {};">{} ({})</span>', color, formatted_margin, formatted_percentage)
    profit_display.short_description = 'Profit'

    def owner_link(self, obj):
        if obj.owner:
            url = reverse('admin:auth_user_change', args=[obj.owner.id])
            return format_html('<a href="{}">{}</a>', url, obj.owner.username)
        return '-'
    owner_link.short_description = 'Owner'
    owner_link.admin_order_field = 'owner__username'

    def inventory_summary(self, obj):
        stock_entries = obj.stock_entries.all()
        total_entries = stock_entries.count()
        purchases = stock_entries.filter(entry_type='purchase').aggregate(total=Sum('quantity'))['total'] or 0
        sales = stock_entries.filter(entry_type='sale').aggregate(total=Sum('quantity'))['total'] or 0
        returns = stock_entries.filter(entry_type='return').aggregate(total=Sum('quantity'))['total'] or 0
        adjustments = stock_entries.filter(entry_type='adjustment').aggregate(total=Sum('quantity'))['total'] or 0

        total_value = float(Decimal(obj.buying_price or 0) * Decimal(obj.quantity or 0))
        formatted_value = 'KSH {:,.2f}'.format(total_value)

        # ✅ ADD: Display identifier info
        identifier_info = ''
        if obj.category.is_single_item and obj.sku_value:
            identifier_info = f'<tr><td style="padding:8px; border:1px solid #dee2e6;">SKU/IMEI</td><td style="padding:8px; text-align:right; border:1px solid #dee2e6;"><code>{obj.sku_value}</code></td></tr>'
        elif obj.category.is_bulk_item and obj.barcode:
            identifier_info = f'<tr><td style="padding:8px; border:1px solid #dee2e6;">Barcode</td><td style="padding:8px; text-align:right; border:1px solid #dee2e6;"><code>{obj.barcode}</code></td></tr>'

        return format_html(
            """
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background-color:#f8f9fa;">
                    <th style="padding:8px; text-align:left; border:1px solid #dee2e6;">Metric</th>
                    <th style="padding:8px; text-align:right; border:1px solid #dee2e6;">Value</th>
                </tr>
                {}
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Total Stock Entries</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Total Purchased</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{} units</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Total Sold</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{} units</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Total Returns</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{} units</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Total Adjustments</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{} units</td>
                </tr>
                <tr style="background-color:#f8f9fa; font-weight:bold;">
                    <td style="padding:8px; border:1px solid #dee2e6;">Current Stock Value</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr style="background-color:#f8f9fa; font-weight:bold;">
                    <td style="padding:8px; border:1px solid #dee2e6;">Can Restock</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
            </table>
            """,
            identifier_info,
            total_entries,
            purchases,
            abs(sales),
            returns,
            adjustments,
            formatted_value,
            'Yes' if getattr(obj, 'can_restock', False) else 'No'
        )
    inventory_summary.short_description = 'Inventory Summary'


# ============================================
# STOCK ENTRY ADMIN
# ============================================

def reverse_stock_entry(modeladmin, request, queryset):
    for entry in queryset:
        if entry.entry_type == 'sale':
            StockEntry.objects.create(
                product=entry.product,
                entry_type='reversal',
                quantity=-entry.quantity,
                unit_price=entry.unit_price,
                total_amount=-float(Decimal(entry.total_amount)),
                reference_id=f"Reversal of {entry.reference_id}",
                created_by=request.user,
                notes='Reversal of sale'
            )
reverse_stock_entry.short_description = "Reverse selected sales"


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'product_link',
        'entry_type_badge',
        'quantity_display',
        'unit_price',
        'total_amount_display',
        'reference_id',
        'created_by_link',
        'created_at',
    ]
    list_filter = [
        'entry_type',
        'created_at',
        'product__category',
    ]
    search_fields = [
        'product__product_code',
        'product__name',
        'reference_id',
        'notes',
        'created_by__username',
    ]
    readonly_fields = [
        'product',
        'quantity',
        'entry_type',
        'unit_price',
        'total_amount',
        'reference_id',
        'notes',
        'created_by',
        'created_at',
        'entry_summary',
    ]
    fieldsets = (
        ('Entry Information', {'fields': ('product', 'entry_type', 'quantity')}),
        ('Financial', {'fields': ('unit_price', 'total_amount')}),
        ('Reference', {'fields': ('reference_id', 'notes')}),
        ('Metadata', {'fields': ('created_by', 'created_at')}),
        ('Summary', {'fields': ('entry_summary',), 'classes': ('collapse',)}),
    )
    date_hierarchy = 'created_at'
    list_per_page = 100
    actions = [export_to_csv, reverse_stock_entry]

    def has_add_permission(self, request):
        return True
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('product', 'product__category', 'created_by')

    def product_link(self, obj):
        if obj.product:
            url = reverse('admin:inventory_product_change', args=[obj.product.id])
            return format_html('<a href="{}">{} ({})</a>', url, obj.product.name, obj.product.product_code)
        return '-'
    product_link.short_description = 'Product'
    product_link.admin_order_field = 'product__name'

    def entry_type_badge(self, obj):
        colors = {
            'purchase': '#28a745',
            'sale': '#dc3545',
            'return': '#17a2b8',
            'reversal': '#17a2b8',
            'adjustment': '#ffc107',
        }
        color = colors.get(obj.entry_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            (obj.get_entry_type_display() or '').upper()
        )
    entry_type_badge.short_description = 'Type'
    entry_type_badge.admin_order_field = 'entry_type'

    def quantity_display(self, obj):
        qty = obj.quantity or 0
        color = '#28a745' if getattr(obj, 'is_stock_in', False) else '#dc3545'
        sign = '+' if getattr(obj, 'is_stock_in', False) else ''
        return format_html('<span style="color: {}; font-weight: bold;">{}{}</span>', color, sign, qty)
    quantity_display.short_description = 'Quantity'
    quantity_display.admin_order_field = 'quantity'

    def total_amount_display(self, obj):
        total_amount = float(Decimal(obj.total_amount or 0))
        formatted_amount = '${:,.2f}'.format(total_amount)
        return format_html('<strong>{}</strong>', formatted_amount)
    total_amount_display.short_description = 'Total'
    total_amount_display.admin_order_field = 'total_amount'

    def created_by_link(self, obj):
        if obj.created_by:
            url = reverse('admin:auth_user_change', args=[obj.created_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.created_by.username)
        return '-'
    created_by_link.short_description = 'Created By'
    created_by_link.admin_order_field = 'created_by__username'

    def entry_summary(self, obj):
        unit_price = float(Decimal(obj.unit_price or 0))
        total_amount = float(Decimal(obj.total_amount or 0))
        formatted_unit = '${:,.2f}'.format(unit_price)
        formatted_total = '${:,.2f}'.format(total_amount)
        
        return format_html(
            """
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background-color:#f8f9fa;">
                    <th style="padding:8px; text-align:left; border:1px solid #dee2e6;">Detail</th>
                    <th style="padding:8px; text-align:right; border:1px solid #dee2e6;">Value</th>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Product</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Product Code</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Entry Type</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Quantity Change</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Unit Price</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr style="background-color:#f8f9fa; font-weight:bold;">
                    <td style="padding:8px; border:1px solid #dee2e6;">Total Amount</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Reference ID</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Created By</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #dee2e6;">Created At</td>
                    <td style="padding:8px; text-align:right; border:1px solid #dee2e6;">{}</td>
                </tr>
                <tr>
                    <td colspan="2" style="padding:8px; border:1px solid #dee2e6;"><strong>Notes:</strong><br>{}</td>
                </tr>
            </table>
            """,
            obj.product.name if obj.product else '-',
            obj.product.product_code if obj.product else '-',
            obj.get_entry_type_display() if hasattr(obj, 'get_entry_type_display') else obj.entry_type,
            '+' if getattr(obj, 'is_stock_in', False) else '',
            obj.quantity or 0,
            formatted_unit,
            formatted_total,
            obj.reference_id or '-',
            (obj.created_by.username if obj.created_by else '-'),
            (obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(obj, 'created_at', None) else '-'),
            obj.notes or '-'
        )
    entry_summary.short_description = 'Entry Details'


# ============================================
# ADMIN SITE CUSTOMIZATION
# ============================================

admin.site.site_header = "Inventory Management System"
admin.site.site_title = "Inventory Admin"
admin.site.index_title = "Welcome to Inventory Management"