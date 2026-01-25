# sales/urls.py - FIXED VERSION

from django.urls import path
from . import views, api, api_views
from .views import (
    SaleListView,
    SaleDetailView,
    SaleCreateView,
    SaleUpdateView,
    RestockView,
    SaleDeleteView,
    SaleReverseView,
    ProductLookupView,
    ClientLookupView,
    sale_etr_view,
    download_receipt_view,
)

app_name = 'sales'

urlpatterns = [
    # ============================================
    # LIVE SEARCH ENDPOINTS (MOVE TO TOP)
    # ============================================
    path('product-search/', views.product_search, name='product_search'),  
    path('record-sale/', views.record_sale, name='record_sale'),     
    
    # Product Lookup (existing)
    path('product-lookup/', views.ProductLookupView.as_view(), name='product-lookup'),
    path('client-lookup/', views.ClientLookupView.as_view(), name='client-lookup'),
    path('api/get-sellers/', views.get_sellers, name='get-sellers'),

    # Sale CRUD
    path('create/', views.SaleCreateView.as_view(), name='sale-create'),
    path('sale/<str:sale_id>/update/', views.SaleUpdateView.as_view(), name='sale-update'),
    path('sale/<str:sale_id>/delete/', views.SaleDeleteView.as_view(), name='sale-delete'),

    # Restock
    path('product/<int:product_id>/restock/', views.RestockView.as_view(), name='sale-restock'),

    # Receipts / ETR
    path('receipt/<str:sale_id>/', views.sale_receipt_view, name='sale-receipt'),
    path('sale/<str:sale_id>/etr/', views.sale_etr_view, name='sale-etr'),
    path('sale/<str:sale_id>/download/', views.download_receipt_view, name='download-receipt'),

    # Reversal endpoints
    path('sale/<str:sale_id>/', views.SaleDetailView.as_view(), name='sale-detail'),
    path("reverse/<str:sale_id>/", SaleReverseView.as_view(), name="reverse-sale"),

    # ============================================
    # BATCH SALE ENDPOINTS
    # ============================================
    path('batch-create/', 
         views.BatchSaleCreateView.as_view(), 
         name='batch-sale-create'),

     # Batch receipt view
    path('fieldmax-receipt/<str:batch_id>/', 
         views.batch_receipt_view, 
         name='fieldmax-receipt'),
    
    # Optional: Download batch receipt as PDF
    path('fieldmax-receipt/<str:batch_id>/download/', 
         views.download_batch_receipt_view, 
         name='download-fieldmax-receipt'),

    # Report APIs
    path('api/reports/', views.sales_report_api, name='sales-report-api'),
    path('api/get-sellers/', views.get_sellers_api, name='get-sellers-api'),
    path('api/get-all-sellers/', views.get_all_sellers_api, name='get-all-sellers-api'),
    path('api/recent-sales/', api.recent_sales, name='api-recent-sales'),

    # API Endpoints
    path('api/sales-list/', api_views.sales_list_api, name='sales-list-api'),
    path('api/recent-sales/', api_views.recent_sales_api, name='recent-sales-api'),
]
