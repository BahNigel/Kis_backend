from django.test import TestCase
from .models import AIJob, TranslationRequest


class BasicModelTest(TestCase):
    def test_create_translation_job_and_request(self):
        job = AIJob.objects.create(job_type='TRANSLATION', input_ref_type='TEXT')
        tr = TranslationRequest.objects.create(job=job, source_lang='en', target_lang='fr', text_chars=10)
        self.assertEqual(tr.job, job)
