from rest_framework import permissions

class RoleBasedPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        
        is_public = getattr(view, 'is_public', False)
        if is_public:
            return True

        
        if not request.user.is_authenticated:
            return False

        required_role = getattr(view, 'required_role', None)
        if required_role:
            if required_role == 'client':
                return request.user.is_client
            elif required_role == 'worker':
                return request.user.is_worker
            elif required_role == 'admin':
                return request.user.is_superuser
        return request.user.is_client or request.user.is_worker  

    def has_object_permission(self, request, view, obj):
        required_role = getattr(view, 'required_role', None)
        if required_role:
            if required_role == 'client':
                return request.user.is_client
            elif required_role == 'worker':
                return request.user.is_worker
            elif required_role == 'admin':
                return request.user.is_superuser
        return request.user.is_client or request.user.is_worker 