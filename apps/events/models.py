from django.db import models
from django.utils import timezone
import uuid


def uuid4():
    return uuid.uuid4()


class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Event(BaseEntity):
    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("unlisted", "Unlisted"),
        ("private", "Private"),
    ]
    TYPE_CHOICES = [
        ("conference", "Conference"),
        ("meetup", "Meetup"),
        ("workshop", "Workshop"),
        ("hybrid", "Hybrid"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    owner_id = models.UUIDField()  # references account.User ID (external app)
    org_id = models.UUIDField(null=True, blank=True)
    group_id = models.UUIDField(null=True, blank=True)

    title = models.CharField(max_length=400)
    slug = models.SlugField(max_length=450, unique=True)
    description = models.TextField(blank=True)

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="UTC")

    location_name = models.CharField(max_length=255, blank=True)
    location_geo = models.CharField(max_length=128, blank=True)  # lat,lng
    virtual_venue_url = models.URLField(blank=True)

    visibility = models.CharField(max_length=32, choices=VISIBILITY_CHOICES, default="public")
    type = models.CharField(max_length=32, choices=TYPE_CHOICES, default="meetup")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="draft")

    capacity = models.PositiveIntegerField(null=True, blank=True)
    accessibility_options = models.JSONField(default=dict, blank=True)
    privacy_policy_id = models.UUIDField(null=True, blank=True)

    linked_content = models.ManyToManyField("content.Content", blank=True)  # from user's content app

    class Meta:
        ordering = ["-start_at"]

    def __str__(self):
        return f"{self.title} ({self.start_at.date()})"


class EventSession(BaseEntity):
    SESSION_TYPES = [
        ("talk", "Talk"),
        ("panel", "Panel"),
        ("workshop", "Workshop"),
        ("keynote", "Keynote"),
    ]

    event = models.ForeignKey(Event, related_name="sessions", on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
    speaker_ids = models.JSONField(default=list, blank=True)  # list of user UUIDs
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    room_id = models.UUIDField(null=True, blank=True)
    stream_id = models.UUIDField(null=True, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    session_type = models.CharField(max_length=32, choices=SESSION_TYPES, default="talk")

    class Meta:
        ordering = ["start_at"]

    def __str__(self):
        return f"{self.title} @ {self.event.title}"


class Venue(BaseEntity):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    geo_json = models.JSONField(default=dict, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    accessibility_info = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class SeatMap(BaseEntity):
    venue = models.ForeignKey(Venue, related_name="seat_maps", on_delete=models.CASCADE)
    layout_json = models.JSONField(default=dict)  # coordinates, rows, zones
    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"SeatMap {self.venue.name} v{self.version}"


class Seat(BaseEntity):
    seat_map = models.ForeignKey(SeatMap, related_name="seats", on_delete=models.CASCADE)
    label = models.CharField(max_length=64)
    x = models.FloatField()
    y = models.FloatField()
    zone = models.CharField(max_length=64, blank=True)
    is_accessible = models.BooleanField(default=False)

    class Meta:
        unique_together = ("seat_map", "label")

    def __str__(self):
        return f"{self.seat_map} - {self.label}"


class Ticket(BaseEntity):
    TYPE_CHOICES = [
        ("general", "General"),
        ("vip", "VIP"),
        ("staff", "Staff"),
        ("free", "Free"),
    ]

    event = models.ForeignKey(Event, related_name="tickets", on_delete=models.CASCADE)
    tier_name = models.CharField(max_length=128)
    sku = models.CharField(max_length=128, unique=True)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    price_cents = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=8, default="USD")
    quantity_total = models.IntegerField(default=0)
    quantity_remaining = models.IntegerField(default=0)
    seat_map = models.ForeignKey(SeatMap, null=True, blank=True, on_delete=models.SET_NULL)
    transferable = models.BooleanField(default=False)
    refundable = models.BooleanField(default=False)
    nft_token_id = models.CharField(max_length=256, blank=True, null=True)
    blockchain_tx_hash = models.CharField(max_length=256, blank=True, null=True)

    def reserve(self, qty=1):
        if self.quantity_remaining < qty:
            raise ValueError("Not enough tickets remaining")
        self.quantity_remaining -= qty
        self.save()

    def release(self, qty=1):
        self.quantity_remaining += qty
        if self.quantity_remaining > self.quantity_total:
            self.quantity_remaining = self.quantity_total
        self.save()

    def __str__(self):
        return f"{self.event.title} - {self.tier_name}"


class TicketVariant(BaseEntity):
    ticket = models.ForeignKey(Ticket, related_name="variants", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    perks = models.JSONField(default=dict, blank=True)
    price_cents = models.BigIntegerField(default=0)
    eligibility_rules = models.JSONField(default=dict, blank=True)


class TicketSale(BaseEntity):
    STATUS_CHOICES = [
        ("completed", "Completed"),
        ("refunded", "Refunded"),
        ("pending", "Pending"),
    ]

    ticket = models.ForeignKey(Ticket, related_name="sales", on_delete=models.PROTECT)
    buyer_id = models.UUIDField()  # points to accounts.User
    qty = models.PositiveIntegerField()
    total_cents = models.BigIntegerField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    payment_ref = models.CharField(max_length=255, blank=True)
    purchased_at = models.DateTimeField(default=timezone.now)
    transferred_to_id = models.UUIDField(null=True, blank=True)

    def mark_completed(self):
        self.status = "completed"
        self.save()


class Refund(BaseEntity):
    ticket_sale = models.ForeignKey(TicketSale, related_name="refunds", on_delete=models.CASCADE)
    amount_cents = models.BigIntegerField()
    currency = models.CharField(max_length=8, default="USD")
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=64, default="requested")


class Waitlist(BaseEntity):
    event = models.ForeignKey(Event, related_name="waitlist", on_delete=models.CASCADE)
    user_id = models.UUIDField()
    requested_at = models.DateTimeField(default=timezone.now)
    notified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, default="waiting")


class HybridStream(BaseEntity):
    PROVIDER_CHOICES = [
        ("webrtc", "WebRTC"),
        ("hls", "HLS"),
        ("low_latency_cdn", "Low-latency CDN"),
    ]

    session = models.OneToOneField(EventSession, related_name="hybrid_stream", on_delete=models.CASCADE)
    provider = models.CharField(max_length=64, choices=PROVIDER_CHOICES)
    ingest_url = models.URLField()
    playback_url = models.URLField()
    latency_ms = models.IntegerField(default=1000)
    max_viewers = models.IntegerField(default=1000)


class CheckInDevice(BaseEntity):
    DEVICE_TYPES = [
        ("kiosk", "Kiosk"),
        ("mobile_scanner", "Mobile Scanner"),
        ("beacon", "Beacon"),
        ("nfc_reader", "NFC Reader"),
    ]
    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=64, choices=DEVICE_TYPES)
    location_geo = models.CharField(max_length=128, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    public_key = models.TextField(blank=True, null=True)


class Beacon(BaseEntity):
    device = models.ForeignKey(CheckInDevice, related_name="beacons", on_delete=models.CASCADE)
    uuid = models.CharField(max_length=128)
    major = models.IntegerField()
    minor = models.IntegerField()
    floor = models.CharField(max_length=64, blank=True, null=True)


class Attendance(BaseEntity):
    STATUS_CHOICES = [
        ("invited", "Invited"),
        ("rsvped", "RSVPed"),
        ("cancelled", "Cancelled"),
        ("checked_in", "Checked in"),
    ]

    event = models.ForeignKey(Event, related_name="attendances", on_delete=models.CASCADE)
    session = models.ForeignKey(EventSession, related_name="attendances", on_delete=models.CASCADE, null=True, blank=True)
    user_id = models.UUIDField()
    ticket = models.ForeignKey(Ticket, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="invited")
    rsvp_at = models.DateTimeField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    check_in_method = models.CharField(max_length=64, blank=True)
    check_in_device = models.ForeignKey(CheckInDevice, null=True, blank=True, on_delete=models.SET_NULL)
    duration_sec = models.IntegerField(null=True, blank=True)
    engagement_score = models.FloatField(null=True, blank=True)
    fraud_score = models.FloatField(null=True, blank=True)


class Sponsor(BaseEntity):
    name = models.CharField(max_length=255)
    contact_info = models.JSONField(default=dict, blank=True)
    tier = models.CharField(max_length=64, blank=True)


class SponsorSlot(BaseEntity):
    event = models.ForeignKey(Event, related_name="sponsor_slots", on_delete=models.CASCADE)
    sponsor = models.ForeignKey(Sponsor, related_name="slots", on_delete=models.CASCADE)
    slot_type = models.CharField(max_length=64)
    price_cents = models.BigIntegerField(default=0)
    metrics = models.JSONField(default=dict, blank=True)


class InsurancePolicy(BaseEntity):
    ticket_sale = models.ForeignKey(TicketSale, related_name="insurance", null=True, blank=True, on_delete=models.SET_NULL)
    provider = models.CharField(max_length=255)
    policy_number = models.CharField(max_length=255)
    coverage_json = models.JSONField(default=dict, blank=True)
    premium_cents = models.BigIntegerField(default=0)
    status = models.CharField(max_length=64, default="active")


class SmartContract(BaseEntity):
    event = models.ForeignKey(Event, related_name="smart_contracts", on_delete=models.CASCADE)
    contract_address = models.CharField(max_length=255)
    terms_json = models.JSONField(default=dict, blank=True)
    payout_rules = models.JSONField(default=dict, blank=True)


class FraudScore(BaseEntity):
    target_id = models.UUIDField()
    target_type = models.CharField(max_length=64)
    score = models.FloatField()
    reasons = models.JSONField(default=list, blank=True)
    computed_at = models.DateTimeField(default=timezone.now)


class Poll(BaseEntity):
    session = models.ForeignKey(EventSession, related_name="polls", on_delete=models.CASCADE, null=True, blank=True)
    question = models.TextField()
    options = models.JSONField(default=list)
    results_json = models.JSONField(default=dict, blank=True)
    is_anonymous = models.BooleanField(default=True)


class QnA(BaseEntity):
    session = models.ForeignKey(EventSession, related_name="qna", on_delete=models.CASCADE)
    question_text = models.TextField()
    asked_by_id = models.UUIDField(null=True, blank=True)
    answered_by_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=32, default="open")


class LiveTranscript(BaseEntity):
    session = models.ForeignKey(EventSession, related_name="transcripts", on_delete=models.CASCADE)
    transcript_url = models.URLField()
    generated_at = models.DateTimeField(default=timezone.now)
    language = models.CharField(max_length=16, default="en")


class Highlights(BaseEntity):
    session = models.ForeignKey(EventSession, related_name="highlights", on_delete=models.CASCADE)
    clip_urls = models.JSONField(default=list)
    generated_at = models.DateTimeField(default=timezone.now)


class AttendanceCertificate(BaseEntity):
    attendance = models.OneToOneField(Attendance, related_name="certificate", on_delete=models.CASCADE)
    certificate_url = models.URLField()
    issued_at = models.DateTimeField(default=timezone.now)
    cert_details = models.JSONField(default=dict, blank=True)


class CEApproval(BaseEntity):
    event = models.ForeignKey(Event, related_name="ce_approvals", on_delete=models.CASCADE)
    provider_name = models.CharField(max_length=255)
    credits = models.FloatField()
    approval_ref = models.CharField(max_length=255)


class MatchmakingProfile(BaseEntity):
    user_id = models.UUIDField()
    event = models.ForeignKey(Event, related_name="matchmaking_profiles", on_delete=models.CASCADE)
    interests = models.JSONField(default=list)
    networking_score = models.FloatField(default=0)


class NetworkingSession(BaseEntity):
    event = models.ForeignKey(Event, related_name="networking_sessions", on_delete=models.CASCADE)
    host_id = models.UUIDField()
    mode = models.CharField(max_length=64)
    capacity = models.IntegerField(default=10)
    matching_rules = models.JSONField(default=dict)


class EventAIAnalysis(BaseEntity):
    event = models.OneToOneField(Event, related_name="ai_analysis", on_delete=models.CASCADE)
    attendance_trend_json = models.JSONField(default=dict)
    sentiment_by_session = models.JSONField(default=dict)
    predicted_no_show_rate = models.FloatField(default=0.0)
    recommended_capacity_adjustments = models.JSONField(default=dict)