from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Iterable

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.statuses.models import StatusItem, StatusItemView
from apps.statuses.serializers import StatusItemSerializer, StatusCreateSerializer


class StatusViewSet(viewsets.ModelViewSet):
    """
    /api/v1/statuses/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "create":
            return StatusCreateSerializer
        return StatusItemSerializer

    def _parse_user_ids(self) -> list[str]:
        request = self.request
        ids: set[str] = set()

        raw_ids = request.query_params.get("userIds") or request.query_params.get("user_ids")
        if raw_ids:
            for token in raw_ids.split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    ids.add(str(uuid.UUID(token)))
                except ValueError:
                    continue

        raw_phones = request.query_params.get("phones")
        if raw_phones:
            phones = [p.strip() for p in raw_phones.split(",") if p.strip()]
            if phones:
                found = User.objects.filter(phone__in=phones).values_list("id", flat=True)
                ids.update({str(uid) for uid in found})

        ids.add(str(request.user.id))
        return list(ids)

    def get_queryset(self):
        now = timezone.now()
        base = (
            StatusItem.objects
            .select_related("user", "user__profile")
            .filter(is_deleted=False, expires_at__gt=now)
        )
        if self.action in ("retrieve", "update", "partial_update", "destroy"):
            return base.filter(user=self.request.user)
        return base

    def list(self, request, *args, **kwargs):
        user_ids = self._parse_user_ids()
        items = (
            self.filter_queryset(self.get_queryset())
            .filter(user_id__in=user_ids)
            .order_by("-created_at")
        )
        viewed_ids = set(
            str(sid)
            for sid in StatusItemView.objects.filter(
                user=request.user,
                status_id__in=[item.id for item in items],
            ).values_list("status_id", flat=True)
        )

        grouped: dict[str, dict] = {}
        items_by_user: dict[str, list] = defaultdict(list)
        for item in items:
            items_by_user[str(item.user_id)].append(item)

        for user_id, user_items in items_by_user.items():
            user = user_items[0].user
            grouped[user_id] = {
                "user": {
                    "id": str(user.id),
                    "display_name": user.display_name or user.phone or f"User {user.id}",
                    "avatar_url": getattr(user.profile, "avatar_url", None),
                },
                "items": StatusItemSerializer(
                    user_items,
                    many=True,
                    context={"request": request, "viewed_ids": viewed_ids},
                ).data,
                "latest_at": user_items[0].created_at,
            }
            grouped[user_id]["has_unseen"] = any(
                not item.get("viewed") for item in grouped[user_id]["items"]
            )

        ordered = sorted(
            grouped.values(),
            key=lambda entry: entry["latest_at"],
            reverse=True,
        )

        # Move current user to the front if present.
        current_id = str(request.user.id)
        ordered = [item for item in ordered if item["user"]["id"] == current_id] + [
            item for item in ordered if item["user"]["id"] != current_id
        ]

        for entry in ordered:
            entry.pop("latest_at", None)

        return Response({"results": ordered}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        items = (
            self.get_queryset()
            .filter(user=request.user)
            .order_by("-created_at")
        )
        viewed_ids = set(
            str(sid)
            for sid in StatusItemView.objects.filter(
                user=request.user,
                status_id__in=[item.id for item in items],
            ).values_list("status_id", flat=True)
        )
        data = StatusItemSerializer(
            items,
            many=True,
            context={"request": request, "viewed_ids": viewed_ids},
        ).data
        return Response({"results": data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="view")
    def mark_view(self, request, pk=None):
        try:
            status_item = StatusItem.objects.get(
                id=pk,
                is_deleted=False,
                expires_at__gt=timezone.now(),
            )
        except StatusItem.DoesNotExist:
            return Response({"detail": "Status not found."}, status=status.HTTP_404_NOT_FOUND)

        StatusItemView.objects.get_or_create(status=status_item, user=request.user)
        return Response({"viewed": True, "id": str(status_item.id)}, status=status.HTTP_200_OK)
