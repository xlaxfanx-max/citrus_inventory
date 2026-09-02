from django.contrib import admin

from .models import (
    Grower,
    ImportBatch,
    Lot,
    LotRoomMove,
    LotTreatment,
    ModelSettings,
    Packout,
    Plant,
    Room,
    RoomCondition,
    UserProfile,
)


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'city', 'report_recipients']


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'plant', 'room_type', 'target_temp_f']
    list_filter = ['plant', 'room_type']


@admin.register(Grower)
class GrowerAdmin(admin.ModelAdmin):
    list_display = ['sunkist_grower_no', 'name']
    search_fields = ['sunkist_grower_no', 'name']


class LotRoomMoveInline(admin.TabularInline):
    model = LotRoomMove
    extra = 0


class PackoutInline(admin.TabularInline):
    model = Packout
    extra = 0
    readonly_fields = ['cartons_total', 'fresh_pct']
    fields = [
        'packed_date', 'bins_packed', 'is_final', 'packout_color', 'decay_pct',
        'soft_pct', 'shrivel_pct', 'chilling_injury_pct', 'meets_spec',
        'downgrade_reason', 'cartons_fancy', 'cartons_choice', 'cartons_standard',
        'cartons_products', 'cartons_total', 'fresh_pct',
    ]


class LotTreatmentInline(admin.TabularInline):
    model = LotTreatment
    extra = 0


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    """Lots are never deleted (model.delete raises); the admin hides the button."""

    list_display = ['lot_no', 'plant', 'grower', 'variety', 'harvest_date', 'receive_date', 'receiving_color', 'intake_cci_mean', 'current_room', 'status', 'packed_date']
    list_filter = ['plant', 'status', 'variety', 'receiving_color']
    search_fields = ['lot_no', 'grower__name', 'grower__sunkist_grower_no']
    date_hierarchy = 'receive_date'
    inlines = [LotRoomMoveInline, LotTreatmentInline, PackoutInline]
    autocomplete_fields = ['grower']

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LotRoomMove)
class LotRoomMoveAdmin(admin.ModelAdmin):
    list_display = ['lot', 'room', 'moved_at', 'moved_by']
    list_filter = ['room__plant']
    search_fields = ['lot__lot_no']


@admin.register(RoomCondition)
class RoomConditionAdmin(admin.ModelAdmin):
    list_display = ['room', 'recorded_at', 'temperature_f', 'relative_humidity_pct', 'ethylene_ppm', 'co2_pct', 'source']
    list_filter = ['room__plant', 'room', 'source']
    search_fields = ['room__name', 'room__plant__code']
    date_hierarchy = 'recorded_at'


@admin.register(LotTreatment)
class LotTreatmentAdmin(admin.ModelAdmin):
    list_display = ['lot', 'applied_at', 'treatment_type', 'product', 'concentration', 'concentration_unit', 'duration_hours']
    list_filter = ['lot__plant', 'treatment_type']
    search_fields = ['lot__lot_no', 'product']
    date_hierarchy = 'applied_at'


@admin.register(Packout)
class PackoutAdmin(admin.ModelAdmin):
    list_display = ['lot', 'packed_date', 'bins_packed', 'is_final', 'packout_color', 'decay_pct', 'meets_spec', 'cartons_total', 'fresh_pct']
    search_fields = ['lot__lot_no']
    readonly_fields = ['cartons_total', 'fresh_pct']


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ['kind', 'original_name', 'plant_scope', 'uploaded_by', 'uploaded_at', 'rows_ok', 'rows_failed']
    list_filter = ['kind']
    readonly_fields = ['kind', 'file', 'original_name', 'plant_scope', 'uploaded_by', 'uploaded_at', 'rows_ok', 'rows_failed', 'error_report']

    def has_add_permission(self, request):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'plant']
    list_filter = ['plant']
    autocomplete_fields = ['user']


@admin.register(ModelSettings)
class ModelSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ModelSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
