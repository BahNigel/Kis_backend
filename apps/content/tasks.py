# content/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import Content, ContentMetrics

@shared_task(bind=True)
def recompute_all_metrics(self, batch_size=500):
    """
    Recompute metrics for all content in batches.
    """
    qs = Content.objects.all()
    total = qs.count()
    for offset in range(0, total, batch_size):
        for content in qs[offset: offset + batch_size]:
            content.recalc_metrics()
    return {"status": "done", "count": total}

@shared_task
def analyze_content_ai(content_id):
    """
    Placeholder for AI analysis pipeline:
      - call external moderation / topic classifier / summarizer
      - store AIAnalysis result
    This should be wired to your LLM/Machine Learning infra.
    """
    from .models import Content, AIAnalysis
    content = Content.objects.get(id=content_id)
    # Example stub: fake analysis
    AIAnalysis.objects.create(
        content=content,
        safety_score=0.95,
        topic_tags=["example"],
        toxicity_score=0.02,
        readability_score=70.0,
        generated_summary=(content.summary or (content.body[:200] + "..."))
    )
    return {"content_id": str(content_id)}
