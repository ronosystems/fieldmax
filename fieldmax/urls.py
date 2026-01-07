from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from website.views import RoleBasedLoginView
from django.contrib.auth.views import LogoutView
from django.views.generic import TemplateView
from website.api_views.offline_sync import sync_offline_queue, get_offline_data
# Add at the top after your imports
from django.http import HttpResponse
from django.contrib.auth import get_user_model

def create_superuser_once(request):
    User = get_user_model()
    
    if User.objects.filter(is_superuser=True).exists():
        return HttpResponse(
            "<h1>Superuser already exists!</h1>"
            "<p>Go to <a href='/admin/'>/admin/</a> to login.</p>"
        )
    
    try:
        User.objects.create_superuser(
            username='FIELDMAX',
            email='fieldmaxsuppliers@gmail.com',
            password='Fsl#2026'
        )
        
        return HttpResponse(
            "<h1>✅ Superuser Created Successfully!</h1>"
            "<p><strong>Username:</strong> FIELDMAX</p>"
            "<p><strong>Email:</strong> fieldmaxsuppliers@gmail.com</p>"
            "<p><strong>Password:</strong> Fsl#2026</p>"
            "<p>Go to <a href='/admin/'>/admin/</a> to login.</p>"
            "<hr>"
            "<p><strong>🔴 DELETE THIS URL FROM urls.py NOW!</strong></p>"
        )
    except Exception as e:
        return HttpResponse(f"<h1>❌ Error:</h1><p>{str(e)}</p>")



urlpatterns = [
    path('admin/', admin.site.urls),
    path('setup-admin-now/', create_superuser_once),

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
