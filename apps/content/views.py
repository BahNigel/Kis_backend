# content/views.py
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import Content, Comment, Reaction, ContentView, Tag, ContentMetrics
from .serializers import (
    ContentSerializer, CommentSerializer, ReactionSerializer,
    ContentMetricsSerializer, TagSerializer
)
from .permissions import IsAuthorOrReadOnly

# --- Swagger / OpenAPI compatibility shim ---
# This tries to support drf-yasg first, then drf-spectacular.
# If neither is installed the decorator becomes a no-op.
try:
    # drf-yasg
    from drf_yasg.utils import swagger_auto_schema
    from drf_yasg import openapi

    def schema_decorator(**kwargs):
        """
        Returns drf_yasg.swagger_auto_schema(**kwargs)
        """
        return swagger_auto_schema(**kwargs)

    _PARAM = lambda name, typ, required=False, desc="": openapi.Parameter(
        name, in_=openapi.IN_QUERY if typ == "query" else openapi.IN_BODY,
        description=desc, type=openapi.TYPE_STRING, required=required
    )

    USING_SCHEMA_LIB = "drf_yasg"

except Exception:
    try:
        # drf-spectacular
        from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

        def schema_decorator(**kwargs):
            """
            Map a limited subset of kwargs to drf-spectacular's extend_schema.
            Supported mapped keys: operation_description, request_body, responses, parameters/manual_parameters
            """
            operation_description = kwargs.get("operation_description")
            request_body = kwargs.get("request_body")
            responses = kwargs.get("responses")
            manual_parameters = kwargs.get("manual_parameters") or kwargs.get("parameters") or []

            # Map drf-yasg openapi.Parameter objects to spectaculr OpenApiParameter where possible
            spect_params = []
            for p in manual_parameters:
                # drf-yasg Parameter objects have attrs 'name' and 'in_' and 'description' and 'required'
                try:
                    name = getattr(p, "name", None) or getattr(p, "param_name", None)
                    location = getattr(p, "in_", None)
                    required = getattr(p, "required", False)
                    desc = getattr(p, "description", "") or ""
                    # Map location
                    if location in ("query", openapi.IN_QUERY) or location is None:
                        loc = OpenApiParameter.QUERY
                    elif location in ("path",):
                        loc = OpenApiParameter.PATH
                    else:
                        loc = OpenApiParameter.QUERY
                    spect_params.append(OpenApiParameter(name=name, description=desc, required=required, type=str, location=loc))
                except Exception:
                    # fallback: ignore parameter
                    continue

            return extend_schema(
                description=operation_description,
                request=request_body,
                responses=responses,
                parameters=spect_params if spect_params else None
            )

        # helper factory for mapping
        def _PARAM(name, typ, required=False, desc=""):
            # drf-spectacular OpenApiParameter expects location constants; typical usage below will pass "query"
            loc = OpenApiParameter.QUERY if typ == "query" else OpenApiParameter.QUERY
            return OpenApiParameter(name=name, description=desc, required=required, type=str, location=loc)

        USING_SCHEMA_LIB = "drf_spectacular"

    except Exception:
        # no swagger libs installed — no-op decorator
        def schema_decorator(**kwargs):
            def _noop(func):
                return func
            return _noop

        def _PARAM(name, typ, required=False, desc=""):
            return None

        USING_SCHEMA_LIB = None

# End of shim
# ----------------------------------------

class ContentViewSet(viewsets.ModelViewSet):
    queryset = Content.objects.select_related("author").all()
    serializer_class = ContentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @schema_decorator(
        operation_description=(
            "Track a view for a given content. "
            "Client may supply duration_sec, device_type, ip_hash, and is_unique fields."
        ),
        manual_parameters=[
            _PARAM("duration_sec", "query", required=False, desc="Number of seconds user viewed the content"),
            _PARAM("device_type", "query", required=False, desc="Device type or user agent info"),
            _PARAM("ip_hash", "query", required=False, desc="Hashed IP address (recommended over raw IP)"),
            _PARAM("is_unique", "query", required=False, desc="Whether this view is unique (true/false)")
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "ok": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="True if view recorded successfully")
                }
            )
        }
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.AllowAny])
    def view(self, request, pk=None):
        """
        Track a view. Client can send optional duration_sec, device_type, ip_hash (server prefer).
        """
        content = self.get_object()
        data = request.data
        ContentView.objects.create(
            content=content,
            user=request.user if request.user.is_authenticated else None,
            duration_sec=data.get("duration_sec"),
            device_type=data.get("device_type"),
            ip_address_hash=data.get("ip_hash"),
            is_unique=data.get("is_unique", True)
        )
        content.recalc_metrics()
        return Response({"ok": True})


    @schema_decorator(
        operation_description="React to a content (like, love, custom emoji, ...). Requires authentication.",
        request_body=ReactionSerializer,
        responses={201: ReactionSerializer()}
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def react(self, request, pk=None):
        content = self.get_object()
        serializer = ReactionSerializer(data={**request.data, "content": str(content.id)})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        content.recalc_metrics()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @schema_decorator(
        operation_description="Get aggregated metrics for the given content (views, shares, comments, reactions, trending score).",
        responses={200: ContentMetricsSerializer()},
    )
    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def metrics(self, request, pk=None):
        content = self.get_object()
        metrics, _ = ContentMetrics.objects.get_or_create(content=content)
        return Response(ContentMetricsSerializer(metrics).data)

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.select_related("author", "content").all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    # Optionally decorate create() with schema; here we keep default DRF behavior.
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
        # Update metrics on create
        serializer.instance.content.recalc_metrics()

class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]
