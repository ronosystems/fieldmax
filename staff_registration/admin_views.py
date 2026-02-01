from django.shortcuts import render, get_object_or_404, redirect 
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone 
from django.contrib import messages
from .models import StaffApplication

def is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Admin dashboard to view and process applications"""
    pending_applications = StaffApplication.objects.filter(status='pending')
    approved_applications = StaffApplication.objects.filter(status='approved')[:10]
    rejected_applications = StaffApplication.objects.filter(status='rejected')[:10]
    
    context = {
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'total_pending': pending_applications.count(),
    }
    return render(request, 'staff_registration/admin_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def approve_application(request, application_id):
    """Approve a staff application"""
    application = get_object_or_404(StaffApplication, id=application_id)
    
    if request.method == 'POST':
        application.status = 'approved'
        application.approved_by = request.user
        application.approval_date = timezone.now()
        application.save()
        
        # TODO: Send approval email
        # TODO: Create user account if needed
        
        messages.success(request, f'Application from {application.full_name} has been approved.')
        return redirect('staff_admin_dashboard')
    
    return render(request, 'staff_registration/review_application.html', {'application': application})

@login_required
@user_passes_test(is_admin)
def reject_application(request, application_id):
    """Reject a staff application"""
    application = get_object_or_404(StaffApplication, id=application_id)
    
    if request.method == 'POST':
        application.status = 'rejected'
        application.rejection_reason = request.POST.get('rejection_reason', '')
        application.save()
        
        # TODO: Send rejection email
        messages.warning(request, f'Application from {application.full_name} has been rejected.')
        return redirect('staff_admin_dashboard')
    
    return render(request, 'staff_registration/reject_application.html', {'application': application})