from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from website.views import RoleBasedLoginView
from django.contrib.auth.views import LogoutView
from django.views.generic import TemplateView
from website.api_views.offline_sync import sync_offline_queue, get_offline_data



from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def create_superuser_once(request):
    """Debug version with detailed error reporting"""
    User = get_user_model()
    
    # Check database connection
    try:
        user_count = User.objects.count()
    except Exception as e:
        return HttpResponse(f"<h1>❌ Database Error</h1><p>{str(e)}</p>")
    
    # Check if superuser exists
    superuser_exists = User.objects.filter(is_superuser=True).exists()
    
    if superuser_exists:
        superusers = User.objects.filter(is_superuser=True).values_list('username', flat=True)
        return HttpResponse(
            f"<h1>ℹ️ Superuser Already Exists!</h1>"
            f"<p>Existing superusers: {', '.join(superusers)}</p>"
            f"<p>Go to <a href='/admin/'>/admin/</a> to login.</p>"
        )
    
    # Try to create superuser with detailed error info
    try:
        user = User.objects.create_superuser(
            username='FIELDMAX',
            email='fieldmaxsuppliers@gmail.com',
            password='Fsl#2026'
        )
        
        # Verify it was created
        if User.objects.filter(username='FIELDMAX', is_superuser=True).exists():
            return HttpResponse(
                "<h1>✅ Superuser Created Successfully!</h1>"
                "<p><strong>Username:</strong> FIELDMAX</p>"
                "<p><strong>Email:</strong> fieldmaxsuppliers@gmail.com</p>"
                "<p><strong>Password:</strong> Fsl#2026</p>"
                "<hr>"
                "<p>Go to <a href='/admin/'>/admin/</a> to login.</p>"
                "<hr>"
                "<p><strong>🔴 DELETE this URL from urls.py NOW!</strong></p>"
            )
        else:
            return HttpResponse(
                "<h1>⚠️ Warning</h1>"
                "<p>Command executed but user not found. Check database.</p>"
            )
            
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return HttpResponse(
            f"<h1>❌ Error Creating Superuser</h1>"
            f"<h3>Error Type: {type(e).__name__}</h3>"
            f"<p><strong>Message:</strong> {str(e)}</p>"
            f"<hr>"
            f"<h3>Full Traceback:</h3>"
            f"<pre>{error_detail}</pre>"
        )


# Also add a simple test endpoint
def test_db(request):
    """Test database connection"""
    try:
        User = get_user_model()
        user_count = User.objects.count()
        superuser_count = User.objects.filter(is_superuser=True).count()
        
        return JsonResponse({
            'status': 'success',
            'total_users': user_count,
            'superusers': superuser_count,
            'database': 'connected'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)




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
