from django.test import TestCase
from .models import Survey, Question

class SurveySmokeTest(TestCase):
    def test_create_survey_with_questions(self):
        s = Survey.objects.create(title='T', type=0)
        q = Question.objects.create(survey=s, text='Q1', vote_type=0, options=[{'id':'a','text':'A'}])
        self.assertEqual(s.questions.count(), 1)