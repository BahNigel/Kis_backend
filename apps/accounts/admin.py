from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import (
    User,
    Profile,
    AccountTier,
    Subscription,
    Session,
    UsageQuota,
    AuditLog,
    ApiToken,
    Experience,
    Education,
    UserSkill,
    Project,
    Recommendation,
    TwoFactor,
    BillingAccount,
    OrganizationLink,
    FeatureFlag,
    AIAccess,
    RevenueAccount,
    GDPRRequest,
)

# -------------------------
# Inline helpers
# -------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'profile'
    fk_name = 'user'
    readonly_fields = ('created_at', 'updated_at', 'completion_score')

class ApiTokenInline(admin.TabularInline):
    model = ApiToken
    fields = ('name', 'expires_at', 'last_used_at', 'last_used_ip', 'is_deleted')
    readonly_fields = ('last_used_at', 'last_used_ip')
    extra = 0
    show_change_link = True

# -------------------------
# User admin
# -------------------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email','phone', 'display_name', 'username', 'tier', 'email_verified', 'is_staff', 'created_at')
    search_fields = ('email', 'display_name', 'username', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'last_login_at', 'last_password_change_at')
    list_filter = ('tier', 'status', 'is_staff', 'email_verified')
    inlines = (ProfileInline, ApiTokenInline)
    ordering = ('-created_at',)

    actions = ['deactivate_users', 'export_user_ids']

    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} users")
    deactivate_users.short_description = 'Deactivate selected users'

    def export_user_ids(self, request, queryset):
        ids = ",".join(str(u.id) for u in queryset)
        self.message_user(request, f"IDs: {ids}")
    export_user_ids.short_description = 'Copy selected user IDs'

# -------------------------
# Profile admin
# -------------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'headline', 'completion_score', 'visibility', 'created_at')
    search_fields = ('user__email', 'headline', 'bio')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'user'

# -------------------------
# ApiToken admin
# -------------------------
@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'name', 'expires_at', 'last_used_at', 'last_used_ip', 'is_deleted')
    search_fields = ('user__email', 'name', 'token_hash')
    readonly_fields = ('token_hash', 'created_at', 'updated_at', 'last_used_at', 'last_used_ip')
    list_filter = ('is_deleted', 'created_via')
    actions = ['revoke_tokens']

    def user_email(self, obj):
        return obj.user.email if obj.user else None

    def revoke_tokens(self, request, queryset):
        for t in queryset:
            try:
                t.revoke()
            except Exception:
                pass
        self.message_user(request, f"Revoked {queryset.count()} tokens")
    revoke_tokens.short_description = 'Revoke selected tokens'

# -------------------------
# Simple model registrations
# -------------------------
@admin.register(AccountTier)
class AccountTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_cents')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'tier', 'status', 'started_at', 'ends_at')
    search_fields = ('user__email', 'tier__name')
    list_filter = ('status',)

    def user_email(self, obj):
        return obj.user.email if obj.user else None

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'ip_address', 'expires_at', 'user_agent')
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email if obj.user else None

@admin.register(UsageQuota)
class UsageQuotaAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'quotas_json', 'last_reset_at')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email if obj.user else None

# -------------------------
# Experience / Education / Skills / Projects
# -------------------------
@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'title', 'start_date', 'end_date', 'currently_working')
    search_fields = ('title', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email if obj.user else None

@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'school', 'start_date', 'end_date', 'currently_studying')
    search_fields = ('school', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email if obj.user else None

@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'skill_id', 'verified', 'endorsements')
    search_fields = ('user__email', 'skill_id')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email if obj.user else None

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'name', 'start_date', 'end_date')
    search_fields = ('name', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email if obj.user else None

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('recommended_user_email', 'recommender_user_email', 'approved', 'created_at')
    search_fields = ('recommended_user__email', 'recommender_user__email')
    list_filter = ('approved',)
    readonly_fields = ('created_at', 'updated_at')

    def recommended_user_email(self, obj):
        return obj.recommended_user.email if obj.recommended_user else None

    def recommender_user_email(self, obj):
        return obj.recommender_user.email if obj.recommender_user else None

# -------------------------
# Misc admin registrations
# -------------------------
admin.site.register(TwoFactor)
admin.site.register(BillingAccount)
admin.site.register(OrganizationLink)
admin.site.register(FeatureFlag)
admin.site.register(AIAccess)
admin.site.register(RevenueAccount)
admin.site.register(GDPRRequest)

# Audit log - read-only
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor_id', 'action', 'created_at')
    readonly_fields = ('actor_id', 'action', 'meta', 'created_at', 'updated_at')
    search_fields = ('action',)

