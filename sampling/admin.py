from django.contrib import admin
from django.utils import timezone

from .models import Sample, SamplePhoto


class SamplePhotoInline(admin.TabularInline):
    model = SamplePhoto
    extra = 0
    readonly_fields = ['uploaded_at', 'processed_at', 'status', 'card_detected', 'fruit_detected', 'mean_cci', 'std_cci', 'error']
    fields = ['image', 'status', 'card_detected', 'fruit_detected', 'mean_cci', 'std_cci', 'error', 'uploaded_at', 'processed_at']


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    """The foreman's call is the baseline: it can be added, never edited."""

    list_display = [
        'lot', 'sampled_at', 'sampled_by', 'purpose', 'selection_method',
        'foreman_color', 'foreman_pack_within_weeks', 'decay_count',
        'soft_count', 'shrivel_count', 'marketability', 'fruit_count',
    ]
    list_filter = ['lot__plant', 'purpose', 'selection_method', 'foreman_color', 'marketability']
    search_fields = ['lot__lot_no']
    autocomplete_fields = ['lot']
    inlines = [SamplePhotoInline]
    readonly_fields_after_create = [
        'lot', 'sampled_at', 'sampled_by', 'purpose', 'selection_method',
        'sampled_bins_count', 'foreman_color', 'foreman_pack_within_weeks',
        'decay_count', 'soft_count', 'shrivel_count', 'chilling_injury_count',
        'rind_breakdown_count', 'firmness_score', 'marketability',
        'failure_reason', 'fruit_count', 'voided_at', 'voided_by',
    ]

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields_after_create if obj else []

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if obj.is_void and not obj.voided_at:
            obj.voided_at = timezone.now()
            obj.voided_by = request.user
            obj.void_reason = obj.void_reason or 'Voided by an administrator.'
        elif not obj.is_void:
            obj.voided_at = None
            obj.voided_by = None
            obj.void_reason = ''
        super().save_model(request, obj, form, change)


@admin.register(SamplePhoto)
class SamplePhotoAdmin(admin.ModelAdmin):
    list_display = ['sample', 'status', 'card_detected', 'fruit_detected', 'mean_cci', 'uploaded_at', 'processed_at']
    list_filter = ['status', 'card_detected']
    search_fields = ['sample__lot__lot_no']
    readonly_fields = [
        'processed_at', 'per_fruit_lab', 'per_fruit_cci', 'pipeline_version',
        'scoring_metadata', 'quality_ok', 'quality_warnings', 'attempt_count',
        'processing_started_at',
    ]
    actions = ['rescore']

    @admin.action(description='Re-queue selected photos for scoring')
    def rescore(self, request, queryset):
        n = queryset.update(status=SamplePhoto.Status.PENDING, error='')
        self.message_user(request, f'{n} photo(s) queued; run manage.py score_photos.')
