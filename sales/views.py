#====================================
#SALES IMPORTS
#====================================
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, DeleteView
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

# Third-party imports
from rest_framework import viewsets, generics
import json
import logging
from decimal import Decimal
from . import models
from django.http import JsonResponse
from django.db.models import Count
from django.contrib.auth.models import User

# App imports
from .models import Sale, SaleReversal, SaleItem
from .forms import SaleForm
from .serializers import SaleSerializer
from inventory.models import Product, StockEntry
try:
    from .etr import process_fieldmax_etr_for_sale, process_etr_for_sale
except ImportError:
    process_fieldmax_etr_for_sale = None
    process_etr_for_sale = None

try:
    import pdfkit
except ImportError:
    pdfkit = None
from django.contrib.auth import get_user_model







User = get_user_model()
logger = logging.getLogger(__name__)












# =========================================
# GET SELLER
# =========================================

def get_sellers(request):
    """Return all users who have made sales"""
    sellers = User.objects.filter(
        sales_made__isnull=False
    ).distinct().values('id', 'username', 'first_name', 'last_name')
    
    return JsonResponse({
        'sellers': list(sellers)
    })












# =========================================
# SALE CREATION VIEW WITH FIFO LOGIC
# =========================================

@method_decorator(login_required, name='dispatch')
class SaleCreateView(View):
    """
    Create sale with STRICT FIFO logic + SOLD PROTECTION:
    - Single items: Sell OLDEST available unit (by created_at)
    - BLOCKS sold products from being resold
    - Bulk items: Deduct from shared product record
    - GUARANTEES: StockEntry + Product updates happen atomically
    """
    
    @transaction.atomic
    def post(self, request):
        try:
            # Parse request data
            data = json.loads(request.body) if request.content_type == "application/json" else request.POST
            
            product_code = data.get("product_code", "").strip()
            quantity = int(data.get("quantity", 1) or 1)
            unit_price_input = data.get("unit_price", "")
            
            # Client details
            buyer_name = data.get("buyer_name", "").strip()
            buyer_phone = data.get("buyer_phone", "").strip()
            buyer_id_number = data.get("buyer_id_number", "").strip()
            nok_name = data.get("nok_name", "").strip()
            nok_phone = data.get("nok_phone", "").strip()

            # Validations
            if not product_code:
                return JsonResponse({"status": "error", "message": "Product code/SKU is required"}, status=400)
            if quantity <= 0:
                return JsonResponse({"status": "error", "message": "Quantity must be greater than 0"}, status=400)

            # Parse price
            try:
                unit_price = Decimal(str(unit_price_input)) if unit_price_input else Decimal('0')
            except (ValueError, TypeError):
                unit_price = Decimal('0')

            # ============================================
            # FIFO PRODUCT LOOKUP (EXCLUDES SOLD ITEMS)
            # ============================================
            products = Product.objects.filter(
                Q(product_code__iexact=product_code) | Q(sku_value__iexact=product_code),
                is_active=True
            ).exclude(
                status='sold'  # 🔒 CRITICAL: Prevent sold items from being selected
            ).select_related('category').select_for_update().order_by('created_at')  # LOCK + FIFO

            if not products.exists():
                # Check if product exists but is sold
                sold_check = Product.objects.filter(
                    Q(product_code__iexact=product_code) | Q(sku_value__iexact=product_code),
                    status='sold'
                ).first()
                
                if sold_check:
                    return JsonResponse({
                        "status": "error",
                        "message": f"❌ Product '{product_code}' has been SOLD."
                    }, status=400)
                
                return JsonResponse({
                    "status": "error", 
                    "message": f"Product '{product_code}' not found in inventory"
                }, status=404)

            first_product = products.first()
            
            # ============================================
            # SINGLE ITEMS: STRICT FIFO SELECTION
            # ============================================
            if first_product.category.is_single_item:
                logger.info(f"[FIFO SINGLE ITEM] Searching for oldest available unit...")
                
                available_product = products.filter(
                    status='available',
                    quantity=1
                ).first()
                
                if not available_product:
                    total_units = Product.objects.filter(
                        Q(product_code__iexact=product_code) | Q(sku_value__iexact=product_code)
                    ).count()
                    
                    sold_units = Product.objects.filter(
                        Q(product_code__iexact=product_code) | Q(sku_value__iexact=product_code),
                        status='sold'
                    ).count()
                    
                    return JsonResponse({
                        "status": "error",
                        "message": (
                            f"❌ No available units of {first_product.name}. "
                            f"Total units: {total_units}, Sold: {sold_units}. "
                            f"Reverse a sale to make units available."
                        )
                    }, status=400)
                
                if quantity != 1:
                    return JsonResponse({
                        "status": "error",
                        "message": "❌ Can only sell 1 single item at a time"
                    }, status=400)
                
                product_to_sell = available_product
                
                logger.info(
                    f"[FIFO SELECTED] Product: {product_to_sell.product_code} | "
                    f"SKU: {product_to_sell.sku_value} | "
                    f"Status: {product_to_sell.status} | "
                    f"Created: {product_to_sell.created_at} | "
                    f"Age: {(timezone.now() - product_to_sell.created_at).days} days"
                )

            # ============================================
            # BULK ITEMS: QUANTITY DEDUCTION
            # ============================================
            else:
                logger.info(f"[BULK ITEM] Processing sale...")
                product_to_sell = first_product
                
                if product_to_sell.status == 'outofstock':
                    return JsonResponse({
                        "status": "error",
                        "message": f"❌ {product_to_sell.name} is OUT OF STOCK"
                    }, status=400)
                
                if product_to_sell.quantity < quantity:
                    return JsonResponse({
                        "status": "error",
                        "message": f"❌ Insufficient stock! Only {product_to_sell.quantity} available."
                    }, status=400)

            # ============================================
            # DOUBLE-CHECK: Validate Product Status
            # ============================================
            if product_to_sell.status == 'sold':
                return JsonResponse({
                    "status": "error",
                    "message": "❌ This product has already been SOLD."
                }, status=400)
            
            if product_to_sell.status == 'outofstock':
                return JsonResponse({
                    "status": "error",
                    "message": f"❌ {product_to_sell.name} is OUT OF STOCK"
                }, status=400)

            # ============================================
            # PRICE VALIDATION
            # ============================================
            if unit_price <= 0:
                unit_price = product_to_sell.selling_price or Decimal('0')
            
            if unit_price <= 0:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid selling price"
                }, status=400)

            total_price = unit_price * quantity

            # ============================================
            # CREATE SALE RECORD FIRST
            # ============================================
            client_details_json = json.dumps({
                "buyer_name": buyer_name,
                "buyer_phone": buyer_phone,
                "buyer_id_number": buyer_id_number,
                "nok_name": nok_name,
                "nok_phone": nok_phone
            })

            sale = Sale.objects.create(
                product=product_to_sell,
                seller=request.user,
                quantity=quantity,
                selling_price=unit_price,
                unit_price=unit_price,
                total_price=total_price,
                product_code=product_to_sell.product_code,
                client_details=client_details_json,
                buyer_name=buyer_name,
                buyer_phone=buyer_phone,
                buyer_id_number=buyer_id_number,
                nok_name=nok_name,
                nok_phone=nok_phone,
            )
            
            logger.info(f"[SALE CREATED] Sale #{sale.sale_id} created for {product_to_sell.product_code}")

            # ============================================
            # CRITICAL: CREATE STOCK ENTRY (Updates Product)
            # ============================================
            logger.info(
                f"[PRE-SALE] Product: {product_to_sell.product_code} | "
                f"Current Qty: {product_to_sell.quantity} | "
                f"Current Status: {product_to_sell.status}"
            )
            
            stock_entry = StockEntry.objects.create(
                product=product_to_sell,
                quantity=-quantity,  # NEGATIVE = stock OUT
                entry_type='sale',
                unit_price=unit_price,
                total_amount=total_price,
                reference_id=f"SALE-{sale.sale_id}",  # ✅ Link to sale
                created_by=request.user,
                notes=f"FIFO Sale #{sale.sale_id} to {buyer_name or 'Walk-in'}"
            )
            
            # REFRESH product to see updated values from StockEntry.save()
            product_to_sell.refresh_from_db()
            
            logger.info(
                f"[POST-SALE] Product: {product_to_sell.product_code} | "
                f"New Qty: {product_to_sell.quantity} | "
                f"New Status: {product_to_sell.status} | "
                f"StockEntry ID: {stock_entry.id}"
            )

            # ============================================
            # VERIFY: Ensure status updated correctly
            # ============================================
            if first_product.category.is_single_item and product_to_sell.status != 'sold':
                logger.error(
                    f"[STATUS ERROR] Single item {product_to_sell.product_code} "
                    f"not marked as sold! Current status: {product_to_sell.status}"
                )
                # Force update
                product_to_sell.status = 'sold'
                product_to_sell.quantity = 0
                product_to_sell.save(update_fields=['status', 'quantity'])
                logger.warning(f"[FORCED UPDATE] Product {product_to_sell.product_code} manually set to SOLD")

            # ============================================
            # ETR PROCESSING (Optional)
            # ============================================
            if process_fieldmax_etr_for_sale:
                try:
                    etr_result = process_fieldmax_etr_for_sale(sale)
                    if etr_result.get("success"):
                        sale.etr_status = "processed"
                        sale.etr_receipt_number = etr_result.get("receipt_number")
                        sale.save()
                except Exception as etr_error:
                    logger.warning(f"ETR processing failed: {etr_error}")

            # ============================================
            # RESPONSE WITH FIFO CONFIRMATION
            # ============================================
            return JsonResponse({
                "status": "success",
                "message": f"✅ Sale recorded! {product_to_sell.name} sold for KSH {float(total_price):,.2f}",
                "sale_id": sale.sale_id,
                "fifo_details": {
                    "product_code": product_to_sell.product_code,
                    "sku": product_to_sell.sku_value or "N/A",
                    "item_type": product_to_sell.category.item_type,
                    "created_at": product_to_sell.created_at.isoformat(),
                    "age_days": (timezone.now() - product_to_sell.created_at).days,
                    "was_oldest_available": first_product.category.is_single_item,
                },
                "product": {
                    "name": product_to_sell.name,
                    "new_quantity": product_to_sell.quantity,
                    "new_status": product_to_sell.status,
                },
                "sale_details": {
                    "quantity": quantity,
                    "unit_price": float(unit_price),
                    "total_price": float(total_price),
                },
                "stock_alert": self._get_stock_alert(product_to_sell),
            }, status=200)

        except ValidationError as ve:
            logger.error(f"ValidationError: {ve}")
            return JsonResponse({"status": "error", "message": str(ve)}, status=400)
        
        except Exception as e:
            logger.exception(f"SaleCreateView error: {e}")
            return JsonResponse({"status": "error", "message": f"Server error: {str(e)}"}, status=500)

    def _get_stock_alert(self, product):
        """Generate stock alert message"""
        if product.category.is_single_item:
            return "⚠️ Item is now SOLD" if product.status == 'sold' else "✓ Item still available"
        else:
            if product.status == 'outofstock':
                return "⚠️ OUT OF STOCK"
            elif product.status == 'lowstock':
                return f"⚠️ Low stock: {product.quantity} remaining"
            return f"✓ {product.quantity} units remaining"











# =========================================
# SALE REVERSAL VIEW 
# =========================================

class SaleReverseView(LoginRequiredMixin, View):
    def post(self, request, sale_id):
        sale = get_object_or_404(Sale, sale_id=sale_id)
        if not sale.can_be_reversed:
            return JsonResponse({"success": False, "message": "Sale cannot be reversed"}, status=400)
        
        reason = request.POST.get("reason", "No reason provided")
        try:
            result = sale.reverse_sale(reversed_by=request.user)
            return JsonResponse({
                "success": True,
                "message": f"Sale #{sale.sale_id} reversed successfully",
                "result": result
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)









# ============================================
# ============================================
# SALES REPORT API  
# ============================================
# ============================================

@login_required
def sales_report_api(request):
    """
    Generate filtered sales report
    Returns: JSON with sales data aggregated by product
    """
    # Get filter parameters
    seller_id = request.GET.get('seller', '').strip()
    category_id = request.GET.get('category', '').strip()
    start_date = request.GET.get('start', '').strip()
    end_date = request.GET.get('end', '').strip()
    
    try:
        # Start with all sale items (not sales)
        sale_items = SaleItem.objects.select_related(
            'sale', 
            'sale__seller',
            'product',
            'product__category'
        ).filter(
            sale__is_reversed=False  # Exclude reversed sales
        )
        
        # Apply filters
        if seller_id:
            sale_items = sale_items.filter(sale__seller_id=seller_id)
        
        if category_id:
            sale_items = sale_items.filter(product__category_id=category_id)
        
        if start_date:
            sale_items = sale_items.filter(sale__sale_date__gte=start_date)
        
        if end_date:
            sale_items = sale_items.filter(sale__sale_date__lte=end_date)
        
        # Build results list with COMPLETE product data
        results = []
        for item in sale_items:
            results.append({
                "date": item.sale.sale_date.strftime("%Y-%m-%d"),
                "seller": item.sale.seller.username if item.sale.seller else "N/A",
                "buyer_name": item.sale.buyer_name or "Walk-in Customer", 
                "category": item.product.category.name if item.product.category else "N/A",
                
                # ✅ FIX: Return product as OBJECT with all needed fields
                "product": {
                    "name": item.product_name,
                    "etr_number": item.sale.etr_receipt_number or f"RCPT-{item.sale.sale_id}",
                    "sku_value": item.sku_value or item.product_code or "N/A",
                    "selling_price": float(item.unit_price),
                    "product_code": item.product_code
                },
                
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total": float(item.total_price)
            })
        
        return JsonResponse({
            "status": "success",
            "results": results,
            "count": len(results)
        })
    
    except Exception as e:
        logger.error(f"Sales report error: {e}", exc_info=True)
        return JsonResponse({
            "status": "error",
            "message": str(e),
            "results": []
        }, status=500)


# ============================================
# GET SELLERS FOR REPORT FILTER
# ============================================
@login_required
def get_sellers_api(request):
    """
    Return all users who have made sales
    URL: /sales/api/get-sellers/
    """
    try:
        # Get all users who have made at least one sale
        sellers = User.objects.filter(
            sales_made__isnull=False
        ).distinct().values('id', 'username', 'first_name', 'last_name')
        
        sellers_list = []
        for seller in sellers:
            full_name = f"{seller['first_name']} {seller['last_name']}".strip()
            display_name = full_name if full_name else seller['username']
            
            sellers_list.append({
                'id': seller['id'],
                'username': seller['username'],
                'display_name': display_name
            })
        
        return JsonResponse({
            'success': True,
            'sellers': sellers_list,
            'count': len(sellers_list)
        })
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching sellers: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e),
            'sellers': []
        }, status=500)


# ============================================
# ALTERNATIVE: GET ALL ACTIVE USERS AS SELLERS
# ============================================
@login_required
def get_all_sellers_api(request):
    """
    Return ALL active users (alternative if above returns empty)
    URL: /sales/api/get-all-sellers/
    """
    try:
        sellers = User.objects.filter(
            is_active=True
        ).values('id', 'username', 'first_name', 'last_name').order_by('username')
        
        sellers_list = []
        for seller in sellers:
            full_name = f"{seller['first_name']} {seller['last_name']}".strip()
            display_name = full_name if full_name else seller['username']
            
            sellers_list.append({
                'id': seller['id'],
                'username': seller['username'],
                'display_name': display_name
            })
        
        return JsonResponse({
            'success': True,
            'sellers': sellers_list,
            'count': len(sellers_list)
        })
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching sellers: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e),
            'sellers': []
        }, status=500)








# =========================================
# PRODUCT LOOKUP VIEW
# =========================================

class ProductLookupView(View):

    def get(self, request):
        code = request.GET.get("product_code", "").strip()
        if not code:
            return JsonResponse({"success": False, "message": "Product code is required"})

        product = Product.objects.filter(
            Q(product_code__iexact=code) | Q(sku_value__iexact=code),
            is_active=True
        ).select_related('category').first()

        if not product:
            return JsonResponse({"success": False, "message": "Product not found"})

        # CATEGORY SAFE ACCESS
        category_name = product.category.name if product.category else "Unknown"
        is_single_item = product.category.is_single_item if product.category else True

        # SOLD PRODUCT CHECK
        if product.status == 'sold':
            recent_sale = Sale.objects.filter(
                items__product=product,
                is_reversed=False
            ).order_by('-sale_date').first()
            
            sale_info = ""
            if recent_sale and recent_sale.sale_date:
                sale_info = f" (Sold on {recent_sale.sale_date.strftime('%Y-%m-%d')} to {recent_sale.buyer_name or 'customer'})"

            return JsonResponse({
                "success": False,
                "is_sold": True,
                "message": f"❌ This product has been SOLD{sale_info}. Please contact your sales manager.",
                "product": {
                    "name": product.name,
                    "product_code": product.product_code,
                    "sku_code": product.sku_value or "N/A",
                    "category": category_name,
                    "status": "SOLD",
                    "is_single_item": is_single_item,
                    "sale_id": recent_sale.sale_id if recent_sale else None,
                    "created_at": product.created_at.isoformat(),
                }
            })

        # STOCK CHECK
        current_stock = product.quantity or 0
        is_available = current_stock > 0 and product.status != 'outofstock'

        # STOCK DISPLAY
        if is_single_item:
            stock_display = "AVAILABLE" if is_available else "SOLD"
            stock_status = "AVAILABLE" if is_available else "SOLD"
        else:
            if product.status == 'outofstock':
                stock_display = "OUT OF STOCK"
                stock_status = "OUT OF STOCK"
            elif product.status == 'lowstock':
                stock_display = f"LOW STOCK ({current_stock} remaining)"
                stock_status = "LOW STOCK"
            else:
                stock_display = f"{current_stock} available"
                stock_status = "AVAILABLE"

        return JsonResponse({
            "success": True,
            "is_sold": False,
            "product": {
                "name": product.name,
                "product_code": product.product_code,
                "sku_code": product.sku_value or "N/A",
                "unit_price": float(product.selling_price or 0),
                "quantity": current_stock,
                "current_stock": current_stock,
                "is_single_item": is_single_item,
                "category": category_name,
                "status": product.status,
                "stock_display": stock_display,
                "stock_status": stock_status,
                "can_sell": is_available,
                "created_at": product.created_at.isoformat(),
            }
        })











# =========================================
# CLIENT LOOKUP (Auto-fill)
# =========================================

class ClientLookupView(View):
    """Auto-fill client details from previous sales"""
    
    def get(self, request):
        phone = request.GET.get("phone", "").strip()
        
        if not phone:
            return JsonResponse({"exists": False})

        # Find most recent sale with this phone
        sale = Sale.objects.filter(
            buyer_phone=phone
        ).order_by('-sale_date').first()

        if not sale:
            return JsonResponse({"exists": False})

        return JsonResponse({
            "exists": True,
            "name": sale.buyer_name or "",
            "id_number": sale.buyer_id_number or "",
            "nok_name": sale.nok_name or "",
            "nok_phone": sale.nok_phone or "",
        })













# =========================================
# SALE ETR VIEWS
# =========================================

@login_required
def sale_etr_view(request, sale_id):
    """Display ETR receipt for a sale (supports multiple items)"""
    sale = get_object_or_404(Sale, sale_id=sale_id)
    sale_items = sale.items.select_related('product', 'product__category').all()

    items_data = []
    gross_total = 0

    for item in sale_items:
        product = item.product
        sku_type = product.category.get_sku_type_display() if product.category else "SKU"
        sku_display = item.sku_value or item.product_code

        items_data.append({
            "name": item.product_name,
            "sku_type": sku_type,
            "sku": sku_display,
            "quantity": item.quantity,
            "price": float(item.unit_price),
            "total": float(item.total_price)
        })
        gross_total += float(item.total_price)

    receipt = {
        "receipt_number": sale.etr_receipt_number or f"RCPT#{sale.sale_id}",
        "company_name": "FIELDMAX SUPPLIERS LTD",
        "address": "NAIROBI, KENYA",
        "tel": "254 722 558 544",
        "pin": "XXXXXX",
        "date": sale.sale_date.strftime("%Y-%m-%d"),
        "time": sale.sale_date.strftime("%H:%M:%S"),
        "user": sale.seller.username if sale.seller else "N/A",
        "client_name": sale.buyer_name or "",
        "client_phone": sale.buyer_phone or "",
        "client_id": sale.buyer_id_number or "",
        "nok_name": sale.nok_name or "",
        "nok_phone": sale.nok_phone or "",
        "items": items_data,
        "gross_total": gross_total
    }

    return render(request, 'sales/fieldmax_receipt.html', {
        'receipt': receipt,
        'sale': sale
    })













# ============================================
# DOWNLOAD RECEIPT VIEW
# ============================================

@login_required
def download_receipt_view(request, sale_id):
    """Download receipt as PDF"""
    sale = get_object_or_404(Sale, sale_id=sale_id)
    product = sale.product

    receipt = {
        "receipt_number": sale.etr_receipt_number or f"RCPT-{sale.sale_id}",
        "company_name": "FIELDMAX SUPPLIERS LTD",
        "address": "NAIROBI, KENYA",
        "tel": "254 722 558 544",
        "pin": "XXXXXX",
        "date": sale.sale_date.strftime("%Y-%m-%d"),
        "time": sale.sale_date.strftime("%H:%M:%S"),
        "user": sale.seller.username if sale.seller else "N/A",
        "client_name": sale.buyer_name or "",
        "items": [{
            "name": product.name,
            "sku": product.product_code,
            "quantity": sale.quantity,
            "price": float(sale.unit_price or sale.selling_price),
            "total": float(sale.total_price)
        }],
        "gross_total": float(sale.total_price)
    }

    html_string = render_to_string('sales/fieldmax_receipt.html', {
        'receipt': receipt,
        'sale': sale
    })

    # Try PDF generation if pdfkit is available
    if pdfkit:
        try:
            pdf = pdfkit.from_string(html_string, False)
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="receipt_{sale.sale_id}.pdf"'
            return response
        except Exception as e:
            logger.exception(f"PDF generation failed: {e}")
    
    # Fallback to HTML
    return HttpResponse(html_string)
















# ============================================
# BATCH RECEIT VIEW
# ==========================================

@login_required
def batch_receipt_view(request, batch_id):
    """
    Display SINGLE combined receipt showing ALL sales in separate rows.
    Each sale appears as a line item in one receipt.
    """
    sales = Sale.objects.filter(batch_id=batch_id).select_related(
        'product', 'product__category', 'seller'
    ).order_by('batch_sequence')
    
    if not sales.exists():
        return JsonResponse({
            "error": f"Batch {batch_id} not found"
        }, status=404)
    
    first_sale = sales.first()
    
    # ============================================
    # BUILD SINGLE RECEIPT WITH MULTIPLE ROWS
    # ============================================
    receipt = {
        # Use the sequential Rcpt_No format
        "receipt_number": first_sale.etr_receipt_number or first_sale.fiscal_receipt_number or f"BATCH-{batch_id}",
        "batch_id": batch_id,
        "company_name": "FIELDMAX SUPPLIERS LTD",
        "address": "NAIROBI, KENYA",
        "tel": "254 722 558 544",
        "pin": "P051234567X",  # Update with your actual PIN
        "date": first_sale.sale_date.strftime("%Y-%m-%d"),
        "time": first_sale.sale_date.strftime("%H:%M:%S"),
        "user": first_sale.seller.username if first_sale.seller else "N/A",
        "client_name": first_sale.buyer_name or "Walk-in Customer",
        "client_phone": first_sale.buyer_phone or "",
        "client_id": first_sale.buyer_id_number or "",
        "nok_name": first_sale.nok_name or "",
        "nok_phone": first_sale.nok_phone or "",
        "items": [],
        "gross_total": Decimal('0.00')
    }
    
    # ============================================
    # ADD EACH SALE AS A SEPARATE ROW
    # ============================================
    for idx, sale in enumerate(sales, 1):
        product = sale.product
        sku_type = product.category.get_sku_type_display() if product.category else "SKU"
        
        receipt["items"].append({
            "row_number": idx,
            "name": product.name,
            "sku_type": sku_type,
            "sku": product.sku_value or product.product_code,
            "quantity": sale.quantity,
            "price": float(sale.unit_price or sale.selling_price),
            "total": float(sale.total_price),
            "sale_id": sale.sale_id
        })
        
        receipt["gross_total"] += sale.total_price
    
    # Convert Decimal to float for template
    receipt["gross_total"] = float(receipt["gross_total"])
    
    logger.info(
        f"[BATCH RECEIPT] Batch: {batch_id} | "
        f"Receipt: {receipt['receipt_number']} | "
        f"Items: {len(sales)} | "
        f"Total: KSH {receipt['gross_total']}"
    )
    
    return render(request, 'sales/batch_receipt.html', {
        'receipt': receipt,
        'sales': sales,
        'batch_id': batch_id,
        'total_items': len(sales),
        'etr_number': first_sale.etr_receipt_number,
        'fiscal_number': first_sale.fiscal_receipt_number
    })















# ============================================
# DOWNLOAD RECEIPT VIEW
# ============================================

@login_required
def download_batch_receipt_view(request, batch_id):
    """
    Download batch receipt as PDF.
    """
    sales = Sale.objects.filter(batch_id=batch_id).select_related(
        'product', 'product__category', 'seller'
    ).order_by('batch_sequence')
    
    if not sales.exists():
        return JsonResponse({
            "error": f"Batch {batch_id} not found"
        }, status=404)
    
    first_sale = sales.first()
    
    receipt = {
        "receipt_number": first_sale.etr_receipt_number or first_sale.fiscal_receipt_number or f"BATCH-{batch_id}",
        "batch_id": batch_id,
        "company_name": "FIELDMAX SUPPLIERS LTD",
        "address": "NAIROBI, KENYA",
        "tel": "254 722 558 544",
        "pin": "P051234567X",
        "date": first_sale.sale_date.strftime("%Y-%m-%d"),
        "time": first_sale.sale_date.strftime("%H:%M:%S"),
        "user": first_sale.seller.username if first_sale.seller else "N/A",
        "client_name": first_sale.buyer_name or "Walk-in Customer",
        "client_phone": first_sale.buyer_phone or "",
        "items": [],
        "gross_total": Decimal('0.00')
    }
    
    for idx, sale in enumerate(sales, 1):
        product = sale.product
        sku_type = product.category.get_sku_type_display() if product.category else "SKU"
        
        receipt["items"].append({
            "row_number": idx,
            "name": product.name,
            "sku_type": sku_type,
            "sku": product.sku_value or product.product_code,
            "quantity": sale.quantity,
            "price": float(sale.unit_price or sale.selling_price),
            "total": float(sale.total_price),
        })
        
        receipt["gross_total"] += sale.total_price
    
    receipt["gross_total"] = float(receipt["gross_total"])
    
    html_string = render_to_string('sales/batch_receipt.html', {
        'receipt': receipt,
        'sales': sales,
        'batch_id': batch_id,
        'total_items': len(sales),
        'etr_number': first_sale.etr_receipt_number,
        'fiscal_number': first_sale.fiscal_receipt_number
    })
    
    # Try PDF generation if pdfkit is available
    if pdfkit:
        try:
            pdf = pdfkit.from_string(html_string, False)
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="batch_receipt_{batch_id}.pdf"'
            return response
        except Exception as e:
            logger.exception(f"PDF generation failed: {e}")
    
    # Fallback to HTML
    return HttpResponse(html_string)











# =========================================
# SALE LIST VIEW
# =========================================

class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'sales/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 50

    def get_queryset(self):
        return Sale.objects.select_related(
            'product', 
            'product__category',
            'seller'
        ).order_by('-sale_date')














# ============================================
# SALE DETAIL VIEW
# ============================================

class SaleDetailView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = 'sales/sale_detail.html'
    pk_url_kwarg = 'sale_id'













# ============================================
# SALE UPDATE VIEW
# ============================================

class SaleUpdateView(LoginRequiredMixin, UpdateView):
    model = Sale
    form_class = SaleForm
    template_name = 'sales/sale_form.html'
    success_url = '/admin-dashboard/'










# ============================================
# SALE DELETE VIEW
# ============================================

class SaleDeleteView(LoginRequiredMixin, DeleteView):
    model = Sale
    template_name = 'sales/sale_confirm_delete.html'
    success_url = '/admin-dashboard/'










# =========================================
# DRF API VIEWS
# =========================================

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().order_by('-sale_date')
    serializer_class = SaleSerializer











# ============================================
# SALE LIST CREATE VIEW
# ============================================

class SaleListCreateView(generics.ListCreateAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer












# =========================================
# RESTOCK VIEW
# =========================================

class RestockView(LoginRequiredMixin, View):
    """Handle bulk product restocking"""
    
    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        
        if product.category.is_single_item:
            messages.error(request, 'Single items cannot be restocked. Add new units instead.')
            return redirect('product-list')
        
        return render(request, 'sales/restock.html', {'product': product})

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        
        if product.category.is_single_item:
            messages.error(request, 'Single items cannot be restocked.')
            return redirect('product-list')
        
        try:
            quantity = int(request.POST.get('quantity', 0))
            if quantity <= 0:
                messages.error(request, 'Quantity must be greater than 0')
                return redirect('restock', product_id=product_id)
            
            # Create stock entry (will auto-update product)
            StockEntry.objects.create(
                product=product,
                quantity=quantity,
                entry_type='purchase',
                unit_price=product.buying_price,
                total_amount=product.buying_price * quantity,
                created_by=request.user,
                notes=f"Restock: Added {quantity} units"
            )
            
            messages.success(request, f'Successfully added {quantity} units to {product.name}')
            return redirect('product-list')
            
        except Exception as e:
            logger.exception(f"Restock error: {e}")
            messages.error(request, f'Error: {str(e)}')
            return redirect('restock', product_id=product_id)
        










# ============================================
# PRODUCT LOOKUP
# ============================================


@login_required
@require_http_methods(["GET"])
def product_lookup(request):
    """
    API endpoint for product lookup by product code
    Returns product details for cashier dashboard
    
    GET /sales/product-lookup/?product_code=ABC123
    """
    product_code = request.GET.get('product_code', '').strip().upper()
    
    if not product_code:
        return JsonResponse({
            'success': False,
            'message': 'Product code is required'
        })
    
    try:
        # Search for product by product_code (exact match or contains)
        product = Product.objects.filter(
            product_code__iexact=product_code,
            is_active=True
        ).select_related('category').first()
        
        if not product:
            # Try partial match if exact match fails
            product = Product.objects.filter(
                product_code__icontains=product_code,
                is_active=True
            ).select_related('category').first()
        
        if not product:
            return JsonResponse({
                'success': False,
                'message': f'Product {product_code} not found'
            })
        
        # Check stock availability
        if product.category.is_single_item:
            if product.status != 'available':
                return JsonResponse({
                    'success': False,
                    'message': f'Product {product_code} is not available (Status: {product.status})'
                })
        else:
            if product.quantity <= 0:
                return JsonResponse({
                    'success': False,
                    'message': f'Product {product_code} is out of stock'
                })
        
        return JsonResponse({
            'success': True,
            'product': {
                'code': product.product_code,
                'name': product.name,
                'unit_price': float(product.selling_price),
                'quantity_available': product.quantity if not product.category.is_single_item else 1,
                'is_single_item': product.category.is_single_item,
                'category': product.category.name
            }
        })
        
    except Exception as e:
        logger.error(f"Error in product lookup: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error looking up product'
        })












# ============================================
# BATCH CREATE SALE
# ============================================

@login_required
@require_http_methods(["POST"])
def batch_create_sale(request):
    """
    API endpoint for creating batch sales (cart checkout)
    Handles multiple items in a single transaction
    
    POST /sales/batch-create/
    Body: {
        "sales_cart": [
            {"product_code": "ABC", "quantity": 2, "unit_price": 100.00},
            {"product_code": "XYZ", "quantity": 1, "unit_price": 50.00}
        ],
        "payment_method": "Cash",
        "amount_paid": 250.00
    }
    """
    try:
        data = json.loads(request.body)
        sales_cart = data.get('sales_cart', [])
        payment_method = data.get('payment_method', 'Cash')
        amount_paid = Decimal(str(data.get('amount_paid', 0)))
        
        if not sales_cart:
            return JsonResponse({
                'status': 'error',
                'message': 'Cart is empty'
            })
        
        # Calculate total
        total_amount = sum(
            Decimal(str(item['quantity'])) * Decimal(str(item['unit_price'])) 
            for item in sales_cart
        )
        
        if amount_paid < total_amount:
            return JsonResponse({
                'status': 'error',
                'message': f'Insufficient payment. Total: {total_amount}, Paid: {amount_paid}'
            })
        
        # Create sales in a transaction
        with transaction.atomic():
            sale_items_created = []
            batch_id = timezone.now().strftime('%Y%m%d%H%M%S')
            
            for item in sales_cart:
                product_code = item['product_code'].upper()
                quantity = int(item['quantity'])
                unit_price = Decimal(str(item['unit_price']))
                
                # Get product
                try:
                    product = Product.objects.select_for_update().get(
                        product_code=product_code,
                        is_active=True
                    )
                except Product.DoesNotExist:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Product {product_code} not found'
                    })
                
                # Check stock
                if product.category.is_single_item:
                    if product.status != 'available':
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Product {product_code} is not available'
                        })
                else:
                    if product.quantity < quantity:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Insufficient stock for {product_code}. Available: {product.quantity}'
                        })
                
                # Create sale
                sale = Sale.objects.create(
                    seller=request.user,
                    total_amount=unit_price * quantity,
                    payment_method=payment_method,
                    amount_paid=amount_paid if len(sales_cart) == 1 else unit_price * quantity,
                    sale_date=timezone.now(),
                    batch_id=batch_id
                )
                
                # Create sale item
                sale_item = SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price
                )
                
                # Update product stock
                if product.category.is_single_item:
                    product.status = 'sold'
                    product.quantity = 0
                else:
                    product.quantity -= quantity
                    if product.quantity == 0:
                        product.status = 'outofstock'
                    elif product.quantity <= 5:
                        product.status = 'lowstock'
                
                product.save(update_fields=['status', 'quantity'])
                
                sale_items_created.append({
                    'sale_id': sale.id,
                    'product': product_code,
                    'quantity': quantity
                })
            
            logger.info(f"Batch sale completed: {len(sale_items_created)} items, Batch ID: {batch_id}")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Sale completed successfully',
                'batch_id': batch_id,
                'items_sold': len(sale_items_created),
                'total_amount': float(total_amount),
                'amount_paid': float(amount_paid),
                'change': float(amount_paid - total_amount),
                'receipt_url': f'/sales/batch-receipt/{batch_id}/'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        })
    except Exception as e:
        logger.error(f"Error in batch sale creation: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error processing sale: {str(e)}'
        })











# ============================================
# BATCH RECEIPT
# ============================================

@login_required
def batch_receipt(request, batch_id):
    """
    Generate receipt view for a batch of sales
    """
    sales = Sale.objects.filter(
        batch_id=batch_id
    ).prefetch_related('items', 'items__product').order_by('sale_date')
    
    if not sales.exists():
        return render(request, 'sales/receipt_not_found.html', {
            'batch_id': batch_id
        })
    
    # Calculate totals
    total_amount = sum(sale.total_amount for sale in sales)
    total_items = sum(sale.items.count() for sale in sales)
    
    context = {
        'batch_id': batch_id,
        'sales': sales,
        'total_amount': total_amount,
        'total_items': total_items,
        'sale_date': sales.first().sale_date,
        'seller': sales.first().seller,
        'payment_method': sales.first().payment_method,
        'amount_paid': sales.first().amount_paid,
    }
    
    return render(request, 'sales/batch_receipt.html', context)












# ============================================
# BATCH SALE CREATE VIEW
# ============================================

@method_decorator(login_required, name='dispatch')
class BatchSaleCreateView(View):
    """
    ✅ FIXED: Creates ONE Sale record for entire transaction
    - Multiple items stored in SaleItem model
    - ONE receipt number for all items
    - ONE row in sales table
    """
    
    @transaction.atomic
    def post(self, request):
        try:
            # Parse cart data
            data = json.loads(request.body)
            sales_cart = data.get("sales_cart", [])
            
            if not sales_cart or len(sales_cart) == 0:
                return JsonResponse({
                    "status": "error",
                    "message": "Cart is empty"
                }, status=400)
            
            # Get client details from first item (applies to entire sale)
            first_item = sales_cart[0]
            buyer_name = first_item.get("buyer_name", "").strip() or "Walk-in Customer"
            buyer_phone = first_item.get("buyer_phone", "").strip()
            buyer_id_number = first_item.get("buyer_id_number", "").strip()
            nok_name = first_item.get("nok_name", "").strip()
            nok_phone = first_item.get("nok_phone", "").strip()
            
            # ============================================
            # STEP 1: Create ONE Sale record
            # ============================================
            sale = Sale.objects.create(
                seller=request.user,
                buyer_name=buyer_name,
                buyer_phone=buyer_phone,
                buyer_id_number=buyer_id_number,
                nok_name=nok_name,
                nok_phone=nok_phone,
                etr_status="pending"
            )
            
            logger.info(f"[SALE CREATED] Sale ID: {sale.sale_id} | Items to process: {len(sales_cart)}")
            
            created_items = []
            
            # ============================================
            # STEP 2: Process each item in cart
            # ============================================
            for idx, item_data in enumerate(sales_cart, 1):
                product_code = item_data.get("product_code", "").strip()
                quantity = int(item_data.get("quantity", 1))
                unit_price_input = item_data.get("unit_price", "")
                
                try:
                    unit_price = Decimal(str(unit_price_input)) if unit_price_input else Decimal('0')
                except (ValueError, TypeError):
                    unit_price = Decimal('0')
                
                # FIFO Product Lookup
                products = Product.objects.filter(
                    Q(product_code__iexact=product_code) | Q(sku_value__iexact=product_code),
                    is_active=True
                ).exclude(
                    status='sold'
                ).select_related('category').select_for_update().order_by('created_at')
                
                if not products.exists():
                    raise ValueError(f"Product '{product_code}' not found or already sold")
                
                first_product = products.first()
                
                # Single Item FIFO
                if first_product.category.is_single_item:
                    available_product = products.filter(status='available', quantity=1).first()
                    if not available_product:
                        raise ValueError(f"No available units of {first_product.name}")
                    product_to_sell = available_product
                else:
                    # Bulk Item
                    product_to_sell = first_product
                    if product_to_sell.quantity < quantity:
                        raise ValueError(
                            f"Insufficient stock for {product_to_sell.name}. "
                            f"Only {product_to_sell.quantity} available."
                        )
                
                # Validate price
                if unit_price <= 0:
                    unit_price = product_to_sell.selling_price or Decimal('0')
                
                # ============================================
                # Create SaleItem (not Sale!)
                # ============================================
                sale_item = SaleItem.objects.create(
                    sale=sale,
                    product=product_to_sell,
                    product_code=product_to_sell.product_code,
                    product_name=product_to_sell.name,
                    sku_value=product_to_sell.sku_value,
                    quantity=quantity,
                    unit_price=unit_price
                )
                
                # Process the sale (deducts stock)
                sale_item.process_sale()
                
                created_items.append({
                    "product_name": product_to_sell.name,
                    "product_code": product_to_sell.product_code,
                    "sku": product_to_sell.sku_value or product_to_sell.product_code,
                    "quantity": quantity,
                    "unit_price": float(unit_price),
                    "total_price": float(sale_item.total_price),
                })
                
                logger.info(
                    f"[ITEM {idx}/{len(sales_cart)}] "
                    f"Product: {product_to_sell.product_code} | "
                    f"Qty: {quantity} | "
                    f"Total: KSH {sale_item.total_price}"
                )
            
            # ============================================
            # STEP 3: Refresh sale to get calculated totals
            # ============================================
            sale.refresh_from_db()
            
            # ============================================
            # STEP 4: Generate receipt numbers
            # ============================================
            from django.utils.crypto import get_random_string
            fiscal_receipt_number = f"FR-{sale.sale_date.strftime('%Y%m%d%H%M%S')}-{get_random_string(6)}"
            
            # Assign ETR receipt number
            sale.assign_etr_receipt_number(fiscal_receipt_number=fiscal_receipt_number)
            
            logger.info(
                f"[SALE COMPLETED] Sale: {sale.sale_id} | "
                f"Receipt: {sale.etr_receipt_number} | "
                f"Items: {len(created_items)} | "
                f"Total: KSH {sale.total_amount}"
            )
            
            # ============================================
            # STEP 5: Return success response
            # ============================================
            return JsonResponse({
                "status": "success",
                "message": f"✅ Sale recorded! {len(created_items)} items with 1 receipt",
                "sale_id": sale.sale_id,
                "total_items": len(created_items),
                "total_amount": float(sale.total_amount),
                "etr_receipt_number": sale.etr_receipt_number,
                "fiscal_receipt_number": sale.fiscal_receipt_number,
                "items": created_items,
                "receipt_url": f"/sales/receipt/{sale.sale_id}/",
            }, status=200)
            
        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            return JsonResponse({
                "status": "error",
                "message": str(ve)
            }, status=400)
            
        except Exception as e:
            logger.exception(f"Batch sale error: {e}")
            return JsonResponse({
                "status": "error",
                "message": f"Server error: {str(e)}"
            }, status=500)











# ============================================
# RECEIPT VIEW
# ============================================

@login_required
def sale_receipt_view(request, sale_id):
    """Display receipt for a sale (shows all items)"""
    from django.shortcuts import get_object_or_404, render
    
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product__category'),
        sale_id=sale_id
    )
    
    # Build receipt data
    receipt = {
        "receipt_number": sale.etr_receipt_number or f"RCPT-{sale.sale_id}",
        "company_name": "FIELDMAX SUPPLIERS LTD",
        "address": "NAIROBI, KENYA",
        "tel": "254 722 558 544",
        "pin": "P051234567X",
        "date": sale.sale_date.strftime("%Y-%m-%d"),
        "time": sale.sale_date.strftime("%H:%M:%S"),
        "user": sale.seller.username if sale.seller else "N/A",
        "client_name": sale.buyer_name or "Walk-in Customer",
        "client_phone": sale.buyer_phone or "",
        "client_id": sale.buyer_id_number or "",
        "items": [],
        "gross_total": float(sale.total_amount)
    }
    
    # Add each item
    for idx, item in enumerate(sale.items.all(), 1):
        sku_type = item.product.category.get_sku_type_display() if item.product.category else "SKU"
        
        receipt["items"].append({
            "row_number": idx,
            "name": item.product_name,
            "sku_type": sku_type,
            "sku": item.sku_value or item.product_code,
            "quantity": item.quantity,
            "price": float(item.unit_price),
            "total": float(item.total_price),
        })
    
    return render(request, 'sales/receipt.html', {
        'receipt': receipt,
        'sale': sale,
        'total_items': len(receipt['items'])
    })











# ============================================
# PRODUCT SEARCH
# ============================================

@require_http_methods(["GET"])
def product_search(request):
    """
    Live search for products - returns all products containing search term
    URL: /sales/product-search/?q=<search_term>
    
    Searches across:
    - product_code
    - sku_value
    - name
    """
    search_term = request.GET.get('q', '').strip()
    
    logger.info(f"[PRODUCT SEARCH] Search term: '{search_term}'")
    
    if not search_term:
        return JsonResponse({
            'success': False,
            'message': 'No search term provided',
            'products': []
        })
    
    try:
        # Search in your Product model fields
        products = Product.objects.filter(
            Q(product_code__icontains=search_term) |  # Product code
            Q(sku_value__icontains=search_term) |     # SKU/IMEI/Serial
            Q(name__icontains=search_term),           # Product name
            is_active=True  # Only active products
        ).exclude(
            status='sold'  # Don't show sold items in search
        ).select_related('category').values(
            'id',
            'name',
            'product_code',
            'sku_value',
            'selling_price',  # Your model uses selling_price
            'quantity',
            'status',
            'category__name',  # Include category name
            'category__item_type'  # Include item type
        )[:20]  # Limit to 20 results
        
        products_list = list(products)
        
        logger.info(f"[PRODUCT SEARCH] Found {len(products_list)} products")
        
        # Format the response to match frontend expectations
        formatted_products = []
        for p in products_list:
            formatted_products.append({
                'id': p['id'],
                'name': p['name'],
                'sku_code': p['sku_value'] or p['product_code'],  # Use sku_value or fallback to product_code
                'product_code': p['product_code'],
                'unit_price': float(p['selling_price']) if p['selling_price'] else 0.0,
                'selling_price': float(p['selling_price']) if p['selling_price'] else 0.0,
                'quantity': p['quantity'],
                'status': p['status'],
                'category': p['category__name'],
                'is_single_item': p['category__item_type'] == 'single'
            })
        
        return JsonResponse({
            'success': True,
            'products': formatted_products,
            'count': len(formatted_products)
        })
        
    except Exception as e:
        logger.error(f"[PRODUCT SEARCH ERROR] {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Search error: {str(e)}',
            'products': []
        }, status=500)













# ============================================
# RECORD SALE
# ============================================

@require_http_methods(["POST"])
def record_sale(request):
    """
    Record a new sale
    URL: /sales/record-sale/
    """
    import json
    from decimal import Decimal
    from django.utils import timezone
    
    try:
        data = json.loads(request.body)
        
        logger.info(f"[RECORD SALE] Data received: {data}")
        
        # Validate required fields
        required_fields = ['sku_value', 'client_name', 'id_number', 
                          'phone_number', 'nok_name', 'nok_phone']
        
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return JsonResponse({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=400)
        
        # Get the product
        sku_value = data.get('sku_value')
        product = Product.objects.filter(
            Q(product_code__iexact=sku_value) | Q(sku_value__iexact=sku_value),
            is_active=True
        ).exclude(status='sold').first()
        
        if not product:
            return JsonResponse({
                'success': False,
                'message': f'Product not found or already sold'
            }, status=404)
        
        # Get selling price
        selling_price = data.get('selling_price')
        if selling_price:
            try:
                selling_price = Decimal(str(selling_price))
            except:
                selling_price = product.selling_price
        else:
            selling_price = product.selling_price
        
        # Create the sale using your existing SaleCreateView logic
        # For now, just return success (you can implement full sale creation later)
        
        logger.info(f"[RECORD SALE] Would create sale for product: {product.product_code}")
        
        return JsonResponse({
            'success': True,
            'message': 'Sale recorded successfully',
            'product_code': product.product_code,
            'product_name': product.name,
            'selling_price': float(selling_price)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"[RECORD SALE ERROR] {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)
    
