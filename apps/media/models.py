# media/models.py
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

USER = settings.AUTH_USER_MODEL

class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True

class MediaAsset(BaseEntity):
    """
    Core asset with packed advanced fields
    """
    MEDIA_TYPES = [
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("document", "Document"),
        ("three_d", "3D"),
    ]
    owner = models.ForeignKey(USER, related_name="media_assets", on_delete=models.SET_NULL, null=True)
    type = models.CharField(max_length=32, choices=MEDIA_TYPES)
    bucket_key = models.CharField(max_length=1024)  # path/key in object storage
    canonical_url = models.URLField(max_length=2000, blank=True, null=True)
    mime_type = models.CharField(max_length=256, blank=True)
    bytes = models.BigIntegerField(default=0)
    dims = models.CharField(max_length=128, blank=True, help_text='WxH or duration')
    checksum = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=64, default="pending", db_index=True)  # pending|ready|blocked
    security = models.JSONField(default=dict, blank=True)      # { clientEncrypted, keyRef, drmPolicyId }
    provenance = models.JSONField(default=dict, blank=True)    # { originHash, anchorTx, editSummary }
    labels = models.JSONField(default=dict, blank=True)        # { synthetic: {...}, fingerprints: {...}, tags: [...] }
    storage = models.JSONField(default=dict, blank=True)       # { tier, retentionPolicy }
    metadata = models.JSONField(default=dict, blank=True)      # generic extensible metadata

    class Meta:
        indexes = [
            models.Index(fields=["type", "status"]),
        ]

    def __str__(self):
        return f"{self.type} {self.id}"

    def mark_ready(self, url=None):
        self.status = "ready"
        if url:
            self.canonical_url = url
        self.save(update_fields=["status", "canonical_url", "updated_at"])

class MediaVariant(BaseEntity):
    asset = models.ForeignKey(MediaAsset, related_name="variants", on_delete=models.CASCADE)
    purpose = models.CharField(max_length=64)   # thumbnail | adaptive | preview | low_bandwidth
    codec = models.CharField(max_length=128, blank=True)
    dims = models.CharField(max_length=128, blank=True)
    bytes = models.BigIntegerField(default=0)
    url = models.URLField(max_length=2000, blank=True, null=True)
    variant_meta = models.JSONField(default=dict, blank=True)  # { signed, edgeHints, personalizationRuleId }

    class Meta:
        unique_together = ("asset", "purpose", "codec")

class ProcessingJob(BaseEntity):
    PIPELINES = [
        ("transcode", "Transcode"),
        ("phash", "PerceptualHash"),
        ("watermark", "Watermark"),
        ("analyze", "Analyze"),
        ("redact", "Redact"),
    ]
    STATUS = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]
    asset = models.ForeignKey(MediaAsset, related_name="jobs", on_delete=models.CASCADE)
    pipeline = models.CharField(max_length=64, choices=PIPELINES)
    status = models.CharField(max_length=32, choices=STATUS, default="queued", db_index=True)
    priority = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    worker_meta = models.JSONField(default=dict, blank=True)   # { region, costEstimateCents }
    result_meta = models.JSONField(default=dict, blank=True)   # outcome (phash, labels, errors...)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def mark_running(self, worker_meta=None):
        self.status = "running"
        self.started_at = timezone.now()
        if worker_meta:
            self.worker_meta = worker_meta
        self.save(update_fields=["status", "started_at", "worker_meta", "updated_at"])

    def mark_done(self, result_meta=None):
        self.status = "done"
        self.finished_at = timezone.now()
        if result_meta:
            self.result_meta = result_meta
        self.save(update_fields=["status", "finished_at", "result_meta", "updated_at"])

class Provenance(BaseEntity):
    asset = models.OneToOneField(MediaAsset, related_name="provenance_detail", on_delete=models.CASCADE)
    origin_hash = models.CharField(max_length=256)
    anchor = models.JSONField(default=dict, blank=True)       # { chain, txHash, anchoredAt }
    version_log = models.JSONField(default=list, blank=True)  # edits and signatures

class Watermark(BaseEntity):
    asset = models.ForeignKey(MediaAsset, related_name="watermarks", on_delete=models.CASCADE)
    type = models.CharField(max_length=32, default="invisible")  # visible|invisible|robust
    proof = models.JSONField(default=dict, blank=True)           # detection proofs, confidence

class AccessPolicy(BaseEntity):
    asset = models.OneToOneField(MediaAsset, related_name="access_policy", on_delete=models.CASCADE)
    rules = models.JSONField(default=dict, blank=True)  # { users, roles, geofence, timeWindow }
    drm = models.JSONField(default=dict, blank=True)    # { enabled, policyId, licenseRef }

class MediaMetrics(BaseEntity):
    asset = models.OneToOneField(MediaAsset, related_name="metrics", on_delete=models.CASCADE)
    views = models.BigIntegerField(default=0)
    stream_minutes = models.BigIntegerField(default=0)
    downloads = models.BigIntegerField(default=0)
    reaction_summary = models.JSONField(default=dict, blank=True)  # aggregated interactions
    carbon_grams = models.FloatField(default=0.0)
    cost_cents = models.BigIntegerField(default=0)

    def add_view(self, minutes=0):
        self.views = models.F('views') + 1
        if minutes:
            self.stream_minutes = models.F('stream_minutes') + minutes
        self.save(update_fields=["views", "stream_minutes", "updated_at"])
        # refresh from db to get int value
        self.refresh_from_db()

    def estimate_carbon(self, bytes_processed: int, region_factor: float = 0.0000001):
        """
        Very simple carbon estimator: bytes_processed * region_factor => grams
        This should be replaced with a more robust model in production.
        """
        added = bytes_processed * region_factor
        self.carbon_grams = models.F('carbon_grams') + added
        self.save(update_fields=["carbon_grams", "updated_at"])
        self.refresh_from_db()
        return self.carbon_grams
