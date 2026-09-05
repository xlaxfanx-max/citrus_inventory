from django.contrib import admin

from .models import PackPlan, PlanDecision, PlanRecommendation, Prediction, ReportDelivery


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ['lot', 'as_of_date', 'stage', 'cci_now', 'drift_per_day', 'pack_by_date', 'decay_flag', 'confidence', 'model_version']
    list_filter = ['lot__plant', 'confidence', 'decay_flag', 'model_version']
    search_fields = ['lot__lot_no']
    readonly_fields = [f.name for f in Prediction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReportDelivery)
class ReportDeliveryAdmin(admin.ModelAdmin):
    list_display = ['plant', 'report_date', 'status', 'attempts', 'sent_at', 'updated_at']
    list_filter = ['plant', 'status']
    readonly_fields = [f.name for f in ReportDelivery._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PlanRecommendationInline(admin.TabularInline):
    model = PlanRecommendation
    extra = 0
    can_delete = False
    fields = ['rank', 'lot', 'action', 'requires_decision', 'pack_by_date', 'stage', 'cci_now', 'confidence', 'decay_flag', 'bins_remaining']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PackPlan)
class PackPlanAdmin(admin.ModelAdmin):
    """Plans are published from the app or the report; the admin is read-only audit."""

    list_display = ['plant', 'version', 'plan_date', 'source', 'published_by', 'model_version', 'locked_at']
    list_filter = ['plant', 'source']
    readonly_fields = [f.name for f in PackPlan._meta.fields]
    inlines = [PlanRecommendationInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PlanDecision)
class PlanDecisionAdmin(admin.ModelAdmin):
    """Decisions are add-only. They are recorded on the plan screen, never edited here."""

    list_display = ['recommendation', 'status', 'reason', 'planned_pack_date', 'decided_by', 'decided_at', 'after_lock']
    list_filter = ['status', 'reason', 'after_lock', 'recommendation__plan__plant']
    search_fields = ['recommendation__lot__lot_no', 'notes']
    readonly_fields = [f.name for f in PlanDecision._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
