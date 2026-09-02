from datetime import date

from django.db.models import OuterRef, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from lots.models import Lot, LotTreatment, Plant, RoomCondition, plant_for
from lots.roles import ADMIN, GM, group_required, resolve_plant
from sampling.models import Sample

from .models import Prediction
from .report import build_report


def accuracy_rows(lots):
    """For each packed lot: the last model pack_by and last foreman call made
    on or before the actual packed_date, and their signed errors in days."""
    rows = []
    for lot in lots:
        if not lot.packed_date:
            continue
        pred = next((p for p in lot.predictions.all() if p.as_of_date <= lot.packed_date), None)
        sample = next((s for s in lot.samples.all() if s.sampled_on <= lot.packed_date), None)
        packouts = list(lot.packouts.all())
        fresh = sum(p.cartons_fresh for p in packouts)
        total = sum(p.cartons_total for p in packouts)
        labelled_packout = next(
            (p for p in sorted(packouts, key=lambda p: p.packed_date, reverse=True)
             if p.packout_color or p.decay_pct is not None),
            None,
        )
        model_err = (pred.pack_by_date - lot.packed_date).days if pred and pred.pack_by_date else None
        foreman_err = (sample.foreman_pack_by_date - lot.packed_date).days if sample else None
        rows.append({
            'lot': lot,
            'pred': pred,
            'sample': sample,
            'model_err': model_err,
            'foreman_err': foreman_err,
            'fresh': fresh,
            'total': total,
            'fresh_pct': round(100 * fresh / total, 1) if total else None,
            'on_time': (lot.packed_date <= pred.pack_by_date) if pred and pred.pack_by_date else None,
            'packout_color': labelled_packout.packout_color if labelled_packout else '',
            'packout_decay_pct': labelled_packout.decay_pct if labelled_packout else None,
            'downgrade_reason': labelled_packout.downgrade_reason if labelled_packout else '',
        })
    return rows


def _mae(values):
    vals = [abs(v) for v in values if v is not None]
    return (round(sum(vals) / len(vals), 1), len(vals)) if vals else (None, 0)


def _fresh_split(rows):
    def agg(group):
        fresh = sum(r['fresh'] for r in group)
        total = sum(r['total'] for r in group)
        return {'n': len(group), 'fresh_pct': round(100 * fresh / total, 1) if total else None}

    on_time = [r for r in rows if r['on_time'] is True and r['total']]
    late = [r for r in rows if r['on_time'] is False and r['total']]
    return agg(on_time), agg(late)


@group_required(GM, ADMIN)
def accuracy(request):
    plant, plants = resolve_plant(request)
    lots = (
        Lot.objects.filter(status=Lot.Status.PACKED).at_plant(plant)
        .select_related('grower')
        .prefetch_related(
            'packouts',
            Prefetch(
                'predictions',
                queryset=Prediction.objects.latest_per_lot(on_or_before=OuterRef('lot__packed_date')),
            ),
            Prefetch('samples', queryset=Sample.objects.filter(is_void=False).order_by('-sampled_at', '-id')),
        )
        .order_by('-packed_date')
    )
    rows = accuracy_rows(lots)
    model_mae, model_n = _mae([r['model_err'] for r in rows])
    foreman_mae, foreman_n = _mae([r['foreman_err'] for r in rows])
    on_time, late = _fresh_split(rows)
    scoped_lots = Lot.objects.at_plant(plant)
    total_lots = scoped_lots.count()
    # Rooms are few and readings are many; resolve the rooms first so the lot
    # query never joins onto the raw reading table.
    monitored_rooms = set(RoomCondition.objects.values_list('room_id', flat=True).distinct())

    def coverage(label, count, why):
        return {
            'label': label,
            'count': count,
            'total': total_lots,
            'percent': round(100 * count / total_lots) if total_lots else 0,
            'why': why,
        }

    readiness = [
        coverage(
            'Harvest date',
            scoped_lots.filter(harvest_date__isnull=False).count(),
            'Separates orchard maturity from days held after receipt.',
        ),
        coverage(
            'Measured intake CCI',
            scoped_lots.filter(intake_cci_mean__isnull=False).count(),
            'Replaces the broad DG/LG/S/Y starting assumption.',
        ),
        coverage(
            'Room-condition exposure',
            scoped_lots.filter(
                Q(room_moves__room_id__in=monitored_rooms) | Q(current_room_id__in=monitored_rooms)
            ).distinct().count(),
            'Makes temperature, humidity and gas history available to calibration.',
        ),
        coverage(
            'Representative sampling recorded',
            scoped_lots.filter(samples__selection_method='across_bins').distinct().count(),
            'Distinguishes representative samples from convenient fruit.',
        ),
        coverage(
            'Direct packout quality',
            scoped_lots.filter(
                Q(packouts__packout_color__gt='')
                | Q(packouts__decay_pct__isnull=False)
                | Q(packouts__soft_pct__isnull=False)
                | Q(packouts__shrivel_pct__isnull=False)
                | Q(packouts__chilling_injury_pct__isnull=False)
                | Q(packouts__meets_spec__isnull=False)
            ).distinct().count(),
            'Supplies outcomes beyond the management-selected packing date.',
        ),
        coverage(
            'Shelf-life holdout outcome',
            scoped_lots.filter(
                samples__purpose='holdout', samples__marketability__gt=''
            ).distinct().count(),
            'Provides an uncensored biological endpoint for remaining-life models.',
        ),
    ]
    conditions = RoomCondition.objects.all()
    treatments = LotTreatment.objects.all()
    if plant is not None:
        conditions = conditions.filter(room__plant=plant)
        treatments = treatments.filter(lot__plant=plant)
    return render(request, 'forecast/accuracy.html', {
        'plant': plant, 'plants': plants, 'rows': rows,
        'model_mae': model_mae, 'model_n': model_n,
        'foreman_mae': foreman_mae, 'foreman_n': foreman_n,
        'on_time': on_time, 'late': late,
        'enough': len(rows) >= 20,
        'outcome_labels': sum(
            1 for row in rows
            if row['packout_color'] or row['packout_decay_pct'] is not None
        ),
        'readiness': readiness,
        'condition_readings': conditions.count(),
        'treatment_events': treatments.count(),
    })


@group_required(GM, ADMIN)
def report_preview(request, code):
    plant = get_object_or_404(Plant, code=code)
    pinned = plant_for(request.user)
    if pinned is not None and pinned.pk != plant.pk:
        raise Http404
    today = timezone.localdate()
    if request.GET.get('date'):
        try:
            today = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    data = build_report(plant, today=today)
    return render(request, 'forecast/report_email.html', {**data, 'standalone': False})
