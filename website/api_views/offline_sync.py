import datetime
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.views.decorators.cache import cache_page

logger = logging.getLogger(__name__)

# ============================================
# HELPER FUNCTIONS
# ============================================

def serialize_cloudinary_image(image_field):
    """Safely convert CloudinaryResource to URL string"""
    if not image_field:
        return None
    
    try:
        # Try different methods to get URL
        if hasattr(image_field, 'url'):
            url = image_field.url
            if callable(url):
                return str(url())
            return str(url)
        elif hasattr(image_field, 'build_url'):
            return str(image_field.build_url())
        else:
            return str(image_field)
    except Exception as e:
        logger.warning(f"Failed to serialize Cloudinary image: {e}")
        return None

# ============================================
# OFFLINE DATA - PUBLIC ENDPOINT
# ============================================
@csrf_exempt
@require_http_methods(["GET"])
@cache_page(300)
def get_offline_data(request):
    """
    Get essential data for offline use
    PUBLIC endpoint - no authentication required
    """
    try:
        from inventory.models import Product, Category
        
        # Get all products with proper serialization
        products_data = []
        products = Product.objects.all().select_related('category')[:200]  # Limit for offline cache
        
        for product in products:
            # Start with basic fields
            product_dict = {
                'id': product.id,
                'name': product.name if hasattr(product, 'name') else '',
                'sku_value': product.sku_value if hasattr(product, 'sku_value') else '',
                'selling_price': float(product.selling_price) if hasattr(product, 'selling_price') and product.selling_price else 0.0,
                'price': float(product.price) if hasattr(product, 'price') and product.price else 0.0,
                'quantity': product.quantity if hasattr(product, 'quantity') else 0,
                'category_id': product.category_id,
                'description': product.description if hasattr(product, 'description') else '',
                'image_url': serialize_cloudinary_image(product.image) if hasattr(product, 'image') else None,
                'category_name': product.category.name if product.category else '',
            }
            
            # Safely add optional fields if they exist
            optional_fields = ['barcode', 'min_stock', 'cost_price', 'alert_quantity']
            
            for field in optional_fields:
                if hasattr(product, field):
                    value = getattr(product, field)
                    if value is not None:
                        product_dict[field] = value
            
            products_data.append(product_dict)
        
        # Get all categories
        categories = list(Category.objects.all().values(
            'id', 'name', 'item_type', 'category_code', 'sku_type'
        ))
        
        # Customer types (generic, no personal data)
        customer_types = [
            {'id': 'cash', 'name': 'Cash Customer'},
            {'id': 'credit', 'name': 'Credit Customer'},
        ]
        
        # Basic company info
        settings = {
            'vat_rate': 0.16,
            'company_name': 'FIELDMAX SUPPLIERS LTD',
            'receipt_prefix': 'RCT',
            'currency': 'KES',
            'offline_sync_time': timezone.now().isoformat(),
            'version': '1.0'
        }
        
        data = {
            'products': products_data,
            'categories': categories,
            'customer_types': customer_types,
            'settings': settings,
            'timestamp': timezone.now().isoformat(),
            'counts': {
                'products': len(products_data),
                'categories': len(categories)
            }
        }
        
        logger.info(f"✅ Offline data sync: {len(products_data)} products, {len(categories)} categories")
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"❌ Error getting offline data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Failed to load offline data. Please check server logs.'
        }, status=500)

# ============================================
# OFFLINE SYNC - AUTHENTICATED ENDPOINT
# ============================================
@login_required
@csrf_exempt
@require_http_methods(["POST"])
def sync_offline_queue(request):
    """
    Sync offline data back to server
    Requires authentication
    """
    try:
        data = json.loads(request.body)
        
        # Process offline sales
        sales_data = data.get('sales', [])
        created_count = 0
        
        from sales.models import Sale  # Import here to avoid circular imports
        
        with transaction.atomic():
            for sale_data in sales_data:
                try:
                    # Create sale from offline data
                    sale = Sale.objects.create(
                        invoice_number=sale_data.get('invoice_number'),
                        customer_name=sale_data.get('customer_name', 'Cash Customer'),
                        total_amount=sale_data.get('total_amount', 0),
                        amount_paid=sale_data.get('amount_paid', 0),
                        balance=sale_data.get('balance', 0),
                        payment_method=sale_data.get('payment_method', 'cash'),
                        sale_type=sale_data.get('sale_type', 'retail'),
                        is_offline=True,
                        offline_sync_time=timezone.now(),
                        created_by=request.user
                    )
                    
                    # Add sale items if provided
                    items = sale_data.get('items', [])
                    for item_data in items:
                        # Create sale item
                        # You'll need to adjust this based on your SaleItem model
                        pass
                    
                    created_count += 1
                    
                except Exception as item_error:
                    logger.error(f"Failed to process sale: {item_error}")
                    continue
        
        return JsonResponse({
            'success': True,
            'message': f'Synced {created_count} offline sales',
            'synced_count': created_count
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error syncing offline data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to sync offline data',
            'detail': str(e)
        }, status=500)