# chat/permissions.py
from typing import Optional, Iterable

from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import (
    Conversation,
    ConversationMember,
    BaseConversationRole,
    RoleScopeType,
    PrincipalRole,
    RolePermission,
    PermissionDefinition,
)


# ---------------------------------------------------------------------------
# Low-level helpers (RBAC + membership)
# ---------------------------------------------------------------------------

def get_conversation_membership(user, conversation: Conversation) -> Optional[ConversationMember]:
    """
    Return the active ConversationMember for this user & conversation, if any.
    """
    if user is None or not user.is_authenticated:
        return None

    try:
        return ConversationMember.objects.get(
            conversation=conversation,
            user=user,
            left_at__isnull=True,
            is_blocked=False,
        )
    except ConversationMember.DoesNotExist:
        return None


def user_is_conversation_member(user, conversation: Conversation) -> bool:
    """
    Basic: is this user an active, non-blocked member of the conversation?
    """
    return get_conversation_membership(user, conversation) is not None


def user_is_conversation_admin_or_owner(user, conversation: Conversation) -> bool:
    """
    Check if user is an active member whose base_role is ADMIN or OWNER.
    """
    membership = get_conversation_membership(user, conversation)
    if membership is None:
        return False

    return membership.base_role in {
        BaseConversationRole.OWNER,
        BaseConversationRole.ADMIN,
    }


def user_has_rbac_permission_for_scope(
    user,
    scope_type: str,
    scope_id: str,
    permission_code: str,
) -> bool:
    """
    Check if user has a given permission_code in a specific scope using RBAC tables.

    Logic:
      - Find all PrincipalRole for (user, scope_type, scope_id).
      - For those roles, join RolePermission and check any matching permission_code
        where allowed=True.
      - If any role denies the permission explicitly (allowed=False), you can
        decide whether deny overrides allow; here we treat allow=True as enough.
    """
    if user is None or not user.is_authenticated:
        return False

    # Ensure permission exists (optional but nice for debugging)
    if not PermissionDefinition.objects.filter(code=permission_code).exists():
        # If you prefer strict mode, you could raise or return False.
        return False

    # Get all role ids for this user in this scope
    role_ids = list(
        PrincipalRole.objects.filter(
            user=user,
            scope_type=scope_type,
            scope_id=scope_id,
        ).values_list('role_id', flat=True)
    )
    if not role_ids:
        return False

    # Check if any of those roles allows the permission
    return RolePermission.objects.filter(
        role_id__in=role_ids,
        permission__code=permission_code,
        allowed=True,
    ).exists()


def user_has_conversation_permission(user, conversation: Conversation, permission_code: str) -> bool:
    """
    Convenience helper for conversation-scoped permissions.
    Uses RoleScopeType.CONVERSATION and conversation.id as scope_id.
    """
    if user is None or not user.is_authenticated:
        return False

    scope_type = RoleScopeType.CONVERSATION
    scope_id = str(conversation.id)

    return user_has_rbac_permission_for_scope(
        user=user,
        scope_type=scope_type,
        scope_id=scope_id,
        permission_code=permission_code,
    )


# ---------------------------------------------------------------------------
# DRF Permission Classes
# ---------------------------------------------------------------------------

class IsConversationMember(BasePermission):
    """
    Allows access only to users who are active members of the conversation.

    Usage:
      - In a ViewSet where `get_object()` returns a Conversation:
            permission_classes = [IsAuthenticated, IsConversationMember]
      - Or override `has_object_permission` manually.
    """

    message = "You are not a member of this conversation."

    def has_object_permission(self, request, view, obj):
        """
        obj is expected to be a Conversation instance.
        """
        if not isinstance(obj, Conversation):
            # If it's not a Conversation, don't block here (let other perms handle).
            return True

        return user_is_conversation_member(request.user, obj)


class IsConversationAdminOrOwner(BasePermission):
    """
    Allows access only to conversation admins or owners.

    Usage:
      - For endpoints that manage members, settings, etc., e.g.:

            class ConversationAdminView(...):
                permission_classes = [IsAuthenticated, IsConversationAdminOrOwner]

      - Expects `get_object()` (or view.get_conversation()) to return a Conversation.
    """

    message = "You must be an admin or owner of this conversation."

    def has_object_permission(self, request, view, obj):
        if not isinstance(obj, Conversation):
            return True

        return user_is_conversation_admin_or_owner(request.user, obj)


class HasConversationPermission(BasePermission):
    """
    Generic RBAC-based permission, driven by a `permission_code` attribute on the view.

    Example:

        class ConversationSettingsView(RetrieveUpdateAPIView):
            queryset = Conversation.objects.all()
            serializer_class = ConversationSettingsSerializer
            permission_classes = [IsAuthenticated, HasConversationPermission]
            permission_code = "chat.manage_conversation_settings"

            def get_object(self):
                return Conversation.objects.get(pk=self.kwargs['pk'])

    Logic:
      - If `permission_code` is not set on the view, this permission returns True
        (no-op).
      - Otherwise, it checks RBAC for the conversation scope.
      - You can combine this with `IsConversationMember` for stricter checks.
    """

    message = "You do not have permission to perform this action in this conversation."

    def has_object_permission(self, request, view, obj):
        # 1. If the view didn't specify a permission code, do nothing here.
        permission_code = getattr(view, 'permission_code', None)
        if not permission_code:
            return True

        # 2. We only handle Conversation objects here.
        if not isinstance(obj, Conversation):
            return True

        # 3. If user isn't even a member, deny
        if not user_is_conversation_member(request.user, obj):
            return False

        # 4. Check RBAC for this conversation scope
        return user_has_conversation_permission(
            user=request.user,
            conversation=obj,
            permission_code=permission_code,
        )
