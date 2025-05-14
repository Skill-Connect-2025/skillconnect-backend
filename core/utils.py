# core/utils.py
from rest_framework import permissions
from apps.users.models import Client

class IsClient(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'client')