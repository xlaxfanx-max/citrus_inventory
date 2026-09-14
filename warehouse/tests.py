from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db.models import Avg, Count
from django.test import TestCase
from django.utils import timezone

from forecast.model import MODEL_VERSION
from forecast.models import PackPlan, PlanAction, PlanDecision, PlanRecommendation, Prediction
from lots.models import Color, Grower, Lot, Packout, Plant
from warehouse.models import DimDate, DimLot, FactDecision, FactPackout, FactPrediction, date_key


class BuildWarehouseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        today = timezone.localdate()
        cls.plant = Plant.objects.create(code='SLA1', name='Plant 1', weekly_pack_capacity_bins=650)
        grower = Grower.objects.create(sunkist_grower_no='10417', name='Sespe')
        cls.lot = Lot.objects.create(
            lot_no='26-1001', plant=cls.plant, grower=grower, receive_date=today - timedelta(days=40),
            harvest_date=today - timedelta(days=42), bins_received=100, receiving_color=Color.DARK_GREEN,
        )
        cls.other = Lot.objects.create(lot_no='26-1002', plant=cls.plant, grower=grower, receive_date=today - timedelta(days=10))
        Prediction.objects.create(
            lot=cls.lot, as_of_date=today - timedelta(days=20), cci_now=-4.0, stage=Color.LIGHT_GREEN, drift_per_day=0.2,
            predicted_yellow_date=today - timedelta(days=3), pack_by_date=today - timedelta(days=10),
            confidence='med', model_version=MODEL_VERSION, inputs={'points': [[10, -6.0], [20, -4.0]], 'method': 'ols'},
        )
        Prediction.objects.create(
            lot=cls.lot, as_of_date=today - timedelta(days=2), cci_now=0.5, stage=Color.SILVER, drift_per_day=0.2,
            predicted_yellow_date=today + timedelta(days=5), pack_by_date=today - timedelta(days=2),
            confidence='high', model_version=MODEL_VERSION, inputs={'points': [[10, -6.0], [20, -4.0], [38, 0.5]], 'method': 'ols'},
        )
        Packout.objects.create(
            lot=cls.lot, packed_date=today - timedelta(days=5), cartons_fancy=300, cartons_choice=150,
            cartons_standard=50, cartons_products=100, bins_packed=Decimal('100'),
        )
        gm = User.objects.create_user('gm', password='pw')
        plan = PackPlan.objects.create(plant=cls.plant, plan_date=today - timedelta(days=7), version=1, model_version=MODEL_VERSION, market_regime='tight')
        rec = PlanRecommendation.objects.create(
            plan=plan, lot=cls.lot, rank=1, action=PlanAction.PACK_THIS_WEEK, requires_decision=True,
            pack_by_date=today - timedelta(days=10), stage=Color.LIGHT_GREEN,
        )
        PlanDecision.objects.create(recommendation=rec, status=PlanDecision.Status.DEFERRED, reason=PlanDecision.Reason.CUSTOMER_ORDER,
                                    planned_pack_date=today - timedelta(days=5), decided_by=gm)

    def test_rebuild_loads_dimensions_and_facts(self):
        out = StringIO()
        call_command('build_warehouse', stdout=out)
        self.assertIn('2 lots', out.getvalue())
        today = timezone.localdate()
        dim = DimLot.objects.get(lot_key=self.lot.pk)
        self.assertEqual((dim.grower_no, dim.plant.code, dim.status), ('10417', 'SLA1', 'packed'))
        self.assertEqual(dim.receive_date.date, self.lot.receive_date)
        self.assertEqual(dim.packed_date.date, today - timedelta(days=5))
        self.assertEqual(FactPrediction.objects.filter(lot=dim).count(), 2)
        packout = FactPackout.objects.get(lot=dim)
        # Latest forecast on or before the pack date said pack by today-10; packed today-5: five days late.
        self.assertEqual(packout.forecast_pack_by_date.date, today - timedelta(days=10))
        self.assertEqual(packout.days_after_pack_by, 5)
        self.assertEqual((packout.cartons_total, float(packout.fresh_pct), packout.days_in_storage), (600, 83.33, 35))
        decision = FactDecision.objects.get(lot=dim)
        self.assertEqual((decision.status, decision.market_regime, decision.plan_version, decision.decided_by), ('deferred', 'tight', 1, 'gm'))
        self.assertTrue(DimDate.objects.filter(date_key=date_key(today)).exists())
        self.assertEqual(DimDate.objects.get(date_key=date_key(date(2026, 9, 14))).is_monday, True)

    def test_rebuild_is_idempotent_and_answers_a_star_query(self):
        call_command('build_warehouse', stdout=StringIO())
        call_command('build_warehouse', stdout=StringIO())
        self.assertEqual(FactPackout.objects.count(), 1)
        # Fact -> lot dimension -> plant dimension, grouped by calendar month of the pack date.
        rows = (
            FactPackout.objects.values('lot__plant__code', 'packed_date__year', 'packed_date__month')
            .annotate(runs=Count('id'), late_days=Avg('days_after_pack_by'))
        )
        row = rows.get()
        self.assertEqual((row['lot__plant__code'], row['runs'], row['late_days']), ('SLA1', 1, 5.0))
