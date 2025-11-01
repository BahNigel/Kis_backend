from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Read-only for anonymous and non-owners.
    Write allowed only for the object's owner as defined by `.user` or `.recommended_user` attrs.
    """
    message = "You must be the owner to perform this action."

    def has_object_permission(self, request, view, obj):
        # always allow safe methods
        if request.method in permissions.SAFE_METHODS:
            return True
        # if object has 'user' field, compare
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "recommender_user"):
            return obj.recommender_user == request.user
        # fallback - deny
        return False
