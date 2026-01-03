from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from website.views import RoleBasedLoginView
from django.contrib.auth.views import LogoutView
from django.views.generic import TemplateView
from website.api_views.offline_sync import sync_offline_queue, get_offline_data

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('login/', RoleBasedLoginView.as_view(), name='login'),
    path('accounts/login/', RoleBasedLoginView.as_view()),  
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),

    # HTML ROUTES (Django Template Views)
    path('inventory/', include('inventory.urls')),
    path('sales/', include('sales.urls')),
    path('users/', include('users.urls')),

    # Main site
    path('', include('website.urls')),
    path('accounts/', include('django.contrib.auth.urls')),

    #offline
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('api/sync-offline-queue/', sync_offline_queue, name='sync_offline_queue'),
    path('api/offline-data/', get_offline_data, name='get_offline_data'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
