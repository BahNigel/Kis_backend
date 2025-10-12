from django.test import TestCase
from django.utils import timezone
from . import models


class EventModelTest(TestCase):
    def test_create_event(self):
        ev = models.Event.objects.create(owner_id=uuid4(), title="Test Event", slug="test-event", start_at=timezone.now(), end_at=timezone.now())
        self.assertIsNotNone(ev.id)
