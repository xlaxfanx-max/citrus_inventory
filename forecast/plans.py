"""Versioned packing plans and the management decision record.

publish_plan freezes the current ranked board for one plant as a new
PackPlan version. Recommendations that ask for a pack (or flag decay) carry
requires_decision=True; the GM records accepted / deferred / overridden with
a structured reason against each, and the coverage helpers turn those
records into the pilot scorecard numbers (decisions recorded, override
reasons complete, decided before the schedule lock).
"""

from django.db import transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from lots.models import ModelSettings
from lots.planning import board_rows, plan_lots

from .model import MODEL_VERSION
from .models import MarketRegime, PackPlan, PlanDecision, PlanRecommendation


def accept_remaining(plan, user):
    """Record an 'accepted' decision on every actionable recommendation that
    has none yet. One PlanDecision row each, so the audit trail is the same
    as clicking Accept on every line. Returns the number recorded."""
    recorded = 0
    with transaction.atomic():
        for rec in plan.recommendations.all():
            if rec.requires_decision and rec.latest_decision is None:
                PlanDecision.objects.create(recommendation=rec, status=PlanDecision.Status.ACCEPTED, decided_by=user)
                recorded += 1
    return recorded


def settings_snapshot(settings):
    return {
        f.name: getattr(settings, f.name)
        for f in ModelSettings._meta.fields
        if f.name != 'id'
    }


def publish_plan(plant, today=None, user=None, source=PackPlan.Source.BOARD, settings=None, market_regime=''):
    """Snapshot the ranked plan for `plant` as the next version. Returns the PackPlan.

    market_regime is the GM's call on the week (tight / normal / oversupplied);
    an automated publish that does not know it inherits the previous plan's."""
    today = today or timezone.localdate()
    settings = settings or ModelSettings.get()
    rows = board_rows(plan_lots(plant, today), today, settings)
    with transaction.atomic():
        previous = PackPlan.objects.filter(plant=plant).order_by('-version').first()
        current = previous.version if previous else 0
        if market_regime not in {m.value for m in MarketRegime}:
            market_regime = previous.market_regime if previous else ''
        plan = PackPlan.objects.create(
            plant=plant,
            plan_date=today,
            version=current + 1,
            source=source,
            published_by=user,
            model_version=MODEL_VERSION,
            settings_snapshot=settings_snapshot(settings),
            market_regime=market_regime,
        )
        recs = []
        for rank, row in enumerate(rows, start=1):
            lot, pred, action = row['lot'], row['pred'], row['action']
            recs.append(PlanRecommendation(
                plan=plan,
                lot=lot,
                prediction=pred,
                rank=rank,
                action=action.code,
                requires_decision=action.requires_decision,
                pack_by_date=pred.pack_by_date if pred else None,
                hold_until_date=pred.hold_until_date if pred else None,
                deadline_kind=pred.deadline_kind if pred else '',
                stage=pred.stage if pred else '',
                cci_now=pred.cci_now if pred else None,
                confidence=pred.confidence if pred else '',
                decay_flag=bool(pred and pred.decay_flag),
                bins_remaining=lot.bins_remaining,
                room_name=lot.current_room.name if lot.current_room else '',
                days_in_storage=max(lot.days_in_storage, 0),
                evidence_notes=row['evidence_notes'],
            ))
        PlanRecommendation.objects.bulk_create(recs)
    return plan


def plans_for(plant):
    """Plan versions for a plant (or all plants when None), newest first,
    with recommendations and decisions loaded for coverage figures."""
    qs = PackPlan.objects.select_related('plant', 'published_by', 'locked_by')
    if plant is not None:
        qs = qs.filter(plant=plant)
    return qs.prefetch_related(
        Prefetch(
            'recommendations',
            queryset=PlanRecommendation.objects.select_related('lot', 'lot__grower').prefetch_related(
                Prefetch('decisions', queryset=PlanDecision.objects.select_related('decided_by'))
            ),
        )
    )


def latest_plan(plant):
    if plant is None:
        return None
    return plans_for(plant).first()


def coverage(plan):
    """Scorecard figures for one plan, from its prefetched recommendations."""
    actionable = [r for r in plan.recommendations.all() if r.requires_decision]
    decided = [r for r in actionable if r.latest_decision is not None]
    needing_reason = [r for r in decided if r.latest_decision.needs_reason]
    reasons_complete = [r for r in needing_reason if r.latest_decision.reason_complete]
    before_lock = [r for r in decided if not r.latest_decision.after_lock]
    by_status = {s.value: 0 for s in PlanDecision.Status}
    for r in decided:
        by_status[r.latest_decision.status] += 1

    def pct(n, d):
        return round(100 * n / d) if d else None

    return {
        'total': len(list(plan.recommendations.all())),
        'actionable': len(actionable),
        'decided': len(decided),
        'undecided': len(actionable) - len(decided),
        'decided_pct': pct(len(decided), len(actionable)),
        'reasons_needed': len(needing_reason),
        'reasons_complete': len(reasons_complete),
        'reasons_pct': pct(len(reasons_complete), len(needing_reason)),
        'before_lock': len(before_lock),
        'before_lock_pct': pct(len(before_lock), len(decided)) if plan.is_locked else None,
        'by_status': by_status,
    }


def scorecard(plans):
    """Aggregate the coverage figures over several plans."""
    totals = {'actionable': 0, 'decided': 0, 'reasons_needed': 0, 'reasons_complete': 0, 'locked_decided': 0, 'before_lock': 0}
    for plan in plans:
        c = coverage(plan)
        totals['actionable'] += c['actionable']
        totals['decided'] += c['decided']
        totals['reasons_needed'] += c['reasons_needed']
        totals['reasons_complete'] += c['reasons_complete']
        if plan.is_locked:
            totals['locked_decided'] += c['decided']
            totals['before_lock'] += c['before_lock']

    def pct(n, d):
        return round(100 * n / d) if d else None

    return {
        'plans': len(plans),
        **totals,
        'decided_pct': pct(totals['decided'], totals['actionable']),
        'reasons_pct': pct(totals['reasons_complete'], totals['reasons_needed']),
        'before_lock_pct': pct(totals['before_lock'], totals['locked_decided']),
    }


def current_decisions(plant):
    """lot_id -> latest PlanDecision in the plant's newest plan, for the board."""
    plan = latest_plan(plant)
    if plan is None:
        return plan, {}
    out = {}
    for rec in plan.recommendations.all():
        decision = rec.latest_decision
        if decision is not None:
            out[rec.lot_id] = decision
    return plan, out


def lot_decision_history(lot):
    """Every plan line for a lot, newest plan first, with its decisions."""
    return (
        PlanRecommendation.objects.filter(lot=lot)
        .select_related('plan', 'plan__plant')
        .prefetch_related(Prefetch('decisions', queryset=PlanDecision.objects.select_related('decided_by')))
        .order_by('-plan__plan_date', '-plan__version')
    )
