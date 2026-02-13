# ====================================
# CREDIT FINANCING VIEWS
# ====================================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal
from datetime import date, timedelta

from .models import (
    CreditPartner,
    CreditCustomer,
    CreditTransaction,
    CustomerInstallment,
    DealerSettlement,
    CreditTransactionLog
)
from inventory.models import Product


# ====================================
# DASHBOARD VIEW
# ====================================
@login_required
def credit_dashboard(request):
    """
    Main dashboard for credit financing overview
    """
    # Get all credit transactions
    all_transactions = CreditTransaction.objects.filter(dealer=request.user)
    
    # Statistics
    stats = {
        'total_transactions': all_transactions.count(),
        'pending_confirmation': all_transactions.filter(status='pending').count(),
        'active_credit': all_transactions.filter(status__in=['confirmed', 'active']).count(),
        'settled_transactions': all_transactions.filter(status='settled').count(),
        
        # Financial stats
        'total_credit_value': all_transactions.filter(
            status__in=['confirmed', 'active', 'settled']
        ).aggregate(Sum('phone_price'))['phone_price__sum'] or Decimal('0.00'),
        
        'pending_settlement': all_transactions.filter(
            status__in=['confirmed', 'active']
        ).aggregate(Sum('phone_price'))['phone_price__sum'] or Decimal('0.00'),
        
        'settled_amount': all_transactions.filter(
            status='settled'
        ).aggregate(Sum('phone_price'))['phone_price__sum'] or Decimal('0.00'),
        
        # Overdue settlements
        'overdue_count': sum(1 for t in all_transactions if t.is_overdue),
    }
    
    # Recent transactions
    recent_transactions = all_transactions.select_related(
        'customer',
        'product',
        'credit_partner'
    ).order_by('-created_at')[:10]
    
    # Overdue settlements
    overdue_transactions = [
        t for t in all_transactions.filter(status__in=['confirmed', 'active'])
        if t.is_overdue
    ]
    
    # Partner breakdown
    partner_stats = CreditPartner.objects.filter(
        is_active=True
    ).annotate(
        transaction_count=Count('transactions'),
        total_value=Sum('transactions__phone_price')
    ).order_by('-total_value')
    
    context = {
        'stats': stats,
        'recent_transactions': recent_transactions,
        'overdue_transactions': overdue_transactions,
        'partner_stats': partner_stats,
    }
    
    return render(request, 'credit_financing/credit_finance.html', context)


# ====================================
# CREATE CREDIT TRANSACTION
# ====================================
@login_required
def create_credit_transaction(request):
    """
    Create new credit transaction when giving phone to customer
    """
    if request.method == 'POST':
        try:
            # Get form data
            product_id = request.POST.get('product')
            customer_id = request.POST.get('customer')
            partner_id = request.POST.get('credit_partner')
            
            phone_price = Decimal(request.POST.get('phone_price'))
            customer_total = Decimal(request.POST.get('customer_total'))
            installment_amount = Decimal(request.POST.get('installment_amount'))
            installment_period = int(request.POST.get('installment_period'))
            
            partner_reference = request.POST.get('partner_reference', '')
            notes = request.POST.get('notes', '')
            
            # Get objects
            product = Product.objects.get(id=product_id)
            customer = CreditCustomer.objects.get(id=customer_id)
            partner = CreditPartner.objects.get(id=partner_id)
            
            # Calculate commission
            if partner.commission_type == 'percentage':
                commission = phone_price * (partner.commission_rate / 100)
            else:
                commission = partner.commission_rate
            
            # Create transaction
            transaction = CreditTransaction.objects.create(
                credit_partner=partner,
                customer=customer,
                dealer=request.user,
                product=product,
                phone_price=phone_price,
                customer_total=customer_total,
                partner_commission=commission,
                installment_amount=installment_amount,
                installment_period=installment_period,
                partner_reference=partner_reference,
                notes=notes,
            )
            
            # Create installment schedule
            _create_installment_schedule(transaction)
            
            # Update product status
            product.status = 'sold'
            product.quantity = 0
            product.save()
            
            # Log creation
            CreditTransactionLog.objects.create(
                credit_transaction=transaction,
                action='created',
                new_status='pending',
                performed_by=request.user,
                notes='Transaction created'
            )
            
            messages.success(
                request,
                f'Credit transaction {transaction.transaction_id} created successfully!'
            )
            return redirect('credit:transaction_detail', pk=transaction.id)
            
        except Exception as e:
            messages.error(request, f'Error creating transaction: {str(e)}')
    
    # GET request - show form
    context = {
        'products': Product.objects.filter(
            status='available',
            category__is_single_item=True
        ),
        'customers': CreditCustomer.objects.filter(is_active=True),
        'partners': CreditPartner.objects.filter(is_active=True),
    }
    
    return render(request, 'credit_financing/create_transaction.html', context)


def _create_installment_schedule(transaction):
    """
    Create installment schedule for customer
    """
    from dateutil.relativedelta import relativedelta
    
    current_date = date.today()
    
    for i in range(1, transaction.installment_period + 1):
        due_date = current_date + relativedelta(months=i)
        
        CustomerInstallment.objects.create(
            credit_transaction=transaction,
            installment_number=i,
            amount=transaction.installment_amount,
            due_date=due_date,
            status='pending'
        )


# ====================================
# TRANSACTION DETAIL VIEW
# ====================================
@login_required
def transaction_detail(request, pk):
    """
    View detailed information about a credit transaction
    """
    transaction = get_object_or_404(
        CreditTransaction.objects.select_related(
            'customer',
            'product',
            'credit_partner',
            'dealer'
        ),
        pk=pk,
        dealer=request.user
    )
    
    # Get installments
    installments = transaction.installments.all()
    
    # Get logs
    logs = transaction.logs.select_related('performed_by').all()
    
    # Calculate installment stats
    installment_stats = {
        'total': installments.count(),
        'paid': installments.filter(status='paid').count(),
        'pending': installments.filter(status='pending').count(),
        'late': installments.filter(status='late').count(),
    }
    
    context = {
        'transaction': transaction,
        'installments': installments,
        'logs': logs,
        'installment_stats': installment_stats,
    }
    
    return render(request, 'credit_financing/transaction_detail.html', context)


# ====================================
# CONFIRM TRANSACTION
# ====================================
@login_required
def confirm_transaction(request, pk):
    """
    Confirm transaction when Company X verifies customer took phone
    """
    transaction = get_object_or_404(
        CreditTransaction,
        pk=pk,
        dealer=request.user
    )
    
    if request.method == 'POST':
        try:
            transaction.confirm_transaction(confirmed_by=request.user)
            
            # Log confirmation
            CreditTransactionLog.objects.create(
                credit_transaction=transaction,
                action='confirmed',
                old_status='pending',
                new_status='confirmed',
                performed_by=request.user,
                notes='Transaction confirmed by Company X'
            )
            
            messages.success(
                request,
                f'Transaction {transaction.transaction_id} confirmed! '
                f'Expected settlement: {transaction.expected_settlement_date}'
            )
        except Exception as e:
            messages.error(request, f'Error confirming transaction: {str(e)}')
    
    return redirect('credit:transaction_detail', pk=pk)


# ====================================
# MARK AS SETTLED
# ====================================
@login_required
def mark_as_settled(request, pk):
    """
    Mark transaction as settled when Company X pays you
    """
    transaction = get_object_or_404(
        CreditTransaction,
        pk=pk,
        dealer=request.user
    )
    
    if request.method == 'POST':
        try:
            settlement_date = request.POST.get('settlement_date')
            settlement_reference = request.POST.get('settlement_reference', '')
            
            transaction.mark_as_settled(
                settlement_date=settlement_date,
                settlement_reference=settlement_reference,
                settled_by=request.user  # Pass the user who marked it settled
            )
            
            # Log settlement
            CreditTransactionLog.objects.create(
                credit_transaction=transaction,
                action='settled',
                old_status=transaction.status,
                new_status='settled',
                performed_by=request.user,
                notes=f'Settled with reference: {settlement_reference}'
            )
            
            messages.success(
                request,
                f'Transaction {transaction.transaction_id} marked as settled! '
                f'StockEntry has been created in inventory.'
            )
        except Exception as e:
            messages.error(request, f'Error settling transaction: {str(e)}')
    
    return redirect('credit:transaction_detail', pk=pk)


# ====================================
# TRANSACTION LIST VIEW
# ====================================
@login_required
def transaction_list(request):
    """
    List all credit transactions with filters
    """
    transactions = CreditTransaction.objects.filter(
        dealer=request.user
    ).select_related('customer', 'product', 'credit_partner')
    
    # Filters
    status_filter = request.GET.get('status')
    partner_filter = request.GET.get('partner')
    search = request.GET.get('search')
    
    if status_filter:
        transactions = transactions.filter(status=status_filter)
    
    if partner_filter:
        transactions = transactions.filter(credit_partner_id=partner_filter)
    
    if search:
        transactions = transactions.filter(
            Q(transaction_id__icontains=search) |
            Q(customer__full_name__icontains=search) |
            Q(customer__id_number__icontains=search) |
            Q(product__name__icontains=search)
        )
    
    # Order by latest
    transactions = transactions.order_by('-created_at')
    
    context = {
        'transactions': transactions,
        'partners': CreditPartner.objects.filter(is_active=True),
        'status_choices': CreditTransaction.STATUS_CHOICES,
    }
    
    return render(request, 'credit_financing/transaction_list.html', context)


# ====================================
# SETTLEMENTS VIEW
# ====================================
@login_required
def settlements_list(request):
    """
    View all settlements from credit partners
    """
    settlements = DealerSettlement.objects.select_related(
        'credit_partner'
    ).prefetch_related('transactions').order_by('-payment_date')
    
    # Filter by partner
    partner_filter = request.GET.get('partner')
    if partner_filter:
        settlements = settlements.filter(credit_partner_id=partner_filter)
    
    context = {
        'settlements': settlements,
        'partners': CreditPartner.objects.filter(is_active=True),
    }
    
    return render(request, 'credit_financing/settlements_list.html', context)


# ====================================
# CUSTOMER MANAGEMENT
# ====================================
@login_required
def customer_list(request):
    """
    List all credit customers
    """
    customers = CreditCustomer.objects.select_related(
        'credit_partner'
    ).annotate(
        transaction_count=Count('credit_transactions')
    ).order_by('-created_at')
    
    # Search
    search = request.GET.get('search')
    if search:
        customers = customers.filter(
            Q(full_name__icontains=search) |
            Q(id_number__icontains=search) |
            Q(phone__icontains=search)
        )
    
    context = {
        'customers': customers,
    }
    
    return render(request, 'credit_financing/customer_list.html', context)


@login_required
def customer_detail(request, pk):
    """
    View customer details and transaction history
    """
    customer = get_object_or_404(
        CreditCustomer.objects.select_related('credit_partner'),
        pk=pk
    )
    
    # Get customer's transactions
    transactions = customer.credit_transactions.select_related(
        'product',
        'credit_partner'
    ).order_by('-created_at')
    
    # Statistics
    stats = {
        'total_transactions': transactions.count(),
        'active_transactions': transactions.filter(
            status__in=['confirmed', 'active']
        ).count(),
        'total_credit_value': transactions.filter(
            status__in=['confirmed', 'active', 'settled']
        ).aggregate(Sum('phone_price'))['phone_price__sum'] or Decimal('0.00'),
    }
    
    context = {
        'customer': customer,
        'transactions': transactions,
        'stats': stats,
    }
    
    return render(request, 'credit_financing/customer_detail.html', context)


# ====================================
# REPORTS VIEW
# ====================================
@login_required
def credit_reports(request):
    """
    Generate reports for credit financing
    """
    # Date range
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = date.fromisoformat(request.GET.get('start_date'))
    if request.GET.get('end_date'):
        end_date = date.fromisoformat(request.GET.get('end_date'))
    
    # Get transactions in date range
    transactions = CreditTransaction.objects.filter(
        dealer=request.user,
        transaction_date__date__range=[start_date, end_date]
    )
    
    # Calculate metrics
    metrics = {
        'total_transactions': transactions.count(),
        'total_value': transactions.aggregate(
            Sum('phone_price')
        )['phone_price__sum'] or Decimal('0.00'),
        
        'settled_count': transactions.filter(status='settled').count(),
        'settled_value': transactions.filter(
            status='settled'
        ).aggregate(Sum('phone_price'))['phone_price__sum'] or Decimal('0.00'),
        
        'pending_count': transactions.filter(
            status__in=['pending', 'confirmed', 'active']
        ).count(),
        'pending_value': transactions.filter(
            status__in=['pending', 'confirmed', 'active']
        ).aggregate(Sum('phone_price'))['phone_price__sum'] or Decimal('0.00'),
    }
    
    # Partner breakdown
    partner_breakdown = transactions.values(
        'credit_partner__name'
    ).annotate(
        count=Count('id'),
        total=Sum('phone_price')
    ).order_by('-total')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'metrics': metrics,
        'partner_breakdown': partner_breakdown,
        'transactions': transactions.select_related(
            'customer',
            'product',
            'credit_partner'
        ).order_by('-transaction_date'),
    }
    
    return render(request, 'credit_financing/reports.html', context)


# ====================================
# API ENDPOINTS (for AJAX)
# ====================================
@login_required
def get_customer_info(request, customer_id):
    """
    Get customer information via AJAX
    """
    customer = get_object_or_404(CreditCustomer, pk=customer_id)
    
    data = {
        'id': customer.id,
        'full_name': customer.full_name,
        'id_number': customer.id_number,
        'phone': customer.phone,
        'credit_limit': str(customer.credit_limit),
        'outstanding_credit': str(customer.outstanding_credit),
        'available_credit': str(customer.available_credit),
    }
    
    return JsonResponse(data)


@login_required
def get_product_price(request, product_id):
    """
    Get product price via AJAX
    """
    product = get_object_or_404(Product, pk=product_id)
    
    data = {
        'id': product.id,
        'name': product.name,
        'product_code': product.product_code,
        'selling_price': str(product.selling_price),
    }
    
    return JsonResponse(data)