from django.contrib import admin
from .models import Survey, Question, Response, SurveyShare, SurveyAnalytics

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('id','title','type','owner_id','visibility','created_at')
    search_fields = ('title','description')
    list_filter = ('type','visibility')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id','survey','text','vote_type','order')

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('id','survey','question','user_id','submitted_at','is_valid')
    search_fields = ('answer',)

admin.site.register(SurveyShare)
admin.site.register(SurveyAnalytics)