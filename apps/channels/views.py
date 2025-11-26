# apps/channels/views.py
from django.db import models
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.channels.models import Channel
from apps.channels.serializers import (
    ChannelListSerializer,
    ChannelDetailSerializer,
    ChannelCreateSerializer,
)


class ChannelViewSet(viewsets.ModelViewSet):
    """
    /api/v1/channels/channels/

    - list:       GET    /api/v1/channels/channels/
    - create:     POST   /api/v1/channels/channels/
    - retrieve:   GET    /api/v1/channels/channels/{id}/
    - update:     PUT/PATCH /api/v1/channels/channels/{id}/
    - archive:    POST   /api/v1/channels/channels/{id}/archive/
    """
    permission_classes = [IsAuthenticated]
    queryset = Channel.objects.select_related("conversation", "owner", "partner", "community")

    def get_serializer_class(self):
        if self.action == "list":
            return ChannelListSerializer
        if self.action == "create":
            return ChannelCreateSerializer
        return ChannelDetailSerializer

    def get_queryset(self):
        """
        For now:
        - Return channels where the user is an active member of the backing conversation.
        """
        user = self.request.user

        return (
            Channel.objects
            .select_related("conversation", "owner", "partner", "community")
            .filter(
                conversation__memberships__user=user,
                conversation__memberships__left_at__isnull=True,
            )
            .distinct()
        )

    def perform_create(self, serializer):
        serializer.save()  # ChannelCreateSerializer handles owner + conversation

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        """
        Archive the channel (and its conversation).

        For now: only the channel owner can archive.
        Later, plug in RBAC (partner/community-level admins, etc.).
        """
        channel = self.get_object()

        if channel.owner != request.user:
            return Response(
                {"detail": "Only the channel owner can archive this channel (for now)."},
                status=status.HTTP_403_FORBIDDEN,
            )

        channel.is_archived = True
        channel.save()

        conv = channel.conversation
        conv.is_archived = True
        conv.save()

        return Response({"detail": "Channel archived."}, status=status.HTTP_200_OK)
