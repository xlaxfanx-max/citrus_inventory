"""Rebuild the reporting star schema from the operational tables.

Extract: read lots, predictions, packouts and decisions.
Transform: flatten grower and plant context onto the lot dimension, turn
dates into calendar keys, and score each packout against the latest
forecast that existed when it happened.
Load: replace every warehouse table inside one transaction.

Run nightly after build_predictions, or on demand before an analysis.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from forecast.models import PlanDecision, Prediction
from lots.models import Lot, Packout, Plant
from warehouse.models import DimDate, DimLot, DimPlant, FactDecision, FactPackout, FactPrediction, date_key


def _calendar(first, last):
    day = first
    while day <= last:
        iso = day.isocalendar()
        yield DimDate(
            date_key=date_key(day), date=day, year=day.year, quarter=(day.month - 1) // 3 + 1,
            month=day.month, week_of_year=iso[1], day_of_week=iso[2], is_monday=iso[2] == 1,
        )
        day += timedelta(days=1)


class Command(BaseCommand):
    help = 'Rebuild the dw_* reporting tables from the operational schema.'

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        FactDecision.objects.all().delete()
        FactPackout.objects.all().delete()
        FactPrediction.objects.all().delete()
        DimLot.objects.all().delete()
        DimPlant.objects.all().delete()
        DimDate.objects.all().delete()

        lots = list(Lot.objects.select_related('plant', 'grower'))
        predictions = list(Prediction.objects.order_by('lot_id', 'as_of_date'))
        packouts = list(Packout.objects.all())
        decisions = list(
            PlanDecision.objects.select_related('recommendation__plan', 'decided_by').order_by('decided_at', 'id')
        )

        # Calendar: from the earliest date the facts mention to a year past today.
        dates = [lot.receive_date for lot in lots] + [lot.harvest_date for lot in lots if lot.harvest_date]
        dates += [p.as_of_date for p in predictions] + [p.pack_by_date for p in predictions if p.pack_by_date]
        dates += [p.hold_until_date for p in predictions if p.hold_until_date]
        dates += [d.recommendation.plan.plan_date for d in decisions]
        first = min(dates, default=today) - timedelta(days=7)
        last = max(dates + [today], default=today) + timedelta(days=366)
        DimDate.objects.bulk_create(_calendar(first, last), batch_size=1000)

        DimPlant.objects.bulk_create(
            DimPlant(plant_key=p.pk, code=p.code, name=p.name, weekly_pack_capacity_bins=p.weekly_pack_capacity_bins)
            for p in Plant.objects.all()
        )

        DimLot.objects.bulk_create(
            DimLot(
                lot_key=lot.pk, plant_id=lot.plant_id, lot_no=lot.lot_no,
                grower_no=lot.grower.sunkist_grower_no, grower_name=lot.grower.name,
                block=lot.block, variety=lot.variety, receiving_color=lot.receiving_color,
                intake_cci_mean=lot.intake_cci_mean,
                receive_date_id=date_key(lot.receive_date), harvest_date_id=date_key(lot.harvest_date),
                bins_received=lot.bins_received, status=lot.status,
                packed_date_id=date_key(lot.packed_date), days_in_storage=lot.days_in_storage,
            )
            for lot in lots
        )

        FactPrediction.objects.bulk_create(
            (
                FactPrediction(
                    lot_id=p.lot_id, as_of_date_id=date_key(p.as_of_date), pack_by_date_id=date_key(p.pack_by_date),
                    days_to_pack_by=(p.pack_by_date - p.as_of_date).days if p.pack_by_date else None,
                    hold_until_date_id=date_key(p.hold_until_date), hold_days_remaining=p.hold_days_remaining,
                    deadline_kind=p.deadline_kind,
                    cci_now=p.cci_now, stage=p.stage, drift_per_day=p.drift_per_day, decay_rate=p.decay_rate,
                    decay_flag=p.decay_flag, confidence=p.confidence, n_points=p.n_points,
                    method=(p.inputs or {}).get('method', ''), model_version=p.model_version,
                )
                for p in predictions
            ),
            batch_size=1000,
        )

        # Latest forecast on or before each pack date, from the ordered list.
        by_lot = {}
        for p in predictions:
            by_lot.setdefault(p.lot_id, []).append(p)
        receive_by_lot = {lot.pk: lot.receive_date for lot in lots}

        def forecast_before(lot_id, day):
            latest = None
            for p in by_lot.get(lot_id, []):
                if p.as_of_date <= day:
                    latest = p
                else:
                    break
            return latest

        rows = []
        for po in packouts:
            forecast = forecast_before(po.lot_id, po.packed_date)
            pack_by = forecast.pack_by_date if forecast else None
            rows.append(FactPackout(
                lot_id=po.lot_id, packed_date_id=date_key(po.packed_date),
                cartons_fancy=po.cartons_fancy, cartons_choice=po.cartons_choice,
                cartons_standard=po.cartons_standard, cartons_products=po.cartons_products,
                cartons_total=po.cartons_total, fresh_pct=po.fresh_pct, bins_packed=po.bins_packed,
                is_final=po.is_final, packout_color=po.packout_color, decay_pct=po.decay_pct,
                meets_spec=po.meets_spec, days_in_storage=(po.packed_date - receive_by_lot[po.lot_id]).days,
                forecast_pack_by_date_id=date_key(pack_by),
                days_after_pack_by=(po.packed_date - pack_by).days if pack_by else None,
            ))
        FactPackout.objects.bulk_create(rows, batch_size=1000)

        FactDecision.objects.bulk_create(
            (
                FactDecision(
                    lot_id=d.recommendation.lot_id,
                    plan_date_id=date_key(d.recommendation.plan.plan_date),
                    decided_date_id=date_key(timezone.localtime(d.decided_at).date()),
                    plan_version=d.recommendation.plan.version, rank=d.recommendation.rank,
                    action=d.recommendation.action,
                    recommended_pack_by_date_id=date_key(d.recommendation.pack_by_date),
                    status=d.status, reason=d.reason, planned_pack_date_id=date_key(d.planned_pack_date),
                    market_regime=d.market_regime, after_lock=d.after_lock,
                    decided_by=d.decided_by.get_username() if d.decided_by else '',
                    source_decision_id=d.pk,
                )
                for d in decisions
            ),
            batch_size=1000,
        )

        self.stdout.write(
            f'warehouse rebuilt: {DimDate.objects.count()} dates, {DimPlant.objects.count()} plants, '
            f'{DimLot.objects.count()} lots, {FactPrediction.objects.count()} predictions, '
            f'{FactPackout.objects.count()} packouts, {FactDecision.objects.count()} decisions'
        )
