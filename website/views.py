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



logger = logging.getLogger(__name__)



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




def home(request):
    return render(request, 'website/home.html')




@login_required
def cashier_dashboard(request):
    """
    Cashier Dashboard View
    Renders the cashier interface for processing sales
    """
    return render(request, 'website/cashier_dashboard.html')




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
    
    context["total_products"] = total_products

    # Total product value (quantity × selling price)
    context["total_product_value"] = Product.objects.filter(is_active=True).aggregate(
        total=Sum(F('quantity') * F('selling_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')

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
# HELPER FUNCTION: Fix Inconsistent Statuses
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
# DEBUGGING VIEW (Optional - for development)
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