from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,   # POST: username/password -> { access, refresh }
    TokenRefreshView,      # POST: { refresh } -> { access }
    TokenVerifyView,       # POST: { token } -> {} if valid
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # --- Versioned app routes ---
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.content.urls")),
    path("api/v1/", include("apps.media.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.moderation.urls")),
    path("api/v1/", include("apps.ai_integration.urls")),
    path("api/v1/", include("apps.commerce.urls")),
    path("api/v1/", include("apps.surveys.urls")),
    path("api/v1/", include("apps.bridge.urls")),
    path("api/v1/", include("apps.analytics.urls")),
    path("api/v1/", include("apps.tiers.urls")),
    path("api/v1/", include("apps.otp.urls")),
    path("api/v1/", include("apps.chat.urls", namespace="chat")),
    path("api/v1/", include("apps.partners.urls", namespace="partners")),
    path("api/v1/", include("apps.communities.urls", namespace="communities")),
    path("api/v1/", include("apps.groups.urls", namespace="groups")),
    path("api/v1/", include("apps.channels.urls", namespace="channels")),

    # --- JWT auth endpoints (SimpleJWT) ---
    # Obtain access/refresh with username/password
    path("api/v1/auth/jwt/create/", TokenObtainPairView.as_view(), name="jwt-create"),
    # Exchange refresh for a new access
    path("api/v1/auth/jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
    # Verify a token (access or refresh)
    path("api/v1/auth/jwt/verify/", TokenVerifyView.as_view(), name="jwt-verify"),

    # --- OpenAPI / Docs ---
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),


    #chat urls

    path("api/v1/chat/", include("apps.chat.urls", namespace="chat")),
]
