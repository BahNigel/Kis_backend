# apps/background_removal/models.py
import uuid
from django.db import models

class BackgroundRemovalJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        PROCESSING = "PROCESSING"
        DONE = "DONE"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    original_image = models.ImageField(upload_to="bg_removal/originals/")
    processed_image = models.ImageField(
        upload_to="bg_removal/processed/",
        null=True,
        blank=True,
    )

    error_message = models.TextField(null=True, blank=True)

    # Optional: link to user/message/etc.
    # owner = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"BGJob {self.id} [{self.status}]"
