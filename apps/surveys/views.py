from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Survey, Question, Response as Resp, SurveyShare, SurveyAnalytics
from .serializers import (
    SurveySerializer,
    SurveyCreateSerializer,
    QuestionSerializer,
    ResponseSerializer,
    SurveyShareSerializer,
    SurveyAnalyticsSerializer,
)
from .permissions import IsSurveyOwnerOrReadOnly
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

# drf-spectacular imports for OpenAPI annotations
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
)

####################################
# Shared examples & params
####################################
SURVEY_FILTER_PARAMS = [
    OpenApiParameter(
        name="owner_id",
        required=False,
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.UUID,
        description="Filter by owner UUID",
    ),
    OpenApiParameter(
        name="org_id",
        required=False,
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.UUID,
        description="Filter by organization UUID",
    ),
    OpenApiParameter(
        name="type",
        required=False,
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.STR,
        description="Filter by survey type (POLL|QUIZ|FEEDBACK)",
    ),
    OpenApiParameter(
        name="visibility",
        required=False,
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.STR,
        description="Filter by visibility (PUBLIC|PRIVATE|GROUP_ONLY)",
    ),
]

SURVEY_SHARE_EXAMPLE = OpenApiExample(
    "Share survey example",
    value={"shared_by_id": "11111111-1111-1111-1111-111111111111", "platform": "feed"},
    response_only=False,
)

RESPONSE_CREATE_EXAMPLE = OpenApiExample(
    "Submit Response Example",
    value={
        "survey": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "question": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "user_id": "11111111-1111-1111-1111-111111111111",
        "answer": {"choice_ids": ["opt1"]},
    },
)

####################################
# SurveyViewSet
####################################
@extend_schema_view(
    list=extend_schema(
        summary="List Surveys",
        description="List surveys with filtering on owner/org/group/type/visibility.",
        parameters=SURVEY_FILTER_PARAMS,
        responses={200: SurveySerializer(many=True)},
        tags=["Surveys"],
    ),
    retrieve=extend_schema(summary="Retrieve Survey", responses={200: SurveySerializer}, tags=["Surveys"]),
    create=extend_schema(
        summary="Create Survey",
        description="Create a new survey with optional nested questions. Use SurveyCreateSerializer payload.",
        request=SurveyCreateSerializer,
        responses={201: SurveySerializer},
        tags=["Surveys"],
    ),
    update=extend_schema(
        summary="Update Survey",
        request=SurveyCreateSerializer,
        responses={200: SurveySerializer},
        tags=["Surveys"],
    ),
    partial_update=extend_schema(
        summary="Partial update Survey",
        request=SurveyCreateSerializer,
        responses={200: SurveySerializer},
        tags=["Surveys"],
    ),
    destroy=extend_schema(
        summary="Delete Survey",
        responses={204: OpenApiResponse(description="deleted")},
        tags=["Surveys"],
    ),
)
class SurveyViewSet(viewsets.ModelViewSet):
    """
    Manage surveys (POLL, QUIZ, FEEDBACK). Supports nested question creation via SurveyCreateSerializer.
    """
    queryset = Survey.objects.all()
    permission_classes = [IsSurveyOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['owner_id', 'org_id', 'group_id', 'type', 'visibility']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'popularity_rank']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SurveyCreateSerializer
        return SurveySerializer

    @extend_schema(
        summary="Share a survey",
        description="Share a survey to a platform (Feed, Chat, External). Saves SurveyShare and can trigger async social-impact jobs.",
        request=SurveyShareSerializer,
        responses={201: SurveyShareSerializer},
        examples=[SURVEY_SHARE_EXAMPLE],
        tags=["Surveys"],
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def share(self, request, pk=None):
        survey = self.get_object()
        serializer = SurveyShareSerializer(data={**request.data, 'survey': str(survey.id)})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Optionally trigger async job to compute social impact
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Get analytics for survey",
        description="Return analytics (total_responses, completion_rate, top_choices, demographic_breakdown) for the survey.",
        responses={200: SurveyAnalyticsSerializer},
        tags=["Surveys"],
    )
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        survey = self.get_object()
        analytics, _ = SurveyAnalytics.objects.get_or_create(survey=survey)
        serializer = SurveyAnalyticsSerializer(analytics)
        return Response(serializer.data)

####################################
# QuestionViewSet
####################################
@extend_schema_view(
    list=extend_schema(
        summary="List Questions",
        responses={200: QuestionSerializer(many=True)},
        tags=["Questions"],
    ),
    retrieve=extend_schema(
        summary="Retrieve Question",
        responses={200: QuestionSerializer},
        tags=["Questions"],
    ),
    create=extend_schema(
        summary="Create Question",
        request=QuestionSerializer,
        responses={201: QuestionSerializer},
        tags=["Questions"],
    ),
    update=extend_schema(
        summary="Update Question",
        request=QuestionSerializer,
        responses={200: QuestionSerializer},
        tags=["Questions"],
    ),
    partial_update=extend_schema(
        summary="Partial update Question",
        request=QuestionSerializer,
        responses={200: QuestionSerializer},
        tags=["Questions"],
    ),
    destroy=extend_schema(
        summary="Delete Question",
        responses={204: OpenApiResponse(description="deleted")},
        tags=["Questions"],
    ),
)
class QuestionViewSet(viewsets.ModelViewSet):
    """
    Questions belong to surveys. Options are stored as JSON and support metadata (correct answers for quizzes).
    """
    queryset = Question.objects.select_related('survey').all()
    serializer_class = QuestionSerializer
    permission_classes = [IsSurveyOwnerOrReadOnly]

####################################
# ResponseViewSet
####################################
@extend_schema_view(
    list=extend_schema(
        summary="List Responses",
        responses={200: ResponseSerializer(many=True)},
        tags=["Responses"],
    ),
    retrieve=extend_schema(
        summary="Retrieve Response",
        responses={200: ResponseSerializer},
        tags=["Responses"],
    ),
    create=extend_schema(
        summary="Submit Response",
        description="Submit a user's response to a question. Server will validate survey active window and required fields.",
        request=ResponseSerializer,
        responses={201: ResponseSerializer, 400: OpenApiResponse(description="Validation error")},
        examples=[RESPONSE_CREATE_EXAMPLE],
        tags=["Responses"],
    ),
    update=extend_schema(
        summary="Update Response",
        request=ResponseSerializer,
        responses={200: ResponseSerializer},
        tags=["Responses"],
    ),
    partial_update=extend_schema(
        summary="Partial update Response",
        request=ResponseSerializer,
        responses={200: ResponseSerializer},
        tags=["Responses"],
    ),
    destroy=extend_schema(
        summary="Delete Response",
        responses={204: OpenApiResponse(description="deleted")},
        tags=["Responses"],
    ),
)
class ResponseViewSet(viewsets.ModelViewSet):
    """
    User or system responses to survey questions. Includes hooks for async analytics and AI enrichment.
    """
    queryset = Resp.objects.select_related('survey', 'question').all()
    serializer_class = ResponseSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="Create a response",
        description="Validates that the survey is active. Returns the created response and schedules analytics/enrichment via signals or tasks.",
        request=ResponseSerializer,
        responses={201: ResponseSerializer, 400: OpenApiResponse(description="Survey inactive or validation error")},
        examples=[RESPONSE_CREATE_EXAMPLE],
        tags=["Responses"],
    )
    def create(self, request, *args, **kwargs):
        # Validate survey open/closed + question requirements
        data = request.data
        survey = get_object_or_404(Survey, id=data.get('survey'))
        if not survey.is_active():
            return Response({'detail': 'Survey is not active'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        resp = serializer.save()
        # enqueue analytics job (signals also available)
        # compute immediate checks
        return Response(ResponseSerializer(resp).data, status=status.HTTP_201_CREATED)
