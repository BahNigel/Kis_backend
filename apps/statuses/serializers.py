import json

from rest_framework import serializers

from apps.statuses.models import StatusItem, StatusType


class StatusItemSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    viewed = serializers.SerializerMethodField()

    class Meta:
        model = StatusItem
        fields = [
            "id",
            "type",
            "text",
            "style",
            "file_url",
            "duration_ms",
            "created_at",
            "expires_at",
            "viewed",
        ]

    def get_file_url(self, obj: StatusItem) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_viewed(self, obj: StatusItem) -> bool:
        viewed_ids = self.context.get("viewed_ids")
        if not viewed_ids:
            return False
        return str(obj.id) in viewed_ids


class StatusCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusItem
        fields = [
            "id",
            "type",
            "text",
            "file",
            "style",
            "duration_ms",
            "created_at",
            "expires_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "expires_at",
        ]

    def validate(self, attrs):
        status_type = attrs.get("type")
        text = (attrs.get("text") or "").strip()
        file = attrs.get("file")
        style = attrs.get("style")

        if isinstance(style, str):
            try:
                attrs["style"] = json.loads(style)
            except Exception:
                raise serializers.ValidationError({"style": "Invalid style payload."})

        if status_type == StatusType.TEXT and not text:
            raise serializers.ValidationError({"text": "Text status requires text."})
        if status_type != StatusType.TEXT and not file:
            raise serializers.ValidationError({"file": "Media status requires a file."})
        return attrs
