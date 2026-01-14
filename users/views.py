from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets, permissions
from .serializers import UserSerializer
from .models import Profile, Role

User = get_user_model()




def get_roles_api(request):
    """API endpoint to get all roles"""
    roles = Role.objects.all().order_by('name')
    roles_data = [{'id': role.id, 'name': role.name} for role in roles]
    return JsonResponse({'roles': roles_data})

# ================================
# API VIEWS (DRF)
# ================================
class UserViewSet(viewsets.ModelViewSet):
    """DRF ViewSet for User API endpoints"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


# ================================
# JSON/API ENDPOINTS
# ================================
class GetUsersJSONView(View):
    """Returns JSON list of users for dropdowns"""
    def get(self, request):
        users = User.objects.all().values("id", "username", "first_name", "last_name")
        # Format for dropdown: full name if available, otherwise username
        user_list = [
            {
                "id": user["id"],
                "name": f"{user['first_name']} {user['last_name']}".strip() or user["username"]
            }
            for user in users
        ]
        return JsonResponse({"users": user_list})


# ================================
# CLASS-BASED VIEWS (Web UI)
# ================================
class UserListView(ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add statistics to context
        context['active_users_count'] = User.objects.filter(is_active=True).count()
        context['admin_count'] = Profile.objects.filter(role__name='Admin').count()
        context['manager_count'] = Profile.objects.filter(role__name='Manager').count()
        return context


class UserDetailView(DetailView):
    model = User
    template_name = 'users/user_detail.html'
    context_object_name = 'user'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure profile exists
        user = self.get_object()
        profile, created = Profile.objects.get_or_create(user=user)
        context['profile'] = profile
        return context


# In your views.py
class UserCreateView(CreateView):
    model = User
    template_name = 'admin/dashboard.html'  # Or whatever your dashboard template is
    fields = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    success_url = reverse_lazy('user-list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add flag to show user form section
        context['show_add_user'] = True
        return context
    
    def form_valid(self, form):
        # Handle password separately
        response = super().form_valid(form)
        password = self.request.POST.get('password')
        if password:
            self.object.set_password(password)
            self.object.save()
        
        # Create or update profile
        profile, created = Profile.objects.get_or_create(user=self.object)
        
        # Handle role assignment
        role_name = self.request.POST.get('role', '').strip()
        if role_name:
            try:
                role = Role.objects.get(name__iexact=role_name)
                profile.role = role
                profile.save()
            except Role.DoesNotExist:
                messages.warning(self.request, f'Role "{role_name}" not found')
        
        messages.success(self.request, f'User "{self.object.username}" created successfully!')
        return response



class UserUpdateView(UpdateView):
    model = User
    template_name = 'admin/dashboard.html'  # Same as above
    fields = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    success_url = reverse_lazy('user-list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_edit_user'] = True
        context['user_id'] = self.kwargs.get('pk')
        context['roles'] = Role.objects.all().order_by('name')  # 
        return context
    
    def form_valid(self, form):
        # Handle password update if provided
        password = self.request.POST.get('password')
        if password:
            self.object.set_password(password)
        
        response = super().form_valid(form)
        
        # Update profile
        profile = Profile.objects.get(user=self.object)
        role_name = self.request.POST.get('role', '').strip()
        if role_name:
            try:
                role = Role.objects.get(name__iexact=role_name)
                profile.role = role
            except Role.DoesNotExist:
                pass
        profile.save()
        
        messages.success(self.request, f'User "{self.object.username}" updated successfully!')
        return response


class UserDeleteView(DeleteView):
    model = User
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('user-list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, f'User deleted successfully!')
        return super().delete(request, *args, **kwargs)


# ================================
# FUNCTION-BASED VIEW (Dashboard Integration)
# ================================
# users/views.py
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.http import JsonResponse
from .models import Profile, Role

User = get_user_model()

@login_required
def user_add(request):
    """
    Handle user creation from dashboard (embedded form)
    """
    # Get all roles from database to pass to template
    roles = Role.objects.all().order_by('name')
    
    if request.method == 'POST':
        try:
            # Get form data
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            confirm_password = request.POST.get('confirm_password', '')
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            
            # Validation
            if not username:
                messages.error(request, 'Username is required')
                return redirect('/#add-user')
            
            if not password:
                messages.error(request, 'Password is required')
                return redirect('/#add-user')
            
            if password != confirm_password:
                messages.error(request, 'Passwords do not match')
                return redirect('/#add-user')
            
            if len(password) < 8:
                messages.error(request, 'Password must be at least 8 characters')
                return redirect('/#add-user')
            
            # Check if username exists
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" already exists')
                return redirect('/#add-user')
            
            # Check if email exists (if provided)
            if email and User.objects.filter(email=email).exists():
                messages.error(request, f'Email "{email}" is already in use')
                return redirect('/#add-user')
            
            # Create user
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email,
                is_active=request.POST.get('is_active') == 'on',
                is_staff=request.POST.get('is_staff') == 'on',
                is_superuser=request.POST.get('is_superuser') == 'on'
            )
            
            # Get or create profile
            profile, created = Profile.objects.get_or_create(user=user)
            
            # Update profile with role
            role_name = request.POST.get('role', '').strip()
            if role_name:
                try:
                    # Try to get the role by name (case-insensitive)
                    role = Role.objects.filter(name__iexact=role_name).first()
                    if role:
                        profile.role = role
                    else:
                        # If role doesn't exist, create it
                        role = Role.objects.create(name=role_name.lower())
                        profile.role = role
                        messages.info(request, f'New role "{role_name}" created automatically')
                except Exception as e:
                    messages.warning(request, f'Error setting role: {str(e)}')
            
            # Update other profile fields
            profile.phone_number = request.POST.get('phone_number', '').strip()
            profile.id_number = request.POST.get('id_number', '').strip()
            
            # Handle date of birth
            date_of_birth = request.POST.get('date_of_birth', '').strip()
            if date_of_birth:
                profile.date_of_birth = date_of_birth
            
            # Handle passport image upload
            if request.FILES.get('passport_image'):
                profile.passport_image = request.FILES['passport_image']
            
            profile.save()
            
            # Handle AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'User "{username}" created successfully!',
                    'user_id': user.id
                })
            
            # Regular form submission
            messages.success(request, f'✅ User "{username}" created successfully!')
            
            # Check which button was clicked
            if 'continue' in request.POST:
                # Save and add another - redirect back to add form
                return redirect('/#add-user')
            elif 'edit' in request.POST:
                # Save and continue editing - redirect to edit page
                return redirect('user-edit', pk=user.pk)
            else:
                # Regular save - redirect to users list in dashboard
                return redirect('/#users-list')
            
        except Exception as e:
            error_msg = f'❌ Error creating user: {str(e)}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('/#add-user')
    
    # GET request - redirect to dashboard add-user section
    # The roles will be fetched by the dashboard view
    return redirect('/#add-user')


# Keep this view for AJAX username availability check
# Add this URL: path('api/check-username/', check_username_availability, name='check-username'),
def check_username_availability(request):
    """API endpoint to check if username is available"""
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({'available': False})
    
    available = not User.objects.filter(username__iexact=username).exists()
    return JsonResponse({'available': available})