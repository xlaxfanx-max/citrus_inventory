from django.contrib import admin

from .models import Prediction, ReportDelivery


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
