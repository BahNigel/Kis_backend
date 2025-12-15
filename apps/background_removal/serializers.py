# apps/background_removal/serializers.py
from rest_framework import serializers
from .models import BackgroundRemovalJob

class BackgroundRemovalJobCreateSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True)

    class Meta:
        model = BackgroundRemovalJob
        fields = ["id", "image"]

    def create(self, validated_data):
        image = validated_data.pop("image")
        job = BackgroundRemovalJob.objects.create(original_image=image)
        return job


class BackgroundRemovalJobStatusSerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(source="id")
    processed_file_url = serializers.SerializerMethodField()

    class Meta:
        model = BackgroundRemovalJob
        fields = [
            "job_id",
            "status",
            "processed_file_url",
            "error_message",
        ]

    def get_processed_file_url(self, obj):
        if not obj.processed_image:
            return None
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(obj.processed_image.url)
        return obj.processed_image.url
