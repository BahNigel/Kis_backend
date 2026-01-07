# apps/partners/urls.py
from rest_framework.routers import DefaultRouter

from .views import PartnerViewSet, PartnerPostViewSet

app_name = "partners"

router = DefaultRouter()
router.register(r"", PartnerViewSet, basename="partner")
router.register(r"posts", PartnerPostViewSet, basename="partner-post")

urlpatterns = router.urls
