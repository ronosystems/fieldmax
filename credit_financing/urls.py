# ====================================
# CREDIT FINANCING URLS
# ====================================
from django.urls import path
from . import views

app_name = 'credit'

urlpatterns = [
    # Dashboard
    path('', views.credit_dashboard, name='dashboard'),
    
    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/create/', views.create_credit_transaction, name='create_transaction'),
    path('transactions/<int:pk>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/<int:pk>/confirm/', views.confirm_transaction, name='confirm_transaction'),
    path('transactions/<int:pk>/settle/', views.mark_as_settled, name='mark_settled'),
    
    # Settlements
    path('settlements/', views.settlements_list, name='settlements_list'),
    
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    
    # Reports
    path('reports/', views.credit_reports, name='reports'),
    
    # API endpoints
    path('api/customer/<int:customer_id>/', views.get_customer_info, name='api_customer_info'),
    path('api/product/<int:product_id>/', views.get_product_price, name='api_product_price'),
]