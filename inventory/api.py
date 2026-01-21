from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Get dashboard statistics"""
    try:
        from inventory.models import Product, Category
        
        # Product has is_active, Category doesn't
        total_products = Product.objects.filter(is_active=True).count()
        total_categories = Category.objects.all().count()  # ✅ Removed is_active filter
        
        # Use 'quantity' instead of 'current_stock'
        low_stock = Product.objects.filter(
            quantity__lte=5,
            is_active=True
        ).count()
        
        out_of_stock = Product.objects.filter(
            quantity=0,
            is_active=True
        ).count()
        
        # Calculate total stock value (quantity × selling_price)
        total_stock_value = 0
        try:
            from django.db.models import F
            total_stock_value = Product.objects.filter(
                is_active=True
            ).aggregate(
                total=Sum(F('quantity') * F('selling_price'))
            )['total'] or 0
        except Exception as calc_error:
            logger.error(f"Stock value calculation error: {calc_error}")
        
        return Response({
            'total_products': total_products,
            'total_categories': total_categories,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'total_stock_value': float(total_stock_value),
        })
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {str(e)}", exc_info=True)
        return Response({
            'error': str(e),
            'total_products': 0,
            'total_categories': 0,
            'low_stock': 0,
            'out_of_stock': 0,
            'total_stock_value': 0,
        }, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def products_list(request):
    """Get products list"""
    try:
        from inventory.models import Product
        
        products = Product.objects.filter(
            is_active=True
        ).select_related('category')[:50]
        
        data = []
        for p in products:
            try:
                data.append({
                    'id': p.id,
                    'name': p.name,
                    'sku': p.sku_value if p.sku_value else 'N/A',
                    'category': p.category.name if p.category else 'N/A',
                    'current_stock': p.quantity,
                    'unit_price': str(p.selling_price),
                    'is_active': p.is_active,
                })
            except Exception as item_error:
                logger.error(f"Error processing product {p.id}: {item_error}")
                continue
        
        return Response(data)
        
    except Exception as e:
        logger.error(f"Products list error: {str(e)}", exc_info=True)
        return Response([], status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_products(request):
    """Get recently added products"""
    try:
        from inventory.models import Product
        
        products = Product.objects.filter(
            is_active=True
        ).order_by('-created_at')[:10]
        
        data = []
        for p in products:
            try:
                data.append({
                    'id': p.id,
                    'name': p.name,
                    'sku': p.sku_value if p.sku_value else 'N/A',
                    'category': p.category.name if p.category else 'N/A',
                    'current_stock': p.quantity,
                    'created_at': p.created_at.strftime('%Y-%m-%d %H:%M'),
                })
            except Exception as item_error:
                logger.error(f"Error processing product {p.id}: {item_error}")
                continue
        
        return Response(data)
        
    except Exception as e:
        logger.error(f"Recent products error: {str(e)}", exc_info=True)
        return Response([], status=200)