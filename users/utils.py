# users/utils.py
from .models import Role

def get_roles_for_dropdown():
    """Get all roles formatted for dropdown"""
    roles = Role.objects.all().order_by('name')
    return roles