from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import timedelta
from .models import StaffApplication
import json

@login_required
@require_GET
def staff_statistics_api(request):
    """Get staff onboarding statistics"""
    try:
        # Calculate dates
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Get counts
        pending_count = StaffApplication.objects.filter(status='pending').count()
        approved_count = StaffApplication.objects.filter(status='approved').count()
        rejected_count = StaffApplication.objects.filter(status='rejected').count()
        total_applications = StaffApplication.objects.count()
        
        # Get pending breakdown
        pending_today = StaffApplication.objects.filter(
            status='pending',
            application_date__date=today
        ).count()
        
        pending_week = StaffApplication.objects.filter(
            status='pending',
            application_date__date__gte=week_ago
        ).count()
        
        pending_month = StaffApplication.objects.filter(
            status='pending',
            application_date__date__gte=month_ago
        ).count()
        
        # Get approved breakdown by position
        approved_staff = StaffApplication.objects.filter(status='approved')
        manager_count = approved_staff.filter(position='store_manager').count()
        cashier_count = approved_staff.filter(position='cashier').count()
        
        # Get rejected breakdown
        rejected_month = StaffApplication.objects.filter(
            status='rejected',
            review_date__date__gte=month_ago
        ).count()
        
        rejected_week = StaffApplication.objects.filter(
            status='rejected',
            review_date__date__gte=week_ago
        ).count()
        
        # Calculate incomplete applications (missing documents)
        incomplete_count = StaffApplication.objects.filter(
            Q(passport_photo='') | Q(id_front='') | Q(id_back='')
        ).count()
        
        # Calculate conversion rate
        conversion_rate = 0
        if total_applications > 0:
            conversion_rate = round((approved_count / total_applications) * 100, 1)
        
        # Calculate average processing time (for approved applications)
        avg_process_time = 0
        approved_with_review = approved_staff.filter(review_date__isnull=False)
        if approved_with_review.exists():
            total_days = sum([
                (app.review_date - app.application_date).days 
                for app in approved_with_review
            ])
            avg_process_time = round(total_days / approved_with_review.count(), 1)
        
        data = {
            'pending_count': pending_count,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'total_applications': total_applications,
            
            'pending_today': pending_today,
            'pending_week': pending_week,
            'pending_month': pending_month,
            
            'active_staff': approved_count,  # Assuming all approved are active
            'manager_count': manager_count,
            'cashier_count': cashier_count,
            
            'rejected_month': rejected_month,
            'rejected_week': rejected_week,
            'incomplete_count': incomplete_count,
            
            'conversion_rate': f"{conversion_rate}%",
            'avg_process_time': f"{avg_process_time} days",
            'portal_visits': 0,  # You can add tracking for this
        }
        
        return JsonResponse({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_GET
def pending_applications_api(request):
    """Get paginated list of pending applications"""
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get pending applications
        pending_apps = StaffApplication.objects.filter(
            status='pending'
        ).order_by('-application_date')
        
        total_count = pending_apps.count()
        
        # Get paginated data
        applications = pending_apps[offset:offset + page_size]
        
        applications_data = []
        for app in applications:
            # Check if documents are complete
            docs_complete = all([
                app.passport_photo,
                app.id_front,
                app.id_back
            ])
            
            applications_data.append({
                'id': app.id,
                'first_name': app.first_name,
                'last_name': app.last_name,
                'id_number': app.id_number,
                'email': app.email,
                'phone': app.phone,
                'position': app.position,
                'position_display': app.get_position_display(),
                'application_date': app.application_date.isoformat(),
                'documents_status': 'complete' if docs_complete else 'incomplete',
                'address': app.address,
                'experience': app.experience,
                'passport_photo': bool(app.passport_photo),
                'id_front': bool(app.id_front),
                'id_back': bool(app.id_back),
            })
        
        # Calculate pagination info
        pages = (total_count + page_size - 1) // page_size  # Ceiling division
        
        pagination = {
            'page': page,
            'page_size': page_size,
            'total': total_count,
            'pages': pages,
            'has_next': page < pages,
            'has_prev': page > 1,
        }
        
        return JsonResponse({
            'success': True,
            'data': {
                'applications': applications_data,
                'pagination': pagination
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_GET
def application_detail_api(request, application_id):
    """Get detailed information about a specific application"""
    try:
        application = StaffApplication.objects.get(id=application_id)
        
        data = {
            'id': application.id,
            'first_name': application.first_name,
            'last_name': application.last_name,
            'id_number': application.id_number,
            'email': application.email,
            'phone': application.phone,
            'position': application.position,
            'position_display': application.get_position_display(),
            'application_date': application.application_date.isoformat(),
            'address': application.address,
            'experience': application.experience,
            'status': application.status,
            'status_display': application.get_status_display(),
            'passport_photo': application.passport_photo.url if application.passport_photo else None,
            'id_front': application.id_front.url if application.id_front else None,
            'id_back': application.id_back.url if application.id_back else None,
            'terms_accepted': application.terms_accepted,
            'privacy_accepted': application.privacy_accepted,
            'ip_address': application.ip_address,
            'user_agent': application.user_agent,
        }
        
        # Add review info if available
        if application.reviewed_by:
            data['reviewed_by'] = application.reviewed_by.username
            data['review_date'] = application.review_date.isoformat() if application.review_date else None
            data['review_notes'] = application.review_notes
        
        return JsonResponse({
            'success': True,
            'data': data
        })
        
    except StaffApplication.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Application not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_POST
@csrf_exempt
def approve_application_api(request, application_id):
    """Approve a staff application"""
    try:
        data = json.loads(request.body)
        notes = data.get('notes', '')
        
        application = StaffApplication.objects.get(id=application_id)
        
        # Update application
        application.status = 'approved'
        application.reviewed_by = request.user
        application.review_date = timezone.now()
        application.review_notes = notes
        application.save()
        
        # TODO: Create user account and send welcome email
        
        return JsonResponse({
            'success': True,
            'message': 'Application approved successfully',
            'data': {
                'application_id': f"APP{application.id:06d}",
                'status': 'approved',
                'reviewed_by': request.user.username,
                'review_date': application.review_date.isoformat()
            }
        })
        
    except StaffApplication.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Application not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_POST
@csrf_exempt
def reject_application_api(request, application_id):
    """Reject a staff application"""
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '')
        notes = data.get('notes', '')
        
        application = StaffApplication.objects.get(id=application_id)
        
        # Update application
        application.status = 'rejected'
        application.reviewed_by = request.user
        application.review_date = timezone.now()
        application.review_notes = f"Reason: {reason}\nNotes: {notes}"
        application.save()
        
        # TODO: Send rejection email
        
        return JsonResponse({
            'success': True,
            'message': 'Application rejected',
            'data': {
                'application_id': f"APP{application.id:06d}",
                'status': 'rejected',
                'reviewed_by': request.user.username,
                'review_date': application.review_date.isoformat()
            }
        })
        
    except StaffApplication.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Application not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_GET
def approved_staff_api(request):
    """Get list of approved staff"""
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        offset = (page - 1) * page_size
        
        approved_staff = StaffApplication.objects.filter(
            status='approved'
        ).order_by('-review_date')
        
        total_count = approved_staff.count()
        
        staff_list = approved_staff[offset:offset + page_size]
        
        staff_data = []
        for staff in staff_list:
            staff_data.append({
                'id': staff.id,
                'staff_id': f"STAFF{staff.id:06d}",
                'first_name': staff.first_name,
                'last_name': staff.last_name,
                'email': staff.email,
                'phone': staff.phone,
                'position': staff.position,
                'position_display': staff.get_position_display(),
                'approved_date': staff.review_date.isoformat() if staff.review_date else None,
                'approved_by': staff.reviewed_by.username if staff.reviewed_by else None,
                'status': 'active',  # You can add more statuses later
                'id_number': staff.id_number,
                'application_date': staff.application_date.isoformat(),
            })
        
        pages = (total_count + page_size - 1) // page_size
        
        pagination = {
            'page': page,
            'page_size': page_size,
            'total': total_count,
            'pages': pages,
            'has_next': page < pages,
            'has_prev': page > 1,
        }
        
        return JsonResponse({
            'success': True,
            'data': {
                'staff': staff_data,
                'pagination': pagination
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_GET
def rejected_applications_api(request):
    """Get list of rejected applications"""
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        offset = (page - 1) * page_size
        
        rejected_apps = StaffApplication.objects.filter(
            status='rejected'
        ).order_by('-review_date')
        
        total_count = rejected_apps.count()
        
        applications = rejected_apps[offset:offset + page_size]
        
        apps_data = []
        for app in applications:
            # Extract reason from review notes
            reason = 'Other'
            if app.review_notes:
                if 'Reason:' in app.review_notes:
                    reason = app.review_notes.split('Reason:')[1].split('\n')[0].strip()
            
            apps_data.append({
                'id': app.id,
                'app_id': f"APP{app.id:06d}",
                'first_name': app.first_name,
                'last_name': app.last_name,
                'position': app.position,
                'position_display': app.get_position_display(),
                'applied_date': app.application_date.isoformat(),
                'rejected_date': app.review_date.isoformat() if app.review_date else None,
                'reason': reason,
                'reviewed_by': app.reviewed_by.username if app.reviewed_by else None,
                'email': app.email,
                'phone': app.phone,
            })
        
        pages = (total_count + page_size - 1) // page_size
        
        pagination = {
            'page': page,
            'page_size': page_size,
            'total': total_count,
            'pages': pages,
            'has_next': page < pages,
            'has_prev': page > 1,
        }
        
        return JsonResponse({
            'success': True,
            'data': {
                'applications': apps_data,
                'pagination': pagination
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_GET
def application_analytics_api(request):
    """Get analytics data for staff applications"""
    try:
        period = request.GET.get('period', '30days')
        
        # Calculate date range
        today = timezone.now().date()
        if period == '7days':
            start_date = today - timedelta(days=7)
        elif period == '90days':
            start_date = today - timedelta(days=90)
        elif period == 'year':
            start_date = today.replace(month=1, day=1)
        else:  # 30days default
            start_date = today - timedelta(days=30)
        
        # Get applications in date range
        applications = StaffApplication.objects.filter(
            application_date__date__gte=start_date
        )
        
        # Group by date for trend chart
        from django.db.models.functions import TruncDate
        trend_data = applications.annotate(
            date=TruncDate('application_date')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Prepare trend data
        dates = []
        counts = []
        for item in trend_data:
            dates.append(item['date'].strftime('%b %d'))
            counts.append(item['count'])
        
        # Get status distribution
        status_data = applications.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        status_labels = []
        status_counts = []
        status_colors = []
        
        for item in status_data:
            status_labels.append(item['status'].title())
            status_counts.append(item['count'])
            
            # Assign colors based on status
            if item['status'] == 'pending':
                status_colors.append('#f59e0b')  # Orange
            elif item['status'] == 'approved':
                status_colors.append('#10b981')  # Green
            elif item['status'] == 'rejected':
                status_colors.append('#ef4444')  # Red
            else:
                status_colors.append('#6b7280')  # Gray
        
        # Get position distribution
        position_data = applications.values('position').annotate(
            count=Count('id')
        ).order_by('-count')
        
        position_labels = []
        position_counts = []
        
        for item in position_data:
            # Get display name for position
            try:
                display_name = dict(StaffApplication.POSITION_CHOICES).get(item['position'], item['position'])
                position_labels.append(display_name)
                position_counts.append(item['count'])
            except:
                continue
        
        # Calculate processing time stats
        processed_apps = applications.filter(
            review_date__isnull=False,
            status__in=['approved', 'rejected']
        )
        
        avg_processing_time = 0
        fastest_processing = 0
        slowest_processing = 0
        on_time_percent = 0
        
        if processed_apps.exists():
            processing_times = []
            for app in processed_apps:
                if app.review_date and app.application_date:
                    days = (app.review_date - app.application_date).days
                    processing_times.append(days)
            
            if processing_times:
                avg_processing_time = round(sum(processing_times) / len(processing_times), 1)
                fastest_processing = min(processing_times)
                slowest_processing = max(processing_times)
                
                # Calculate on-time percentage (processed within 3 days)
                on_time = sum(1 for time in processing_times if time <= 3)
                on_time_percent = round((on_time / len(processing_times)) * 100, 1)
        
        analytics_data = {
            'trend': {
                'dates': dates,
                'counts': counts,
            },
            'status_distribution': {
                'labels': status_labels,
                'counts': status_counts,
                'colors': status_colors,
            },
            'position_distribution': {
                'labels': position_labels,
                'counts': position_counts,
            },
            'processing_stats': {
                'avg_processing_time': avg_processing_time,
                'fastest_processing': fastest_processing,
                'slowest_processing': slowest_processing,
                'on_time_percent': on_time_percent,
            }
        }
        
        return JsonResponse({
            'success': True,
            'data': analytics_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)