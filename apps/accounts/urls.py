from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CheckContact,
    EducationViewSet,
    ExperienceViewSet,
    ProjectViewSet,
    RecommendationViewSet,
    RegisterView,     # ViewSet (create -> JWTs)
    LoginView,        # APIView (returns JWTs)
    LogoutView,       # APIView (blacklists refresh if enabled)
    UserSkillViewSet,
    UserViewSet,
    ProfileViewSet,
    AccountTierViewSet,
    SubscriptionViewSet,
    SessionViewSet,
)

# Optional: SimpleJWT endpoints (convenience here too)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,   # username/password -> {access, refresh}
    TokenRefreshView,      # {refresh} -> {access}
    TokenVerifyView,       # {token} -> {} if valid
)

router = DefaultRouter()

# Auth (registration via ViewSet create)
router.register(r"auth/register", RegisterView, basename="auth-register")

# NOTE: removed ApiTokenViewSet — no more opaque API tokens in JWT flow
# router.register(r"auth/tokens", ApiTokenViewSet, basename="auth-tokens")

# Core resources
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
    # JWT login/logout you defined in views.py
    path("auth/login/",  LoginView.as_view(),  name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),

    # Optional: direct SimpleJWT endpoints (tooling-friendly)
    path("auth/jwt/create/",  TokenObtainPairView.as_view(), name="jwt-create"),
    path("auth/jwt/refresh/", TokenRefreshView.as_view(),   name="jwt-refresh"),
    path("auth/jwt/verify/",  TokenVerifyView.as_view(),    name="jwt-verify"),
    path("contacts/check", CheckContact.as_view(), name="check_contact"),

    path("", include(router.urls)),
]
