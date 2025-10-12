# content/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Content, Comment, Reaction, ContentView, ContentMetrics

User = get_user_model()

class ContentMetricsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.content = Content.objects.create(author=self.user, title="T", body="B", is_published=True)

    def test_views_recalc(self):
        ContentView.objects.create(content=self.content, user=self.user, is_unique=True)
        m = self.content.recalc_metrics()
        self.assertEqual(m.views_count, 1)

    def test_reactions_and_comments(self):
        Reaction.objects.create(content=self.content, user=self.user, reaction_type="like")
        Comment.objects.create(content=self.content, author=self.user, text="hey")
        m = self.content.recalc_metrics()
        self.assertEqual(m.reactions_count, 1)
        self.assertEqual(m.comments_count, 1)
