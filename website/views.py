from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.contrib.auth.models import User
from sales.models import Sale
from users.models import Profile 
from django.utils import timezone
from django.urls import reverse
from django.db.models import Sum, Q, F, DecimalField, Count
from inventory.models import Product, Category, StockEntry
from decimal import Decimal
import logging
from datetime import timedelta
from django.http import JsonResponse
import json
from django.db import transaction
from sales.models import Sale, SaleItem
from django.views.decorators.csrf import csrf_exempt
from .models import PendingOrder, PendingOrderItem
from django.views.generic import ListView
from django.conf import settings  
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from .models import Order, Customer





logger = logging.getLogger(__name__)






# ============================================
# HOME VIEW -
# ============================================

def home(request):
    """
    Home page with top 12 most frequently sold products
    """
    # Dashboard URL logic
    dashboard_url = '#'
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile:
            role = request.user.profile.role
            if role == 'admin':
                dashboard_url = '/admin-dashboard/'
            elif role == 'manager':
                dashboard_url = '/manager-dashboard/'
            elif role == 'agent':
                dashboard_url = '/agent-dashboard/'
            elif role == 'cashier':
                dashboard_url = '/cashier-dashboard/'
        elif request.user.is_superuser:
            dashboard_url = '/admin-dashboard/'
    
    # Get top 12 best-selling items
    best_sellers = []
    
    try:
        # Method 1: Just count all sales (no status filter if Sale doesn't have status field)
        best_sellers = Product.objects.filter(
            sale_items__isnull=False  # Has at least one sale
        ).annotate(
            times_ordered=Count('sale_items__id', distinct=True)
        ).filter(
            Q(status='available') | Q(status='lowstock')
        ).order_by('-times_ordered')[:12]
        
    except Exception as e:
        
        # Fallback: Show newest available products
        best_sellers = Product.objects.filter(
            Q(status='available') | Q(status='lowstock')
        ).order_by('-created_at')[:12]
    
    # If less than 12 products, fill with newest
    try:
        count = best_sellers.count() if hasattr(best_sellers, 'count') else len(best_sellers)
        
        if count < 12:
            if hasattr(best_sellers, 'values_list'):
                best_seller_ids = list(best_sellers.values_list('id', flat=True))
            else:
                best_seller_ids = [p.id for p in best_sellers]
            
            remaining_count = 12 - count
            
            newest_products = Product.objects.filter(
                Q(status='available') | Q(status='lowstock')
            ).exclude(
                id__in=best_seller_ids
            ).order_by('-created_at')[:remaining_count]
            
            from itertools import chain
            best_sellers = list(chain(best_sellers, newest_products))
        else:
            best_sellers = list(best_sellers) if not isinstance(best_sellers, list) else best_sellers
            
    except Exception as e:
        best_sellers = Product.objects.filter(
            Q(status='available') | Q(status='lowstock')
        ).order_by('-created_at')[:12]
    
    context = {
        'page_title': 'Home - Fieldmax | Premium Tech at Unbeatable Prices',
        'dashboard_url': dashboard_url,
        'featured_products': best_sellers,
    }
    
    return render(request, 'website/home.html', context)







# ============================================
# HOME STATS -
# ============================================

@require_http_methods(["GET"])
def home_stats(request):
    """
    API endpoint to fetch homepage statistics
    Returns: JSON with total products, customers, and satisfaction rate
    """
    try:
        # Get total products (only available and low stock)
        total_products = Product.objects.filter(
            Q(status='available') | Q(status='lowstock')
        ).count()
        
        # Get total customers (or use total orders as proxy)
        # If you have a Customer model:
        total_customers = Customer.objects.filter(is_active=True).count()
        # OR if you're counting unique customers from orders:
        # total_customers = Order.objects.values('customer_email').distinct().count()
        
        # Calculate satisfaction rate from completed orders
        # Assuming you have a rating field or feedback system
        completed_orders = Order.objects.filter(status='completed')
        if completed_orders.exists():
            # If you have a rating field:
            # satisfaction = completed_orders.aggregate(Avg('rating'))['rating__avg']
            # satisfaction = round(satisfaction * 20) if satisfaction else 98  # Convert to percentage
            
            # OR use successful delivery rate:
            total_orders = Order.objects.count()
            successful_orders = completed_orders.count()
            satisfaction = round((successful_orders / total_orders) * 100) if total_orders > 0 else 98
        else:
            satisfaction = 98  # Default value
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_products': total_products,
                'total_customers': total_customers,
                'satisfaction': satisfaction
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'stats': {
                'total_products': 0,
                'total_customers': 0,
                'satisfaction': 0
            }
        }, status=500)





# ============================================
# FEATURED PRODUCTS -
# ============================================

@require_http_methods(["GET"])
def featured_products(request):
    """
    API endpoint to fetch featured/best-selling products
    Returns: JSON with product details including emoji representation
    """
    try:
        # Get featured products (most sold or marked as featured)
        # Option 1: Get products with most orders
        # You'll need to have a way to track sales
        
        # Option 2: Get products marked as featured
        products = Product.objects.filter(
            Q(status='available') | Q(status='lowstock'),
            is_featured=True  # Add this field to your model
        ).order_by('-created_at')[:8]  # Limit to 8 products
        
        # OR get best sellers by counting related orders
        # products = Product.objects.filter(
        #     Q(status='available') | Q(status='lowstock')
        # ).annotate(
        #     order_count=Count('orderitem')
        # ).order_by('-order_count')[:8]
        
        product_list = []
        for product in products:
            # Determine badge based on status
            badge = None
            if product.status == 'lowstock':
                badge = 'LOW STOCK'
            elif product.status == 'available' and product.quantity < 5:
                badge = 'HURRY UP!'
            
            # Get emoji based on category or product type
            emoji = get_product_emoji(product)
            
            product_list.append({
                'id': product.id,
                'name': product.name,
                'price': float(product.selling_price),
                'code': product.product_code,
                'emoji': emoji,
                'badge': badge,
                'is_single_item': product.category.is_single_item if hasattr(product, 'category') else False,
                'quantity': product.quantity,
                'image_url': product.image.url if product.image else None
            })
        
        return JsonResponse({
            'success': True,
            'products': product_list,
            'count': len(product_list)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'products': []
        }, status=500)





# ============================================
# PRODUCT EMOJI-
# ============================================

def get_product_emoji(product):
    """
    Helper function to return emoji based on product category or type
    """
    # You can customize this based on your product categories
    emoji_map = {
        'phone': '📱',
        'smartphone': '📱',
        'laptop': '💻',
        'tablet': '📲',
        'headphone': '🎧',
        'earphone': '🎧',
        'speaker': '🔊',
        'smartwatch': '⌚',
        'watch': '⌚',
        'camera': '📷',
        'charger': '🔌',
        'cable': '🔌',
        'case': '📦',
        'cover': '📦',
        'protector': '🛡️',
        'power bank': '🔋',
        'battery': '🔋',
        'mouse': '🖱️',
        'keyboard': '⌨️',
        'gaming': '🎮',
        'console': '🎮',
    }
    
    # Check product name or category for keywords
    product_name = product.name.lower()
    for keyword, emoji in emoji_map.items():
        if keyword in product_name:
            return emoji
    
    # Check category if available
    if hasattr(product, 'category') and product.category:
        category_name = product.category.name.lower()
        for keyword, emoji in emoji_map.items():
            if keyword in category_name:
                return emoji
    
    # Default emoji
    return '📦'






# ============================================
# TRENDING STATS -
# ============================================

@require_http_methods(["GET"])
def trending_stats(request):
    """
    API endpoint to get trending products and recent activity stats
    """
    try:
        # Get recent orders (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_orders = Order.objects.filter(
            created_at__gte=week_ago
        ).count()
        
        # Get trending products (most viewed/ordered in last 7 days)
        # This assumes you have a view_count or order tracking
        trending = Product.objects.filter(
            Q(status='available') | Q(status='lowstock')
        ).order_by('-view_count')[:5]  # Add view_count field to track views
        
        trending_list = [{
            'id': p.id,
            'name': p.name,
            'price': float(p.selling_price),
            'views': getattr(p, 'view_count', 0)
        } for p in trending]
        
        return JsonResponse({
            'success': True,
            'data': {
                'recent_orders': recent_orders,
                'trending_products': trending_list
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)








# ============================================
# PRODUCT INCREAMENT -
# ============================================

# Optional: View to increment product view count
@require_http_methods(["POST"])
@csrf_exempt
def increment_product_view(request, product_id):
    """
    Increment view count when a product is viewed
    """
    try:
        product = Product.objects.get(id=product_id)
        if hasattr(product, 'view_count'):
            product.view_count += 1
            product.save(update_fields=['view_count'])
        
        return JsonResponse({
            'success': True,
            'view_count': getattr(product, 'view_count', 0)
        })
    
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)




# ============================================
# DASHBOARD URL
# ============================================

def dashboard_url(request):
    """Make dashboard URL available globally in all templates"""
    url = '#'
    
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile:
            role = request.user.profile.role
            if role == 'admin':
                url = '/admin-dashboard/'
            elif role == 'manager':
                url = '/manager-dashboard/'
            elif role == 'agent':
                url = '/agent-dashboard/'
            elif role == 'cashier':
                url = '/cashier-dashboard/'
        elif request.user.is_superuser:
            url = '/admin-dashboard/'
    
    return {'dashboard_url': url}








# ============================================
# PRODUCT PAGE
# ============================================

@require_http_methods(["GET"])
def products_page(request):
    """
    Products listing page
    """
    from inventory.models import Product
    
    products = Product.objects.filter(
        is_active=True,
        status__in=['available', 'lowstock']
    ).select_related('category').order_by('-created_at')
    
    context = {
        'page_title': 'Shop - Fieldmax',
        'products': products
    }
    
    return render(request, 'website/products.html', context)









# ============================================
# API FEATURED PRODUCT
# ============================================

@require_http_methods(["GET"])
def api_featured_products(request):
    """
    API endpoint to get featured/best-selling products for home page
    URL: /api/featured-products/
    
    Returns up to 8 products with highest sales or newest arrivals
    """
    try:
        # Get products with sales count
        products = Product.objects.filter(
            is_active=True,
            status__in=['available', 'lowstock']  # Only show available products
        ).select_related('category').annotate(
            sales_count=Count('sale_items')
        ).order_by('-sales_count', '-created_at')[:8]
        
        product_list = []
        
        for product in products:
            # Determine badge
            badge = 'HOT' if product.sales_count > 5 else 'NEW'
            if product.status == 'lowstock':
                badge = 'SALE'
            
            # Get product emoji based on category
            emoji = '📱'  # Default
            if product.category:
                category_name = product.category.name.lower()
                if 'phone' in category_name or 'mobile' in category_name:
                    emoji = '📱'
                elif 'headphone' in category_name or 'earphone' in category_name:
                    emoji = '🎧'
                elif 'watch' in category_name:
                    emoji = '⌚'
                elif 'accessory' in category_name or 'cable' in category_name:
                    emoji = '🔌'
                elif 'screen' in category_name or 'protector' in category_name:
                    emoji = '🛡️'
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'product_code': product.product_code,
                'price': float(product.selling_price or 0),
                'category': product.category.name if product.category else 'Uncategorized',
                'status': product.status,
                'quantity': product.quantity or 0,
                'is_single_item': product.category.is_single_item if product.category else False,
                'badge': badge,
                'emoji': emoji,
                'image': None  # We'll handle images separately
            }
            
            product_list.append(product_data)
        
        logger.info(f"[API] Returned {len(product_list)} featured products")
        
        return JsonResponse({
            'success': True,
            'products': product_list,
            'count': len(product_list)
        })
        
    except Exception as e:
        logger.error(f"[API ERROR] Featured products: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e),
            'products': []
        }, status=500)









# ============================================
# API  HOME STATS
# ============================================

@require_http_methods(["GET"])
def api_home_stats(request):
    """
    API endpoint for homepage statistics
    URL: /api/home-stats/
    """
    try:
        # Total products in stock
        total_products = Product.objects.filter(
            is_active=True,
            quantity__gt=0
        ).count()
        
        # Total customers (unique buyers)
        total_customers = Sale.objects.filter(
            buyer_name__isnull=False
        ).values('buyer_phone').distinct().count()
        
        # Calculate satisfaction (mock for now, can be based on returns vs sales)
        total_sales = Sale.objects.filter(is_reversed=False).count()
        total_returns = Sale.objects.filter(is_reversed=True).count()
        
        if total_sales > 0:
            satisfaction = int(((total_sales - total_returns) / total_sales) * 100)
        else:
            satisfaction = 98  # Default
        
        stats = {
            'total_products': total_products,
            'total_customers': min(total_customers * 1000, 100000),  # Scale for display
            'satisfaction': satisfaction,
            'support': '24/7'
        }
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"[API ERROR] Home stats: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e),
            'stats': {
                'total_products': 1000,
                'total_customers': 50000,
                'satisfaction': 98,
                'support': '24/7'
            }
        })







# ============================================
# API PRODUCTS  CATEGORY
# ============================================

@require_http_methods(["GET"])
def api_product_categories(request):
    """
    Get all active categories with product counts
    URL: /api/categories/
    """
    try:
        categories = Category.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        ).filter(product_count__gt=0)
        
        category_list = []
        for cat in categories:
            category_list.append({
                'id': cat.id,
                'name': cat.name,
                'code': cat.category_code,
                'item_type': cat.get_item_type_display(),
                'product_count': cat.product_count
            })
        
        return JsonResponse({
            'success': True,
            'categories': category_list
        })
        
    except Exception as e:
        logger.error(f"[API ERROR] Categories: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e),
            'categories': []
        }, status=500)








# ============================================
# API QUICK SEARCH
# ============================================

@require_http_methods(["POST"])
def api_quick_search(request):
    """
    Quick product search for home page search bar
    URL: /api/quick-search/
    """
    import json
    
    try:
        data = json.loads(request.body)
        search_term = data.get('search', '').strip()
        
        if not search_term or len(search_term) < 2:
            return JsonResponse({
                'success': False,
                'message': 'Search term too short',
                'products': []
            })
        
        # Search products
        products = Product.objects.filter(
            Q(name__icontains=search_term) |
            Q(product_code__icontains=search_term) |
            Q(sku_value__icontains=search_term),
            is_active=True
        ).select_related('category')[:10]
        
        results = []
        for product in products:
            results.append({
                'id': product.id,
                'name': product.name,
                'product_code': product.product_code,
                'price': float(product.selling_price or 0),
                'category': product.category.name if product.category else 'Other',
                'status': product.status,
                'url': f'/products/{product.id}/'  # Update with your product detail URL
            })
        
        return JsonResponse({
            'success': True,
            'products': results,
            'count': len(results)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON',
            'products': []
        }, status=400)
    except Exception as e:
        logger.error(f"[API ERROR] Quick search: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e),
            'products': []
        }, status=500)











# ============================================
# SHOPING CART
# ============================================

def shopping_cart(request):
    """Display shopping cart page"""
    return render(request, 'website/cart.html', {
        'page_title': 'Shopping Cart - Fieldmax'
    })








# ============================================
# VALIDATE CART
# ============================================

@require_http_methods(["POST"])
def validate_cart(request):
    """
    Validate cart items against current database inventory
    Returns updated prices and availability
    """
    try:
        data = json.loads(request.body)
        cart_items = data.get('cart', [])
        
        validated_items = []
        total = 0
        errors = []
        
        for item in cart_items:
            product_id = item.get('id')
            quantity = item.get('quantity', 1)
            
            try:
                product = Product.objects.get(id=product_id, is_active=True)
                
                # Check availability
                if product.status == 'sold':
                    errors.append(f"{product.name} has been sold")
                    continue
                
                if product.category.is_single_item and quantity > 1:
                    errors.append(f"{product.name} is a single item (quantity must be 1)")
                    quantity = 1
                
                if not product.category.is_single_item and product.quantity < quantity:
                    errors.append(f"Only {product.quantity} units of {product.name} available")
                    quantity = product.quantity
                
                # Validate price hasn't changed
                current_price = float(product.selling_price or 0)
                cart_price = float(item.get('price', 0))
                
                price_changed = abs(current_price - cart_price) > 0.01
                
                validated_item = {
                    'id': product.id,
                    'name': product.name,
                    'product_code': product.product_code,
                    'price': current_price,
                    'old_price': cart_price if price_changed else None,
                    'quantity': quantity,
                    'max_quantity': product.quantity if not product.category.is_single_item else 1,
                    'is_single_item': product.category.is_single_item,
                    'subtotal': current_price * quantity,
                    'available': True
                }
                
                validated_items.append(validated_item)
                total += validated_item['subtotal']
                
            except Product.DoesNotExist:
                errors.append(f"Product ID {product_id} not found")
        
        return JsonResponse({
            'success': True,
            'items': validated_items,
            'total': total,
            'errors': errors,
            'item_count': len(validated_items)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Cart validation error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)









# ============================================
# CHECKOUT
# ============================================

@require_http_methods(["POST"])
def checkout(request):
    """
    Process checkout - create sales for cart items
    """
    try:
        data = json.loads(request.body)
        cart_items = data.get('cart', [])
        buyer_name = data.get('buyer_name', '').strip()
        buyer_phone = data.get('buyer_phone', '').strip()
        buyer_id = data.get('buyer_id', '').strip()
        
        if not cart_items:
            return JsonResponse({
                'success': False,
                'message': 'Cart is empty'
            }, status=400)
        
        if not buyer_name or not buyer_phone:
            return JsonResponse({
                'success': False,
                'message': 'Customer name and phone are required'
            }, status=400)
        
        # Redirect to sales system for actual checkout
        # Store cart data in session
        request.session['checkout_cart'] = cart_items
        request.session['checkout_buyer'] = {
            'name': buyer_name,
            'phone': buyer_phone,
            'id_number': buyer_id
        }
        
        return JsonResponse({
            'success': True,
            'message': 'Redirecting to checkout...',
            'redirect_url': '/sales/checkout/'  # Update with your checkout URL
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Checkout error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Checkout failed: {str(e)}'
        }, status=500)









# ============================================
# CREATE PENDING ORDER
# ============================================

@csrf_exempt  # Remove this if you're properly handling CSRF tokens
@require_http_methods(["POST"])
def create_pending_order(request):
    """
    API endpoint for customers to submit orders
    URL: /api/pending-orders/create/
    """
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        cart_items = data.get('cart', [])
        buyer_name = data.get('buyer_name', '').strip()
        buyer_phone = data.get('buyer_phone', '').strip()
        
        if not cart_items:
            return JsonResponse({
                'success': False,
                'message': 'Cart is empty'
            }, status=400)
        
        if not buyer_name or not buyer_phone:
            return JsonResponse({
                'success': False,
                'message': 'Buyer name and phone are required'
            }, status=400)
        
        # Calculate totals
        item_count = sum(item.get('quantity', 1) for item in cart_items)
        total_amount = sum(
            float(item.get('price', 0)) * item.get('quantity', 1) 
            for item in cart_items
        )
        
        # Create PendingOrder
        with transaction.atomic():
            order = PendingOrder.objects.create(
                buyer_name=buyer_name,
                buyer_phone=buyer_phone,
                buyer_email=data.get('buyer_email', ''),
                buyer_id_number=data.get('buyer_id', ''),
                payment_method=data.get('payment_method', 'cash'),
                notes=data.get('notes', ''),
                cart_data=json.dumps(cart_items),
                total_amount=total_amount,
                item_count=item_count,
                status='pending'
            )
            
            # Create individual order items
            for item in cart_items:
                PendingOrderItem.objects.create(
                    order=order,
                    product_name=item.get('name', 'Unknown'),
                    quantity=item.get('quantity', 1),
                    unit_price=item.get('price', 0)
                )
        
        logger.info(
            f"[PENDING ORDER CREATED] {order.order_id} | "
            f"Buyer: {buyer_name} | Items: {item_count} | "
            f"Total: KSh {total_amount}"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Order submitted successfully and is pending approval.',
            'order_id': order.order_id,
            'redirect_url': '/orders/pending/'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"[PENDING ORDER ERROR] {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Failed to create order: {str(e)}'
        }, status=500)









# ============================================
# 2. CHECKOUT PAGE
# ============================================

@require_http_methods(["GET"])
def checkout_page(request):
    """
    Render checkout page
    URL: /checkout/
    """
    return render(request, 'website/checkout.html', {
        'page_title': 'Checkout - Fieldmax'
    })










# ============================================
# 3. STAFF VIEW: LIST PENDING ORDERS
# ============================================

@login_required
@require_http_methods(["GET"])
def pending_orders_list(request):
    """
    Staff view to see all pending orders
    URL: /staff/pending-orders/
    """
    # Get all pending orders and prefetch related items
    pending_orders = PendingOrder.objects.filter(
        status__iexact='pending'  # case-insensitive just in case
    ).prefetch_related('items').order_by('-created_at')

    context = {
        'page_title': 'Pending Orders - Fieldmax',
        'pending_orders': pending_orders,
        'pending_count': pending_orders.count()
    }

    return render(request, 'website/pending_orders.html', context)









# ============================================
# 4. API: GET PENDING ORDERS COUNT (for badge)
# ============================================

@login_required
@require_http_methods(["GET"])
def pending_orders_count(request):
    """
    API endpoint to get count of pending orders (for staff badge)
    URL: /api/pending-orders/count/
    """
    try:
        count = PendingOrder.objects.filter(status='pending').count()
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        logger.error(f"[PENDING COUNT ERROR] {str(e)}")
        return JsonResponse({
            'success': False,
            'count': 0,
            'error': str(e)
        })








# ============================================
# 5. STAFF ACTION: APPROVE ORDER
# ============================================

@login_required
@require_http_methods(["POST"])
def approve_order(request, order_id):
    """
    Staff approves order → Creates actual Sale
    URL: /staff/approve-order/<order_id>/
    """
    try:
        # Get pending order
        pending_order = PendingOrder.objects.get(
            order_id=order_id,
            status='pending'
        )
        
        with transaction.atomic():
            # Lock the pending order
            pending_order = PendingOrder.objects.select_for_update().get(
                pk=pending_order.pk
            )
            
            # Parse cart items
            cart_items = pending_order.cart_items
            
            # Create the Sale
            sale = Sale.objects.create(
                seller=request.user,
                buyer_name=pending_order.buyer_name,
                buyer_phone=pending_order.buyer_phone,
                buyer_id_number=pending_order.buyer_id_number,
                payment_method=pending_order.payment_method,
            )
            
            # Add items to sale
            created_items = []
            errors = []
            
            for item in cart_items:
                try:
                    # Get product from database with lock
                    product = Product.objects.select_for_update().get(
                        id=item['id'],
                        is_active=True
                    )
                    
                    quantity = item['quantity']
                    
                    # Validate availability
                    if product.status == 'sold' and product.category.is_single_item:
                        errors.append(f"{product.name} is no longer available")
                        continue
                    
                    if not product.category.is_single_item and product.quantity < quantity:
                        errors.append(f"Only {product.quantity} units of {product.name} available")
                        continue
                    
                    # Create SaleItem
                    sale_item = SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        product_code=product.product_code,
                        product_name=product.name,
                        sku_value=product.sku_value,
                        quantity=quantity,
                        unit_price=product.selling_price,
                    )
                    
                    # Process sale (deduct stock)
                    sale_item.process_sale()
                    created_items.append(sale_item)
                    
                except Product.DoesNotExist:
                    errors.append(f"Product ID {item['id']} not found")
                    continue
                except Exception as e:
                    logger.error(f"[APPROVAL ITEM ERROR] {str(e)}", exc_info=True)
                    errors.append(f"Error: {str(e)}")
                    continue
            
            if not created_items:
                raise Exception("No items could be processed: " + "; ".join(errors))
            
            # Update pending order
            sale.refresh_from_db()
            pending_order.status = 'completed'
            pending_order.sale_id = sale.sale_id
            pending_order.reviewed_by = request.user
            pending_order.reviewed_at = timezone.now()
            pending_order.save()
            
            logger.info(
                f"[ORDER APPROVED] {pending_order.order_id} → Sale {sale.sale_id} | "
                f"Staff: {request.user.username} | "
                f"Items: {len(created_items)}/{len(cart_items)}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Order approved! Sale {sale.sale_id} created with {len(created_items)} items.',
                'sale_id': sale.sale_id,
                'items_processed': len(created_items),
                'total_items': len(cart_items),
                'errors': errors if errors else None
            })
            
    except PendingOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Order not found or already processed'
        }, status=404)
    except Exception as e:
        logger.error(f"[ORDER APPROVAL ERROR] {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Failed to approve order: {str(e)}'
        }, status=500)








# ============================================
# 6. STAFF ACTION: REJECT ORDER
# ============================================

@login_required
@require_http_methods(["POST"])
def reject_order(request, order_id):
    """
    Staff rejects order
    URL: /staff/reject-order/<order_id>/
    """
    try:
        data = json.loads(request.body)
        reason = data.get('reason', 'No reason provided')
        
        pending_order = PendingOrder.objects.get(
            order_id=order_id,
            status='pending'
        )
        
        pending_order.status = 'rejected'
        pending_order.rejection_reason = reason
        pending_order.reviewed_by = request.user
        pending_order.reviewed_at = timezone.now()
        pending_order.save()
        
        logger.info(
            f"[ORDER REJECTED] {pending_order.order_id} | "
            f"Staff: {request.user.username} | "
            f"Reason: {reason}"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Order rejected successfully'
        })
        
    except PendingOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Order not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"[ORDER REJECTION ERROR] {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Failed to reject order: {str(e)}'
        }, status=500)







# ============================================
# PROCESS ORDER
# ============================================

@require_http_methods(["POST"])
def process_order(request):
    """
    ✅ FIXED: Process order with new Sale/SaleItem structure
    - Creates ONE Sale record per order
    - Creates multiple SaleItem records for each product
    - Each SaleItem processes its own stock deduction
    """
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        cart_items = data.get('cart', [])
        buyer_name = data.get('buyer_name', '').strip()
        buyer_phone = data.get('buyer_phone', '').strip()
        buyer_email = data.get('buyer_email', '').strip()
        buyer_id = data.get('buyer_id', '').strip()
        payment_method = data.get('payment_method', 'cash')
        notes = data.get('notes', '').strip()
        
        if not cart_items:
            return JsonResponse({
                'success': False,
                'message': 'Cart is empty'
            }, status=400)
        
        if not buyer_name or not buyer_phone:
            return JsonResponse({
                'success': False,
                'message': 'Buyer name and phone are required'
            }, status=400)
        
        # Use atomic transaction to ensure data consistency
        with transaction.atomic():
            
            # ============================================
            # STEP 1: CREATE THE SALE (ONE PER ORDER)
            # ============================================
            seller = request.user if request.user.is_authenticated else User.objects.filter(is_superuser=True).first()
            
            sale = Sale.objects.create(
                seller=seller,
                buyer_name=buyer_name,
                buyer_phone=buyer_phone,
                buyer_id_number=buyer_id,
                payment_method=payment_method,
                # Totals will be calculated after adding items
            )
            
            logger.info(f"[WEB ORDER] Created Sale {sale.sale_id} for {buyer_name}")
            
            # ============================================
            # STEP 2: ADD ITEMS TO THE SALE
            # ============================================
            created_items = []
            errors = []
            
            for item in cart_items:
                try:
                    # Get product from database with lock
                    product = Product.objects.select_for_update().get(
                        id=item['id'],
                        is_active=True
                    )
                    
                    quantity = item['quantity']
                    
                    # Validate product availability
                    if product.status == 'sold' and product.category.is_single_item:
                        errors.append(f"{product.name} is no longer available (already sold)")
                        continue
                    
                    if not product.category.is_single_item and product.quantity < quantity:
                        errors.append(f"Only {product.quantity} units of {product.name} available")
                        continue
                    
                    # ============================================
                    # CREATE SALE ITEM
                    # ============================================
                    sale_item = SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        product_code=product.product_code,
                        product_name=product.name,
                        sku_value=product.sku_value,
                        quantity=quantity,
                        unit_price=product.selling_price,
                        # total_price calculated automatically in SaleItem.save()
                    )
                    
                    # ============================================
                    # PROCESS THE SALE (DEDUCT STOCK)
                    # ============================================
                    sale_item.process_sale()
                    
                    created_items.append(sale_item)
                    
                    logger.info(
                        f"[WEB ORDER ITEM] Sale: {sale.sale_id} | "
                        f"Product: {product.product_code} | "
                        f"Qty: {quantity} | "
                        f"Price: KSh {sale_item.total_price}"
                    )
                    
                except Product.DoesNotExist:
                    errors.append(f"Product ID {item['id']} not found")
                    continue
                except Exception as e:
                    logger.error(f"Error processing item {item['id']}: {str(e)}", exc_info=True)
                    errors.append(f"Error processing {item.get('name', 'item')}: {str(e)}")
                    continue
            
            # ============================================
            # STEP 3: VALIDATE RESULTS
            # ============================================
            if not created_items:
                raise Exception("No items could be processed. " + "; ".join(errors))
            
            # Sale totals are automatically recalculated by SaleItem.save()
            sale.refresh_from_db()
            
            # ============================================
            # STEP 4: PREPARE RESPONSE
            # ============================================
            success_count = len(created_items)
            total_count = len(cart_items)
            
            response_data = {
                'success': True,
                'message': f'Order placed successfully! {success_count} of {total_count} items processed.',
                'order_count': success_count,
                'sale_id': sale.sale_id,
                'total_amount': float(sale.total_amount),
                'items': [
                    {
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'amount': float(item.total_price)
                    }
                    for item in created_items
                ],
                'redirect_url': '/order-success/',
                'errors': errors if errors else None
            }
            
            # Store order info in session for success page
            request.session['last_order'] = {
                'sale_id': sale.sale_id,
                'buyer_name': buyer_name,
                'buyer_phone': buyer_phone,
                'total_amount': float(sale.total_amount),
                'item_count': success_count,
                'payment_method': payment_method,
                'items': [
                    {
                        'name': item.product_name,
                        'quantity': item.quantity,
                        'total': float(item.total_price)
                    }
                    for item in created_items
                ]
            }
            
            logger.info(
                f"[WEB ORDER COMPLETE] Sale: {sale.sale_id} | "
                f"Items: {success_count} | "
                f"Total: KSh {sale.total_amount} | "
                f"Buyer: {buyer_name}"
            )
            
            return JsonResponse(response_data)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Order processing error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Failed to process order: {str(e)}'
        }, status=500)








# ============================================
# ORDER SUCCESS
# ============================================

@require_http_methods(["GET"])
def order_success(request):
    """
    Order success page - renders template that loads data from browser sessionStorage
    The JavaScript in the template handles loading order details from sessionStorage
    """
    # Just render the template - let JavaScript handle the data
    return render(request, 'website/order_success.html', {
        'page_title': 'Order Successful - Fieldmax',
    })








# ============================================
# SHOP VIEW
# ============================================

@csrf_exempt
@require_POST
def api_add_to_cart(request):
    try:
        # Parse incoming JSON data
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        # Validate product
        product = Product.objects.filter(id=product_id, is_active=True).first()
        if not product:
            return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)
        
        # Initialize or retrieve cart from session
        cart = request.session.get('cart', {})
        
        # Check if product already in cart
        product_key = str(product_id)
        if product_key in cart:
            # Update quantity
            cart[product_key]['quantity'] += quantity
            # Optional: prevent exceeding stock
            max_quantity = product.quantity if not product.category.is_single_item else 1
            if cart[product_key]['quantity'] > max_quantity:
                cart[product_key]['quantity'] = max_quantity
        else:
            # Add new item
            max_quantity = product.quantity if not product.category.is_single_item else 1
            if quantity > max_quantity:
                quantity = max_quantity
            
            cart[product_key] = {
                'name': product.name,
                'product_code': product.product_code,
                'price': float(product.selling_price),
                'quantity': quantity,
            }
        
        # Save updated cart into session
        request.session['cart'] = cart
        request.session.modified = True  # Mark session as modified to save changes
        
        return JsonResponse({'status': 'success', 'message': 'Product added to cart'})
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)






# ============================================
# SHOP VIEW - UPDATED WITH CATEGORY FILTERING
# ============================================

def shop_view(request):
    """
    Display all products organized by category
    Shows: Product image, name, price, status, and add to cart button
    Supports filtering by category via URL parameter: ?category=<id>
    """
    # Get category filter from URL parameter
    category_id = request.GET.get('category')
    selected_category = None
    
    # Get all categories
    all_categories = Category.objects.all()
    
    # Determine which categories to display
    if category_id:
        try:
            # Filter to show only the selected category
            selected_category = Category.objects.get(id=category_id)
            categories = [selected_category]
        except Category.DoesNotExist:
            # If invalid category ID, show all categories
            categories = all_categories
    else:
        # No filter - show all categories
        categories = all_categories
    
    # Prepare categories with their active products
    categories_with_products = []
    for category in categories:
        # Filter to include only active products
        active_products = category.products.filter(is_active=True).order_by('-created_at')
        # Attach filtered products as an attribute
        category.filtered_products = active_products
        # Only include categories that have products
        if active_products.exists():
            categories_with_products.append(category)
    
    context = {
        'categories': categories_with_products,
        'all_categories': all_categories,  # For category dropdown navigation
        'selected_category': selected_category,  # To highlight active category
        'debug': settings.DEBUG,
    }
    
    return render(request, 'website/shop.html', context)


# ============================================
# ALTERNATIVE: CLASS-BASED VIEW WITH FILTERING
# ============================================

from django.views.generic import ListView

class ShopListView(ListView):
    """
    Class-based view for shop page with category filtering
    URL: /shop/ or /shop/?category=<id>
    """
    model = Category
    template_name = 'website/shop.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        """Get categories with their active products, optionally filtered"""
        # Get category filter from URL
        category_id = self.request.GET.get('category')
        
        # Determine which categories to show
        if category_id:
            try:
                selected_category = Category.objects.get(id=category_id)
                categories = [selected_category]
            except Category.DoesNotExist:
                categories = Category.objects.all()
        else:
            categories = Category.objects.all()
        
        # Filter products for each category
        filtered_categories = []
        for category in categories:
            active_products = category.products.filter(is_active=True).order_by('-created_at')
            category.filtered_products = active_products
            if active_products.exists():
                filtered_categories.append(category)
        
        return filtered_categories
    
    def get_context_data(self, **kwargs):
        """Add additional context"""
        context = super().get_context_data(**kwargs)
        
        # Get selected category
        category_id = self.request.GET.get('category')
        if category_id:
            try:
                context['selected_category'] = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                context['selected_category'] = None
        else:
            context['selected_category'] = None
        
        # Add all categories for dropdown
        context['all_categories'] = Category.objects.all()
        context['debug'] = settings.DEBUG
        
        return context







# ============================================
# ROLE BASED LOGIN VIEW
# ============================================

class RoleBasedLoginView(LoginView):
    template_name = 'registration/login.html'
        
    def get_success_url(self):
        user = self.request.user
        role = getattr(user.profile, 'role', None)

        if role == 'admin':
            return '/admin-dashboard/'
        elif role == 'manager':
            return '/manager-dashboard/'
        elif role == 'agent':
            return '/agent-dashboard/'
        elif role == 'cashier':
            return '/cashier-dashboard/'
        return '/'









# ============================================
# CAHIER DASHBOARD
# ============================================

@login_required
def cashier_dashboard(request):
    """
    Cashier Dashboard View
    Renders the cashier interface for processing sales
    """
    return render(request, 'website/cashier_dashboard.html')











# ============================================
# ADMIN DASHBOARD
# ============================================

@login_required
def admin_dashboard(request):
    """
    Admin Dashboard:
    - Single items: Uses product.status field directly
    - Bulk items: Calculates status from quantity
    - Handles recent products and recent sales
    - Displays comprehensive statistics for cards with dropdowns
    """
    context = {}

    # ============================================
    # CURRENT TIME CALCULATIONS
    # ============================================
    now = timezone.now()
    
    # Calculate start of today
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timezone.timedelta(days=1)
    
    # Calculate start of week (Monday)
    start_of_week = now - timezone.timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate start of month
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate start of year
    start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # ============================================
    # CARD A: 📦 INVENTORY
    # ============================================
    # Total products count (sum of quantities for bulk, count for single items)
    all_products = Product.objects.filter(is_active=True)
    
    total_products = 0
    for product in all_products:
        if product.category.is_single_item:
            if product.status == 'available':
                total_products += 1
        else:
            total_products += product.quantity or 0
    
    # Total products (sum of quantities)
    context["total_products"] = Product.objects.filter(is_active=True).aggregate(
        total=Sum('quantity', output_field=DecimalField())
    )['total'] or 0

    # Total product value (quantity × selling price)
    context["total_product_value"] = Product.objects.filter(is_active=True).aggregate(
        total=Sum(F('quantity') * F('selling_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    # Total product value for in-stock products only (quantity > 0)
    context["total_product_value"] = Product.objects.filter(
        is_active=True,
        quantity__gt=0  # Only products with quantity greater than 0
    ).aggregate(
        total=Sum(F('quantity') * F('selling_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')

    # instock product value (quantity × selling price)
    context["instock_products_count"] = Product.objects.filter(
        is_active=True,
        quantity__gt=0
    ).count()

    # Total product cost (quantity × buying price)
    context["total_product_cost"] = Product.objects.filter(is_active=True).aggregate(
        total=Sum(F('quantity') * F('buying_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')

    # ============================================
    # CARD B: ✅ SALES COUNT
    # ============================================
    all_sales = Sale.objects.filter(is_reversed=False)
    
    # Daily sales count
    context["daily_sales_count"] = all_sales.filter(
        sale_date__gte=start_of_day,
        sale_date__lt=end_of_day
    ).count()
    
    # Weekly sales count
    context["weekly_sales_count"] = all_sales.filter(
        sale_date__gte=start_of_week
    ).count()
    
    # Monthly sales count
    context["monthly_sales_count"] = all_sales.filter(
        sale_date__gte=start_of_month
    ).count()
    
    # Total sales count (for main display)
    context["total_sales_count"] = all_sales.count()

    # ============================================
    # CARD C: 💰 SALES VALUE
    # ============================================
    # Daily sales value
    context["daily_sales_value"] = all_sales.filter(
        sale_date__gte=start_of_day,
        sale_date__lt=end_of_day
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Weekly sales value
    context["weekly_sales_value"] = all_sales.filter(
        sale_date__gte=start_of_week
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Monthly sales value
    context["monthly_sales_value"] = all_sales.filter(
        sale_date__gte=start_of_month
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Total sales value (for main display)
    context["total_sales_value"] = all_sales.aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')

    # ============================================
    # CARD D: 💵 PROFITS
    # ============================================
    # Calculate profits by subtracting cost from revenue
    # For each sale, profit = total_amount - (sum of buying_price * quantity for all items)
    
    def calculate_profit_for_period(sales_queryset):
        """Helper function to calculate profit for a given sales queryset"""
        total_profit = Decimal('0.00')
        
        for sale in sales_queryset.prefetch_related('items', 'items__product'):
            sale_profit = Decimal('0.00')
            for item in sale.items.all():
                if item.product:
                    buying_price = item.product.buying_price or Decimal('0.00')
                    quantity = item.quantity or 1
                    unit_profit = (item.unit_price or Decimal('0.00')) - buying_price
                    sale_profit += unit_profit * quantity
            total_profit += sale_profit
        
        return total_profit
    
    # Daily profit
    daily_sales = all_sales.filter(
        sale_date__gte=start_of_day,
        sale_date__lt=end_of_day
    )
    context["daily_profit"] = calculate_profit_for_period(daily_sales)
    
    # Weekly profit
    weekly_sales = all_sales.filter(sale_date__gte=start_of_week)
    context["weekly_profit"] = calculate_profit_for_period(weekly_sales)
    
    # Monthly profit
    monthly_sales = all_sales.filter(sale_date__gte=start_of_month)
    context["monthly_profit"] = calculate_profit_for_period(monthly_sales)
    
    # Total profit (for main display)
    context["total_profit"] = calculate_profit_for_period(all_sales)

    # ============================================
    # CARD E: 👤 USERS
    # ============================================
    all_users = User.objects.select_related('profile')
    
    context["total_users"] = all_users.count()
    
    # Count by role
    context["total_admin"] = all_users.filter(profile__role='admin').count()
    context["total_managers"] = all_users.filter(profile__role='manager').count()
    context["total_cashiers"] = all_users.filter(profile__role='cashier').count()
    context["total_agents"] = all_users.filter(profile__role='agent').count()

    # ============================================
    # OTHER SUMMARY DATA
    # ============================================
    context["total_categories"] = Category.objects.count()
    context["total_stock_entries"] = StockEntry.objects.count()

    # ============================================
    # RECENT PRODUCTS
    # ============================================
    recent_products = Product.objects.filter(is_active=True).select_related(
        "category", "owner"
    ).order_by("-created_at")[:5]

    recent_products_with_margin_and_status = []
    for product in recent_products:
        buying_price = product.buying_price or Decimal('0.00')
        selling_price = product.selling_price or Decimal('0.00')

        margin_pct = ((selling_price - buying_price) / buying_price * 100) if buying_price else Decimal('0.00')
        status = product.status if product.category.is_single_item else (
            "outofstock" if product.quantity == 0 else ("lowstock" if product.quantity <= 5 else "instock")
        )

        recent_products_with_margin_and_status.append({
            "product": product,
            "margin_pct": margin_pct,
            "status": status,
        })

    context["recent_products_with_margin_and_status"] = recent_products_with_margin_and_status

    # ============================================
    # RECENT SALES
    # ============================================
    recent_sales = Sale.objects.prefetch_related(
        'items', 'items__product', 'seller'
    ).order_by("-sale_date")[:5]

    context["recent_sales"] = recent_sales

    # ============================================
    # ALL PRODUCTS WITH STATUS & MARGIN
    # ============================================
    all_products_list = Product.objects.filter(is_active=True).select_related(
        "category", "owner"
    ).order_by("-created_at")

    products_with_margin_and_status = []
    in_stock_count = low_stock_count = out_of_stock_count = sold_count = 0

    for product in all_products_list:
        buying_price = product.buying_price or Decimal('0.00')
        selling_price = product.selling_price or Decimal('0.00')
        quantity = product.quantity or 0

        margin_pct = ((selling_price - buying_price) / buying_price * 100) if buying_price else Decimal('0.00')

        if product.category.is_single_item:
            status = product.status
            if status == "sold":
                sold_count += 1
            elif status == "available":
                in_stock_count += 1
        else:
            if quantity == 0:
                status = "outofstock"
                out_of_stock_count += 1
            elif quantity <= 5:
                status = "lowstock"
                low_stock_count += 1
            else:
                status = "instock"
                in_stock_count += 1

        products_with_margin_and_status.append({
            "product": product,
            "margin_pct": margin_pct,
            "status": status,
        })

    context.update({
        "products_with_margin_and_status": products_with_margin_and_status,
        "in_stock_count": in_stock_count,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "sold_count": sold_count,
    })

    # ============================================
    # ALL SALES WITH ADDITIONAL STATISTICS
    # ============================================
    all_sales_list = Sale.objects.prefetch_related(
        'items', 'items__product', 'seller'
    ).order_by("-sale_date")

    # Annual sales count
    context["annual_sales_count"] = all_sales_list.filter(
        sale_date__gte=start_of_year,
        is_reversed=False
    ).count()
    
    context["active_sales_count"] = all_sales_list.filter(is_reversed=False).count()
    context["reversed_sales_count"] = all_sales_list.filter(is_reversed=True).count()
    
    context["all_sales"] = all_sales_list

    # ============================================
    # USERS, CATEGORIES, STOCK ENTRIES
    # ============================================
    context["users"] = User.objects.prefetch_related("profile").order_by("username")
    context["categories"] = Category.objects.order_by("name")
    context["stockentries"] = StockEntry.objects.select_related(
        "product", "created_by"
    ).order_by("-created_at")[:50]

    # ============================================
    # ROLE CHOICES FOR USER FORM
    # ============================================
    try:
        context["roles"] = Profile.ROLE_CHOICES
    except:
        context["roles"] = [
            ('admin', 'Admin'),
            ('manager', 'Manager'),
            ('agent', 'Agent'),
        ]

    # ============================================
    # SAFE URL RESOLUTION
    # ============================================
    url_mapping = {
        "user_add": "user-add",
        "product_add": "inventory:product-create",
        "category_add": "inventory:category-create",
        "stockentry_add": "inventory:stockentry-create",
        "sale_add": "sales:sale-create",
    }

    for key, url_name in url_mapping.items():
        try:
            context[f"url_{key}"] = reverse(url_name)
        except Exception as e:
            logger.warning(f"URL '{url_name}' not found: {e}")
            context[f"url_{key}"] = "#"

    # ============================================
    # RENDER TEMPLATE
    # ============================================
    return render(request, "website/admin_dashboard.html", context)











# ============================================
# FIX PRODUCT STATUSES
# ============================================
def fix_product_statuses():
    """
    Management command to fix inconsistent product statuses.
    Run this if you have products with wrong status values.
    
    Usage:
        python manage.py shell
        >>> from website.views import fix_product_statuses
        >>> fix_product_statuses()
    """
    
    fixed_count = 0
    
    # Fix single items
    single_items = Product.objects.filter(
        category__item_type='single',
        is_active=True
    )
    
    for product in single_items:
        old_status = product.status
        
        # Check if product has active sales
        has_active_sale = Sale.objects.filter(
            product=product,
            is_reversed=False
        ).exists()
        
        # Determine correct status
        if has_active_sale:
            correct_status = 'sold'
            correct_quantity = 0
        else:
            correct_status = 'available'
            correct_quantity = 1
        
        # Fix if incorrect
        if product.status != correct_status or product.quantity != correct_quantity:
            logger.info(
                f"Fixing {product.product_code}: "
                f"Status {old_status} → {correct_status}, "
                f"Quantity {product.quantity} → {correct_quantity}"
            )
            
            product.status = correct_status
            product.quantity = correct_quantity
            product.save(update_fields=['status', 'quantity'])
            fixed_count += 1
    
    # Fix bulk items
    bulk_items = Product.objects.filter(
        category__item_type='bulk',
        is_active=True
    )
    
    for product in bulk_items:
        old_status = product.status
        quantity = product.quantity or 0
        
        # Determine correct status based on quantity
        if quantity > 5:
            correct_status = 'available'
        elif quantity > 0:
            correct_status = 'lowstock'
        else:
            correct_status = 'outofstock'
        
        # Fix if incorrect
        if product.status != correct_status:
            logger.info(
                f"Fixing bulk item {product.product_code}: "
                f"Status {old_status} → {correct_status}"
            )
            
            product.status = correct_status
            product.save(update_fields=['status'])
            fixed_count += 1
    
    logger.info(f"✅ Fixed {fixed_count} products with inconsistent statuses")
    return fixed_count







# ============================================
# DEBUG PRODUCT STATUS
# ============================================
@login_required
def debug_product_status(request, product_code):
    """
    Debug endpoint to check product status consistency.
    Usage: /admin/debug-product/<product_code>/
    """
    
    try:
        product = Product.objects.get(product_code=product_code)
    except Product.DoesNotExist:
        return render(request, "debug.html", {
            "error": f"Product {product_code} not found"
        })
    
    # Get related data
    active_sales = Sale.objects.filter(
        product=product,
        is_reversed=False
    )
    
    stock_entries = StockEntry.objects.filter(
        product=product
    ).order_by('-created_at')[:10]
    
    # Determine expected status
    if product.category.is_single_item:
        expected_status = 'sold' if active_sales.exists() else 'available'
        expected_quantity = 0 if active_sales.exists() else 1
    else:
        quantity = product.quantity or 0
        if quantity > 5:
            expected_status = 'available'
        elif quantity > 0:
            expected_status = 'lowstock'
        else:
            expected_status = 'outofstock'
        expected_quantity = quantity
    
    debug_info = {
        "product": product,
        "actual_status": product.status,
        "expected_status": expected_status,
        "actual_quantity": product.quantity,
        "expected_quantity": expected_quantity,
        "is_consistent": (
            product.status == expected_status and 
            product.quantity == expected_quantity
        ),
        "active_sales": active_sales,
        "stock_entries": stock_entries,
        "category_type": product.category.item_type,
    }
    
    return render(request, "debug_product.html", debug_info)









# ============================================
# MANAGER DASHBOARD
# ============================================

@login_required
def manager_dashboard(request):
    context = {}

    # ============================================
    # SUMMARY CARDS
    # ============================================
    context["total_users"] = User.objects.count()
    context["total_categories"] = Category.objects.count()
    context["total_stock_entries"] = StockEntry.objects.count()

    # Total products (sum of quantities)
    context["total_products"] = Product.objects.filter(is_active=True).aggregate(
        total=Sum('quantity', output_field=DecimalField())
    )['total'] or 0

    # Total product value (quantity × selling price)
    context["total_product_value"] = Product.objects.filter(is_active=True).aggregate(
        total=Sum(F('quantity') * F('selling_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')

    # Total product cost (quantity × buying price)
    context["total_product_cost"] = Product.objects.filter(is_active=True).aggregate(
        total=Sum(F('quantity') * F('buying_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')

    # Total sales revenue
    context["total_sales"] = Sale.objects.filter(is_reversed=False).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')

    # ============================================
    # RECENT PRODUCTS
    # ============================================
    recent_products = Product.objects.filter(is_active=True).select_related(
        "category", "owner"
    ).order_by("-created_at")[:5]

    recent_products_with_margin_and_status = []
    for product in recent_products:
        buying_price = product.buying_price or Decimal('0.00')
        selling_price = product.selling_price or Decimal('0.00')

        margin_pct = ((selling_price - buying_price) / buying_price * 100) if buying_price else Decimal('0.00')
        status = product.status if product.category.is_single_item else (
            "outofstock" if product.quantity == 0 else ("lowstock" if product.quantity <= 5 else "instock")
        )

        recent_products_with_margin_and_status.append({
            "product": product,
            "margin_pct": margin_pct,
            "status": status,
        })

    context["recent_products_with_margin_and_status"] = recent_products_with_margin_and_status

    # ============================================
    # RECENT SALES
    # ============================================
    recent_sales = Sale.objects.prefetch_related(
        'items', 'items__product', 'seller'
    ).order_by("-sale_date")[:5]

    context["recent_sales"] = recent_sales

    # ============================================
    # ALL PRODUCTS WITH STATUS & MARGIN
    # ============================================
    all_products = Product.objects.filter(is_active=True).select_related(
        "category", "owner"
    ).order_by("-created_at")

    products_with_margin_and_status = []
    in_stock_count = low_stock_count = out_of_stock_count = sold_count = 0

    for product in all_products:
        buying_price = product.buying_price or Decimal('0.00')
        selling_price = product.selling_price or Decimal('0.00')
        quantity = product.quantity or 0

        margin_pct = ((selling_price - buying_price) / buying_price * 100) if buying_price else Decimal('0.00')

        if product.category.is_single_item:
            status = product.status
            if status == "sold":
                sold_count += 1
            elif status == "available":
                in_stock_count += 1
        else:
            if quantity == 0:
                status = "outofstock"
                out_of_stock_count += 1
            elif quantity <= 5:
                status = "lowstock"
                low_stock_count += 1
            else:
                status = "instock"
                in_stock_count += 1

        products_with_margin_and_status.append({
            "product": product,
            "margin_pct": margin_pct,
            "status": status,
        })

    context.update({
        "products_with_margin_and_status": products_with_margin_and_status,
        "in_stock_count": in_stock_count,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "sold_count": sold_count,
    })

    # ============================================
    # ALL SALES
    # ============================================
    # Fetch all sales with related data
    all_sales = Sale.objects.prefetch_related('items', 'items__product', 'seller').order_by("-sale_date")

    # Current time
    now = timezone.now()

    # Calculate start of today
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timezone.timedelta(days=1)

    # Calculate start of week (Monday)
    start_of_week = now - timezone.timedelta(days=now.weekday())

    # Calculate start of month
    start_of_month = now.replace(day=1)

    # Calculate start of year
    start_of_year = now.replace(month=1, day=1)

    # Filter sales within each period
    daily_sales = all_sales.filter(sale_date__gte=start_of_day, sale_date__lt=end_of_day)
    weekly_sales = all_sales.filter(sale_date__gte=start_of_week)
    monthly_sales = all_sales.filter(sale_date__gte=start_of_month)
    annual_sales = all_sales.filter(sale_date__gte=start_of_year)

    # Update context with all statistics
    context.update({
        "all_sales": all_sales,
        "daily_sales_count": daily_sales.filter(is_reversed=False).count(),
        "weekly_sales_count": weekly_sales.filter(is_reversed=False).count(),
        "monthly_sales_count": monthly_sales.filter(is_reversed=False).count(),
        "annual_sales_count": annual_sales.filter(is_reversed=False).count(),
        "active_sales_count": all_sales.filter(is_reversed=False).count(),
        "reversed_sales_count": all_sales.filter(is_reversed=True).count(),       
    })

    # ============================================
    # USERS, CATEGORIES, STOCK ENTRIES
    # ============================================
    context["users"] = User.objects.prefetch_related("profile").order_by("username")
    context["categories"] = Category.objects.order_by("name")
    context["stockentries"] = StockEntry.objects.select_related("product", "created_by").order_by("-created_at")[:50]

    # ============================================
    # SAFE URL RESOLUTION
    # ============================================
    url_mapping = {
        "user_add": "user-add",
        "product_add": "inventory:product-create",
        "category_add": "inventory:category-create",
        "stockentry_add": "inventory:stockentry-create",
        "sale_add": "sales:sale-create",
    }

    for key, url_name in url_mapping.items():
        try:
            context[f"url_{key}"] = reverse(url_name)
        except Exception as e:
            logger.warning(f"URL '{url_name}' not found: {e}")
            context[f"url_{key}"] = "#"

    # ============================================
    # RENDER TEMPLATE
    # ============================================


    return render(request, 'website/manager_dashboard.html', context)












# ============================================
# AGENT DASHBOARD
# ============================================

@login_required(login_url='/accounts/login/')
def agent_dashboard(request):
    user = request.user
    today = timezone.now().date()

    # Products
    my_products = Product.objects.filter(
        is_active=True,
        owner=user
    ).select_related('category').order_by('name')

    my_products_count = my_products.count()

    # Sales for this user
    user_sales = Sale.objects.filter(seller=user)

    # Today's Sales Total (use total_amount field)
    todays_sales_total = user_sales.filter(
        sale_date__date=today
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    todays_sales = f"{float(todays_sales_total):.2f}"

    # Total Sales Count (all time)
    total_sales_count = user_sales.count()

    # Total Sales Revenue (all time)
    total_sales_revenue = user_sales.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    total_sales = f"{float(total_sales_revenue):.2f}"

    # Monthly Sales Revenue (current month)
    monthly_sales_total = user_sales.filter(
        sale_date__year=today.year,
        sale_date__month=today.month
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    monthly_sales = f"{float(monthly_sales_total):.2f}"

    # Monthly Sales Count (number of transactions this month)
    monthly_sales_count = user_sales.filter(
        sale_date__year=today.year,
        sale_date__month=today.month
    ).count()

    # Recent Sales (prefetch items)
    recent_sales = user_sales.prefetch_related(
        'items', 'items__product'
    ).order_by('-sale_date')[:5]

    # All Sales (prefetch items)
    all_sales = user_sales.prefetch_related(
        'items', 'items__product'
    ).order_by('-sale_date')

    # Additional Metrics
    total_revenue = total_sales_revenue  # Already calculated above

    week_start = today - timezone.timedelta(days=today.weekday())
    week_sales = user_sales.filter(
        sale_date__date__gte=week_start
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    month_sales = monthly_sales_total  # Already calculated above

    # Stock
    low_stock_count = my_products.filter(quantity__lte=5, quantity__gt=0).count()
    out_of_stock_count = my_products.filter(quantity=0).count()

    return render(request, "website/agent_dashboard.html", {
        'todays_sales': todays_sales,
        'total_sales_count': total_sales_count,
        'total_sales': total_sales,  # Total revenue (KSH)
        'my_products_count': my_products_count,

        # Monthly metrics
        'monthly_sales': monthly_sales,  # Revenue amount (KSH)
        'monthly_sales_count': monthly_sales_count,  # Number of transactions

        'recent_sales': recent_sales,
        'all_sales': all_sales,

        'my_products': my_products,

        'total_revenue': total_revenue,
        'week_sales': week_sales,
        'month_sales': month_sales,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,

        'user': user,
    })