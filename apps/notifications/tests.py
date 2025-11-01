
from django.test import TestCase
from django.utils import timezone
from . import models, services
import uuid


class NotificationTest(TestCase):
    def test_create_and_dedupe(self):
        uid = uuid.uuid4()
        notif1 = services.create_notification(user_id=uid, type="EVENT_ALERT", title="Hello", body="World", dedup_key="evt-1")
        notif2 = services.create_notification(user_id=uid, type="EVENT_ALERT", title="Hello", body="World", dedup_key="evt-1")
        self.assertEqual(str(notif1.id), str(notif2.id))

    def test_template_render(self):
        tpl = models.NotificationTemplate.objects.create(key="test.tpl", title_template="Hi {{name}}", body_template="Welcome {{name}}")
        title, body = tpl.render({"name": "Nigel"})
        self.assertIn("Nigel", title)