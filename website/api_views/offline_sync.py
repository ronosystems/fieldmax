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
# OFFLINE DATA - PUBLIC ENDPOINT
# ============================================
@csrf_exempt
@require_http_methods(["GET"])
# Cache for 5 minutes (300 seconds) for offline use
@cache_page(300)
def get_offline_data(request):
    """
    Get essential data for offline use
    PUBLIC endpoint - no authentication required
    """
    try:
        from inventory.models import Product, Category
        from website.models import Customer
        
        # Get all products (remove is_active filter if field doesn't exist)
        products = list(Product.objects.all().values(
            'id', 'name', 'sku_value', 'selling_price', 'price',
            'quantity', 'category_id', 'description', 'image'
        )[:200])  # Limit for offline cache
        
        # Get all categories - FIXED: Using correct field names
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
            'currency': 'KES'
        }
        
        data = {
            'products': products,
            'categories': categories,
            'customer_types': customer_types,
            'settings': settings,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"Offline data sync: {len(products)} products, {len(categories)} categories")
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error getting offline data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to load offline data'
        }, status=500)

# ============================================
# OFFLINE SYNC - AUTHENTICATED ENDPOINT
# ============================================
@login_required
@csrf_exempt
@require_http_methods(["POST"])
def sync_offline_queue(request):  # CHANGED: Renamed from sync_offline_data to sync_offline_queue
    """
    Sync offline data back to server
    Requires authentication
    """
    try:
        data = json.loads(request.body)
        
        # Process offline sales
        sales_data = data.get('sales', [])
        created_count = 0
        
        for sale in sales_data:
            # Process each sale
            # Add your sales processing logic here
            pass
        
        return JsonResponse({
            'success': True,
            'message': f'Synced {created_count} sales'
        })
        
    except Exception as e:
        logger.error(f"Error syncing offline data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to sync offline data'
        }, status=500)
