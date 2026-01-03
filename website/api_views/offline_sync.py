import datetime
# Create a new file: website/views/offline_sync.py
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
import json
import logging






logger = logging.getLogger(__name__)




# ============================================
# OFLINE QUEUE
# ============================================
@login_required
@require_http_methods(["POST"])
def sync_offline_queue(request):
    """
    Process queued offline requests
    """
    try:
        data = json.loads(request.body)
        queue = data.get('queue', [])
        
        results = {
            'success': [],
            'failed': [],
            'conflicts': []
        }
        
        for item in queue:
            try:
                result = process_offline_item(request, item)
                if result['status'] == 'success':
                    results['success'].append({
                        'id': item['id'],
                        'result': result
                    })
                elif result['status'] == 'conflict':
                    results['conflicts'].append({
                        'id': item['id'],
                        'conflict': result
                    })
                else:
                    results['failed'].append({
                        'id': item['id'],
                        'error': result.get('error')
                    })
            except Exception as e:
                logger.error(f"Error processing offline item: {e}")
                results['failed'].append({
                    'id': item['id'],
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'summary': {
                'total': len(queue),
                'success': len(results['success']),
                'failed': len(results['failed']),
                'conflicts': len(results['conflicts'])
            }
        })
        
    except Exception as e:
        logger.error(f"Sync queue error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)







# ============================================
# OFLINE ITEM
# ============================================
def process_offline_item(request, item):
    """
    Process a single offline queued item
    """
    item_type = item.get('type')
    data = item.get('data', {})
    timestamp = item.get('timestamp')
    
    try:
        if item_type == 'sale':
            return process_offline_sale(request, data, timestamp)
        elif item_type == 'stock_update':
            return process_offline_stock_update(request, data, timestamp)
        elif item_type == 'customer':
            return process_offline_customer(request, data, timestamp)
        else:
            return {
                'status': 'error',
                'error': f'Unknown item type: {item_type}'
            }
    except Exception as e:
        logger.error(f"Error processing {item_type}: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }









# ============================================
# OFLINE SALE
# ============================================
@transaction.atomic
def process_offline_sale(request, data, timestamp):
    """
    Process an offline sale transaction
    """
    from sales.models import Sale, SaleItem
    from inventory.models import Product
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Check for conflicts
    conflicts = check_sale_conflicts(data)
    if conflicts:
        return {
            'status': 'conflict',
            'conflicts': conflicts,
            'data': data
        }
    
    # Create sale
    sale = Sale.objects.create(
        customer_name=data.get('customer_name'),
        customer_phone=data.get('customer_phone'),
        total_amount=data.get('total_amount', 0),
        payment_method=data.get('payment_method', 'cash'),
        created_by=request.user,
        created_at=timestamp,
        is_synced=True,
        offline_created=True
    )
    
    # Create sale items
    for item_data in data.get('items', []):
        product = Product.objects.get(id=item_data['product_id'])
        
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price'],
            total_price=item_data['total_price']
        )
        
        # Update stock
        product.quantity -= item_data['quantity']
        product.save()
    
    logger.info(f"Synced offline sale: {sale.receipt_number}")
    
    return {
        'status': 'success',
        'sale_id': sale.id,
        'receipt_number': sale.receipt_number
    }








# ============================================
# CHECK SALE 
# ============================================
def check_sale_conflicts(data):
    """
    Check for conflicts in offline sale data
    """
    from inventory.models import Product
    
    conflicts = []
    
    for item in data.get('items', []):
        try:
            product = Product.objects.get(id=item['product_id'])
            
            # Check if enough stock is available
            if product.quantity < item['quantity']:
                conflicts.append({
                    'type': 'insufficient_stock',
                    'product': product.name,
                    'requested': item['quantity'],
                    'available': product.quantity
                })
            
            # Check if price has changed significantly
            price_diff = abs(product.selling_price - item['unit_price'])
            if price_diff > (product.selling_price * 0.1):  # 10% difference
                conflicts.append({
                    'type': 'price_changed',
                    'product': product.name,
                    'offline_price': item['unit_price'],
                    'current_price': product.selling_price
                })
        except Product.DoesNotExist:
            conflicts.append({
                'type': 'product_not_found',
                'product_id': item['product_id']
            })
    
    return conflicts






# ============================================
# OFLINE STOCK UPDATE
# ============================================
@transaction.atomic
def process_offline_stock_update(request, data, timestamp):
    """
    Process an offline stock update
    """
    from inventory.models import Product, StockEntry
    
    product = Product.objects.get(id=data['product_id'])
    
    # Check for conflicts
    if product.updated_at > datetime.datetime.fromisoformat(timestamp):
        return {
            'status': 'conflict',
            'conflict': {
                'type': 'outdated_update',
                'product': product.name,
                'offline_timestamp': timestamp,
                'server_timestamp': product.updated_at.isoformat()
            }
        }
    
    # Create stock entry
    stock_entry = StockEntry.objects.create(
        product=product,
        entry_type=data.get('entry_type', 'purchase'),
        quantity=data['quantity'],
        unit_cost=data.get('unit_cost'),
        reference=data.get('reference', 'OFFLINE'),
        notes=f"Synced from offline. Original timestamp: {timestamp}",
        created_by=request.user,
        is_synced=True
    )
    
    # Update product quantity
    if data.get('entry_type') == 'purchase':
        product.quantity += data['quantity']
    else:
        product.quantity -= data['quantity']
    
    product.save()
    
    logger.info(f"Synced offline stock update for: {product.name}")
    
    return {
        'status': 'success',
        'stock_entry_id': stock_entry.id
    }







# ============================================
# OFLINE CUSTOMER
# ============================================
def process_offline_customer(request, data, timestamp):
    """
    Process an offline customer creation
    """
    from website.models import Customer
    
    # Check if customer already exists by phone or email
    existing = Customer.objects.filter(
        phone=data['phone']
    ).first()
    
    if existing:
        return {
            'status': 'conflict',
            'conflict': {
                'type': 'customer_exists',
                'existing_customer': {
                    'id': existing.id,
                    'name': existing.full_name,
                    'phone': existing.phone
                }
            }
        }
    
    # Create customer - use full_name field
    customer = Customer.objects.create(
        full_name=data['name'],
        phone=data['phone'],
        email=data.get('email', ''),
        address=data.get('address', ''),
        created_by=request.user,
        is_synced=True
    )
    
    logger.info(f"Synced offline customer: {customer.full_name}")
    
    return {
        'status': 'success',
        'customer_id': customer.id
    }








# ============================================
# OFLINE DATA
# ============================================
@login_required
def get_offline_data(request):
    """
    Get essential data for offline use
    """
    from inventory.models import Product, Category
    from website.models import Customer
    from django.db.models import F
    
    try:
        data = {
            'products': list(Product.objects.filter(
                is_active=True
            ).values(
                'id', 'name', 'sku_value', 'selling_price', 
                'quantity', 'category__name'
            )[:500]),  # Limit to 500 most recent
            
            'categories': list(Category.objects.values(
                'id', 'name', 'category_code'  # Already fixed this one
            )),
            
            # FIX: Change 'name' to 'full_name'
            'customers': list(Customer.objects.values(
                'id', 'full_name', 'phone', 'email'  # Changed 'name' to 'full_name'
            )[:200]),  # Limit to 200 most recent
            
            'settings': {
                'vat_rate': 0.16,
                'company_name': 'FIELDMAX SUPPLIERS LTD',
                'receipt_prefix': 'RCT'
            },
            
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        logger.error(f"Error getting offline data: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    

    





# ============================================
# SYNC  DATA OFLINE
# ============================================
def sync_offline_requests(request):
    """Endpoint for syncing queued offline requests"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            requests = data.get('requests', [])
            results = []
            
            for req in requests:
                try:
                    # Process each queued request
                    # This would be specific to your application logic
                    result = {
                        'id': req['id'],
                        'success': True,
                        'timestamp': timezone.now().isoformat()
                    }
                    results.append(result)
                except Exception as e:
                    result = {
                        'id': req['id'],
                        'success': False,
                        'error': str(e)
                    }
                    results.append(result)
            
            return JsonResponse({
                'success': True,
                'results': results,
                'synced_at': timezone.now().isoformat()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)