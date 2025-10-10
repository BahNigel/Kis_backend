# core/views.py
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter

from . import models, serializers

# Convenience user model
from django.apps import apps
from django.conf import settings
UserModel = apps.get_model(settings.AUTH_USER_MODEL)


# ---------------------------
# Custom DRF permission wrappers
# ---------------------------
class IsSuperuserOrAdmin(IsAdminUser):
    """
    Slight wrapper: admin users or Django superusers.
    """
    def has_permission(self, request, view):
        if getattr(request.user, "is_superuser", False):
            return True
        return super().has_permission(request, view)


class CanManageRolesPermission(IsAuthenticated):
    """
    Placeholder permission: restrict role/permission/ace management to staff or superusers.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_superuser", False):
            return True
        return bool(getattr(request.user, "is_staff", False))


# ---------------------------
# Simple ModelViewSets for Permission & Role
# ---------------------------
@extend_schema(tags=["Permissions"])
class PermissionViewSet(viewsets.ModelViewSet):
    queryset = models.Permission.objects.all()
    serializer_class = serializers.PermissionSerializer
    permission_classes = [IsSuperuserOrAdmin]


@extend_schema(tags=["Roles"])
class RoleViewSet(viewsets.ModelViewSet):
    queryset = models.Role.objects.prefetch_related("permissions").all()
    serializer_class = serializers.RoleShortSerializer
    permission_classes = [IsSuperuserOrAdmin]

    @extend_schema(
        request=serializers.PermissionSerializer,
        responses=serializers.RoleShortSerializer,
        description="Add a permission to a role",
    )
    @action(detail=True, methods=["post"], permission_classes=[IsSuperuserOrAdmin])
    def add_permission(self, request, pk=None):
        role = self.get_object()
        codename = request.data.get("codename")
        if not codename:
            return Response({"detail": "codename required"}, status=status.HTTP_400_BAD_REQUEST)
        perm, _ = models.Permission.objects.get_or_create(codename=codename)
        role.permissions.add(perm)
        role.save()
        return Response(self.get_serializer(role).data)


# ---------------------------
# RoleAssignment & ACE management
# ---------------------------
@extend_schema(tags=["RoleAssignments"])
class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = models.RoleAssignment.objects.select_related("role").all()
    serializer_class = serializers.RoleAssignmentSerializer
    permission_classes = [CanManageRolesPermission]

    @extend_schema(description="Assign a role to a principal")
    def perform_create(self, serializer):
        serializer.save()


@extend_schema(tags=["AccessControlEntries"])
class AccessControlEntryViewSet(viewsets.ModelViewSet):
    queryset = models.AccessControlEntry.objects.all()
    serializer_class = serializers.AccessControlEntrySerializer
    permission_classes = [CanManageRolesPermission]

    @extend_schema(description="Create an Access Control Entry (ACE)")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


# ---------------------------
# Community / Group / Channel ViewSets
# ---------------------------
@extend_schema(tags=["Communities"])
class CommunityViewSet(viewsets.ModelViewSet):
    queryset = models.Community.objects.all()
    serializer_class = serializers.CommunitySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        # set owner to request.user by default if not provided
        owner = serializer.validated_data.get("owner", None)
        if owner is None:
            # set owner generic fields to request.user
            user_ct = ContentType.objects.get_for_model(self.request.user.__class__)
            serializer.validated_data["owner"] = self.request.user
        serializer.save()

    @extend_schema(
        request=serializers.AccessControlEntrySerializer,
        responses=serializers.AccessControlEntrySerializer,
        description="Grant an ACE to a principal on this community",
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def grant(self, request, pk=None):
        community = self.get_object()
        data = request.data.copy()
        data["target"] = {"type": f"{community._meta.app_label}.{community._meta.model_name}", "id": str(community.pk)}
        serializer = serializers.AccessControlEntrySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        ace = serializer.save()
        return Response(serializers.AccessControlEntrySerializer(ace).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Groups"])
class GroupViewSet(viewsets.ModelViewSet):
    queryset = models.Group.objects.select_related("community").all()
    serializer_class = serializers.GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        # Create group and default settings handled by serializer.create
        serializer.save()

    @extend_schema(description="Join a group respecting its join policy")
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        group = self.get_object()
        user = request.user
        settings_obj = getattr(group, "settings", None)
        join_policy = settings_obj.join_policy if settings_obj else "OPEN"
        invite_token = request.data.get("invite_token")

        if join_policy == "INVITE" and not invite_token:
            return Response({"detail": "Invite token required"}, status=status.HTTP_400_BAD_REQUEST)

        if invite_token:
            try:
                invite = models.MembershipInvite.objects.get(token=invite_token, group=group)
            except models.MembershipInvite.DoesNotExist:
                return Response({"detail": "Invalid invite token"}, status=status.HTTP_400_BAD_REQUEST)
            if not invite.is_valid():
                return Response({"detail": "Invite expired/used"}, status=status.HTTP_400_BAD_REQUEST)
            invite.use()

        user_ct = ContentType.objects.get_for_model(user.__class__)
        with transaction.atomic():
            mem, created = models.Membership.objects.update_or_create(
                group=group,
                user_content_type=user_ct,
                user_object_id=str(user.pk),
                defaults={"status": models.Membership.STATUS_ACTIVE, "joined_at": timezone.now()},
            )
            group.recalc_member_count()
        return Response(serializers.MembershipSerializer(mem).data, status=status.HTTP_200_OK)

    @extend_schema(description="Leave a group")
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        group = self.get_object()
        user = request.user
        user_ct = ContentType.objects.get_for_model(user.__class__)
        try:
            mem = models.Membership.objects.get(group=group, user_content_type=user_ct, user_object_id=str(user.pk))
        except models.Membership.DoesNotExist:
            return Response({"detail": "Not a member"}, status=status.HTTP_400_BAD_REQUEST)
        mem.status = models.Membership.STATUS_LEFT
        mem.save()
        group.recalc_member_count()
        return Response({"detail": "Left group"}, status=status.HTTP_200_OK)

    @extend_schema(
        request=serializers.MembershipInviteSerializer,
        responses=serializers.MembershipInviteSerializer,
        description="Create an invite for the group",
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def invite(self, request, pk=None):
        group = self.get_object()
        user = request.user
        if not (group.can_user(user, "group.invite") or group.is_member(user) and group.memberships.filter(
                user_content_type=ContentType.objects.get_for_model(user.__class__),
                user_object_id=str(user.pk),
                is_moderator=True).exists()):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        serializer = serializers.MembershipInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = serializer.save(group=group, created_by=user)
        return Response(serializers.MembershipInviteSerializer(invite).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request={"type": "object", "properties": {"user": {}, "role": {"type": "string"}}},
        responses=serializers.MembershipSerializer,
        description="Promote a member to a role",
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def promote(self, request, pk=None):
        group = self.get_object()
        user = request.user
        if not group.can_user(user, "group.manage_members"):
            if not group.memberships.filter(user_content_type=ContentType.objects.get_for_model(user.__class__),
                                            user_object_id=str(user.pk),
                                            is_moderator=True).exists():
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        target_user_data = request.data.get("user")
        role_id = request.data.get("role")
        if not target_user_data or not role_id:
            return Response({"detail": "user and role required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target = serializers.GenericRelatedField().to_internal_value(target_user_data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        role = get_object_or_404(models.Role, pk=role_id)
        user_ct = ContentType.objects.get_for_model(target.__class__)
        try:
            mem = models.Membership.objects.get(group=group, user_content_type=user_ct, user_object_id=str(target.pk))
        except models.Membership.DoesNotExist:
            return Response({"detail": "Target is not a member"}, status=status.HTTP_400_BAD_REQUEST)

        mem.promote_to_role(role)
        return Response(serializers.MembershipSerializer(mem).data, status=status.HTTP_200_OK)


@extend_schema(tags=["Channels"])
class ChannelViewSet(viewsets.ModelViewSet):
    queryset = models.Channel.objects.prefetch_related("communities", "groups").all()
    serializer_class = serializers.ChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(description="Join a channel if allowed by group/community membership or ACEs")
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        channel = self.get_object()
        user = request.user

        if channel.is_public:
            for g in channel.groups.all():
                if g.is_member(user):
                    return Response({"detail": "Allowed via group membership"}, status=status.HTTP_200_OK)
            for c in channel.communities.all():
                if models.CommunityPermissionHelper.can_user_on_community(user, c, "community.member"):
                    return Response({"detail": "Allowed via community membership"}, status=status.HTTP_200_OK)

        if channel.can_user(user, "channel.join"):
            return Response({"detail": "Allowed"}, status=status.HTTP_200_OK)

        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)


# ---------------------------
# Membership & Invite ViewSets
# ---------------------------
@extend_schema(tags=["Memberships"])
class MembershipViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet,
                        mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    queryset = models.Membership.objects.select_related("group").all()
    serializer_class = serializers.MembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_superuser", False) or user.is_staff:
            return super().get_queryset()
        user_ct = ContentType.objects.get_for_model(user.__class__)
        return super().get_queryset().filter(user_content_type=user_ct, user_object_id=str(user.pk))


@extend_schema(tags=["MembershipInvites"])
class MembershipInviteViewSet(viewsets.ModelViewSet):
    queryset = models.MembershipInvite.objects.all()
    serializer_class = serializers.MembershipInviteSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={"type": "object", "properties": {"token": {"type": "string"}}},
        responses=serializers.MembershipSerializer,
        description="Redeem an invite token to join a group/community",
    )
    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def redeem(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"detail": "token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            invite = models.MembershipInvite.objects.get(token=token)
        except models.MembershipInvite.DoesNotExist:
            return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

        if not invite.is_valid():
            return Response({"detail": "Invite expired or used"}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Authentication required to redeem"}, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        user_ct = ContentType.objects.get_for_model(user.__class__)

        with transaction.atomic():
            if invite.group:
                mem, created = models.Membership.objects.update_or_create(
                    group=invite.group,
                    user_content_type=user_ct,
                    user_object_id=str(user.pk),
                    defaults={"status": models.Membership.STATUS_ACTIVE, "joined_at": timezone.now()}
                )
                invite.use()
                invite.save()
                invite.group.recalc_member_count()
                return Response(serializers.MembershipSerializer(mem).data, status=status.HTTP_201_CREATED)
            elif invite.community:
                invite.use()
                return Response({"detail": "Invite redeemed for community (application-defined)"},
                                status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Invite has no target"}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------
# ModerationAction ViewSet
# ---------------------------
@extend_schema(tags=["ModerationActions"])
class ModerationActionViewSet(viewsets.ModelViewSet):
    queryset = models.ModerationAction.objects.all()
    serializer_class = serializers.ModerationActionSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(description="Create a moderation action with permission checks")
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data.setdefault("performed_by", {"type": f"{request.user._meta.app_label}.{request.user._meta.model_name}", "id": str(request.user.pk)})
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        target = serializer.validated_data["target"]
        if not getattr(request.user, "is_superuser", False):
            if hasattr(target, "can_user"):
                if not target.can_user(request.user, "moderation.action"):
                    return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ---------------------------
# Settings viewsets - update only
# ---------------------------
@extend_schema(tags=["GroupSettings"])
class GroupSettingsViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    queryset = models.GroupSettings.objects.select_related("group").all()
    serializer_class = serializers.GroupSettingsUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return super().get_object()


@extend_schema(tags=["ChannelSettings"])
class ChannelSettingsViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    queryset = models.ChannelSettings.objects.select_related("channel").all()
    serializer_class = serializers.ChannelSettingsUpdateSerializer
    permission_classes = [IsAuthenticated]
