"""
Website Middleware
Contains session and dashboard-related middleware
"""

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class DashboardSessionMiddleware:
    """
    Existing dashboard session middleware
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response


class StrictSessionMiddleware:
    """
    Middleware to enforce strict session expiration.
    
    Features:
    - Automatic logout after 30 minutes of inactivity
    - Tracks last activity timestamp
    - Logs session expirations for security auditing
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout_minutes = 30  # Configurable timeout
        
    def __call__(self, request):
        if request.user.is_authenticated:
            # Get last activity timestamp from session
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                try:
                    # Convert ISO format string back to datetime
                    last_activity_time = timezone.datetime.fromisoformat(last_activity)
                    time_since_activity = timezone.now() - last_activity_time
                    
                    # Check if session has expired
                    if time_since_activity > timedelta(minutes=self.timeout_minutes):
                        # Log the automatic logout
                        logger.info(
                            f"[SESSION EXPIRED] User: {request.user.username} | "
                            f"Inactive for: {time_since_activity.total_seconds() / 60:.1f} minutes"
                        )
                        
                        # Logout the user
                        logout(request)
                        
                        # Redirect to login with timeout message
                        return redirect('/login/?session_expired=1')
                        
                except (ValueError, TypeError) as e:
                    # Handle invalid timestamp format
                    logger.warning(f"Invalid session timestamp: {e}")
                    request.session['last_activity'] = timezone.now().isoformat()
            
            # Update last activity timestamp for valid sessions
            request.session['last_activity'] = timezone.now().isoformat()
            request.session.modified = True
        
        response = self.get_response(request)
        return response







# Simple middleware that does nothing
class DashboardSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        return self.get_response(request)
