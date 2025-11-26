# apps/partners/views.py
from django.db import models  # 👈 for models.Q

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.partners.models import Partner
from apps.partners.serializers import (
    PartnerListSerializer,
    PartnerDetailSerializer,
    PartnerCreateSerializer,
)


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
