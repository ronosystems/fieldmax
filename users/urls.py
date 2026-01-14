# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    UserViewSet, 
    GetUsersJSONView,
    user_add,  # Function-based view
    UserListView,
    UserDetailView, 
    UserUpdateView, 
    UserDeleteView
    # REMOVE UserCreateView from imports
)

router = DefaultRouter()
router.register(r'api/users', UserViewSet, basename='user-api')

urlpatterns = [
    # API endpoints (DRF)
    path('api/', include(router.urls)),
    
    # JSON endpoint for dropdowns
    path('api/get-users/', GetUsersJSONView.as_view(), name='get-users-json'),
    path('api/roles/', views.get_roles_api, name='get-roles-api'),
    
    # Web UI endpoints
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/add/', user_add, name='user-add'),  # Function-based view
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user-edit'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user-delete'),
]