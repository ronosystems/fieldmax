from django.contrib import admin
from .models import StaffApplication
from django.utils import timezone

@admin.register(StaffApplication)
class StaffApplicationAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'position', 'status', 'application_date']
    list_filter = ['status', 'position', 'application_date']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'id_number']
    readonly_fields = ['application_date', 'ip_address', 'user_agent']
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'id_number', 'address')
        }),
        ('Application Details', {
            'fields': ('position', 'experience', 'passport_photo', 'id_front', 'id_back')
        }),
        ('Status & Review', {
            'fields': ('status', 'reviewed_by', 'review_date', 'review_notes')
        }),
        ('Terms & System Info', {
            'fields': ('terms_accepted', 'privacy_accepted', 'application_date', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        return obj.full_name()
    full_name.short_description = 'Full Name'
    
    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data and form.cleaned_data['status'] != 'pending':
            obj.reviewed_by = request.user
            obj.review_date = timezone.now()
        super().save_model(request, obj, form, change)