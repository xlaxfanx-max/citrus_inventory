from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from forecast.chart import cci_chart_svg
from forecast.features import environment_features
from forecast.models import Prediction
from sampling.models import Sample, SamplePhoto

from .forms import ImportForm, ModelSettingsForm, PlantRecipientsFormSet
from .importers import IMPORTERS, blank_template, run_import
from .models import ImportBatch, Lot, ModelSettings, Room, plant_for
from .roles import ADMIN, FOREMAN, GM, group_required, resolve_plant


def _board_rows(lots, today, settings):
    rows = []
    for lot in lots:
        pred = next(iter(lot.predictions.all()), None)
        sample = next(iter(lot.samples.all()), None)
        photo = sample.best_photo if sample else None
        statuses = {p.status for p in sample.photos.all()} if sample else set()
        # "retake" only when the latest visit produced no usable photo at all
        photo_failed = SamplePhoto.Status.FAILED in statuses and SamplePhoto.Status.SCORED not in statuses
        photo_pending = SamplePhoto.Status.PENDING in statuses and SamplePhoto.Status.SCORED not in statuses
        photo_processing = SamplePhoto.Status.PROCESSING in statuses and SamplePhoto.Status.SCORED not in statuses
        photo_quality_low = bool(photo and not photo.quality_ok)
        days_to = pred.days_to_pack_by(today) if pred else None
        if days_to is None:
            urgency = ''
        elif days_to <= 7:
            urgency = 'red'
        elif days_to <= 14:
            urgency = 'amber'
        else:
            urgency = ''
        days_since_sample = (today - sample.sampled_on).days if sample else None
        sample_overdue = (days_since_sample if days_since_sample is not None else lot.days_in_storage) >= settings.sample_overdue_days
        if pred and pred.decay_flag:
            priority = 'Decay risk'
            priority_tone = 'red'
            priority_rank = 0
        elif days_to is not None and days_to < 0:
            priority = 'Pack overdue'
            priority_tone = 'red'
            priority_rank = 0
        elif days_to is not None and days_to <= 7:
            priority = 'Pack this week'
            priority_tone = 'red'
            priority_rank = 1
        elif photo_failed or photo_quality_low:
            priority = 'Retake photo'
            priority_tone = 'amber'
            priority_rank = 2
        elif sample_overdue:
            priority = 'Sample due'
            priority_tone = 'amber'
            priority_rank = 3
        elif days_to is not None and days_to <= 14:
            priority = 'Pack soon'
            priority_tone = 'amber'
            priority_rank = 4
        elif photo_pending or photo_processing:
            priority = 'Scoring'
            priority_tone = 'grey'
            priority_rank = 5
        elif pred:
            priority = 'Monitor'
            priority_tone = 'ok'
            priority_rank = 6
        else:
            priority = 'Needs baseline'
            priority_tone = 'grey'
            priority_rank = 5
        rows.append({
            'lot': lot,
            'pred': pred,
            'sample': sample,
            'photo': photo,
            'photo_failed': photo_failed,
            'photo_pending': photo_pending,
            'photo_processing': photo_processing,
            'photo_quality_low': photo_quality_low,
            'days_to_pack_by': days_to,
            'overdue_days': -days_to if days_to is not None and days_to < 0 else None,
            'urgency': urgency,
            'days_since_sample': days_since_sample,
            'sample_overdue': sample_overdue,
            'priority': priority,
            'priority_tone': priority_tone,
            'priority_rank': priority_rank,
        })
    rows.sort(key=lambda r: (
        r['priority_rank'],
        r['pred'].pack_by_date if r['pred'] and r['pred'].pack_by_date else date.max,
        -r['lot'].days_in_storage,
    ))
    return rows


def _capacity_projection(rows, plant, today, weeks=8):
    """Bucket known remaining bins by model pack-by week for planning."""
    week_zero = today - timedelta(days=today.weekday())
    capacity = plant.weekly_pack_capacity_bins if plant else None
    buckets = []
    for offset in range(weeks):
        start = week_zero + timedelta(days=7 * offset)
        end = start + timedelta(days=6)
        bucket_rows = []
        for row in rows:
            pack_by = row['pred'].pack_by_date if row['pred'] else None
            if not pack_by:
                continue
            if offset == 0:
                include = pack_by <= end
            else:
                include = start <= pack_by <= end
            if include:
                bucket_rows.append(row)
        known_bins = sum(
            (row['lot'].bins_remaining for row in bucket_rows if row['lot'].bins_remaining is not None),
            Decimal('0'),
        )
        unknown_bins = sum(1 for row in bucket_rows if row['lot'].bins_remaining is None)
        buckets.append({
            'start': start,
            'end': end,
            'lots': len(bucket_rows),
            'known_bins': known_bins,
            'unknown_bins': unknown_bins,
            'capacity': capacity,
            'over_capacity': capacity is not None and known_bins > capacity,
        })
    return buckets


@group_required(FOREMAN, GM, ADMIN)
def board(request):
    """Plant packing plan: active lots ranked by the next decision required."""
    plant, plants = resolve_plant(request)
    settings = ModelSettings.get()
    today = timezone.localdate()
    rooms = Room.objects.filter(plant=plant) if plant else Room.objects.none()
    room_id = request.GET.get('room') or ''
    query = request.GET.get('q', '').strip()
    attention = request.GET.get('attention', 'all')
    if attention not in {'all', 'due', 'decay', 'sample', 'retake'}:
        attention = 'all'

    lots = (
        Lot.objects.in_storage().at_plant(plant)
        .select_related('grower', 'current_room', 'plant')
        .prefetch_related(
            Prefetch('predictions', queryset=Prediction.objects.latest_per_lot()),
            Prefetch(
                'samples',
                queryset=Sample.objects.filter(is_void=False).order_by('-sampled_at', '-id').prefetch_related('photos'),
            ),
            'packouts',
        )
    )
    if room_id.isdigit():
        lots = lots.filter(current_room_id=int(room_id))
    if query:
        lots = lots.filter(
            Q(lot_no__icontains=query)
            | Q(grower__name__icontains=query)
            | Q(grower__sunkist_grower_no__icontains=query)
            | Q(block__icontains=query)
            | Q(current_room__name__icontains=query)
        )
    all_rows = _board_rows(lots, today, settings)
    due_rows = [r for r in all_rows if r['days_to_pack_by'] is not None and r['days_to_pack_by'] <= 7]
    due_bins_7 = sum(
        (r['lot'].bins_remaining for r in due_rows if r['lot'].bins_remaining is not None),
        Decimal('0'),
    )
    attention_counts = {
        'all': len(all_rows),
        'due': len(due_rows),
        'decay': sum(1 for r in all_rows if r['pred'] and r['pred'].decay_flag),
        'sample': sum(1 for r in all_rows if r['sample_overdue']),
        'retake': sum(1 for r in all_rows if r['photo_failed'] or r['photo_quality_low']),
    }
    filters = {
        'all': lambda r: True,
        'due': lambda r: r['days_to_pack_by'] is not None and r['days_to_pack_by'] <= 7,
        'decay': lambda r: bool(r['pred'] and r['pred'].decay_flag),
        'sample': lambda r: r['sample_overdue'],
        'retake': lambda r: r['photo_failed'] or r['photo_quality_low'],
    }
    rows = [r for r in all_rows if filters[attention](r)]

    context = {
        'plant': plant,
        'plants': plants,
        'rooms': rooms,
        'room_id': room_id,
        'query': query,
        'attention': attention,
        'rows': rows,
        'today': today,
        'total_rows': len(all_rows),
        'n_red': sum(1 for r in all_rows if r['urgency'] == 'red'),
        'n_amber': sum(1 for r in all_rows if r['urgency'] == 'amber'),
        'n_decay': attention_counts['decay'],
        'n_overdue': attention_counts['sample'],
        'n_failed': attention_counts['retake'],
        'count_all': attention_counts['all'],
        'count_due': attention_counts['due'],
        'count_decay': attention_counts['decay'],
        'count_sample': attention_counts['sample'],
        'count_retake': attention_counts['retake'],
        'overdue_days': settings.sample_overdue_days,
        'due_bins_7': due_bins_7,
        'due_bins_unknown': sum(1 for r in due_rows if r['lot'].bins_remaining is None),
        'capacity_projection': _capacity_projection(all_rows, plant, today),
    }
    return render(request, 'lots/board.html', context)


@group_required(FOREMAN, GM, ADMIN)
def lot_detail(request, pk):
    lot = get_object_or_404(
        Lot.objects.select_related('grower', 'plant', 'current_room').prefetch_related(
            'room_moves__room',
            'packouts',
            'treatments',
            Prefetch(
                'samples',
                queryset=Sample.objects.filter(is_void=False).order_by('-sampled_at', '-id').prefetch_related('photos').select_related('sampled_by'),
            ),
            Prefetch('predictions', queryset=Prediction.objects.order_by('-as_of_date', '-id')),
        ),
        pk=pk,
    )
    pinned = plant_for(request.user)
    if pinned is not None and lot.plant_id != pinned.id:
        raise Http404
    settings = ModelSettings.get()
    samples = list(lot.samples.all())
    predictions = list(lot.predictions.all())
    latest = predictions[0] if predictions else None
    points = [
        {'sample': s, 'day': (s.sampled_on - lot.receive_date).days, 'cci': s.mean_cci}
        for s in samples if s.mean_cci is not None
    ]
    chart = cci_chart_svg(lot, points, latest, settings, today=timezone.localdate())
    photos = [p for s in samples for p in s.photos.all()]
    today = timezone.localdate()
    plan_row = _board_rows([lot], today, settings)[0] if lot.status == Lot.Status.IN_STORAGE else None
    environment = environment_features(lot, today)
    context = {
        'lot': lot,
        'samples': samples,
        'photos': photos,
        'predictions': predictions,
        'latest': latest,
        'chart_svg': chart,
        'stage': settings.stage_for(latest.cci_now) if latest else None,
        'today': today,
        'plan_row': plan_row,
        'environment': environment,
    }
    return render(request, 'lots/lot_detail.html', context)


@group_required(GM, ADMIN)
def imports(request):
    if request.method == 'POST':
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data['file']
            batch = run_import(
                form.cleaned_data['kind'],
                f,
                user=request.user,
                original_name=f.name,
                plant_scope=plant_for(request.user),
            )
            if batch.rows_failed:
                messages.warning(request, f'{batch.rows_ok} rows imported, {batch.rows_failed} rows had problems.')
            else:
                messages.success(request, f'{batch.rows_ok} rows imported with no problems.')
            return redirect('lots:import_detail', pk=batch.pk)
    else:
        form = ImportForm()
    batches = ImportBatch.objects.select_related('uploaded_by', 'plant_scope')
    pinned = plant_for(request.user)
    if pinned is not None:
        batches = batches.filter(plant_scope=pinned)
    batches = batches[:50]
    templates = [(kind, label, IMPORTERS[kind].COLUMNS) for kind, label in ImportBatch.Kind.choices]
    return render(request, 'lots/imports.html', {'form': form, 'batches': batches, 'templates': templates})


@group_required(GM, ADMIN)
def import_detail(request, pk):
    batch = get_object_or_404(ImportBatch.objects.select_related('uploaded_by'), pk=pk)
    pinned = plant_for(request.user)
    if pinned is not None and batch.plant_scope_id != pinned.id:
        raise Http404
    return render(request, 'lots/import_detail.html', {'batch': batch})


@group_required(GM, ADMIN)
def import_template(request, kind):
    if kind not in IMPORTERS:
        raise Http404
    resp = HttpResponse(blank_template(kind), content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{kind}_template.csv"'
    return resp


@group_required(ADMIN)
def model_settings(request):
    settings = ModelSettings.get()
    if request.method == 'POST':
        form = ModelSettingsForm(request.POST, instance=settings)
        formset = PlantRecipientsFormSet(request.POST, prefix='plants')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Settings saved. Predictions pick up the new values on the next build.')
            return redirect('lots:settings')
    else:
        form = ModelSettingsForm(instance=settings)
        formset = PlantRecipientsFormSet(prefix='plants')
    return render(request, 'lots/settings.html', {'form': form, 'formset': formset})
