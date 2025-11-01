from django.test import TestCase
from .models import Metric

class AnalyticsSmokeTest(TestCase):
    def test_metric_and_prediction(self):
        m = Metric.objects.create(kind='system', name='test', value=10.0)
        self.assertIsNotNone(m.id)