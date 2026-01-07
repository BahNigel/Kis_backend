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
    TwoFactorSetupView,
    TwoFactorEnableView,
    TwoFactorDisableView,
    E2EERegisterKeysView,
    E2EEFetchBundleView,
    UserSkillViewSet,
    UserViewSet,
    ProfileViewSet,
    ProfileFieldVisibilityViewSet,
    ProfileArticleViewSet,
    ProfilePreferencesViewSet,
    ProfileShowcaseViewSet,
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
router.register(r"profile-privacy", ProfileFieldVisibilityViewSet, basename="profile-privacy")
router.register(r"profile-articles", ProfileArticleViewSet, basename="profile-articles")
router.register(r"profile-preferences", ProfilePreferencesViewSet, basename="profile-preferences")
router.register(r"profile-showcases", ProfileShowcaseViewSet, basename="profile-showcases")
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
    path("auth/2fa/setup/", TwoFactorSetupView.as_view(), name="auth-2fa-setup"),
    path("auth/2fa/enable/", TwoFactorEnableView.as_view(), name="auth-2fa-enable"),
    path("auth/2fa/disable/", TwoFactorDisableView.as_view(), name="auth-2fa-disable"),
    path("auth/e2ee/keys/", E2EERegisterKeysView.as_view(), name="auth-e2ee-keys"),
    path("auth/e2ee/keys/<uuid:user_id>/", E2EEFetchBundleView.as_view(), name="auth-e2ee-keys-user"),

    # Optional: direct SimpleJWT endpoints (tooling-friendly)
    path("auth/jwt/create/",  TokenObtainPairView.as_view(), name="jwt-create"),
    path("auth/jwt/refresh/", TokenRefreshView.as_view(),   name="jwt-refresh"),
    path("auth/jwt/verify/",  TokenVerifyView.as_view(),    name="jwt-verify"),
    path("contacts/check", CheckContact.as_view(), name="check_contact"),

    path("", include(router.urls)),
]
