from rest_framework.permissions import BasePermission

class IsSuperuser(BasePermission):
    """Permission class to check if the user is a superuser."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser