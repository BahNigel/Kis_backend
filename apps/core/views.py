# core/views.py
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

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
# (admin protected)
# ---------------------------
class PermissionViewSet(viewsets.ModelViewSet):
    queryset = models.Permission.objects.all()
    serializer_class = serializers.PermissionSerializer
    permission_classes = [IsSuperuserOrAdmin]


class RoleViewSet(viewsets.ModelViewSet):
    queryset = models.Role.objects.prefetch_related("permissions").all()
    serializer_class = serializers.RoleShortSerializer
    permission_classes = [IsSuperuserOrAdmin]

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
class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = models.RoleAssignment.objects.select_related("role").all()
    serializer_class = serializers.RoleAssignmentSerializer
    permission_classes = [CanManageRolesPermission]  # restrict role assignment management

    def perform_create(self, serializer):
        # ensure role scope matches target if target provided (optional)
        serializer.save()


class AccessControlEntryViewSet(viewsets.ModelViewSet):
    queryset = models.AccessControlEntry.objects.all()
    serializer_class = serializers.AccessControlEntrySerializer
    permission_classes = [CanManageRolesPermission]

    def create(self, request, *args, **kwargs):
        # Validate permissions exist optionally; but serializer will ensure
        return super().create(request, *args, **kwargs)


# ---------------------------
# Community / Group / Channel ViewSets
# ---------------------------
class CommunityViewSet(viewsets.ModelViewSet):
    queryset = models.Community.objects.all()
    serializer_class = serializers.CommunitySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # allow read for anyone if community is public; write requires authentication + permission
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

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def grant(self, request, pk=None):
        """
        Convenience endpoint: grant an ACE to a principal on this community.
        body: { "principal": {"type":"accounts.User","id":"..."} | null (public), "permissions": ["perm1"], "effect": "ALLOW", "expires_at": null }
        """
        community = self.get_object()
        data = request.data.copy()
        data["target"] = {"type": f"{community._meta.app_label}.{community._meta.model_name}", "id": str(community.pk)}
        serializer = serializers.AccessControlEntrySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        ace = serializer.save()
        return Response(serializers.AccessControlEntrySerializer(ace).data, status=status.HTTP_201_CREATED)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = models.Group.objects.select_related("community").all()
    serializer_class = serializers.GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # list/retrieve open to any authenticated or public listing - allow any for read
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # Create group and default settings handled by serializer.create
        serializer.save()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        """
        Join a group (respecting group's join policy).
        If group is invite-only, client must provide invite token in body { "invite_token": "..." }.
        """
        group = self.get_object()
        user = request.user

        # check join policy
        settings_obj = getattr(group, "settings", None)
        join_policy = settings_obj.join_policy if settings_obj else "OPEN"

        # If invite required
        invite_token = request.data.get("invite_token")
        if join_policy == "INVITE" and not invite_token:
            return Response({"detail": "Invite token required"}, status=status.HTTP_400_BAD_REQUEST)

        # If invite provided, validate
        if invite_token:
            try:
                invite = models.MembershipInvite.objects.get(token=invite_token, group=group)
            except models.MembershipInvite.DoesNotExist:
                return Response({"detail": "Invalid invite token"}, status=status.HTTP_400_BAD_REQUEST)
            if not invite.is_valid():
                return Response({"detail": "Invite expired/used"}, status=status.HTTP_400_BAD_REQUEST)
            invite.use()

        # Create membership
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

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def invite(self, request, pk=None):
        """
        Create an invite for the group. Permission required: 'group.invite' or be group moderator/owner.
        body: { "expires_at": "...", "max_uses": 5 }
        """
        group = self.get_object()
        user = request.user
        # permission check: allow if user can 'group.invite' or is member moderator
        if not (group.can_user(user, "group.invite") or group.is_member(user) and group.memberships.filter(
                user_content_type=ContentType.objects.get_for_model(user.__class__),
                user_object_id=str(user.pk),
                is_moderator=True).exists()):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        serializer = serializers.MembershipInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Assign group automatically
        invite = serializer.save(group=group, created_by=user)
        return Response(serializers.MembershipInviteSerializer(invite).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def promote(self, request, pk=None):
        """
        Promote a member to a role (body: { "user": {"type":"accounts.User","id":"..."}, "role": "<role_id>" })
        Requires 'group.manage_members' permission or moderator.
        """
        group = self.get_object()
        user = request.user
        if not group.can_user(user, "group.manage_members"):
            # some moderators may also be allowed; check membership
            if not group.memberships.filter(user_content_type=ContentType.objects.get_for_model(user.__class__),
                                            user_object_id=str(user.pk),
                                            is_moderator=True).exists():
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        target_user_data = request.data.get("user")
        role_id = request.data.get("role")
        if not target_user_data or not role_id:
            return Response({"detail": "user and role required"}, status=status.HTTP_400_BAD_REQUEST)

        # resolve user via GenericRelatedField logic: use ContentType lookup
        # Expecting format {"type":"accounts.User","id":"<pk>"}
        # reuse serializer helper to validate
        try:
            target = serializers.GenericRelatedField().to_internal_value(target_user_data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        role = get_object_or_404(models.Role, pk=role_id)
        # find membership
        user_ct = ContentType.objects.get_for_model(target.__class__)
        try:
            mem = models.Membership.objects.get(group=group, user_content_type=user_ct, user_object_id=str(target.pk))
        except models.Membership.DoesNotExist:
            return Response({"detail": "Target is not a member"}, status=status.HTTP_400_BAD_REQUEST)

        mem.promote_to_role(role)
        return Response(serializers.MembershipSerializer(mem).data, status=status.HTTP_200_OK)


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = models.Channel.objects.prefetch_related("communities", "groups").all()
    serializer_class = serializers.ChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        """
        Join a channel: requires membership in at least one linked group/community or explicit channel role.
        """
        channel = self.get_object()
        user = request.user

        # Quick checks: if channel public and user has group/community membership that's active, allow
        if channel.is_public:
            # check group membership
            for g in channel.groups.all():
                if g.is_member(user):
                    # create channel-level role assignment or membership if you model it later
                    return Response({"detail": "Allowed via group membership"}, status=status.HTTP_200_OK)
            for c in channel.communities.all():
                # if user has community-level permission, allow
                if models.CommunityPermissionHelper.can_user_on_community(user, c, "community.member"):
                    return Response({"detail": "Allowed via community membership"}, status=status.HTTP_200_OK)

        # fallback: check channel ACEs or role assignments
        if channel.can_user(user, "channel.join"):
            return Response({"detail": "Allowed"}, status=status.HTTP_200_OK)

        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)


# ---------------------------
# Membership & Invite ViewSets (detail operations)
# ---------------------------
class MembershipViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet,
                        mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    queryset = models.Membership.objects.select_related("group").all()
    serializer_class = serializers.MembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # restrict listing to memberships related to the requesting user or groups they manage
        user = self.request.user
        if getattr(user, "is_superuser", False) or user.is_staff:
            return super().get_queryset()
        user_ct = ContentType.objects.get_for_model(user.__class__)
        return super().get_queryset().filter(user_content_type=user_ct, user_object_id=str(user.pk))


class MembershipInviteViewSet(viewsets.ModelViewSet):
    queryset = models.MembershipInvite.objects.all()
    serializer_class = serializers.MembershipInviteSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def redeem(self, request):
        """
        Redeem invite token to join group/community. Body: { "token": "abc123" }
        If invite not valid => 400. If valid, create membership.
        """
        token = request.data.get("token")
        if not token:
            return Response({"detail": "token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            invite = models.MembershipInvite.objects.get(token=token)
        except models.MembershipInvite.DoesNotExist:
            return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

        if not invite.is_valid():
            return Response({"detail": "Invite expired or used"}, status=status.HTTP_400_BAD_REQUEST)

        # require authentication unless invite is intended for anonymous users (app-specific)
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Authentication required to redeem"}, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        user_ct = ContentType.objects.get_for_model(user.__class__)

        with transaction.atomic():
            # create membership for group or community; group priority if both set
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
                # membership at community-level might map to group-less membership (not implemented),
                # but you can choose to add the user to a default group, or track community membership separately.
                invite.use()
                return Response({"detail": "Invite redeemed for community (application-defined)"},
                                status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Invite has no target"}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------
# ModerationAction ViewSet
# ---------------------------
class ModerationActionViewSet(viewsets.ModelViewSet):
    queryset = models.ModerationAction.objects.all()
    serializer_class = serializers.ModerationActionSerializer
    permission_classes = [IsAuthenticated]  # exposing to authenticated users; use more restrictive permission in prod

    def create(self, request, *args, **kwargs):
        """
        When creating moderation actions, ensure the performer is set to request.user (if provided)
        and check that the performer has moderation permissions on the target.
        """
        data = request.data.copy()
        # Default performed_by to request.user
        data.setdefault("performed_by", {"type": f"{request.user._meta.app_label}.{request.user._meta.model_name}", "id": str(request.user.pk)})

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        target = serializer.validated_data["target"]
        # permission check: can user moderate target?
        if not getattr(request.user, "is_superuser", False):
            # try to ask the target for permission if it supports can_user
            if hasattr(target, "can_user"):
                if not target.can_user(request.user, "moderation.action"):
                    return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ---------------------------
# Settings viewsets - update only
# ---------------------------
class GroupSettingsViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    queryset = models.GroupSettings.objects.select_related("group").all()
    serializer_class = serializers.GroupSettingsUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Allow retrieving by group pk via /groups/{pk}/settings/ if needed; otherwise use default pk
        return super().get_object()


class ChannelSettingsViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    queryset = models.ChannelSettings.objects.select_related("channel").all()
    serializer_class = serializers.ChannelSettingsUpdateSerializer
    permission_classes = [IsAuthenticated]

