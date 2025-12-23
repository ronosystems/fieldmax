# website/urls.py
from django.urls import path
from .views import (
    RoleBasedLoginView,
    admin_dashboard,
    manager_dashboard,
    agent_dashboard,
    cashier_dashboard,
    home,
    shopping_cart,
    validate_cart,
    pending_orders_count,
)
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    # ============================================
    # HOME & PRODUCTS
    # ============================================
    path('', home, name='home'),
    path('products/', views.products_page, name='products_page'),

    # ============================================
    # API ENDPOINTS FOR HOME PAGE
    # ============================================
    path('api/featured-products/', views.api_featured_products, name='api-featured-products'),
    path('api/home-stats/', views.api_home_stats, name='api-home-stats'),
    path('api/categories/', views.api_product_categories, name='api-categories'),
    path('api/quick-search/', views.api_quick_search, name='api-quick-search'),
    
    # ============================================
    # SHOPPING CART & CHECKOUT
    # ============================================
    path('shop/', views.shop_view, name='shop'),
    path('cart/', shopping_cart, name='shopping-cart'),
    path('api/validate-cart/', validate_cart, name='validate-cart'),
    path('checkout/', views.checkout_page, name='checkout'),
    path('order-success/', views.order_success, name='order-success'),

    # ============================================
    # PENDING ORDERS SYSTEM
    # ============================================
    # Customer submits order
    path('api/pending-orders/create/', views.create_pending_order, name='create-pending-order'),
    path('api/pending-orders-count/', pending_orders_count, name='pending_orders_count'),
    
    # Staff views and actions
    path('staff/pending-orders/', views.pending_orders_list, name='pending-orders-list'),
    path('staff/approve-order/<str:order_id>/', views.approve_order, name='approve-order'),
    path('staff/reject-order/<str:order_id>/', views.reject_order, name='reject-order'),
    
    # API for badge count
    path('api/pending-orders/count/', views.pending_orders_count, name='pending-orders-count'),

    # ============================================
    # AUTHENTICATION
    # ============================================
    path('login/', RoleBasedLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    
    # ============================================
    # DASHBOARDS
    # ============================================
    path('admin-dashboard/', admin_dashboard, name='admin-dashboard'),
    path('manager-dashboard/', manager_dashboard, name='manager-dashboard'),
    path('agent-dashboard/', agent_dashboard, name='agent-dashboard'),
    path('cashier-dashboard/', cashier_dashboard, name='cashier-dashboard'),
]