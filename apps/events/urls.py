from rest_framework.routers import DefaultRouter
from .views import EventViewSet, TicketViewSet, AttendanceViewSet
from django.urls import path, include

router = DefaultRouter()
router.register(r"events", EventViewSet, basename="events")
router.register(r"tickets", TicketViewSet, basename="tickets")
router.register(r"attendances", AttendanceViewSet, basename="attendances")


urlpatterns = [
    # Primary API routes for the events app
    path("api/", include((router.urls, "events"), namespace="events")),
]
