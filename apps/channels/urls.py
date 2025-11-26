# apps/channels/urls.py
from rest_framework.routers import DefaultRouter

from .views import ChannelViewSet

app_name = "channels"

router = DefaultRouter()
router.register(r"channels", ChannelViewSet, basename="channel")

urlpatterns = router.urls
