# apps/partners/urls.py
from rest_framework.routers import DefaultRouter

from .views import PartnerViewSet

app_name = "partners"

router = DefaultRouter()
router.register(r"partners", PartnerViewSet, basename="partner")

urlpatterns = router.urls
