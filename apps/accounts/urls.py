from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EducationViewSet,
    ExperienceViewSet,
    ProjectViewSet,
    RecommendationViewSet,
    RegisterView,
    LoginView,
    LogoutView,
    ApiTokenViewSet,
    UserSkillViewSet,
    UserViewSet,
    ProfileViewSet,
    AccountTierViewSet,
    SubscriptionViewSet,
    SessionViewSet,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r"auth/register", RegisterView, basename="auth-register")
router.register(r"auth/tokens", ApiTokenViewSet, basename="auth-tokens")
router.register(r"users", UserViewSet, basename="users")
router.register(r"profiles", ProfileViewSet, basename="profiles")
router.register(r"tiers", AccountTierViewSet, basename="tiers")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscriptions")
router.register(r"sessions", SessionViewSet, basename="sessions")
router.register(r"experiences", ExperienceViewSet, basename="experiences")
router.register(r"educations", EducationViewSet, basename="educations")
router.register(r"skills", UserSkillViewSet, basename="skills")
router.register(r"projects", ProjectViewSet, basename="projects")
router.register(r"recommendations", RecommendationViewSet, basename="recommendations")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("", include(router.urls)),
]
