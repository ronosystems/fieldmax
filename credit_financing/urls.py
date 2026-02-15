# credit_financing/urls.py
from django.urls import path
from . import views

app_name = 'credit'

urlpatterns = [
    # Dashboard (main page with all sections)
    path('', views.credit_dashboard, name='dashboard'),
    path('<str:section>/', views.credit_dashboard, name='dashboard_section'),
    
    # Form submissions (POST only)
    path('companies/add/', views.add_company, name='add_company'),
    path('companies/<int:company_id>/edit/', views.edit_company, name='edit_company'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('transactions/create/', views.create_transaction, name='create_transaction'),
    path('transactions/<int:pk>/mark-paid/', views.mark_transaction_paid, name='mark_transaction_paid'),
    path('transactions/<int:pk>/cancel/', views.cancel_transaction, name='cancel_transaction'),
    path('payments/create/', views.create_payment, name='create_payment'),
    
    # Detail views (if you still want separate pages)
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('transactions/<int:pk>/', views.transaction_detail, name='transaction_detail'),
    path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
    
    # API endpoints
    path('api/company/<int:company_id>/pending-transactions/', 
         views.get_company_pending_transactions, 
         name='company_pending_transactions'),
    path('api/customer/<int:customer_id>/', views.get_customer_info, name='get_customer_info'),
    path('api/product/<int:product_id>/', views.get_product_info, name='get_product_info'),
    path('api/receipt/<str:transaction_id>/', views.get_receipt_data, name='get_receipt_data'),
]