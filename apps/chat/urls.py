# apps/chat/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ConversationViewSet, MessageThreadLinkViewSet

app_name = "chat"  # <-- this is the missing piece

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'threads', MessageThreadLinkViewSet, basename='thread')

urlpatterns = [
    path('', include(router.urls)),
]
