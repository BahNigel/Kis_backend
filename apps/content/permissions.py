# content/permissions.py
from rest_framework import permissions

class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow authors (or superusers) to edit objects.
    Read-only allowed to all authenticated/anonymous depending on view.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # if object has author attribute:
        author = getattr(obj, "author", None)
        if author is None:
            return request.user.is_staff
        return obj.author == request.user or request.user.is_superuser
