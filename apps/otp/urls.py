from django.urls import path
from .views import OtpInitiateView, OtpVerifyView

urlpatterns = [
    path("auth/otp/initiate/", OtpInitiateView.as_view()),
    path("auth/otp/verify/", OtpVerifyView.as_view()),
]
