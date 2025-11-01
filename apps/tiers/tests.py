from django.test import TestCase
from .models import BillingPlan

class TiersSmokeTest(TestCase):
    def test_plan_create(self):
        p = BillingPlan.objects.create(slug='basic', display_name='Basic', price_per_month=0)
        self.assertIsNotNone(p.id)