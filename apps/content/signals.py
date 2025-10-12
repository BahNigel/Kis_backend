# content/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import Comment, Share, Reaction, ContentView, ContentMetrics, Content

@receiver(post_save, sender=Comment)
def on_comment_saved(sender, instance, created, **kwargs):
    # update metrics when comments are created or deleted (or edited)
    try:
        instance.content.recalc_metrics()
    except Exception:
        pass

@receiver(post_save, sender=Share)
def on_share_saved(sender, instance, created, **kwargs):
    try:
        instance.content.recalc_metrics()
    except Exception:
        pass

@receiver(post_save, sender=Reaction)
def on_reaction_saved(sender, instance, created, **kwargs):
    try:
        instance.content.recalc_metrics()
    except Exception:
        pass

@receiver(post_save, sender=ContentView)
def on_view_saved(sender, instance, created, **kwargs):
    # If many views are inserted rapidly consider batching / Celery
    try:
        instance.content.recalc_metrics()
    except Exception:
        pass
