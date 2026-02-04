from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os

def passport_upload_path(instance, filename):
    # Upload to: staff_documents/passport/{application_id}/{filename}
    return f'staff_documents/passport/{instance.id}/{filename}'

def id_front_upload_path(instance, filename):
    return f'staff_documents/id_front/{instance.id}/{filename}'

def id_back_upload_path(instance, filename):
    return f'staff_documents/id_back/{instance.id}/{filename}'

class StaffApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('under_review', 'Under Review'),
    ]
    
    POSITION_CHOICES = [
        ('sales_assistant', 'Sales Officer'),
        ('cashier', 'Cashier Desk'),
        ('store_manager', 'Store Manager'),
        ('inventory_clerk', 'Inventory Clerk'),
        ('customer_service', 'Customer Care Service '),
        ('supervisor', 'Supervisor'),
        ('assistant_manager', 'Sales Manager'),
        ('security', 'Security Officer'),
        ('cleaner', 'Office Cleaner'),
    ]
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    id_number = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    
    # Application Details
    position = models.CharField(max_length=50, choices=POSITION_CHOICES)
    experience = models.TextField(blank=True)
    
    # Document Uploads
    passport_photo = models.ImageField(upload_to=passport_upload_path)
    id_front = models.ImageField(upload_to=id_front_upload_path)
    id_back = models.ImageField(upload_to=id_back_upload_path)
    
    # Status Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    application_date = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications')
    review_date = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Terms Acceptance
    terms_accepted = models.BooleanField(default=False)
    privacy_accepted = models.BooleanField(default=False)
    
    # System Fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='staff_applications'
    )
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_position_display()}"
    
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_status_badge(self):
        badges = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'under_review': 'info',
        }
        return badges.get(self.status, 'secondary')
    
    class Meta:
        ordering = ['-application_date']
        verbose_name = 'Staff Application'
        verbose_name_plural = 'Staff Applications'