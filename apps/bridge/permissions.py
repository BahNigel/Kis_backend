from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsBridgeOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user_uuid = getattr(request.user, 'id', None)
        return str(getattr(obj, 'user_id', getattr(obj, 'user_id', None))) == str(user_uuid) or request.user.is_staff