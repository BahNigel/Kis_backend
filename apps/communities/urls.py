# apps/communities/urls.py
from rest_framework.routers import DefaultRouter

from .views import CommunityViewSet, CommunityPostViewSet

app_name = "communities"

router = DefaultRouter()
router.register(r"communities", CommunityViewSet, basename="community")
router.register(r"posts", CommunityPostViewSet, basename="community-post")

urlpatterns = router.urls
