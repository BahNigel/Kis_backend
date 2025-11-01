from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsSurveyOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user_uuid = getattr(request.user, 'id', None)
        # If owner_id is null, allow staff to modify
        if obj.owner_id is None:
            return request.user.is_staff
        return str(obj.owner_id) == str(user_uuid) or request.user.is_staff