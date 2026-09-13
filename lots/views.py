from decimal import Decimal

from django.contrib import messages
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from forecast.chart import cci_chart_svg
from forecast.features import environment_features, warm_exposure
from forecast.models import MarketRegime, Prediction
from forecast.plans import current_decisions, lot_decision_history
from sampling.models import Sample

from .forms import ImportForm, ModelSettingsForm, PackoutQualityForm, PlantRecipientsFormSet
from .importers import IMPORTERS, blank_template, run_import
from .models import ImportBatch, Lot, ModelSettings, Packout, Room, plant_for
from .planning import board_rows, capacity_projection, plan_lots
from .roles import ADMIN, FOREMAN, GM, group_required, is_gm, resolve_plant


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

    lots = plan_lots(plant)
    # A saved URL or a plant switch can carry a room from another plant.
    # Ignore invalid selections rather than silently showing an empty board.
    if not room_id.isdigit() or not rooms.filter(pk=room_id).exists():
        room_id = ''
    if room_id:
        lots = lots.filter(current_room_id=int(room_id))
    if query:
        lots = lots.filter(
            Q(lot_no__icontains=query)
            | Q(grower__name__icontains=query)
            | Q(grower__sunkist_grower_no__icontains=query)
            | Q(block__icontains=query)
            | Q(current_room__name__icontains=query)
        )
    all_rows = board_rows(lots, today, settings)
    plan, decisions = current_decisions(plant)
    for r in all_rows:
        r['decision'] = decisions.get(r['lot'].id)
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
        'capacity_projection': capacity_projection(all_rows, plant, today),
        'plan': plan,
        'plan_undecided': sum(1 for r in all_rows if r['requires_decision'] and r['decision'] is None) if plan else None,
        'plan_actionable': sum(1 for r in all_rows if r['requires_decision']),
        'market_regimes': MarketRegime.choices,
    }
    return render(request, 'lots/board.html', context)


@group_required(FOREMAN, GM, ADMIN)
def lot_detail(request, pk, packout_form=None):
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
        for s in samples if s.mean_cci is not None and s.purpose == Sample.Purpose.ROUTINE
    ]
    chart = cci_chart_svg(lot, points, latest, settings, today=timezone.localdate())
    photos = [p for s in samples for p in s.photos.all()]
    today = timezone.localdate()
    plan_row = board_rows([lot], today, settings)[0] if lot.status == Lot.Status.IN_STORAGE else None
    environment = environment_features(lot, today)
    overdue_days = days_to_pack_by = None
    if latest and latest.pack_by_date and lot.status == Lot.Status.IN_STORAGE:
        days_to_pack_by = (latest.pack_by_date - today).days
        if days_to_pack_by < 0:
            overdue_days, days_to_pack_by = -days_to_pack_by, None
    packout_forms = {}
    if is_gm(request.user):
        packout_forms = {
            p.pk: (packout_form if packout_form is not None and packout_form.instance.pk == p.pk else PackoutQualityForm(instance=p, prefix=f'po{p.pk}'))
            for p in lot.packouts.all()
        }
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
        'warm': warm_exposure(lot, today, settings),
        'overdue_days': overdue_days,
        'days_to_pack_by': days_to_pack_by,
        'packout_forms': packout_forms,
        'plan_history': list(lot_decision_history(lot)),
    }
    return render(request, 'lots/lot_detail.html', context, status=400 if packout_form is not None and packout_form.errors else 200)


@group_required(GM, ADMIN)
def packout_quality(request, pk, packout_pk):
    """QC records observed color, decay and specification result for one
    packout run. Carton counts stay with the import."""
    packout = get_object_or_404(Packout.objects.select_related('lot'), pk=packout_pk, lot_id=pk)
    pinned = plant_for(request.user)
    if pinned is not None and packout.lot.plant_id != pinned.id:
        raise Http404
    if request.method != 'POST':
        return redirect('lots:lot_detail', pk=pk)
    form = PackoutQualityForm(request.POST, instance=packout, prefix=f'po{packout.pk}')
    if form.is_valid():
        form.save()
        messages.success(request, f'Quality labels saved for the {packout.packed_date:%b %d} packout of lot {packout.lot.lot_no}.')
        return redirect(f"{reverse('lots:lot_detail', args=[pk])}#packout")
    return lot_detail(request, pk, packout_form=form)


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
