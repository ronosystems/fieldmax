from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# REST API Router
router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category-api')
router.register(r'products', views.ProductViewSet, basename='product-api')
router.register(r'stock-entries', views.StockEntryViewSet, basename='stockentry-api')

app_name = 'inventory'

urlpatterns = [
    # ============================================
    # REST API ENDPOINTS
    # ============================================
    path('api/', include(router.urls)),
    
    # ====================================
    # CATEGORY URLS
    # ====================================
    path('api/get-categories/', views.get_categories_api, name='get-categories-api'),
    path('api/get-categories/', views.get_categories_api, name='get-categories'),
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('category/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    path('category/create/', views.CategoryCreateView.as_view(), name='category-create'),
    path('category/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-edit'),
    path('category/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),
    
    # ============================================
    # PRODUCT URLS
    # ============================================
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product-create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:pk>/edit/', views.ProductEditView.as_view(), name='product-edit'),
    path('products/<int:pk>/update/', views.ProductUpdateView.as_view(), name='product-update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product-delete'),
    path('print-labels/', views.print_labels_view, name='print_labels'),
    
    # ============================================
    # PRODUCT TRANSFER URLS (FIXED)
    # ============================================
    path('transfer/search/', views.product_transfer_search, name='product-transfer-search'),
    path('transfer/process/', views.product_transfer_process, name='product-transfer-process'),
    path('transfer/users/', views.get_transfer_users, name='get-transfer-users'),
    
    # ============================================
    # RESTOCK URLS
    # ============================================
    path('restock/', views.ProductRestockView.as_view(), name='product-restock'),
    path('restock/search/', views.search_product_for_restock, name='restock-search'),
    path('restock/process/', views.process_restock, name='restock-process'),
    
    # ============================================
    # PRODUCT LOOKUP (for POS/Sales)
    # ============================================
    path('lookup/', views.InventoryProductLookupView.as_view(), name='product-lookup'),
    
    # ============================================
    # STOCK ENTRY URLS
    # ============================================
    path('stock-entries/', views.StockEntryListView.as_view(), name='stockentry-list'),
    path('stock-entries/create/', views.StockEntryCreateView.as_view(), name='stockentry-create'),
    
    # ============================================
    # UTILITY URLS
    # ============================================
    path('get-product-by-sku/', views.get_product_by_sku, name='get-product-by-sku'),
    path('dashboard-stats/', views.dashboard_stats, name='dashboard-stats'),
]