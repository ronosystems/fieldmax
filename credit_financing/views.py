# ====================================
# CREDIT FINANCING VIEWS
# Simplified for your business: You add companies, give phones to customers, companies pay you
# ====================================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal
from datetime import date, timedelta
import json
import logging
from .models import (
    CreditCompany,
    CreditCustomer,
    CreditTransaction,
    CompanyPayment,
    CreditTransactionLog
)
from inventory.models import Product





logger = logging.getLogger(__name__)




# ====================================
# DASHBOARD VIEW (Main page with all sections) - SHOW ALL DATA
# ====================================
@login_required
def credit_dashboard(request):
    """
    Main dashboard showing overview of all credit transactions
    Shows ALL data in the system (admin view)
    """
    # Get all transactions in the system (not filtered by dealer)
    all_transactions = CreditTransaction.objects.all()
    
    # Statistics - based on ALL transactions
    stats = {
        'total_transactions': all_transactions.count(),
        'pending_count': all_transactions.filter(payment_status='pending').count(),
        'paid_count': all_transactions.filter(payment_status='paid').count(),
        'total_credit_value': all_transactions.aggregate(
            Sum('ceiling_price')
        )['ceiling_price__sum'] or Decimal('0.00'),
        'total_pending_amount': all_transactions.filter(
            payment_status='pending'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00'),
        'total_paid_amount': all_transactions.filter(
            payment_status='paid'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00'),
    }
    
    # Recent transactions - from ALL dealers
    recent_transactions = all_transactions.select_related(
        'customer', 'product', 'credit_company', 'dealer'
    ).order_by('-transaction_date')[:10]
    
    # Company breakdown - based on ALL transactions
    company_breakdown = CreditCompany.objects.filter(
        is_active=True
    ).annotate(
        pending_count=Count('transactions', filter=Q(transactions__payment_status='pending')),
        paid_count=Count('transactions', filter=Q(transactions__payment_status='paid')),
        pending_amount=Sum('transactions__ceiling_price', filter=Q(transactions__payment_status='pending')),
        paid_amount=Sum('transactions__ceiling_price', filter=Q(transactions__payment_status='paid')),
    ).order_by('-pending_amount')
    
    # Get ALL companies in the system
    companies = CreditCompany.objects.all()
    print(f"ALL Companies in system: {companies.count()}")  # Debug in console
    
    # Get ALL customers in the system
    customers = CreditCustomer.objects.all()
    print(f"ALL Customers in system: {customers.count()}")  # Debug in console
    
    # Get ALL transactions (already have all_transactions)
    transactions = all_transactions.select_related('customer', 'credit_company', 'dealer')
    
    # Filter transactions by status
    pending_transactions = transactions.filter(payment_status='pending')
    paid_transactions = transactions.filter(payment_status='paid')
    
    # Get ALL payments in the system
    payments = CompanyPayment.objects.all().select_related('credit_company', 'created_by')
    
    # Get ALL available products
    products = Product.objects.filter(quantity__gt=0).select_related('category')
    
    # Calculate totals
    pending_total = pending_transactions.aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00')
    paid_total = paid_transactions.aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00')
    
    context = {
        'stats': stats,
        'recent_transactions': recent_transactions,
        'company_breakdown': company_breakdown,
        'companies': companies,
        'customers': customers,
        'transactions': transactions,
        'pending_transactions': pending_transactions,
        'paid_transactions': paid_transactions,
        'payments': payments,
        'products': products,
        'pending_total': pending_total,
        'paid_total': paid_total,
        'companies_count': companies.count(),
        'customers_count': customers.count(),
        'payments_count': payments.count(),
    }
    
    return render(request, 'credit_financing/credit_dashboard.html', context)







# ====================================
# COMPANY MANAGEMENT
# ====================================
@login_required
def add_company(request):
    """
    Add a new credit company
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        contact_person = request.POST.get('contact_person', '')
        payment_terms = request.POST.get('payment_terms', '')
        address = request.POST.get('address', '')
        
        if not name or not email:
            messages.error(request, 'Name and email are required')
            return redirect('credit:dashboard#add-company')
        
        try:
            company = CreditCompany.objects.create(
                name=name,
                email=email,
                phone=phone,
                contact_person=contact_person,
                payment_terms=payment_terms,
                address=address,
                created_by=request.user,
                is_active=True
            )
            messages.success(request, f'Company "{name}" added successfully!')
            return redirect('credit:dashboard')
        except Exception as e:
            messages.error(request, f'Error adding company: {str(e)}')
            return redirect('credit:dashboard')
    
    return redirect('credit:dashboard')


@login_required
def edit_company(request, company_id):
    """
    Edit company details
    """
    company = get_object_or_404(CreditCompany, id=company_id, created_by=request.user)
    
    if request.method == 'POST':
        company.name = request.POST.get('name', company.name)
        company.email = request.POST.get('email', company.email)
        company.phone = request.POST.get('phone', company.phone)
        company.contact_person = request.POST.get('contact_person', company.contact_person)
        company.payment_terms = request.POST.get('payment_terms', company.payment_terms)
        company.address = request.POST.get('address', company.address)
        company.is_active = request.POST.get('is_active') == 'on'
        company.save()
        
        messages.success(request, f'Company "{company.name}" updated successfully!')
        return redirect('credit:dashboard')
    
    return redirect('credit:dashboard')


# ====================================
# CUSTOMER MANAGEMENT
# ====================================
# ====================================
# CUSTOMER MANAGEMENT - FIXED WITH BETTER ERROR HANDLING
# ====================================
@login_required
def add_customer(request):
    """
    Add a new customer with AJAX support
    """
    if request.method == 'POST':
        try:
            # Get form data with proper defaults and stripping
            full_name = request.POST.get('full_name', '').strip()
            id_number = request.POST.get('id_number', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            email = request.POST.get('email', '').strip()
            alternate_phone = request.POST.get('alternate_phone', '').strip()
            county = request.POST.get('county', '').strip()
            town = request.POST.get('town', '').strip()
            nok_name = request.POST.get('nok_name', '').strip()
            nok_phone = request.POST.get('nok_phone', '').strip()
            
            # Debug print
            print(f"=== ADD CUSTOMER DEBUG ===")
            print(f"Full Name: '{full_name}'")
            print(f"ID Number: '{id_number}'")
            print(f"Phone: '{phone_number}'")
            print(f"Email: '{email}'")
            print(f"NOK Name: '{nok_name}'")
            print(f"NOK Phone: '{nok_phone}'")
            print(f"==========================")
            
            # Validate required fields
            if not full_name:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': 'Full name is required'
                    })
                messages.error(request, 'Full name is required')
                return redirect('credit:dashboard')
            
            if not id_number:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': 'ID number is required'
                    })
                messages.error(request, 'ID number is required')
                return redirect('credit:dashboard')
            
            if not phone_number:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': 'Phone number is required'
                    })
                messages.error(request, 'Phone number is required')
                return redirect('credit:dashboard')
            
            # Check for duplicate ID number
            if CreditCustomer.objects.filter(id_number=id_number).exists():
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'Customer with ID number {id_number} already exists'
                    })
                messages.error(request, f'Customer with ID number {id_number} already exists')
                return redirect('credit:dashboard')
            
            # Create customer
            customer = CreditCustomer.objects.create(
                full_name=full_name,
                id_number=id_number,
                phone_number=phone_number,
                email=email,
                alternate_phone=alternate_phone,
                county=county,
                town=town,
                nok_name=nok_name,
                nok_phone=nok_phone,
                created_by=request.user,
                is_active=True
            )
            
            print(f"✅ Customer created successfully! ID: {customer.id}")
            
            # If AJAX request, return JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'customer': {
                        'id': customer.id,
                        'full_name': customer.full_name,
                        'id_number': customer.id_number,
                        'phone_number': customer.phone_number,
                    },
                    'message': f'Customer "{full_name}" added successfully!'
                })
            
            messages.success(request, f'Customer "{full_name}" added successfully!')
            
            # Check if this is from agent dashboard
            referer = request.META.get('HTTP_REFERER', '')
            if 'agent' in referer:
                return redirect('credit:agent_dashboard')
            return redirect('credit:dashboard')
            
        except Exception as e:
            print(f"❌ Error adding customer: {str(e)}")
            import traceback
            traceback.print_exc()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': f'Error adding customer: {str(e)}'
                })
            
            messages.error(request, f'Error adding customer: {str(e)}')
            
            # Check if this is from agent dashboard
            referer = request.META.get('HTTP_REFERER', '')
            if 'agent' in referer:
                return redirect('credit:agent_dashboard')
            return redirect('credit:dashboard')
    
    return redirect('credit:dashboard')


@login_required
def customer_detail(request, pk):
    """
    View customer details and their transactions
    """
    customer = get_object_or_404(CreditCustomer, pk=pk, created_by=request.user)
    
    # Get customer's transactions
    transactions = customer.transactions.select_related(
        'product', 'credit_company'
    ).order_by('-transaction_date')
    
    # Statistics
    stats = {
        'total_transactions': transactions.count(),
        'pending_transactions': transactions.filter(payment_status='pending').count(),
        'paid_transactions': transactions.filter(payment_status='paid').count(),
        'total_credit': transactions.aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00'),
    }
    
    context = {
        'customer': customer,
        'transactions': transactions,
        'stats': stats,
    }
    
    return render(request, 'credit_financing/customer_detail.html', context)


# ====================================
# ====================================
# CREDIT TRANSACTION MANAGEMENT - UPDATED WITH ETR
# ====================================
@login_required
def create_transaction(request):
    """
    Create new credit transaction - when you give phone to customer
    Supports both regular POST and AJAX requests
    Now includes ETR number in response
    """
    if request.method == 'POST':
        try:
            # Get form data
            company_id = request.POST.get('credit_company')
            customer_id = request.POST.get('customer')
            product_id = request.POST.get('product')
            ceiling_price = request.POST.get('ceiling_price')
            imei = request.POST.get('imei', '')
            company_reference = request.POST.get('company_reference', '')
            notes = request.POST.get('notes', '')
            
            # Validate required fields
            if not company_id or not customer_id or not product_id or not ceiling_price:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': 'Please select company, customer, product and enter ceiling price'
                    })
                messages.error(request, 'Please select company, customer, product and enter ceiling price')
                return redirect('credit:dashboard')
            
            # Convert ceiling price to Decimal
            try:
                ceiling_price = Decimal(ceiling_price)
            except:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Invalid ceiling price'})
                messages.error(request, 'Invalid ceiling price')
                return redirect('credit:dashboard')
            
            # Get company - allow any company
            try:
                company = CreditCompany.objects.get(id=company_id)
            except CreditCompany.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Company not found'})
                messages.error(request, 'Company not found')
                return redirect('credit:dashboard')
            
            # Get customer (must belong to this user)
            try:
                customer = CreditCustomer.objects.get(id=customer_id, created_by=request.user)
            except CreditCustomer.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Customer not found or does not belong to you'})
                messages.error(request, 'Customer not found')
                return redirect('credit:dashboard')
            
            # CRITICAL: Check product availability with a lock to prevent race conditions
            from django.db import transaction as db_transaction
            
            with db_transaction.atomic():
                # Select the product for update (locks it until transaction completes)
                # Ensure product belongs to this user
                try:
                    product = Product.objects.select_for_update().get(
                        id=product_id,
                        owner=request.user  # Only products owned by this user
                    )
                except Product.DoesNotExist:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False, 
                            'error': 'Product not found or does not belong to you'
                        })
                    messages.error(request, 'Product not found or does not belong to you')
                    return redirect('credit:dashboard')
                
                # Check if product is available
                if product.status != 'available' or product.quantity < 1:
                    error_msg = f'Product "{product.name}" is not available. Status: {product.get_status_display()}'
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': error_msg})
                    messages.error(request, error_msg)
                    return redirect('credit:dashboard')
                
                # Check if product already has a pending credit transaction
                existing_transaction = CreditTransaction.objects.filter(
                    product=product,
                    payment_status='pending'
                ).exists()
                
                if existing_transaction:
                    error_msg = f'Product "{product.name}" already has a pending credit transaction and cannot be used again.'
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': error_msg})
                    messages.error(request, error_msg)
                    return redirect('credit:dashboard')
                
                # Check for duplicate submission (last 10 seconds)
                from django.utils import timezone
                from datetime import timedelta
                
                recent_cutoff = timezone.now() - timedelta(seconds=10)
                recent_duplicate = CreditTransaction.objects.filter(
                    credit_company=company,
                    customer=customer,
                    product=product,
                    ceiling_price=ceiling_price,
                    dealer=request.user,
                    created_at__gte=recent_cutoff
                ).exists()
                
                if recent_duplicate:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False, 
                            'error': 'Duplicate transaction detected. Please check if the transaction was already created.'
                        })
                    messages.warning(request, 'Duplicate transaction detected')
                    return redirect('credit:dashboard')
                
                # ============================================
                # CREATE TRANSACTION - NOW AUTO-GENERATES SALE ID AND ETR
                # ============================================
                transaction = CreditTransaction.objects.create(
                    credit_company=company,
                    customer=customer,
                    dealer=request.user,
                    product=product,
                    product_name=product.name,
                    product_code=product.product_code,
                    imei=imei or product.sku_value or '',
                    ceiling_price=ceiling_price,
                    company_reference=company_reference,
                    notes=notes,
                    payment_status='pending'
                )
                
                # Update product status to sold/unavailable
                if hasattr(product, 'status'):
                    product.status = 'sold'
                
                # Decrease quantity
                if product.quantity > 0:
                    product.quantity -= 1
                
                product.save()
                
                # Create stock entry
                from inventory.models import StockEntry
                StockEntry.objects.create(
                    product=product,
                    quantity=-1,
                    entry_type='sale',
                    unit_price=ceiling_price,
                    total_amount=ceiling_price,
                    reference_id=transaction.transaction_id,
                    notes=f'Credit sale - {customer.full_name} via {company.name}',
                    created_by=request.user
                )
                
                # Create transaction log
                CreditTransactionLog.objects.create(
                    transaction=transaction,
                    action='created',
                    performed_by=request.user,
                    notes=f'Transaction created for {customer.full_name} with {company.name}'
                )
                
                # Log the ETR generation
                logger.info(
                    f"[CREDIT TRANSACTION] Created: {transaction.transaction_id} | "
                    f"ETR: {transaction.etr_number} | "
                    f"Product: {product.product_code} | "
                    f"Customer: {customer.full_name}"
                )
                
                # If AJAX request, return JSON for receipt with ETR number
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    transaction_data = {
                        'id': transaction.id,
                        'transaction_id': transaction.transaction_id,
                        'etr_number': transaction.etr_number,  # Add ETR number
                        'customer_name': customer.full_name,
                        'customer_phone': customer.phone_number,
                        'customer_id_number': customer.id_number,
                        'customer_nok_name': customer.nok_name or '',
                        'customer_nok_phone': customer.nok_phone or '',
                        'product_name': product.name,
                        'product_sku': product.sku_value or '',
                        'imei': imei or product.sku_value or '',
                        'ceiling_price': str(ceiling_price),
                        'dealer_name': request.user.get_full_name() or request.user.username,
                        'company_name': company.name,
                    }
                    
                    return JsonResponse({
                        'success': True,
                        'transaction': transaction_data,
                        'message': f'Transaction {transaction.transaction_id} created successfully! ETR: {transaction.etr_number}'
                    })
                
                messages.success(
                    request,
                    f'Transaction {transaction.transaction_id} created successfully! '
                    f'ETR: {transaction.etr_number} | '
                    f'Company {company.name} owes you KSH {ceiling_price:,.2f}'
                )
                
                # Check if this is from agent dashboard
                referer = request.META.get('HTTP_REFERER', '')
                if 'agent' in referer:
                    return redirect('credit:agent_dashboard')
                return redirect('credit:dashboard')
            
        except CreditCompany.DoesNotExist:
            error_msg = 'Invalid credit company selected'
        except CreditCustomer.DoesNotExist:
            error_msg = 'Invalid customer selected'
        except Product.DoesNotExist:
            error_msg = 'Invalid product selected'
        except Exception as e:
            error_msg = f'Error creating transaction: {str(e)}'
            import traceback
            traceback.print_exc()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        
        messages.error(request, error_msg)
        
        # Check if this is from agent dashboard
        referer = request.META.get('HTTP_REFERER', '')
        if 'agent' in referer:
            return redirect('credit:agent_dashboard')
        return redirect('credit:dashboard')
    
    return redirect('credit:dashboard')






@login_required
def transaction_detail(request, pk):
    """
    View transaction details
    """
    transaction = get_object_or_404(
        CreditTransaction.objects.select_related(
            'customer', 'product', 'credit_company', 'dealer'
        ),
        pk=pk,
        dealer=request.user
    )
    
    # Get logs
    logs = transaction.logs.select_related('performed_by').all()
    
    # Get related payments
    payments = transaction.company_payments.all()
    
    context = {
        'transaction': transaction,
        'logs': logs,
        'payments': payments,
    }
    
    return render(request, 'credit_financing/transaction_detail.html', context)


@login_required
def mark_transaction_paid(request, pk):
    """
    Mark a single transaction as paid (when company pays for one phone)
    """
    transaction = get_object_or_404(
        CreditTransaction,
        pk=pk,
        dealer=request.user
    )
    
    if request.method == 'POST':
        try:
            payment_ref = request.POST.get('payment_reference', '')
            
            transaction.mark_as_paid(
                payment_ref=payment_ref,
                paid_by=request.user
            )
            
            messages.success(
                request,
                f'Transaction {transaction.transaction_id} marked as paid!'
            )
        except Exception as e:
            messages.error(request, f'Error marking as paid: {str(e)}')
    
    return redirect('credit:dashboard#transactions')


@login_required
def cancel_transaction(request, pk):
    """
    Cancel a transaction
    """
    transaction = get_object_or_404(
        CreditTransaction,
        pk=pk,
        dealer=request.user
    )
    
    if request.method == 'POST':
        try:
            reason = request.POST.get('reason', '')
            transaction.cancel(reason=reason, cancelled_by=request.user)
            
            # Return product to inventory
            product = transaction.product
            product.quantity += 1
            product.status = 'available'
            product.save()
            
            messages.success(request, f'Transaction {transaction.transaction_id} cancelled')
        except Exception as e:
            messages.error(request, f'Error cancelling transaction: {str(e)}')
    
    return redirect('credit:dashboard#transactions')


# ====================================
# COMPANY PAYMENTS (Bulk payments)
# ====================================
@login_required
def create_payment(request):
    """
    Record a bulk payment from a company (for multiple transactions)
    """
    if request.method == 'POST':
        try:
            company_id = request.POST.get('credit_company')
            amount = Decimal(request.POST.get('amount'))
            payment_method = request.POST.get('payment_method')
            payment_reference = request.POST.get('payment_reference')
            payment_date = request.POST.get('payment_date', date.today().isoformat())
            transaction_ids = request.POST.getlist('transactions')
            
            if not transaction_ids:
                messages.error(request, 'Please select at least one transaction')
                return redirect('credit:dashboard#create-payment')
            
            company = CreditCompany.objects.get(id=company_id, created_by=request.user)
            
            # Create payment record
            payment = CompanyPayment.objects.create(
                credit_company=company,
                amount=amount,
                payment_method=payment_method,
                payment_reference=payment_reference,
                payment_date=payment_date,
                created_by=request.user
            )
            
            # Add transactions and mark them as paid
            total_amount = Decimal('0.00')
            for trans_id in transaction_ids:
                transaction = CreditTransaction.objects.get(
                    id=trans_id,
                    dealer=request.user,
                    credit_company=company,
                    payment_status='pending'
                )
                payment.transactions.add(transaction)
                total_amount += transaction.ceiling_price
                transaction.mark_as_paid(
                    payment_ref=payment_reference,
                    paid_by=request.user
                )
            
            # Verify amount matches
            if total_amount != amount:
                messages.warning(
                    request, 
                    f'Payment recorded but amount mismatch! '
                    f'Selected transactions total: KSH {total_amount:,.2f}, '
                    f'Payment amount: KSH {amount:,.2f}'
                )
            
            messages.success(
                request,
                f'Payment of KSH {amount:,.2f} from {company.name} recorded successfully! '
                f'{len(transaction_ids)} transactions marked as paid.'
            )
            return redirect('credit:dashboard#payments')
            
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
            return redirect('credit:dashboard#create-payment')
    
    return redirect('credit:dashboard#create-payment')


@login_required
def payment_detail(request, pk):
    """
    View payment details
    """
    payment = get_object_or_404(
        CompanyPayment.objects.select_related('credit_company', 'created_by'),
        pk=pk,
        created_by=request.user
    )
    
    # Get transactions in this payment
    transactions = payment.transactions.select_related('customer', 'product').all()
    
    context = {
        'payment': payment,
        'transactions': transactions,
    }
    
    return render(request, 'credit_financing/payment_detail.html', context)


# ====================================
# REPORTS
# ====================================
@login_required
def reports(request):
    """
    Generate reports for credit financing
    """
    # Default to last 30 days
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
    
    # Summary metrics
    metrics = {
        'total_transactions': transactions.count(),
        'total_value': transactions.aggregate(
            Sum('ceiling_price')
        )['ceiling_price__sum'] or Decimal('0.00'),
        
        'pending_count': transactions.filter(payment_status='pending').count(),
        'pending_value': transactions.filter(
            payment_status='pending'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00'),
        
        'paid_count': transactions.filter(payment_status='paid').count(),
        'paid_value': transactions.filter(
            payment_status='paid'
        ).aggregate(Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00'),
    }
    
    # Company breakdown
    company_breakdown = transactions.values(
        'credit_company__name'
    ).annotate(
        count=Count('id'),
        total=Sum('ceiling_price'),
        pending=Sum('ceiling_price', filter=Q(payment_status='pending')),
        paid=Sum('ceiling_price', filter=Q(payment_status='paid'))
    ).order_by('-total')
    
    # Monthly trend
    monthly_data = transactions.extra(
        select={'month': "EXTRACT(month FROM transaction_date)"}
    ).values('month').annotate(
        count=Count('id'),
        total=Sum('ceiling_price')
    ).order_by('month')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'metrics': metrics,
        'company_breakdown': company_breakdown,
        'monthly_data': monthly_data,
        'transactions': transactions.select_related(
            'customer', 'product', 'credit_company'
        ).order_by('-transaction_date')[:50],
    }
    
    return render(request, 'credit_financing/reports.html', context)


# ====================================
# API ENDPOINTS (AJAX)
# ====================================
@login_required
def get_customer_info(request, customer_id):
    """
    Get customer information via AJAX
    """
    customer = get_object_or_404(CreditCustomer, pk=customer_id, created_by=request.user)
    
    data = {
        'id': customer.id,
        'full_name': customer.full_name,
        'id_number': customer.id_number,
        'phone': customer.phone_number,
    }
    
    return JsonResponse(data)


@login_required
def get_product_info(request, product_id):
    """
    Get product information via AJAX
    """
    product = get_object_or_404(Product, pk=product_id)
    
    data = {
        'id': product.id,
        'name': product.name,
        'product_code': product.product_code,
        'selling_price': str(product.selling_price),
        'quantity': product.quantity,
    }
    
    return JsonResponse(data)


@login_required
def get_company_pending_transactions(request, company_id):
    """
    Get pending transactions for a specific company (for payment form)
    """
    transactions = CreditTransaction.objects.filter(
        dealer=request.user,
        credit_company_id=company_id,
        payment_status='pending'
    ).select_related('customer').order_by('-transaction_date')
    
    data = {
        'transactions': [
            {
                'id': t.id,
                'transaction_id': t.transaction_id,
                'customer_name': t.customer.full_name,
                'ceiling_price': str(t.ceiling_price),
                'date': t.transaction_date.strftime('%Y-%m-%d'),
            }
            for t in transactions
        ],
        'total_amount': str(transactions.aggregate(
            Sum('ceiling_price'))['ceiling_price__sum'] or Decimal('0.00'))
    }
    
    return JsonResponse(data)



# ====================================
# API ENDPOINT FOR RECEIPT DATA - FIXED FOR CR FORMAT
# ====================================
@login_required
def get_receipt_data(request, transaction_id):
    """
    Get transaction data for receipt generation
    Handles both CR-YYYYMMDD-XXXX and #SALE-XXXX formats
    """
    try:
        print(f"=== GET RECEIPT DATA ===")
        print(f"Transaction ID: {transaction_id}")
        print(f"User: {request.user.username}")
        
        # Try to find the transaction by exact transaction_id first
        try:
            transaction = CreditTransaction.objects.select_related(
                'customer', 'product', 'credit_company', 'dealer'
            ).get(
                transaction_id=transaction_id
            )
            print(f"✅ Found transaction by exact ID: {transaction.transaction_id}")
        except CreditTransaction.DoesNotExist:
            # If not found, try to find by the numeric part (for #SALE-XXXX format)
            # Extract the numeric part if it exists
            if '-' in transaction_id:
                parts = transaction_id.split('-')
                numeric_part = parts[-1]  # Get the last part
                
                # Try to find by transaction_id ending with this number
                transaction = CreditTransaction.objects.filter(
                    transaction_id__endswith=numeric_part
                ).first()
                
                if transaction:
                    print(f"✅ Found transaction by numeric part: {transaction.transaction_id}")
                else:
                    print(f"❌ Transaction not found with ID: {transaction_id}")
                    return JsonResponse({
                        'success': False, 
                        'error': f'Transaction {transaction_id} not found'
                    }, status=404)
            else:
                print(f"❌ Transaction not found with ID: {transaction_id}")
                return JsonResponse({
                    'success': False, 
                    'error': f'Transaction {transaction_id} not found'
                }, status=404)
        
        # Calculate ETR number (use the numeric part of the transaction ID)
        # For CR-20260215-0001, ETR would be 0001
        etr_number = "0000"
        if transaction.transaction_id:
            parts = transaction.transaction_id.split('-')
            if len(parts) > 0:
                etr_number = parts[-1]  # Take the last part as ETR
        
        # Prepare data with safe access to all fields
        data = {
            'transaction_id': transaction.transaction_id,
            'etr_number': etr_number,
            'customer_name': transaction.customer.full_name if transaction.customer else 'Unknown',
            'customer_phone': transaction.customer.phone_number if transaction.customer else '',
            'customer_id_number': transaction.customer.id_number if transaction.customer else '',
            'customer_nok_name': transaction.customer.nok_name if transaction.customer and transaction.customer.nok_name else '',
            'customer_nok_phone': transaction.customer.nok_phone if transaction.customer and transaction.customer.nok_phone else '',
            'product_name': transaction.product_name or (transaction.product.name if transaction.product else 'Unknown'),
            'product_sku': transaction.product.sku_value if transaction.product else '',
            'imei': transaction.imei or '',
            'ceiling_price': str(transaction.ceiling_price),
            'dealer_name': transaction.dealer.get_full_name() or transaction.dealer.username if transaction.dealer else 'System',
            'company_name': transaction.credit_company.name if transaction.credit_company else 'Unknown',
            'date': transaction.transaction_date.strftime('%d/%m/%Y') if transaction.transaction_date else '',
            'time': transaction.transaction_date.strftime('%H:%M:%S') if transaction.transaction_date else '',
        }
        
        print(f"✅ Data prepared successfully")
        print(f"   ETR Number: {data['etr_number']}")
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)