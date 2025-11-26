# chat/views_roles.py
from apps.accounts.models import User
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Conversation,
    ConversationMember,
    RoleDefinition,
    RoleScopeType,
    PermissionDefinition,
    RolePermission,
    PrincipalRole,
)
from .permissions import PermissionEngine, PermissionCheckContext


class ConversationRoleViewSet(viewsets.ViewSet):
    """
    Manage custom roles & permissions at conversation scope.
    URL base: /api/v1/chat/rooms/{conversation_id}/roles/...
    """
    permission_classes = [IsAuthenticated]

    def _get_conversation(self, conversation_id, user):
        convo = Conversation.objects.filter(pk=conversation_id).first()
        if not convo:
            return None, Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        ctx = PermissionCheckContext(user=user, conversation=convo)
        if not PermissionEngine.check('chat.set_settings', ctx):
            return None, Response(
                {"detail": "You are not allowed to manage roles in this conversation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return convo, None

    @action(detail=False, methods=['get'], url_path='list')
    def list_roles(self, request, conversation_id=None):
        convo, error = self._get_conversation(conversation_id, request.user)
        if error:
            return error

        roles = RoleDefinition.objects.filter(
            scope_type=RoleScopeType.CONVERSATION,
            scope_id=str(convo.id),
        ).order_by('rank', 'name')

        data = [
            {
                "id": r.id,
                "name": r.name,
                "slug": r.slug,
                "is_system": r.is_system,
                "rank": r.rank,
            }
            for r in roles
        ]
        return Response(data)

    @action(detail=False, methods=['post'], url_path='create')
    def create_role(self, request, conversation_id=None):
        convo, error = self._get_conversation(conversation_id, request.user)
        if error:
            return error

        name = request.data.get('name')
        slug = request.data.get('slug')
        rank = int(request.data.get('rank', 100))
        if not name or not slug:
            return Response(
                {"detail": "name and slug are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role = RoleDefinition.objects.create(
            name=name,
            slug=slug,
            scope_type=RoleScopeType.CONVERSATION,
            scope_id=str(convo.id),
            is_system=False,
            is_default_for_scope=False,
            rank=rank,
            created_by=request.user,
        )
        return Response(
            {"id": role.id, "name": role.name, "slug": role.slug, "rank": role.rank},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='set-permissions')
    def set_permissions(self, request, conversation_id=None):
        """
        Body:
        {
          "role_id": 123,
          "permissions": {
            "chat.pin_message": true,
            "chat.remove_member": false,
            ...
          }
        }
        """
        convo, error = self._get_conversation(conversation_id, request.user)
        if error:
            return error

        role_id = request.data.get('role_id')
        perms_map = request.data.get('permissions') or {}

        try:
            role = RoleDefinition.objects.get(
                id=role_id,
                scope_type=RoleScopeType.CONVERSATION,
                scope_id=str(convo.id),
            )
        except RoleDefinition.DoesNotExist:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)

        for code, allowed in perms_map.items():
            perm, _ = PermissionDefinition.objects.get_or_create(
                code=code,
                defaults={"description": code, "category": "chat"},
            )
            rp, _ = RolePermission.objects.get_or_create(
                role=role,
                permission=perm,
                defaults={"allowed": bool(allowed)},
            )
            if rp.allowed != bool(allowed):
                rp.allowed = bool(allowed)
                rp.save(update_fields=['allowed'])

        return Response({"detail": "Permissions updated."})

    @action(detail=False, methods=['post'], url_path='assign')
    def assign_role(self, request, conversation_id=None):
        """
        Assign a role to a user in this conversation.
        Body: { "role_id": 123, "user_id": 456 }
        """
        convo, error = self._get_conversation(conversation_id, request.user)
        if error:
            return error

        role_id = request.data.get('role_id')
        user_id = request.data.get('user_id')

        role = RoleDefinition.objects.filter(
            id=role_id,
            scope_type=RoleScopeType.CONVERSATION,
            scope_id=str(convo.id),
        ).first()
        if not role:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            target = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ensure target is member
        if not ConversationMember.objects.filter(
            conversation=convo,
            user=target,
            left_at__isnull=True,
        ).exists():
            return Response(
                {"detail": "User is not a member of this conversation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        PrincipalRole.objects.update_or_create(
            user=target,
            role=role,
            scope_type=RoleScopeType.CONVERSATION,
            scope_id=str(convo.id),
            defaults={},
        )

        return Response({"detail": "Role assigned."})
