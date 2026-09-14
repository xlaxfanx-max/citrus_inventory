"""The Monday report: per plant, the ranked pack list and the exceptions.

build_report gathers the data; render_report turns it into subject + HTML +
text; send_report emails it to the plant's recipients. The same data feeds
the on-screen preview at /report/<plant code>/.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from lots.models import Lot, ModelSettings
from lots.planning import board_rows, plan_lots
from sampling.models import Sample

from .models import PackPlan, Prediction, ReportDelivery
from .plans import publish_plan

logger = logging.getLogger(__name__)


def latest_predictions(lots, on_or_before):
    """lot_id -> most recent Prediction with as_of_date <= on_or_before."""
    qs = Prediction.objects.filter(lot__in=lots).latest_per_lot(on_or_before=on_or_before)
    return {p.lot_id: p for p in qs}


def latest_samples(lots):
    out = {}
    for s in Sample.objects.filter(lot__in=lots, is_void=False, purpose=Sample.Purpose.ROUTINE).order_by('lot_id', '-sampled_at', '-id'):
        out.setdefault(s.lot_id, s)
    return out


def build_report(plant, today=None, settings=None, plan=None):
    today = today or timezone.localdate()
    settings = settings or ModelSettings.get()
    week_ago = today - timedelta(days=7)
    lots = list(
        Lot.objects.in_storage().at_plant(plant)
        .select_related('grower', 'current_room')
        .prefetch_related('packouts')
    )
    now_preds = latest_predictions(lots, today)
    prev_preds = latest_predictions(lots, week_ago)
    samples = latest_samples(lots)
    ranked = {row['lot'].pk: row for row in board_rows(plan_lots(plant, today), today, settings)}
    data_checks = [(row['lot'], ' '.join(row['evidence_notes'])) for row in ranked.values() if row['evidence_notes']]

    to_pack, new_decay, moved_up, unsampled, import_gaps = [], [], [], [], []
    for lot in lots:
        pred = now_preds.get(lot.id)
        prev = prev_preds.get(lot.id)
        sample = samples.get(lot.id)
        if pred and ranked[lot.pk]['dates_usable'] and pred.deadline_date and (pred.deadline_date - today).days <= 7:
            to_pack.append((pred.deadline_date, lot, pred, sample))
        if pred and pred.decay_flag and not (prev and prev.decay_flag):
            new_decay.append((lot, pred, sample))
        if pred and ranked[lot.pk]['dates_usable'] and prev and pred.deadline_date and prev.deadline_date:
            shift = (prev.deadline_date - pred.deadline_date).days
            if shift > 7:
                moved_up.append((shift, lot, pred, prev))
        days_since = (today - sample.sampled_on).days if sample else lot.days_in_storage
        if days_since >= settings.sample_overdue_days:
            unsampled.append((days_since, lot, sample))
        if lot.days_in_storage > settings.import_gap_days:
            import_gaps.append(lot)

    to_pack.sort(key=lambda t: (t[0], -t[1].days_in_storage))
    moved_up.sort(key=lambda t: -t[0])
    unsampled.sort(key=lambda t: -t[0])
    import_gaps.sort(key=lambda l: -l.days_in_storage)

    to_pack_bins = sum(
        (lot.bins_remaining for _, lot, _, _ in to_pack if lot.bins_remaining is not None),
        Decimal('0'),
    )
    return {
        'plant': plant,
        'demo_mode': django_settings.DEMO_MODE,
        'today': today,
        'week_ago': week_ago,
        'board_url': f'{django_settings.SITE_URL}{reverse("lots:board")}?plant={plant.code}',
        'plan': plan,
        'plan_url': f'{django_settings.SITE_URL}{plan.get_absolute_url()}' if plan else '',
        'plan_actionable': sum(1 for r in plan.recommendations.all() if r.requires_decision) if plan else 0,
        'n_lots': len(lots),
        'to_pack': to_pack,
        'to_pack_bins': to_pack_bins,
        'to_pack_bins_unknown': sum(1 for _, lot, _, _ in to_pack if lot.bins_remaining is None),
        'weekly_capacity_bins': plant.weekly_pack_capacity_bins,
        'new_decay': new_decay,
        'moved_up': moved_up,
        'unsampled': unsampled,
        'import_gaps': import_gaps,
        'data_checks': data_checks,
        'overdue_days': settings.sample_overdue_days,
        'import_gap_days': settings.import_gap_days,
    }


def render_report(data):
    subject = f'{data["plant"].code} lemon storage: {len(data["to_pack"])} lots to pack this week ({data["today"]:%b %d})'
    html = render_to_string('forecast/report_email.html', {**data, 'standalone': True})
    text = render_to_string('forecast/report_email.txt', data)
    return subject, html, text


def send_report(plant, today=None, force=False):
    """Email the report. Returns the number of recipients it went to (0 when
    the plant has none configured)."""
    today = today or timezone.localdate()
    recipients = plant.recipient_list
    delivery = ReportDelivery.objects.filter(plant=plant, report_date=today).first()
    if delivery and delivery.status == ReportDelivery.Status.SENT and not force:
        logger.info('plant %s report for %s already sent; skipping duplicate', plant.code, today)
        return -1
    # The report is the weekly recommendation, so it publishes the plan
    # version the GM records decisions against.
    plan = publish_plan(plant, today=today, source=PackPlan.Source.REPORT)
    data = build_report(plant, today=today, plan=plan)
    subject, html, text = render_report(data)
    if delivery is None:
        delivery = ReportDelivery.objects.create(plant=plant, report_date=today, recipients=recipients, subject=subject)
    delivery.recipients = recipients
    delivery.subject = subject
    delivery.attempts += 1
    delivery.error = ''
    if not recipients:
        logger.warning('plant %s has no report recipients; report not sent', plant.code)
        delivery.status = ReportDelivery.Status.SKIPPED
        delivery.save()
        return 0
    delivery.status = ReportDelivery.Status.PENDING
    delivery.save()
    msg = EmailMultiAlternatives(subject, text, django_settings.DEFAULT_FROM_EMAIL, recipients)
    msg.attach_alternative(html, 'text/html')
    try:
        msg.send()
    except Exception as exc:
        delivery.status = ReportDelivery.Status.FAILED
        delivery.error = str(exc)[:2000]
        delivery.save(update_fields=['status', 'error', 'updated_at'])
        raise
    delivery.status = ReportDelivery.Status.SENT
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=['status', 'sent_at', 'updated_at'])
    return len(recipients)
