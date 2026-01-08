# users/views.py
from rest_framework import viewsets
from django.contrib.auth.models import User
from .serializers import UserSerializer  # Make sure you have this
from .models import Role
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView





# ================================
# GET USERS 
# ================================
User = get_user_model()

def get_users_as_json(request):
    """
    Returns a JSON list of all users for transfer dropdown.
    """
    users = User.objects.all()
    user_list = [{"id": user.id, "name": user.get_full_name() or user.username} for user in users]
    return JsonResponse({"users": user_list})







class GetUsersJSONView(View):
    def get(self, request):
        users = User.objects.all().values("id", "username")
        return JsonResponse({"users": list(users)}, safe=False)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserListView(ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'


class UserDetailView(DetailView):
    model = User
    template_name = 'users/user_detail.html'
    context_object_name = 'user'


class UserCreateView(CreateView):
    model = User
    template_name = 'users/user_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'password']
    success_url = reverse_lazy('user-list')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()
        
        return super().form_valid(form)


class UserUpdateView(UpdateView):
    model = User
    template_name = 'users/user_form.html'
    fields = ['username', 'email', 'is_staff', 'is_active']
    success_url = reverse_lazy('user-list')


class UserDeleteView(DeleteView):
    model = User
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('user-list')




def user_management_view(request):
    """
    View to display all users with their profiles and statistics
    """
    # Get all users with related profile data
    users = User.objects.select_related('profile', 'profile__role').all()
    
    # Calculate statistics
    active_users_count = users.filter(is_active=True).count()
    
    # Count users by role
    admin_count = users.filter(profile__role__name='Admin').count()
    manager_count = users.filter(profile__role__name='Manager').count()
    
    context = {
        'users': users,
        'active_users_count': active_users_count,
        'admin_count': admin_count,
        'manager_count': manager_count,
    }
    
    return render(request, 'users', context)