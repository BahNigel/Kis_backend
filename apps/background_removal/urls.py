# apps/background_removal/urls.py
from django.urls import path
from .views import StartBackgroundRemovalView, BackgroundRemovalJobStatusView

urlpatterns = [
    path("remove-background/", StartBackgroundRemovalView.as_view(), name="remove-background"),
    path("gbJobs/<uuid:job_id>/", BackgroundRemovalJobStatusView.as_view(), name="bg-job-status"),
]
