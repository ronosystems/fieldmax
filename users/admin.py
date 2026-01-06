# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Profile, Role

# Register Role admin so you can add roles
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

# Inline Profile in User admin
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    fk_name = 'user'
    fields = ('role', 'phone_number', 'id_number', 'date_of_birth', 'passport_image')

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    
    # Fields to display in the user list
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'get_phone', 'is_staff', 'is_active')
    
    # Add filters
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'profile__role')
    
    # Search fields
    search_fields = ('username', 'first_name', 'last_name', 'email', 'profile__phone_number', 'profile__id_number')
    
    def get_role(self, obj):
        """Display the user's role from their profile"""
        try:
            return obj.profile.role.name if obj.profile.role else "No Role"
        except Profile.DoesNotExist:
            return "No Profile"
    get_role.short_description = 'Role'
    
    def get_phone(self, obj):
        """Display the user's phone number"""
        try:
            return obj.profile.phone_number if obj.profile.phone_number else "-"
        except Profile.DoesNotExist:
            return "-"
    get_phone.short_description = 'Phone'

# Unregister the default User admin and register the customized one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Register Profile admin separately
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number', 'id_number', 'date_of_birth')
    list_filter = ('role',)
    search_fields = ('user__username', 'phone_number', 'id_number')