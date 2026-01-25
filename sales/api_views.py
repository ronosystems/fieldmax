from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import Product
from sales.models import Sale
from users.models import User

@require_http_methods(["GET"])
@login_required
def dashboard_stats_api(request):
    """Real-time dashboard statistics"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        
        # Product stats
        total_products = Product.objects.filter(is_active=True).count()
        total_product_value = Product.objects.filter(is_active=True).aggregate(
            total=Sum('selling_price')
        )['total'] or 0
        
        # Sales stats
        active_sales = Sale.objects.filter(is_reversed=False)
        
        daily_sales_count = active_sales.filter(sale_date__gte=today_start).count()
        weekly_sales_count = active_sales.filter(sale_date__gte=week_start).count()
        monthly_sales_count = active_sales.filter(sale_date__gte=month_start).count()
        total_sales_count = active_sales.count()
        
        daily_sales_value = active_sales.filter(sale_date__gte=today_start).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        weekly_sales_value = active_sales.filter(sale_date__gte=week_start).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        monthly_sales_value = active_sales.filter(sale_date__gte=month_start).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        total_sales_value = active_sales.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Profit calculation (simplified - adjust based on your model)
        daily_profit = daily_sales_value * 0.3  # Adjust calculation as needed
        weekly_profit = weekly_sales_value * 0.3
        monthly_profit = monthly_sales_value * 0.3
        total_profit = total_sales_value * 0.3
        
        # User stats
        total_users = User.objects.filter(is_active=True).count()
        total_managers = User.objects.filter(
            profile__role__name='Manager', is_active=True
        ).count()
        total_cashiers = User.objects.filter(
            profile__role__name='Cashier', is_active=True
        ).count()
        total_agents = User.objects.filter(
            profile__role__name='Agent', is_active=True
        ).count()
        
        stats = {
            'total_products': total_products,
            'total_product_value': float(total_product_value),
            'daily_sales_count': daily_sales_count,
            'weekly_sales_count': weekly_sales_count,
            'monthly_sales_count': monthly_sales_count,
            'total_sales_count': total_sales_count,
            'daily_sales_value': float(daily_sales_value),
            'weekly_sales_value': float(weekly_sales_value),
            'monthly_sales_value': float(monthly_sales_value),
            'total_sales_value': float(total_sales_value),
            'daily_profit': float(daily_profit),
            'weekly_profit': float(weekly_profit),
            'monthly_profit': float(monthly_profit),
            'total_profit': float(total_profit),
            'total_users': total_users,
            'total_managers': total_managers,
            'total_cashiers': total_cashiers,
            'total_agents': total_agents,
        }
        
        return JsonResponse({'success': True, 'stats': stats})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def products_list_api(request):
    """Real-time products list"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        products = Product.objects.filter(is_active=True).select_related(
            'category', 'owner'
        ).order_by('-created_at')[:50]  # Latest 50 products
        
        products_data = []
        in_stock = 0
        low_stock = 0
        out_of_stock = 0
        
        for product in products:
            # Determine status
            if product.category.is_single_item:
                status = 'sold' if product.status == 'sold' else 'instock'
                if status == 'instock':
                    in_stock += 1
                else:
                    out_of_stock += 1
            else:
                if product.quantity == 0:
                    status = 'outofstock'
                    out_of_stock += 1
                elif product.quantity <= 5:
                    status = 'lowstock'
                    low_stock += 1
                else:
                    status = 'instock'
                    in_stock += 1
            
            # Calculate margin
            margin = product.selling_price - product.buying_price
            margin_pct = (margin / product.buying_price * 100) if product.buying_price > 0 else 0
            
            products_data.append({
                'id': product.id,
                'product_code': product.product_code,
                'name': product.name,
                'category': product.category.name,
                'category_id': product.category.id,
                'is_single': product.category.is_single_item,
                'status': status,
                'quantity': product.quantity if not product.category.is_single_item else 1,
                'buying_price': float(product.buying_price),
                'selling_price': float(product.selling_price),
                'margin_pct': float(margin_pct),
                'owner': product.owner.username if product.owner else 'FIELDMAX',
                'created_at': product.created_at.strftime('%b %d, %Y'),
            })
        
        stats = {
            'total': len(products),
            'in_stock': in_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
        }
        
        return JsonResponse({
            'success': True,
            'products': products_data,
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def sales_list_api(request):
    """Real-time sales list"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        sales = Sale.objects.select_related('seller').order_by('-sale_date')[:50]
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        
        sales_data = []
        active_count = 0
        reversed_count = 0
        daily_count = 0
        weekly_count = 0
        monthly_count = 0
        
        for sale in sales:
            if sale.is_reversed:
                reversed_count += 1
            else:
                active_count += 1
                
                if sale.sale_date >= today_start:
                    daily_count += 1
                if sale.sale_date >= week_start:
                    weekly_count += 1
                if sale.sale_date >= month_start:
                    monthly_count += 1
            
            sales_data.append({
                'sale_id': sale.sale_id,
                'etr_receipt_number': sale.etr_receipt_number or 'N/A',
                'buyer_name': sale.buyer_name or 'Walk-in',
                'total_amount': f'KSH {sale.total_amount:,.2f}',
                'seller_username': sale.seller.username if sale.seller else 'N/A',
                'seller_id': sale.seller.id if sale.seller else None,
                'sale_date': sale.sale_date.strftime('%b %d, %Y %H:%M'),
                'is_reversed': sale.is_reversed,
                'has_sku_items': hasattr(sale, 'items') and any(
                    item.product.category.is_single_item for item in sale.items.all()
                ),
                'batch_id': sale.batch_id if hasattr(sale, 'batch_id') else None,
            })
        
        stats = {
            'daily_count': daily_count,
            'weekly_count': weekly_count,
            'monthly_count': monthly_count,
            'active_count': active_count,
            'reversed_count': reversed_count,
        }
        
        return JsonResponse({
            'success': True,
            'sales': sales_data,
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def recent_products_api(request):
    """Recent products for dashboard"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        products = Product.objects.filter(is_active=True).select_related(
            'category', 'owner'
        ).order_by('-created_at')[:10]  # Latest 10 products
        
        products_data = []
        
        for product in products:
            # Determine status
            if product.category.is_single_item:
                status = 'sold' if product.status == 'sold' else 'instock'
            else:
                if product.quantity == 0:
                    status = 'outofstock'
                elif product.quantity <= 5:
                    status = 'lowstock'
                else:
                    status = 'instock'
            
            # Calculate margin
            margin = product.selling_price - product.buying_price
            margin_pct = (margin / product.buying_price * 100) if product.buying_price > 0 else 0
            
            products_data.append({
                'id': product.id,
                'product_code': product.product_code,
                'name': product.name,
                'category': product.category.name,
                'is_single': product.category.is_single_item,
                'status': status,
                'quantity': product.quantity if not product.category.is_single_item else 1,
                'buying_price': float(product.buying_price),
                'selling_price': float(product.selling_price),
                'margin_pct': float(margin_pct),
                'owner': product.owner.username if product.owner else 'FIELDMAX',
                'created_at': product.created_at.strftime('%b %d, %Y'),
            })
        
        return JsonResponse({'success': True, 'products': products_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def recent_sales_api(request):
    """Recent sales for dashboard"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        sales = Sale.objects.select_related('seller').order_by('-sale_date')[:10]
        
        sales_data = []
        
        for sale in sales:
            sales_data.append({
                'sale_id': sale.sale_id,
                'etr_receipt_number': sale.etr_receipt_number or 'N/A',
                'buyer_name': sale.buyer_name or 'Walk-in',
                'total_amount': f'KSH {sale.total_amount:,.2f}',
                'seller_username': sale.seller.username if sale.seller else 'N/A',
                'sale_date': sale.sale_date.strftime('%b %d, %Y %H:%M'),
                'is_reversed': sale.is_reversed,
                'batch_id': sale.batch_id if hasattr(sale, 'batch_id') else None,
                'batch_total_sales': 0,  # Calculate if needed
            })
        
        return JsonResponse({'success': True, 'sales': sales_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)