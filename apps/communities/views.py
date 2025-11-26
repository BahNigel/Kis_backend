# apps/communities/views.py
from django.db import models
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.communities.models import Community
from apps.communities.serializers import (
    CommunityListSerializer,
    CommunityDetailSerializer,
    CommunityCreateSerializer,
)


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
          - the user is an active member of the community main conversation (if any).
        """
        user = self.request.user
        from apps.chat.models import ConversationMember

        return (
            Community.objects
            .select_related("partner", "owner", "main_conversation")
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
        serializer.save()

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
