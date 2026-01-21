from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_sales(request):
    """Get recent sales"""
    try:
        from sales.models import Sale
        
        # Use correct field names from your Sale model
        sales = Sale.objects.select_related('seller').order_by('-sale_date')[:10]
        
        data = []
        for sale in sales:
            try:
                # Map to correct field names
                data.append({
                    'id': sale.sale_id,
                    'receipt_number': sale.etr_receipt_number if sale.etr_receipt_number else f'SALE-{sale.sale_id}',
                    'customer': sale.buyer_name if sale.buyer_name else 'Walk-in',
                    'total_amount': str(sale.total_amount),
                    'payment_method': sale.payment_method,
                    'created_at': sale.sale_date.strftime('%Y-%m-%d %H:%M'),
                    'created_by': sale.seller.username if sale.seller else 'N/A',
                })
            except Exception as item_error:
                logger.error(f"Error processing sale {sale.sale_id}: {item_error}")
                continue
        
        return Response(data)
        
    except Exception as e:
        logger.error(f"Recent sales error: {str(e)}", exc_info=True)
        return Response([], status=200)