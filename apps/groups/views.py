# apps/groups/views.py
from django.db import models
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

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
)


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
    queryset = Group.objects.select_related("conversation", "owner", "partner", "community")

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

    def get_queryset(self):
        user = self.request.user
        # List groups where user is owner OR active member of the backing conversation.
        return (
            Group.objects
            .select_related("conversation", "owner", "partner", "community")
            .filter(
                models.Q(owner=user)
                | models.Q(
                    conversation__memberships__user=user,
                    conversation__memberships__left_at__isnull=True,
                )
            )
            .distinct()
        )

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
