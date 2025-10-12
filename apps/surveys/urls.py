from rest_framework.routers import DefaultRouter
from .views import SurveyViewSet, QuestionViewSet, ResponseViewSet

router = DefaultRouter()
router.register('surveys', SurveyViewSet, basename='survey')
router.register('questions', QuestionViewSet, basename='question')
router.register('responses', ResponseViewSet, basename='response')

urlpatterns = router.urls