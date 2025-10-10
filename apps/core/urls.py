# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PermissionViewSet,
    RoleViewSet,
    RoleAssignmentViewSet,
    AccessControlEntryViewSet,
    CommunityViewSet,
    GroupViewSet,
    ChannelViewSet,
    MembershipViewSet,
    MembershipInviteViewSet,
    ModerationActionViewSet,
    GroupSettingsViewSet,
    ChannelSettingsViewSet,
)

app_name = "core"

router = DefaultRouter()
router.register(r"permissions", PermissionViewSet, basename="permission")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"role-assignments", RoleAssignmentViewSet, basename="roleassignment")
router.register(r"aces", AccessControlEntryViewSet, basename="ace")
router.register(r"communities", CommunityViewSet, basename="community")
router.register(r"groups", GroupViewSet, basename="group")
router.register(r"channels", ChannelViewSet, basename="channel")
router.register(r"memberships", MembershipViewSet, basename="membership")
router.register(r"invites", MembershipInviteViewSet, basename="invite")
router.register(r"moderation-actions", ModerationActionViewSet, basename="moderationaction")
router.register(r"group-settings", GroupSettingsViewSet, basename="groupsettings")
router.register(r"channel-settings", ChannelSettingsViewSet, basename="channelsettings")

urlpatterns = [
    # Primary API routes for the core app
    path("api/core/", include((router.urls, app_name), namespace=app_name)),
]

# Optional: add schema / docs routes (uncomment if you use drf-yasg or drf-spectacular)
# from rest_framework.schemas import get_schema_view
# from rest_framework.documentation import include_docs_urls
#
# schema_view = get_schema_view(title="Core API")
# urlpatterns += [
#     path("api/core/schema/", schema_view, name="core-schema"),
#     path("api/core/docs/", include_docs_urls(title="Core API Docs")),
# ]
#
# If you use drf-yasg (recommended for Swagger UI), add:
# from drf_yasg.views import get_schema_view as yasg_get_schema_view
# from drf_yasg import openapi
# yasg_schema = yasg_get_schema_view(
#     openapi.Info(title="Core API", default_version="v1"),
#     public=True,
# )
# urlpatterns += [
#     path("api/core/swagger.json", yasg_schema.without_ui(cache_timeout=0), name="schema-json"),
#     path("api/core/swagger/", yasg_schema.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
# ]
