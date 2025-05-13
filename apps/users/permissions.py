from rest_framework import permissions

class RoleBasedPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return True
        required_role = getattr(view, 'required_role', None)
        if required_role:
            if required_role == 'client':
                return request.user.is_client
            elif required_role == 'worker':
                return request.user.is_worker
            elif required_role == 'admin':
                return request.user.is_superuser
        return True

    def has_object_permission(self, request, view, obj):
        required_role = getattr(view, 'required_role', None)
        if required_role:
            if required_role == 'client':
                return request.user.is_client
            elif required_role == 'worker':
                return request.user.is_worker
            elif required_role == 'admin':
                return request.user.is_superuser
        return True