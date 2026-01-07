# apps/partners/views.py
from django.db import models  # 👈 for models.Q

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.partners.models import Partner, PartnerPost
from apps.partners.serializers import (
    PartnerListSerializer,
    PartnerDetailSerializer,
    PartnerCreateSerializer,
    PartnerPostSerializer,
    PartnerPostCreateSerializer,
)
from apps.chat.models import BaseConversationRole, ConversationMember


class PartnerViewSet(viewsets.ModelViewSet):
    """
    /api/v1/partners/partners/

    - list:       GET     /api/v1/partners/partners/
    - create:     POST    /api/v1/partners/partners/
    - retrieve:   GET     /api/v1/partners/partners/{id}/
    - update:     PUT/PATCH /api/v1/partners/partners/{id}/
    - deactivate: POST    /api/v1/partners/partners/{id}/deactivate/
    """
    permission_classes = [IsAuthenticated]
    queryset = Partner.objects.select_related("owner", "main_conversation")
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return PartnerListSerializer
        if self.action == "create":
            return PartnerCreateSerializer
        return PartnerDetailSerializer

    def get_queryset(self):
        """
        For now:
        - Return partners where the user is the owner, OR
        - The user is a member of the partner's main conversation (if exists).
        """
        user = self.request.user

        # Only used in the filter; import kept here if needed elsewhere
        from apps.chat.models import ConversationMember  # noqa: F401

        return (
            Partner.objects
            .select_related("owner", "main_conversation")
            .filter(
                models.Q(owner=user)
                | models.Q(
                    main_conversation__memberships__user=user,
                    main_conversation__memberships__left_at__isnull=True,
                )
            )
            .distinct()
        )

    def perform_create(self, serializer):
        # Uses PartnerCreateSerializer.create(), which handles conversation creation
        serializer.save()

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """
        Soft-deactivate a partner.

        Later you can add RBAC (e.g. only owner or global admin).
        """
        partner = self.get_object()
        if partner.owner != request.user:
            return Response(
                {"detail": "Only the partner owner can deactivate this partner (for now)."},
                status=status.HTTP_403_FORBIDDEN,
            )

        partner.is_active = False
        partner.save(update_fields=["is_active"])

        return Response(
            {"detail": "Partner deactivated."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="admins")
    def add_admin(self, request, pk=None):
        """
        Add or promote a partner admin by user_id.
        """
        partner = self.get_object()
        if partner.owner != request.user:
            return Response(
                {"detail": "Only the partner owner can manage admins (for now)."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not partner.main_conversation_id:
            return Response(
                {"detail": "Partner has no main conversation to manage admins."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.models import User
        from apps.chat.models import ConversationMember

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        member, _ = ConversationMember.objects.get_or_create(
            conversation_id=partner.main_conversation_id,
            user=user,
            defaults={"base_role": BaseConversationRole.ADMIN},
        )
        if member.base_role not in (BaseConversationRole.OWNER, BaseConversationRole.ADMIN):
            member.base_role = BaseConversationRole.ADMIN
            member.save(update_fields=["base_role"])

        return Response({"detail": "Admin updated."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="admins/remove")
    def remove_admin(self, request, pk=None):
        """
        Demote an admin to MEMBER.
        """
        partner = self.get_object()
        if partner.owner != request.user:
            return Response(
                {"detail": "Only the partner owner can manage admins (for now)."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not partner.main_conversation_id:
            return Response(
                {"detail": "Partner has no main conversation to manage admins."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        member = ConversationMember.objects.filter(
            conversation_id=partner.main_conversation_id,
            user_id=user_id,
            left_at__isnull=True,
        ).first()

        if not member:
            return Response({"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND)

        if member.base_role == BaseConversationRole.OWNER:
            return Response(
                {"detail": "Owner role cannot be removed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.base_role = BaseConversationRole.MEMBER
        member.save(update_fields=["base_role"])

        return Response({"detail": "Admin removed."}, status=status.HTTP_200_OK)


class PartnerPostViewSet(viewsets.ModelViewSet):
    """
    /api/v1/partners/posts/

    - list:     GET  /api/v1/partners/posts/?partner=<partner_id>
    - create:   POST /api/v1/partners/posts/
    - retrieve: GET  /api/v1/partners/posts/{id}/
    """
    permission_classes = [IsAuthenticated]
    queryset = PartnerPost.objects.select_related("partner", "author")

    def get_serializer_class(self):
        if self.action == "create":
            return PartnerPostCreateSerializer
        return PartnerPostSerializer

    def _user_can_access_partner(self, partner: Partner, user) -> bool:
        if partner.owner_id == user.id:
            return True
        if partner.main_conversation_id:
            return partner.main_conversation.memberships.filter(
                user=user,
                left_at__isnull=True,
            ).exists()
        return False

    def get_queryset(self):
        user = self.request.user
        partner_id = self.request.query_params.get("partner")
        if partner_id:
            partner = Partner.objects.filter(id=partner_id).first()
            if not partner or not self._user_can_access_partner(partner, user):
                return PartnerPost.objects.none()
            return (
                PartnerPost.objects
                .select_related("partner", "author")
                .filter(partner=partner, is_deleted=False)
                .order_by("-created_at")
            )

        accessible_partners = Partner.objects.filter(
            models.Q(owner=user)
            | models.Q(
                main_conversation__memberships__user=user,
                main_conversation__memberships__left_at__isnull=True,
            )
        )
        return (
            PartnerPost.objects
            .select_related("partner", "author")
            .filter(partner__in=accessible_partners, is_deleted=False)
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        partner_id = self.request.data.get("partner")
        if not partner_id:
            raise ValidationError({"partner": "This field is required."})
        partner = Partner.objects.filter(id=partner_id).first()
        if not partner or not self._user_can_access_partner(partner, self.request.user):
            raise PermissionDenied("Not allowed to post to this partner.")
        serializer.save()
