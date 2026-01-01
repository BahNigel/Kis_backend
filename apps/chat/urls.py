from django.urls import path, include
from apps.chat.views_introspect import IntrospectView
from rest_framework.routers import DefaultRouter

from .views import ConversationViewSet, MessageThreadLinkViewSet

app_name = "chat"

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'threads', MessageThreadLinkViewSet, basename='thread')

urlpatterns = [
    path('auth/introspect/', IntrospectView.as_view(), name='auth-introspect'),
    path('', include(router.urls)),
]
