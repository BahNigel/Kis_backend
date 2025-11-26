# apps/communities/urls.py
from rest_framework.routers import DefaultRouter

from .views import CommunityViewSet

app_name = "communities"

router = DefaultRouter()
router.register(r"communities", CommunityViewSet, basename="community")

urlpatterns = router.urls
