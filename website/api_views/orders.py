# website/api_views/orders.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from website.models import Order, PendingOrder, OrderItem
from inventory.models import Product

@csrf_exempt
def search_order(request):
    """Search for orders by ID, phone, or name"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            search_term = data.get('search_term', '').strip()
            
            if not search_term:
                return JsonResponse({
                    'success': False,
                    'message': 'Please enter a search term'
                })
            
            # Try to find order by order_number (from Order model)
            try:
                order = Order.objects.get(order_number__iexact=search_term)
                
                # Get order items for regular Order model
                order_items = OrderItem.objects.filter(order=order)
                items_data = []
                for item in order_items:
                    items_data.append({
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': float(item.product_price),
                        'total_price': float(item.subtotal)
                    })
                
                return JsonResponse({
                    'success': True,
                    'order': {
                        'order_id': order.order_number,
                        'buyer_name': order.customer_name,
                        'buyer_phone': order.customer_phone,
                        'buyer_email': order.customer_email,
                        'total_amount': float(order.total_amount),
                        'payment_method': 'Not specified',
                        'status': order.get_status_display(),
                        'created_at': order.created_at.isoformat(),
                        'items': items_data
                    }
                })
                
            except Order.DoesNotExist:
                # Try to find in PendingOrder by order_id
                try:
                    order = PendingOrder.objects.get(order_id__iexact=search_term)
                    return JsonResponse({
                        'success': True,
                        'order': {
                            'order_id': order.order_id,
                            'buyer_name': order.buyer_name,
                            'buyer_phone': order.buyer_phone,
                            'buyer_email': order.buyer_email or '',
                            'total_amount': float(order.total_amount),
                            'payment_method': order.payment_method,
                            'status': order.get_status_display(),
                            'created_at': order.created_at.isoformat(),
                            'items': order.cart_items
                        }
                    })
                except PendingOrder.DoesNotExist:
                    pass
            
            # Search by phone number
            orders = Order.objects.filter(customer_phone__icontains=search_term)
            if orders.exists():
                order = orders.first()
                order_items = OrderItem.objects.filter(order=order)
                items_data = []
                for item in order_items:
                    items_data.append({
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': float(item.product_price),
                        'total_price': float(item.subtotal)
                    })
                
                return JsonResponse({
                    'success': True,
                    'order': {
                        'order_id': order.order_number,
                        'buyer_name': order.customer_name,
                        'buyer_phone': order.customer_phone,
                        'buyer_email': order.customer_email,
                        'total_amount': float(order.total_amount),
                        'payment_method': 'Not specified',
                        'status': order.get_status_display(),
                        'created_at': order.created_at.isoformat(),
                        'items': items_data
                    }
                })
            
            # Search in PendingOrder by phone
            pending_orders = PendingOrder.objects.filter(buyer_phone__icontains=search_term)
            if pending_orders.exists():
                order = pending_orders.first()
                return JsonResponse({
                    'success': True,
                    'order': {
                        'order_id': order.order_id,
                        'buyer_name': order.buyer_name,
                        'buyer_phone': order.buyer_phone,
                        'buyer_email': order.buyer_email or '',
                        'total_amount': float(order.total_amount),
                        'payment_method': order.payment_method,
                        'status': order.get_status_display(),
                        'created_at': order.created_at.isoformat(),
                        'items': order.cart_items
                    }
                })
            
            # Search by customer name in Order
            orders = Order.objects.filter(customer_name__icontains=search_term)
            if orders.exists():
                order = orders.first()
                order_items = OrderItem.objects.filter(order=order)
                items_data = []
                for item in order_items:
                    items_data.append({
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': float(item.product_price),
                        'total_price': float(item.subtotal)
                    })
                
                return JsonResponse({
                    'success': True,
                    'order': {
                        'order_id': order.order_number,
                        'buyer_name': order.customer_name,
                        'buyer_phone': order.customer_phone,
                        'buyer_email': order.customer_email,
                        'total_amount': float(order.total_amount),
                        'payment_method': 'Not specified',
                        'status': order.get_status_display(),
                        'created_at': order.created_at.isoformat(),
                        'items': items_data
                    }
                })
            
            # Search in PendingOrder by name
            pending_orders = PendingOrder.objects.filter(buyer_name__icontains=search_term)
            if pending_orders.exists():
                order = pending_orders.first()
                return JsonResponse({
                    'success': True,
                    'order': {
                        'order_id': order.order_id,
                        'buyer_name': order.buyer_name,
                        'buyer_phone': order.buyer_phone,
                        'buyer_email': order.buyer_email or '',
                        'total_amount': float(order.total_amount),
                        'payment_method': order.payment_method,
                        'status': order.get_status_display(),
                        'created_at': order.created_at.isoformat(),
                        'items': order.cart_items
                    }
                })
            
            # No order found
            return JsonResponse({
                'success': False,
                'message': 'No order found with that search term'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error searching order: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

# Update the view_receipt function in website/api_views/orders.py


@csrf_exempt
def view_receipt(request, order_id):
    """View order receipt - search in both Order and PendingOrder models"""
    try:
        # Try to find in Order model first
        try:
            order = Order.objects.get(order_number=order_id)
            order_items = OrderItem.objects.filter(order=order)
            
            # Generate items HTML for regular Order
            items_html = ""
            total_items = 0
            for item in order_items:
                items_html += f"""
                <tr>
                    <td class="product-name">{item.product_name}</td>
                    <td class="text-center">{item.quantity}</td>
                    <td class="text-end">KSh {float(item.product_price):,.2f}</td>
                    <td class="text-end">KSh {float(item.subtotal):,.2f}</td>
                </tr>
                """
                total_items += item.quantity
            
            order_total = float(order.total_amount)
            customer_name = order.customer_name
            customer_phone = order.customer_phone
            customer_email = order.customer_email
            
        except Order.DoesNotExist:
            # Try to find in PendingOrder model
            order = PendingOrder.objects.get(order_id=order_id)
            cart_items = order.cart_items
            
            # Generate items HTML for PendingOrder
            items_html = ""
            total_items = 0
            for item in cart_items:
                quantity = item.get('quantity', 1)
                price = float(item.get('price', 0))
                subtotal = price * quantity
                items_html += f"""
                <tr>
                    <td class="product-name">{item.get('name', 'Product')}</td>
                    <td class="text-center">{quantity}</td>
                    <td class="text-end">KSh {price:,.2f}</td>
                    <td class="text-end">KSh {subtotal:,.2f}</td>
                </tr>
                """
                total_items += quantity
            
            order_total = float(order.total_amount)
            customer_name = order.buyer_name
            customer_phone = order.buyer_phone
            customer_email = order.buyer_email or ''
        
        # Check if we need multiple pages
        items_per_page = 12  # Adjust based on your font size
        num_items = total_items
        needs_multiple_pages = num_items > items_per_page
        
        # Generate beautiful receipt HTML with official styling
        receipt_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Fieldmax Receipt - {order_id}</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <style>
                :root {{
                    --primary-blue: #0066cc;
                    --primary-dark: #003366;
                    --primary-light: #e6f2ff;
                    --accent-green: #28a745;
                    --gray-light: #f8f9fa;
                    --gray-medium: #dee2e6;
                    --gray-dark: #6c757d;
                }}
                
                @page {{
                    size: A4;
                    margin: 15mm;
                }}
                
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    color: #333;
                    background: white;
                    font-size: 11pt;
                    line-height: 1.4;
                }}
                
                .receipt-page {{
                    width: 180mm;
                    min-height: 297mm;
                    margin: 0 auto;
                    background: white;
                    page-break-after: always;
                }}
                
                .receipt-page:last-child {{
                    page-break-after: avoid;
                }}
                
                .receipt-header {{
                    background: linear-gradient(135deg, var(--primary-blue) 0%, var(--primary-dark) 100%);
                    color: white;
                    padding: 15px 20px;
                    text-align: center;
                }}
                
                .logo-section {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }}
                
                .brand-logo {{
                    height: 50px;
                    width: auto;
                    border-radius: 5px;
                    border: 1px solid white;
                    background: white;
                }}
                
                .company-info {{
                    flex: 1;
                    text-align: left;
                }}
                
                .company-name {{
                    font-size: 1.5rem;
                    font-weight: 700;
                    margin-bottom: 3px;
                }}
                
                .company-tagline {{
                    font-size: 0.85rem;
                    opacity: 0.9;
                }}
                
                .receipt-title {{
                    background: rgba(255, 255, 255, 0.15);
                    padding: 10px;
                    border-radius: 5px;
                    margin-top: 10px;
                }}
                
                .receipt-title h1 {{
                    font-size: 1.3rem;
                    margin: 0;
                    font-weight: 700;
                }}
                
                .receipt-body {{
                    padding: 15px;
                }}
                
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 10px;
                    margin-bottom: 15px;
                    font-size: 10pt;
                }}
                
                .info-box {{
                    background: var(--primary-light);
                    border-radius: 5px;
                    padding: 10px;
                    border-left: 3px solid var(--primary-blue);
                }}
                
                .info-box h6 {{
                    color: var(--primary-dark);
                    font-weight: 700;
                    margin-bottom: 8px;
                    font-size: 10.5pt;
                }}
                
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 5px;
                    font-size: 9.5pt;
                }}
                
                .items-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    font-size: 10pt;
                }}
                
                .items-table thead {{
                    background: #000000;
                    color: white;
                }}
                
                .items-table th {{
                    padding: 8px 6px;
                    font-weight: 600;
                    font-size: 10pt;
                }}
                
                .items-table td {{
                    padding: 6px;
                    border-bottom: 1px solid var(--gray-medium);
                    font-size: 9.5pt;
                }}
                
                .items-table .product-name {{
                    max-width: 200px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}
                
                .total-row {{
                    background: var(--primary-light);
                    font-weight: 700;
                    font-size: 11pt;
                }}
                
                .payment-info {{
                    background: rgba(40, 167, 69, 0.05);
                    border-radius: 5px;
                    padding: 12px;
                    margin: 15px 0;
                    border-left: 3px solid var(--accent-green);
                    font-size: 9.5pt;
                }}
                
                .payment-info h6 {{
                    color: var(--primary-dark);
                    font-weight: 700;
                    margin-bottom: 8px;
                    font-size: 10.5pt;
                }}
                
                .terms-section {{
                    background: #fff9e6;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 15px 0;
                    font-size: 9pt;
                }}
                
                .terms-section h6 {{
                    color: var(--primary-dark);
                    font-weight: 700;
                    margin-bottom: 5px;
                    font-size: 10pt;
                }}
                
                .terms-list {{
                    list-style: none;
                    padding-left: 0;
                    margin-bottom: 0;
                }}
                
                .terms-list li {{
                    padding: 3px 0;
                    display: flex;
                    align-items: flex-start;
                    gap: 6px;
                }}
                
                .terms-list li i {{
                    color: #f59e0b;
                    font-size: 9pt;
                    margin-top: 2px;
                }}
                
                .footer-section {{
                    text-align: center;
                    padding: 15px;
                    background: var(--primary-light);
                    border-radius: 5px;
                    margin-top: 15px;
                    font-size: 10pt;
                }}
                
                .contact-info {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 10px;
                    margin-top: 10px;
                    font-size: 9pt;
                }}
                
                .contact-item {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 5px;
                }}
                
                /* Print specific styles */
                @media print {{
                    body {{
                        font-size: 10pt;
                        background: white;
                    }}
                    
                    .receipt-page {{
                        width: 100%;
                        min-height: 0;
                        margin: 0;
                        padding: 0;
                    }}
                    
                    .brand-logo {{
                        height: 40px;
                    }}
                    
                    .no-print {{
                        display: none !important;
                    }}
                    
                    /* Page break handling */
                    .page-break {{
                        page-break-before: always;
                    }}
                }}
                
                /* Mobile responsive */
                @media (max-width: 768px) {{
                    body {{
                        font-size: 10pt;
                        padding: 10px;
                    }}
                    
                    .receipt-page {{
                        width: 100%;
                        min-height: 0;
                    }}
                    
                    .logo-section {{
                        flex-direction: column;
                        text-align: center;
                    }}
                    
                    .company-info {{
                        text-align: center;
                    }}
                    
                    .contact-info {{
                        grid-template-columns: 1fr;
                        gap: 8px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="receipt-page">
                <!-- Header Section -->
                <div class="receipt-header">
                    <div class="logo-section">
                        <div class="company-info">
                            <div class="company-name">Fieldmax Electronics</div>
                            <div class="company-tagline">Quality Electronics & Professional Services</div>
                        </div>
                        <img src="/static/images/LOGO.jpg?v=2" alt="Fieldmax Logo" class="brand-logo" onerror="this.style.display='none';">
                    </div>
                    <div class="receipt-title">
                        <h1><i class="fas fa-file-invoice-dollar"></i> INVOICE / RECEIPT</h1>
                    </div>
                </div>
                
                <!-- Body Section -->
                <div class="receipt-body">
                    <!-- Invoice & Customer Info -->
                    <div class="info-grid">
                        <div class="info-box">
                            <h6><i class="fas fa-hashtag"></i> INVOICE DETAILS</h6>
                            <div class="info-row">
                                <span>Invoice No:</span>
                                <strong>{order_id}</strong>
                            </div>
                            <div class="info-row">
                                <span>Date:</span>
                                <span>{order.created_at.strftime('%d/%m/%Y')}</span>
                            </div>
                            <div class="info-row">
                                <span>Time:</span>
                                <span>{order.created_at.strftime('%I:%M %p')}</span>
                            </div>
                            <div class="info-row">
                                <span>Total Items:</span>
                                <span>{total_items}</span>
                            </div>
                        </div>
                        
                        <div class="info-box">
                            <h6><i class="fas fa-user-tie"></i> CUSTOMER INFO</h6>
                            <div class="info-row">
                                <span>Name:</span>
                                <strong>{customer_name}</strong>
                            </div>
                            <div class="info-row">
                                <span>Phone:</span>
                                <span>{customer_phone}</span>
                            </div>
                            <div class="info-row">
                                <span>Email:</span>
                                <span>{customer_email if customer_email else '-'}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Items Table -->
                    <h6 style="color: var(--primary-dark); margin-bottom: 10px;">
                        <i class="fas fa-shopping-basket"></i> ORDER ITEMS
                    </h6>
                    <table class="items-table">
                        <thead>
                            <tr>
                                <th>Description</th>
                                <th class="text-center">Qty</th>
                                <th class="text-end">Unit Price</th>
                                <th class="text-end">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                        <tfoot>
                            <tr class="total-row">
                                <td colspan="3" class="text-end"><strong>GRAND TOTAL:</strong></td>
                                <td class="text-end"><strong>KSh {order_total:,.2f}</strong></td>
                            </tr>
                        </tfoot>
                    </table>
                    
                    <!-- Payment Information -->
                    <div class="payment-info">
                        <h6><i class="fas fa-credit-card"></i> PAYMENT INSTRUCTIONS</h6>
                        <div class="info-row">
                            <span>M-PESA:</span>
                            <strong>56 27 132</strong>
                        </div>
                        <div class="info-row">
                            <span>Bank:</span>
                            <strong>Kenya Commercial Bank</strong>
                        </div>
                        <div class="info-row">
                            <span>Account:</span>
                            <strong>13311844320</strong>
                        </div>
                        <div class="info-row">
                            <span>Reference:</span>
                            <strong style="color: #155724;">{order_id}</strong>
                        </div>
                    </div>
                    
                    <!-- Terms & Conditions -->
                    <div class="terms-section">
                        <h6><i class="fas fa-file-contract"></i> TERMS & CONDITIONS</h6>
                        <ul class="terms-list">
                            <li><i class="fas fa-check-circle"></i> 1 year manufacturer warranty</li>
                            <li><i class="fas fa-check-circle"></i> Goods not returnable unless defective</li>
                            <li><i class="fas fa-check-circle"></i> All prices include VAT</li>
                        </ul>
                    </div>
                    
                    <!-- Footer -->
                    <div class="footer-section">
                        <h6 style="color: var(--primary-dark); margin-bottom: 8px;">
                            <i class="fas fa-heart" style="color: #e74c3c;"></i> THANK YOU FOR YOUR BUSINESS!
                        </h6>
                        <div class="contact-info">
                            <div class="contact-item">
                                <i class="fas fa-phone-alt"></i>
                                <span>0722 558 544</span>
                            </div>
                            <div class="contact-item">
                                <i class="fas fa-envelope"></i>
                                <span>fieldmaxsuppliers@gmail.com</span>
                            </div>
                            <div class="contact-item">
                                <i class="fas fa-globe-africa"></i>
                                <span>fieldmax.co.ke</span>
                            </div>
                        </div>
                        <p style="margin-top: 10px; font-style: italic; color: var(--primary-dark); font-size: 9.5pt;">
                            "Quality Electronics, Professional Service"
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return JsonResponse({
            'success': True,
            'receipt_html': receipt_html
        })
        
    except (Order.DoesNotExist, PendingOrder.DoesNotExist):
        return JsonResponse({
            'success': False,
            'message': 'Order not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error generating receipt: {str(e)}'
        })