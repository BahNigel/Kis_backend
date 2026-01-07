# apps/groups/views.py
from django.db import models
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
)

from apps.groups.models import Group
from apps.groups.serializers import (
    GroupListSerializer,
    GroupDetailSerializer,
    GroupCreateSerializer,
    GroupMembershipSerializer,
    GroupJoinRequestSerializer,
    GroupBanSerializer,
)
from apps.groups.models import (
    GroupMembership,
    GroupJoinRequest,
    GroupJoinRequestStatus,
    GroupRole,
    GroupJoinPolicy,
    GroupBan,
)
from apps.accounts.models import User
from apps.communities.models import CommunityMembership, CommunityRole
from apps.chat.models import ConversationMember, BaseConversationRole


@extend_schema_view(
    list=extend_schema(
        summary="List groups",
        description=(
            "Return all groups where the authenticated user is either:\n"
            "- the group owner, or\n"
            "- an active member of the backing conversation."
        ),
        responses={200: GroupListSerializer},
    ),
    create=extend_schema(
        summary="Create a group",
        description=(
            "Create a new group and automatically:\n"
            "- create a backing Conversation of type `group`,\n"
            "- add the creator as OWNER in ConversationMember,\n"
            "- create ConversationSettings for that conversation."
        ),
        request=GroupCreateSerializer,
        responses={201: GroupDetailSerializer},
    ),
    retrieve=extend_schema(
        summary="Retrieve group details",
        description="Get full details for a single group, including conversation linkage.",
        responses={200: GroupDetailSerializer},
    ),
    update=extend_schema(
        summary="Update a group",
        description=(
            "Update a group. Only the group owner is allowed to update. "
            "Later, this can be extended to conversation admins via RBAC."
        ),
        request=GroupDetailSerializer,
        responses={200: GroupDetailSerializer},
    ),
    partial_update=extend_schema(
        summary="Partially update a group",
        description="Partially update group fields. Only the group owner is allowed.",
        request=GroupDetailSerializer,
        responses={200: GroupDetailSerializer},
    ),
    destroy=extend_schema(
        summary="Delete a group",
        description="Delete a group. Only the group owner is allowed to delete.",
        responses={204: OpenApiResponse(description="Group deleted")},
    ),
)
class GroupViewSet(viewsets.ModelViewSet):
    """
    Endpoints (assuming mounted at /api/v1/groups/):

      - GET    /api/v1/groups/groups/                 -> list
      - POST   /api/v1/groups/groups/                 -> create
      - GET    /api/v1/groups/groups/{id}/            -> retrieve
      - PUT    /api/v1/groups/groups/{id}/            -> update
      - PATCH  /api/v1/groups/groups/{id}/            -> partial_update
      - DELETE /api/v1/groups/groups/{id}/            -> destroy
      - POST   /api/v1/groups/groups/{id}/archive/    -> archive
    """
    permission_classes = [IsAuthenticated]
    queryset = Group.objects.select_related("conversation", "owner", "partner", "community", "channel")

    # Explicitly allow POST etc.
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return GroupListSerializer
        if self.action == "create":
            return GroupCreateSerializer
        return GroupDetailSerializer

    def perform_create(self, serializer):
        """
        GroupCreateSerializer.create() auto-creates:
        - Conversation(type=GROUP)
        - ConversationMember for the owner (base_role=OWNER)
        - ConversationSettings for that conversation
        """
        serializer.save()

    def _get_membership(self, group: Group, user):
        return GroupMembership.objects.filter(
            group=group,
            user=user,
            left_at__isnull=True,
        ).first()

    def _is_admin(self, membership: GroupMembership | None) -> bool:
        return membership and membership.role in (
            GroupRole.OWNER,
            GroupRole.ADMIN,
            GroupRole.MOD,
        )

    def _community_access_all(self, community_id, user) -> bool:
        if not community_id:
            return False
        cm = CommunityMembership.objects.filter(
            community_id=community_id,
            user=user,
            left_at__isnull=True,
            is_banned=False,
        ).first()
        if not cm:
            return False
        if cm.role in (CommunityRole.OWNER, CommunityRole.ADMIN, CommunityRole.MOD):
            return True
        return bool(cm.can_access_all_groups)

    def get_queryset(self):
        user = self.request.user
        qs = Group.objects.select_related("conversation", "owner", "partner", "community", "channel")
        community_id = self.request.query_params.get("community")
        if community_id:
            if self._community_access_all(community_id, user):
                qs = qs.filter(community_id=community_id)
            else:
                qs = qs.filter(
                    models.Q(community_id=community_id)
                    & (models.Q(owner=user) | models.Q(
                        memberships__user=user,
                        memberships__left_at__isnull=True,
                        memberships__is_banned=False,
                    ))
                )
        else:
            qs = qs.filter(
                models.Q(owner=user)
                | models.Q(
                    memberships__user=user,
                    memberships__left_at__isnull=True,
                    memberships__is_banned=False,
                )
            )
        partner_id = self.request.query_params.get("partner")
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        channel_id = self.request.query_params.get("channel")
        if channel_id:
            qs = qs.filter(channel_id=channel_id)
        return qs.distinct()

    def perform_update(self, serializer):
        group = self.get_object()
        if group.owner != self.request.user:
            # Better to raise a DRF PermissionDenied so Swagger shows 403 as error
            raise PermissionDenied("Only the group owner can update this group (for now).")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.owner != request.user:
            return Response(
                {"detail": "Only the group owner can delete this group (for now)."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Archive a group",
        description=(
            "Archive the group and its backing conversation.\n\n"
            "- Sets `group.is_archived = True`.\n"
            "- Sets `conversation.is_archived = True`.\n\n"
            "Only the group owner is allowed to archive (for now)."
        ),
        responses={
            200: OpenApiResponse(description="Group archived"),
            403: OpenApiResponse(description="Forbidden – not the group owner"),
        },
    )
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        """
        Archive the group (and its conversation).
        """
        group = self.get_object()

        if group.owner != request.user:
            return Response(
                {"detail": "Only the group owner can archive this group (for now)."},
                status=status.HTTP_403_FORBIDDEN,
            )

        group.is_archived = True
        group.save()

        # Also archive backing conversation for consistency
        conversation = group.conversation
        conversation.is_archived = True
        conversation.save()

        return Response({"detail": "Group archived."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        group = self.get_object()
        qs = GroupMembership.objects.filter(group=group, left_at__isnull=True)
        serializer = GroupMembershipSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="join")
    def join(self, request, pk=None):
        group = self.get_object()
        user = request.user

        if group.join_policy != GroupJoinPolicy.OPEN:
            return Response({"detail": "Group is not open to direct join."}, status=status.HTTP_400_BAD_REQUEST)

        membership, _ = GroupMembership.objects.get_or_create(
            group=group,
            user=user,
            defaults={"role": GroupRole.MEMBER},
        )
        if membership.left_at is not None:
            membership.left_at = None
            membership.is_banned = False
            membership.save(update_fields=["left_at", "is_banned"])

        ConversationMember.objects.get_or_create(
            conversation=group.conversation,
            user=user,
            defaults={"base_role": BaseConversationRole.MEMBER},
        )

        return Response(GroupMembershipSerializer(membership).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="add-members")
    def add_members(self, request, pk=None):
        """
        Add members to a group by user IDs.
        Payload:
          {
            "userIds": ["uuid", "uuid", ...]
          }
        """
        group = self.get_object()
        user = request.user
        membership = self._get_membership(group, user)
        if group.owner != user and not self._is_admin(membership):
            raise PermissionDenied("Only group admins can add members.")

        raw_ids = request.data.get("userIds") or request.data.get("user_ids") or []
        if not isinstance(raw_ids, list):
            return Response({"detail": "userIds must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        user_ids = [str(uid) for uid in raw_ids if uid]
        if not user_ids:
            return Response({"detail": "No userIds provided."}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(id__in=user_ids, is_active=True)
        added: list[str] = []

        for target in users:
            if target.id == user.id:
                continue
            m, created = GroupMembership.objects.get_or_create(
                group=group,
                user=target,
                defaults={"role": GroupRole.MEMBER},
            )
            if m.left_at is not None or m.is_banned:
                m.left_at = None
                m.is_banned = False
                m.save(update_fields=["left_at", "is_banned"])
            ConversationMember.objects.get_or_create(
                conversation=group.conversation,
                user=target,
                defaults={"base_role": BaseConversationRole.MEMBER},
            )
            if group.community_id:
                CommunityMembership.objects.update_or_create(
                    community_id=group.community_id,
                    user=target,
                    defaults={"role": CommunityRole.MEMBER, "left_at": None, "is_banned": False},
                )
                community = group.community
                if community and community.main_conversation_id:
                    ConversationMember.objects.get_or_create(
                        conversation=community.main_conversation,
                        user=target,
                        defaults={"base_role": BaseConversationRole.MEMBER},
                    )
                if community and community.posts_conversation_id:
                    ConversationMember.objects.get_or_create(
                        conversation=community.posts_conversation,
                        user=target,
                        defaults={"base_role": BaseConversationRole.MEMBER},
                    )
            if created:
                added.append(str(target.id))

        return Response({"added": added, "count": len(added)}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="leave")
    def leave(self, request, pk=None):
        group = self.get_object()
        membership = self._get_membership(group, request.user)
        if not membership:
            return Response({"detail": "Not a member."}, status=status.HTTP_400_BAD_REQUEST)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        ConversationMember.objects.filter(conversation=group.conversation, user=request.user).update(left_at=timezone.now())
        return Response({"detail": "Left group."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="request-join")
    def request_join(self, request, pk=None):
        group = self.get_object()
        user = request.user
        if group.join_policy != GroupJoinPolicy.REQUEST:
            return Response({"detail": "Group does not use join requests."}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = GroupJoinRequest.objects.get_or_create(
            group=group,
            user=user,
            defaults={"message": request.data.get("message", "")},
        )
        serializer = GroupJoinRequestSerializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="approve-request")
    def approve_request(self, request, pk=None):
        group = self.get_object()
        membership = self._get_membership(group, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can approve requests.")

        request_id = request.data.get("request_id")
        join_req = GroupJoinRequest.objects.filter(id=request_id, group=group).first()
        if not join_req:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        join_req.status = GroupJoinRequestStatus.APPROVED
        join_req.reviewed_by = request.user
        join_req.reviewed_at = timezone.now()
        join_req.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        GroupMembership.objects.update_or_create(
            group=group,
            user=join_req.user,
            defaults={"role": GroupRole.MEMBER, "left_at": None, "is_banned": False},
        )

        ConversationMember.objects.update_or_create(
            conversation=group.conversation,
            user=join_req.user,
            defaults={"base_role": BaseConversationRole.MEMBER, "left_at": None},
        )

        return Response({"detail": "Approved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject-request")
    def reject_request(self, request, pk=None):
        group = self.get_object()
        membership = self._get_membership(group, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can reject requests.")

        request_id = request.data.get("request_id")
        join_req = GroupJoinRequest.objects.filter(id=request_id, group=group).first()
        if not join_req:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        join_req.status = GroupJoinRequestStatus.REJECTED
        join_req.reviewed_by = request.user
        join_req.reviewed_at = timezone.now()
        join_req.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        return Response({"detail": "Rejected."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="ban")
    def ban(self, request, pk=None):
        group = self.get_object()
        membership = self._get_membership(group, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can ban.")

        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id required."}, status=status.HTTP_400_BAD_REQUEST)
        ban, _ = GroupBan.objects.update_or_create(
            group=group,
            user_id=user_id,
            defaults={
                "reason": request.data.get("reason", ""),
                "banned_by": request.user,
                "expires_at": request.data.get("expires_at"),
            },
        )
        GroupMembership.objects.filter(group=group, user_id=user_id).update(is_banned=True)
        return Response(GroupBanSerializer(ban).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="unban")
    def unban(self, request, pk=None):
        group = self.get_object()
        membership = self._get_membership(group, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can unban.")

        user_id = request.data.get("user_id")
        GroupBan.objects.filter(group=group, user_id=user_id).delete()
        GroupMembership.objects.filter(group=group, user_id=user_id).update(is_banned=False)
        return Response({"detail": "Unbanned."}, status=status.HTTP_200_OK)
