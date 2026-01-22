from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from website.views import RoleBasedLoginView
from django.contrib.auth.views import LogoutView
from django.views.generic import TemplateView
from website.api_views.offline_sync import sync_offline_queue, get_offline_data
from django.http import HttpResponse
import json


def serve_manifest(request):
    manifest_data = {
        "name": "FieldMax",
        "short_name": "FieldMax",
        "description": "Inventory & Sales Management System",
        "start_url": "/",
        "display": "standalone", 
        "background_color": "#ffffff",
        "theme_color": "#0066cc",
        "icons": [
            {"src": "/static/icons/icon-72x72.png", "sizes": "72x72", "type": "image/png"},
            {"src": "/static/icons/icon-96x96.png", "sizes": "96x96", "type": "image/png"},
            {"src": "/static/icons/icon-128x128.png", "sizes": "128x128", "type": "image/png"},
            {"src": "/static/icons/icon-144x144.png", "sizes": "144x144", "type": "image/png"},
            {"src": "/static/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-384x384.png", "sizes": "384x384", "type": "image/png"},
            {"src": "/static/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }
    return HttpResponse(json.dumps(manifest_data), content_type='application/json')


urlpatterns = [
    # Manifest
    path('manifest.json', serve_manifest, name='manifest'),
    
    # Admin
    path('admin/', admin.site.urls),

    # ============================================
    # AUTHENTICATION - CUSTOM OVERRIDES
    # ============================================
    # Your custom login view (MUST come before django.contrib.auth.urls)
    path('login/', RoleBasedLoginView.as_view(), name='login'),
    path('accounts/login/', RoleBasedLoginView.as_view()),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),

    # ============================================
    # AUTHENTICATION - DJANGO DEFAULTS
    # ============================================
    # path('accounts/password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    # path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    # path('accounts/password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),

    # ============================================
    # APP ROUTES
    # ============================================
    path('inventory/', include('inventory.urls')),
    path('sales/', include('sales.urls')),
    path('users/', include('users.urls')),
    path('', include('website.urls')),

    # ============================================
    # OFFLINE SUPPORT
    # ============================================
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('api/sync-offline-queue/', sync_offline_queue, name='sync_offline_queue'),
    path('api/offline-data/', get_offline_data, name='get_offline_data'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)