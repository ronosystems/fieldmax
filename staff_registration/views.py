from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import StaffApplication
from .forms import StaffApplicationForm
import json
from django.conf import settings  # Add this import


@csrf_exempt
def staff_registration_view(request):
    """Handle staff registration with file uploads - Updated for Render free tier"""
    
    # Since Render free tier doesn't support subdomains, we'll use the main domain
    # Remove subdomain check and allow access from main domain
    
    if request.method == 'POST':
        try:
            # Handle multipart form data (file uploads)
            if request.content_type == 'multipart/form-data':
                form = StaffApplicationForm(request.POST, request.FILES)
                
                if form.is_valid():
                    # Save application
                    application = form.save(commit=False)
                    
                    # Add metadata
                    application.ip_address = get_client_ip(request)
                    application.user_agent = request.META.get('HTTP_USER_AGENT', '')
                    
                    # Save to database
                    application.save()
                    
                    # Generate application ID
                    application_id = f"APP{application.id:06d}"
                    
                    # Prepare success response
                    response_data = {
                        'success': True,
                        'message': 'Application submitted successfully!',
                        'application_id': application_id,
                        'data': {
                            'name': f"{application.first_name} {application.last_name}",
                            'email': application.email,
                            'position': application.get_position_display(),
                            'application_date': application.application_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'status': application.get_status_display(),
                        },
                        'instructions': 'Your application is under review. You will be notified via email within 3-5 business days.'
                    }
                    
                    # TODO: Send confirmation email
                    # send_confirmation_email(application)
                    
                    return JsonResponse(response_data)
                else:
                    # Return form errors
                    errors = {}
                    for field, error_list in form.errors.items():
                        errors[field] = error_list[0] if error_list else 'Invalid value'
                    
                    return JsonResponse({
                        'success': False,
                        'error': 'Please correct the errors below.',
                        'errors': errors
                    }, status=400)
            
            # Handle JSON data (for testing)
            else:
                data = json.loads(request.body) if request.body else {}
                return JsonResponse({
                    'success': True,
                    'message': 'Application received (JSON mode)',
                    'data': data,
                    'note': 'In production, use multipart/form-data for file uploads.'
                })
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Registration error: {e}\n{error_details}")
            
            return JsonResponse({
                'success': False,
                'error': f'Server error: {str(e)}'
            }, status=500)
    
    # GET request - show the form
    form = StaffApplicationForm()
    host = request.get_host()
    context = {
        'form': form,
        'current_host': host,
        'is_production': not settings.DEBUG,  # Use DEBUG setting instead
    }
    
    # Try to render the template from different locations
    template_path = 'staff_registration/form.html'
    return render(request, template_path, context)


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_application_status(request, reference_id):
    """Check application status"""
    try:
        # Extract ID from reference (APP000001)
        app_id = int(reference_id.replace('APP', ''))
        application = StaffApplication.objects.get(id=app_id)
        
        return JsonResponse({
            'status': application.status,
            'status_display': application.get_status_display(),
            'name': application.full_name(),
            'position': application.get_position_display(),
            'application_date': application.application_date.strftime('%Y-%m-%d'),
            'review_date': application.review_date.strftime('%Y-%m-%d') if application.review_date else None,
            'review_notes': application.review_notes,
        })
    except (ValueError, StaffApplication.DoesNotExist):
        return JsonResponse({
            'error': 'Application not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)




@login_required
def staff_onboarding_view(request):
    """Main staff onboarding dashboard view"""
    
    # Get all applications
    all_applications = StaffApplication.objects.all()
    
    # Filter by status
    pending_applications = StaffApplication.objects.filter(status='pending')
    approved_applications = StaffApplication.objects.filter(status='approved')
    rejected_applications = StaffApplication.objects.filter(status='rejected')
    under_review = StaffApplication.objects.filter(status='under_review')
    
    # Today's date
    today = timezone.now().date()
    
    # Statistics
    pending_today = pending_applications.filter(application_date__date=today)
    pending_week = pending_applications.filter(
        application_date__gte=today - timedelta(days=7)
    )
    
    rejected_month = rejected_applications.filter(
        review_date__month=today.month,
        review_date__year=today.year
    )
    
    # Position counts
    sales_assistants = approved_applications.filter(position='sales_assistant')
    cashiers = approved_applications.filter(position='cashier')
    
    # Calculate conversion rate
    total_applications = all_applications.count()
    approved_count = approved_applications.count()
    conversion_rate = (approved_count / total_applications * 100) if total_applications > 0 else 0
    
    # Calculate average processing time
    avg_process_time = 2.5
    
    context = {
        # Applications
        'all_applications': all_applications,
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'under_review': under_review,
        
        # Statistics
        'pending_today': pending_today,
        'pending_week': pending_week,
        'rejected_month': rejected_month,
        'sales_assistants': sales_assistants,
        'cashiers': cashiers,
        'conversion_rate': conversion_rate,
        'avg_process_time': avg_process_time,
        
        # Choices for dropdown
        'position_choices': StaffApplication.POSITION_CHOICES,
    }
    
    # ⭐ CORRECTED - render the admin dashboard template
    return render(request, 'website/admin_dashboard.html', context)




@login_required
def application_details(request, pk):
    """Get application details as JSON"""
    try:
        application = StaffApplication.objects.get(pk=pk)
        data = {
            'full_name': application.full_name(),
            'email': application.email,
            'phone': application.phone,
            'id_number': application.id_number,
            'address': application.address,
            'position': application.get_position_display(),
            'experience': application.experience,
            'application_date': application.application_date.strftime('%Y-%m-%d %H:%M'),
            'status_display': application.get_status_display(),
            'status_badge': application.get_status_badge(),
            'reviewed_by': application.reviewed_by.get_full_name() if application.reviewed_by else None,
            'review_notes': application.review_notes,
            'passport_photo': application.passport_photo.url if application.passport_photo else '',
            'id_front': application.id_front.url if application.id_front else '',
            'id_back': application.id_back.url if application.id_back else '',
        }
        return JsonResponse(data)
    except StaffApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found'}, status=404)


@login_required
@require_POST
def approve_application(request, pk):
    """Approve a staff application"""
    try:
        application = StaffApplication.objects.get(pk=pk)
        application.status = 'approved'
        application.reviewed_by = request.user
        application.review_date = timezone.now()
        application.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Application for {application.full_name()} approved successfully!'
        })
    except StaffApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def reject_application(request, pk):
    """Reject a staff application"""
    try:
        data = json.loads(request.body)
        reason = data.get('reason', 'No reason provided')
        
        application = StaffApplication.objects.get(pk=pk)
        application.status = 'rejected'
        application.reviewed_by = request.user
        application.review_date = timezone.now()
        application.review_notes = reason
        application.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Application for {application.full_name()} rejected.'
        })
    except StaffApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def undo_approval(request, pk):
    """Undo approval and set back to pending"""
    try:
        application = StaffApplication.objects.get(pk=pk)
        application.status = 'pending'
        application.reviewed_by = None
        application.review_date = None
        application.review_notes = ''
        application.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Approval for {application.full_name()} has been undone.'
        })
    except StaffApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def reconsider_application(request, pk):
    """Reconsider a rejected application"""
    try:
        application = StaffApplication.objects.get(pk=pk)
        application.status = 'pending'
        application.reviewed_by = None
        application.review_date = None
        application.review_notes = ''
        application.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Application for {application.full_name()} moved back to pending for reconsideration.'
        })
    except StaffApplication.DoesNotExist:
        return JsonResponse({'error': 'Application not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def batch_approve(request):
    """Batch approve multiple applications"""
    try:
        data = json.loads(request.body)
        application_ids = data.get('application_ids', [])
        
        if not application_ids:
            return JsonResponse({'error': 'No applications selected'}, status=400)
        
        applications = StaffApplication.objects.filter(id__in=application_ids, status='pending')
        approved_count = 0
        
        for application in applications:
            application.status = 'approved'
            application.reviewed_by = request.user
            application.review_date = timezone.now()
            application.save()
            approved_count += 1
        
        return JsonResponse({
            'success': True,
            'approved_count': approved_count,
            'message': f'{approved_count} application(s) approved successfully!'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)