from django.urls import path
from . import api_views

app_name = 'staff_registration_api'

urlpatterns = [
    # Statistics
    path('statistics/', api_views.staff_statistics_api, name='staff_statistics'),
    
    # Applications
    path('pending/', api_views.pending_applications_api, name='pending_applications'),
    path('approved/', api_views.approved_staff_api, name='approved_staff'),
    path('rejected/', api_views.rejected_applications_api, name='rejected_applications'),
    path('analytics/', api_views.application_analytics_api, name='application_analytics'),
    
    # Individual application operations
    path('application/<int:application_id>/', api_views.application_detail_api, name='application_detail'),
    path('application/<int:application_id>/approve/', api_views.approve_application_api, name='approve_application'),
    path('application/<int:application_id>/reject/', api_views.reject_application_api, name='reject_application'),
]