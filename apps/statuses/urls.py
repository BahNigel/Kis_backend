from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.statuses.views import StatusViewSet

app_name = "statuses"

router = DefaultRouter()
router.register(r"statuses", StatusViewSet, basename="status")

urlpatterns = [
    path("", include(router.urls)),
]
