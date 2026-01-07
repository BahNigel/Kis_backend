# apps/communities/views.py
from django.db import models, transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from apps.communities.models import Community
from apps.communities.serializers import (
    CommunityListSerializer,
    CommunityDetailSerializer,
    CommunityCreateSerializer,
    CommunityMembershipSerializer,
    CommunityJoinRequestSerializer,
    CommunityBanSerializer,
    CommunityPostSerializer,
    CommunityPostCreateSerializer,
    CommunityPostCommentSerializer,
)
from apps.communities.models import (
    CommunityMembership,
    CommunityJoinRequest,
    CommunityJoinRequestStatus,
    CommunityRole,
    CommunityBan,
    CommunityPost,
    CommunityPostComment,
    CommunityPostReaction,
    CommunityCommentReaction,
    CommunityPostStatus,
    CommunityJoinPolicy,
    CommunityPostPolicy,
)
from apps.accounts.models import User


class CommunityViewSet(viewsets.ModelViewSet):
    """
    /api/v1/communities/communities/

    - list:       GET    /api/v1/communities/communities/
    - create:     POST   /api/v1/communities/communities/
    - retrieve:   GET    /api/v1/communities/communities/{id}/
    - update:     PUT/PATCH /api/v1/communities/communities/{id}/
    - deactivate: POST   /api/v1/communities/communities/{id}/deactivate/
    """
    permission_classes = [IsAuthenticated]
    queryset = Community.objects.select_related("partner", "owner", "main_conversation")

    def get_serializer_class(self):
        if self.action == "list":
            return CommunityListSerializer
        if self.action == "create":
            return CommunityCreateSerializer
        return CommunityDetailSerializer

    def get_queryset(self):
        """
        For now:
        - Return communities where:
          - the user is the owner, OR
          - the user is an active member of the community.
        """
        user = self.request.user
        qs = (
            Community.objects
            .select_related("partner", "owner", "main_conversation")
            .filter(
                models.Q(owner=user)
                | models.Q(
                    memberships__user=user,
                    memberships__left_at__isnull=True,
                    memberships__is_banned=False,
                )
            )
        )
        partner_id = self.request.query_params.get("partner")
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save()

    def _get_membership(self, community: Community, user):
        return CommunityMembership.objects.filter(
            community=community,
            user=user,
            left_at__isnull=True,
        ).first()

    def _is_admin(self, membership: CommunityMembership | None) -> bool:
        return membership and membership.role in (
            CommunityRole.OWNER,
            CommunityRole.ADMIN,
            CommunityRole.MOD,
        )

    def _ensure_conversation_membership(self, community: Community, user):
        from apps.chat.models import ConversationMember, BaseConversationRole

        if community.main_conversation_id:
            ConversationMember.objects.get_or_create(
                conversation=community.main_conversation,
                user=user,
                defaults={"base_role": BaseConversationRole.MEMBER},
            )
        if community.posts_conversation_id:
            ConversationMember.objects.get_or_create(
                conversation=community.posts_conversation,
                user=user,
                defaults={"base_role": BaseConversationRole.MEMBER},
            )

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """
        Soft-deactivate a community.

        For now: only the community owner can deactivate.
        Later you can plug in RBAC (partner-level admin, global admin, etc.).
        """
        community = self.get_object()

        if community.owner != request.user:
            return Response(
                {"detail": "Only the community owner can deactivate this community (for now)."},
                status=status.HTTP_403_FORBIDDEN,
            )

        community.is_active = False
        community.save()

        return Response({"detail": "Community deactivated."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        community = self.get_object()
        qs = CommunityMembership.objects.filter(community=community, left_at__isnull=True)
        serializer = CommunityMembershipSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="join")
    def join(self, request, pk=None):
        community = self.get_object()
        user = request.user

        if community.join_policy != CommunityJoinPolicy.OPEN:
            return Response(
                {"detail": "Community is not open to direct join."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership, _ = CommunityMembership.objects.get_or_create(
            community=community,
            user=user,
            defaults={"role": CommunityRole.MEMBER},
        )
        if membership.left_at is not None:
            membership.left_at = None
            membership.is_banned = False
            membership.save(update_fields=["left_at", "is_banned"])

        self._ensure_conversation_membership(community, user)

        return Response(CommunityMembershipSerializer(membership).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="add-members")
    def add_members(self, request, pk=None):
        """
        Add members to a community by user IDs.
        Payload:
          {
            "userIds": ["uuid", "uuid", ...]
          }
        """
        community = self.get_object()
        membership = self._get_membership(community, request.user)
        if community.owner != request.user and not self._is_admin(membership):
            raise PermissionDenied("Only community admins can add members.")

        raw_ids = request.data.get("userIds") or request.data.get("user_ids") or []
        if not isinstance(raw_ids, list):
            return Response({"detail": "userIds must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        user_ids = [str(uid) for uid in raw_ids if uid]
        if not user_ids:
            return Response({"detail": "No userIds provided."}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(id__in=user_ids, is_active=True)
        added: list[str] = []

        for target in users:
            if target.id == request.user.id:
                continue
            m, created = CommunityMembership.objects.get_or_create(
                community=community,
                user=target,
                defaults={"role": CommunityRole.MEMBER},
            )
            if m.left_at is not None or m.is_banned:
                m.left_at = None
                m.is_banned = False
                m.save(update_fields=["left_at", "is_banned"])
            self._ensure_conversation_membership(community, target)
            if created:
                added.append(str(target.id))

        return Response({"added": added, "count": len(added)}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="leave")
    def leave(self, request, pk=None):
        community = self.get_object()
        membership = self._get_membership(community, request.user)
        if not membership:
            return Response({"detail": "Not a member."}, status=status.HTTP_400_BAD_REQUEST)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        return Response({"detail": "Left community."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="request-join")
    def request_join(self, request, pk=None):
        community = self.get_object()
        user = request.user
        if community.join_policy != CommunityJoinPolicy.REQUEST:
            return Response(
                {"detail": "Community does not use join requests."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj, _ = CommunityJoinRequest.objects.get_or_create(
            community=community,
            user=user,
            defaults={"message": request.data.get("message", "")},
        )
        serializer = CommunityJoinRequestSerializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="approve-request")
    def approve_request(self, request, pk=None):
        community = self.get_object()
        membership = self._get_membership(community, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can approve requests.")

        request_id = request.data.get("request_id")
        join_req = CommunityJoinRequest.objects.filter(id=request_id, community=community).first()
        if not join_req:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        join_req.status = CommunityJoinRequestStatus.APPROVED
        join_req.reviewed_by = request.user
        join_req.reviewed_at = timezone.now()
        join_req.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        CommunityMembership.objects.update_or_create(
            community=community,
            user=join_req.user,
            defaults={"role": CommunityRole.MEMBER, "left_at": None, "is_banned": False},
        )

        self._ensure_conversation_membership(community, join_req.user)

        return Response({"detail": "Approved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject-request")
    def reject_request(self, request, pk=None):
        community = self.get_object()
        membership = self._get_membership(community, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can reject requests.")

        request_id = request.data.get("request_id")
        join_req = CommunityJoinRequest.objects.filter(id=request_id, community=community).first()
        if not join_req:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        join_req.status = CommunityJoinRequestStatus.REJECTED
        join_req.reviewed_by = request.user
        join_req.reviewed_at = timezone.now()
        join_req.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        return Response({"detail": "Rejected."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="ban")
    def ban(self, request, pk=None):
        community = self.get_object()
        membership = self._get_membership(community, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can ban.")

        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id required."}, status=status.HTTP_400_BAD_REQUEST)
        ban, _ = CommunityBan.objects.update_or_create(
            community=community,
            user_id=user_id,
            defaults={
                "reason": request.data.get("reason", ""),
                "banned_by": request.user,
                "expires_at": request.data.get("expires_at"),
            },
        )
        CommunityMembership.objects.filter(community=community, user_id=user_id).update(is_banned=True)
        return Response(CommunityBanSerializer(ban).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="unban")
    def unban(self, request, pk=None):
        community = self.get_object()
        membership = self._get_membership(community, request.user)
        if not self._is_admin(membership):
            raise PermissionDenied("Only admins can unban.")

        user_id = request.data.get("user_id")
        CommunityBan.objects.filter(community=community, user_id=user_id).delete()
        CommunityMembership.objects.filter(community=community, user_id=user_id).update(is_banned=False)
        return Response({"detail": "Unbanned."}, status=status.HTTP_200_OK)


class CommunityPostViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = CommunityPost.objects.select_related("community", "author")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return CommunityPostCreateSerializer
        return CommunityPostSerializer

    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get("community")
        qs = CommunityPost.objects.select_related("community", "author")
        if community_id:
            qs = qs.filter(community_id=community_id)
        return qs.filter(is_deleted=False)

    def _get_membership(self, community: Community, user):
        return CommunityMembership.objects.filter(
            community=community,
            user=user,
            left_at__isnull=True,
            is_banned=False,
        ).first()

    def perform_create(self, serializer):
        community = serializer.validated_data["community"]
        membership = self._get_membership(community, self.request.user)
        if not membership:
            raise PermissionDenied("Join the community to post.")

        if community.post_policy in (CommunityPostPolicy.ADMINS_ONLY, CommunityPostPolicy.MODS_ONLY):
            if membership.role not in (CommunityRole.OWNER, CommunityRole.ADMIN, CommunityRole.MOD):
                raise PermissionDenied("Only admins/moderators can post.")

        status_val = CommunityPostStatus.PUBLISHED
        if community.require_post_approval:
            status_val = CommunityPostStatus.PENDING

        serializer.save(author=self.request.user, status=status_val)

    @action(detail=True, methods=["post"], url_path="comment")
    def comment(self, request, pk=None):
        post = self.get_object()
        membership = self._get_membership(post.community, request.user)
        if not membership:
            raise PermissionDenied("Join the community to comment.")
        if not post.community.allow_comments:
            raise PermissionDenied("Comments are disabled.")
        comment = CommunityPostComment.objects.create(
            post=post,
            author=request.user,
            text=request.data.get("text", ""),
        )
        return Response(CommunityPostCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="react")
    def react(self, request, pk=None):
        post = self.get_object()
        membership = self._get_membership(post.community, request.user)
        if not membership:
            raise PermissionDenied("Join the community to react.")
        if not post.community.allow_reactions:
            raise PermissionDenied("Reactions are disabled.")
        emoji = request.data.get("emoji")
        if not emoji:
            return Response({"detail": "emoji required."}, status=status.HTTP_400_BAD_REQUEST)

        reaction, created = CommunityPostReaction.objects.get_or_create(
            post=post,
            user=request.user,
            defaults={"emoji": emoji},
        )
        if not created:
            reaction.emoji = emoji
            reaction.save(update_fields=["emoji"])

        return Response({"detail": "Reaction saved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="pin")
    def pin(self, request, pk=None):
        post = self.get_object()
        membership = self._get_membership(post.community, request.user)
        if not membership or membership.role not in (CommunityRole.OWNER, CommunityRole.ADMIN, CommunityRole.MOD):
            raise PermissionDenied("Only admins/moderators can pin.")
        post.is_pinned = True
        post.pinned_by = request.user
        post.pinned_at = timezone.now()
        post.save(update_fields=["is_pinned", "pinned_by", "pinned_at"])
        return Response({"detail": "Pinned."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="unpin")
    def unpin(self, request, pk=None):
        post = self.get_object()
        membership = self._get_membership(post.community, request.user)
        if not membership or membership.role not in (CommunityRole.OWNER, CommunityRole.ADMIN, CommunityRole.MOD):
            raise PermissionDenied("Only admins/moderators can unpin.")
        post.is_pinned = False
        post.pinned_by = None
        post.pinned_at = None
        post.save(update_fields=["is_pinned", "pinned_by", "pinned_at"])
        return Response({"detail": "Unpinned."}, status=status.HTTP_200_OK)
