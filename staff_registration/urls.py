# staff_registration/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Public registration (accessible at /staff/)
    path('', views.staff_registration_view, name='staff_registration'),
    
    # Application status check
    path('status/<str:reference_id>/', views.check_application_status, name='check_application_status'),
    
    # Admin dashboard (login required, accessible at /staff/admin/)
    path('admin/', views.staff_onboarding_view, name='staff_admin'),
    
    # API endpoints for admin dashboard (all require login)
    path('api/application/<int:pk>/', views.application_details, name='application_details'),
    path('api/approve/<int:pk>/', views.approve_application, name='approve_application'),
    path('api/reject/<int:pk>/', views.reject_application, name='reject_application'),
    path('api/undo-approval/<int:pk>/', views.undo_approval, name='undo_approval'),
    path('api/reconsider/<int:pk>/', views.reconsider_application, name='reconsider_application'),
    path('api/batch-approve/', views.batch_approve, name='batch_approve'),
]