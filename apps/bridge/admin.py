from django.contrib import admin
from .models import BridgeAccount, BridgeThread, BridgeMessage, BridgeAutomation, BridgeAnalytics

@admin.register(BridgeAccount)
class BridgeAccountAdmin(admin.ModelAdmin):
    list_display = ('id','user_id','external_app','external_user_id','last_sync_at')
    search_fields = ('external_user_id',)

@admin.register(BridgeThread)
class BridgeThreadAdmin(admin.ModelAdmin):
    list_display = ('id','external_app','external_thread_id','topic','is_archived')

@admin.register(BridgeMessage)
class BridgeMessageAdmin(admin.ModelAdmin):
    list_display = ('id','bridge_thread','direction','message_type','status','sent_at')

admin.site.register(BridgeAutomation)
admin.site.register(BridgeAnalytics)