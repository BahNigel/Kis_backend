# media/urls.py
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import MediaAssetViewSet, ProcessingJobViewSet

router = DefaultRouter()
router.register(r"assets", MediaAssetViewSet, basename="asset")
router.register(r"jobs", ProcessingJobViewSet, basename="job")

urlpatterns = [
    path("", include(router.urls)),
]
