from django.contrib import admin
from .models import Metric, EventStream, Dashboard, AppSetting, FeatureFlag, Alert, EngagementScore

@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('id','name','kind','value','captured_at')
    search_fields = ('name',)

@admin.register(EventStream)
class EventStreamAdmin(admin.ModelAdmin):
    list_display = ('id','event_type','timestamp','processed')

admin.site.register(Dashboard)
admin.site.register(AppSetting)
admin.site.register(FeatureFlag)
admin.site.register(Alert)
admin.site.register(EngagementScore)