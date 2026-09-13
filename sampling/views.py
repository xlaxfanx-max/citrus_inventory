import mimetypes
from django.conf import settings as django_settings
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from lots.models import Lot, ModelSettings, plant_for
from lots.roles import ADMIN, FOREMAN, GM, group_required, resolve_plant

from .forms import CaptureForm
from .models import Sample, SamplePhoto


def _picker_lots(plant, query=''):
    lots = (
        Lot.objects.in_storage().at_plant(plant)
        .select_related('grower', 'current_room')
        .prefetch_related(
            Prefetch('samples', queryset=Sample.objects.filter(is_void=False, purpose=Sample.Purpose.ROUTINE).order_by('-sampled_at', '-id'))
        )
        .order_by('receive_date', 'lot_no')
    )
    if query:
        query = query.strip()
        lots = lots.filter(
            Q(lot_no__icontains=query)
            | Q(grower__name__icontains=query)
            | Q(grower__sunkist_grower_no__icontains=query)
            | Q(block__icontains=query)
            | Q(current_room__name__icontains=query)
        )
    return list(lots)


def _picker_rows(plant, query='', today=None):
    today = today or timezone.localdate()
    overdue_days = ModelSettings.get().sample_overdue_days
    rows = []
    for lot in _picker_lots(plant, query):
        last = next(iter(lot.samples.all()), None)
        done_today = bool(last) and last.sampled_on == today
        days_since = (today - last.sampled_on).days if last else None
        needs_sample = not last or days_since >= overdue_days
        rows.append({
            'lot': lot,
            'last': last,
            'done_today': done_today,
            'days_since': days_since,
            'needs_sample': needs_sample,
        })
    rows.sort(key=lambda r: (
        r['done_today'],
        0 if r['last'] is None else (1 if r['needs_sample'] else 2),
        -(r['days_since'] if r['days_since'] is not None else r['lot'].days_in_storage),
        r['lot'].receive_date,
        r['lot'].lot_no,
    ))
    return rows, overdue_days


@group_required(FOREMAN, GM, ADMIN)
def picker(request):
    plant, plants = resolve_plant(request)
    query = request.GET.get('q', '').strip()
    today = timezone.localdate()
    rows, overdue_days = _picker_rows(plant, query, today)
    route_rows = _picker_rows(plant, today=today)[0] if query else rows
    done_today = [r for r in route_rows if r['done_today']]
    due_rows = [r for r in route_rows if r['needs_sample'] and not r['done_today']]
    recent_rows = [r for r in route_rows if not r['needs_sample'] and not r['done_today']]
    route_total = len(done_today) + len(due_rows)
    route_percent = round(100 * len(done_today) / route_total) if route_total else 100
    template = 'sampling/_lot_list.html' if request.headers.get('HX-Request') else 'sampling/picker.html'
    return render(request, template, {
        'plant': plant,
        'plants': plants,
        'rows': rows,
        'done_today': done_today,
        'due_rows': due_rows,
        'recent_rows': recent_rows,
        'next_row': due_rows[0] if due_rows else None,
        'route_total': route_total,
        'route_done': len(done_today),
        'route_remaining': len(due_rows),
        'route_percent': route_percent,
        'overdue_days': overdue_days,
        'query': query,
        'today': today,
    })


@group_required(FOREMAN, GM, ADMIN)
def capture(request, lot_id):
    lot = get_object_or_404(Lot.objects.select_related('grower', 'current_room', 'plant'), pk=lot_id)
    pinned = plant_for(request.user)
    if pinned is not None and lot.plant_id != pinned.id:
        raise Http404
    if lot.status == Lot.Status.DUMPED:
        messages.error(request, _('Lot %(lot)s was dumped; it cannot be sampled.') % {'lot': lot.lot_no})
        return redirect('sampling:picker')

    settings = ModelSettings.get()
    form_kwargs = {'plant': lot.plant, 'fruit_count': settings.sample_fruit_count}
    if request.method == 'POST':
        form = CaptureForm(request.POST, request.FILES, **form_kwargs)
        if lot.status == Lot.Status.PACKED and not request.POST.get('is_holdout'):
            form.add_error(None, _('After final packing, only shelf-life holdout assessments may be recorded.'))
        if form.is_valid():
            data = form.cleaned_data
            sample = Sample.objects.create(
                lot=lot,
                sampled_by=request.user,
                foreman_color=data['foreman_color'],
                foreman_pack_within_weeks=data['foreman_pack_within_weeks'],
                decay_count=data['decay_count'],
                fruit_count=data.get('fruit_count') or settings.sample_fruit_count,
                capture_seconds=_capture_seconds(data.get('opened_at')),
                # A legacy or API-style POST that omits this field must not be
                # counted as representative sampling on the readiness dashboard.
                selection_method=data.get('selection_method') or Sample.SelectionMethod.UNKNOWN,
                sampled_bins_count=data.get('sampled_bins_count') or 1,
                purpose=(Sample.Purpose.HOLDOUT if data.get('is_holdout') else Sample.Purpose.ROUTINE),
                soft_count=data.get('soft_count') or 0,
                shrivel_count=data.get('shrivel_count') or 0,
                chilling_injury_count=data.get('chilling_injury_count') or 0,
                rind_breakdown_count=data.get('rind_breakdown_count') or 0,
                firmness_score=data.get('firmness_score'),
                marketability=data.get('marketability') or '',
                failure_reason=data.get('failure_reason') or '',
                notes=data.get('notes', ''),
            )
            device_info = request.META.get('HTTP_USER_AGENT', '')[:200]
            for f in (data['photo'], data.get('photo2')):
                if f:
                    calibration = data.get('calibration')
                    SamplePhoto.objects.create(sample=sample, image=f, device_info=device_info,
                        calibration_snapshot=calibration.snapshot() if calibration else {})
            messages.success(request, _('Lot %(lot)s saved. Scoring in the background.') % {'lot': lot.lot_no})
            return redirect('sampling:sample_status', pk=sample.pk)
    else:
        form = CaptureForm(initial={'is_holdout': lot.status == Lot.Status.PACKED, 'opened_at': int(timezone.now().timestamp())}, **form_kwargs)
    last = lot.samples.filter(is_void=False, purpose=Sample.Purpose.ROUTINE).order_by('-sampled_at').first()
    return render(request, 'sampling/capture.html', {
        'lot': lot, 'form': form, 'last': last,
        'fruit_count': form.base_fruit_count, 'double_count': form.double_fruit_count,
        'decay_flag_pct': settings.decay_flag_pct,
    })


def _capture_seconds(opened_at):
    """Seconds between opening the capture screen and saving, or None when the
    hidden timestamp is missing or implausible (clock skew, page left open)."""
    if not opened_at:
        return None
    elapsed = int(timezone.now().timestamp()) - int(opened_at)
    return elapsed if 0 <= elapsed <= 4 * 3600 else None


@group_required(FOREMAN, GM, ADMIN)
def photo(request, pk):
    """Serve a photo (or its thumbnail with ?thumb=1) to logged-in users only.
    Redirects to a signed URL when storage is Supabase/S3."""
    p = get_object_or_404(SamplePhoto.objects.select_related('sample__lot'), pk=pk)
    pinned = plant_for(request.user)
    if pinned is not None and p.sample.lot.plant_id != pinned.id:
        raise Http404
    field = p.thumb if request.GET.get('thumb') and p.thumb else p.image
    if not field:
        raise Http404
    if getattr(django_settings, 'PHOTO_URLS_ARE_SIGNED', False):
        return redirect(field.url)
    ctype = mimetypes.guess_type(field.name)[0] or 'image/jpeg'
    resp = FileResponse(field.open('rb'), content_type=ctype)
    resp['Cache-Control'] = 'private, max-age=86400'
    resp['X-Content-Type-Options'] = 'nosniff'
    resp['Content-Disposition'] = 'inline'
    return resp


@group_required(FOREMAN, GM, ADMIN)
def sample_status(request, pk):
    sample = get_object_or_404(
        Sample.objects.select_related('lot__plant', 'lot__grower').prefetch_related('photos'),
        pk=pk,
        is_void=False,
    )
    pinned = plant_for(request.user)
    if pinned is not None and sample.lot.plant_id != pinned.id:
        raise Http404
    photos = list(sample.photos.all())
    waiting = any(
        p.status in {SamplePhoto.Status.PENDING, SamplePhoto.Status.PROCESSING} for p in photos
    )
    failed = [p for p in photos if p.status == SamplePhoto.Status.FAILED]
    usable = [p for p in photos if p.status == SamplePhoto.Status.SCORED and p.quality_ok]
    low_quality = [p for p in photos if p.status == SamplePhoto.Status.SCORED and not p.quality_ok]
    picker_rows, _ = _picker_rows(sample.lot.plant, today=timezone.localdate())
    next_row = next((r for r in picker_rows if r['needs_sample'] and not r['done_today']), None)
    return render(request, 'sampling/sample_status.html', {
        'sample': sample,
        'photos': photos,
        'waiting': waiting,
        'failed': failed,
        'usable': usable,
        'low_quality': low_quality,
        'next_row': next_row,
    })
