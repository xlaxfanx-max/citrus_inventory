from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from lots.models import (
    Color, Grower, Lot, LotRoomMove, LotTreatment, ModelSettings, Packout,
    Plant, Room, RoomCondition, UserProfile,
)
from sampling.models import Sample, SamplePhoto

from .features import environment_features
from .model import MODEL_VERSION, decay_summary, ols, predict
from .models import PackPlan, PlanAction, PlanDecision, PlanRecommendation, Prediction, ReportDelivery
from .plans import coverage, plans_for, publish_plan, scorecard
from .report import build_report, send_report
from .services import rebuild_for_lot
from .training import rows_for_lot

TODAY = date(2026, 10, 5)


class ModelTests(TestCase):
    def test_passing_time_does_not_move_yellow_crossing(self):
        settings = ModelSettings.get()
        received = TODAY - timedelta(days=30)
        results = [predict(as_of=TODAY + timedelta(days=offset), receive_date=received,
            receiving_color='LG', points=[(0, -1), (10, 1), (20, 3), (30, 5)],
            decay_samples=[], settings=settings) for offset in (0, 7, 14)]
        self.assertEqual({r['predicted_yellow_date'] for r in results}, {received + timedelta(days=15)})
        self.assertEqual(len({r['pack_by_date'] for r in results}), 1)
        self.assertEqual(results[-1]['confidence'], 'low')

    def test_duplicate_day_and_future_visits_cannot_inflate_support(self):
        s = ModelSettings.get()
        result = predict(as_of=TODAY, receive_date=TODAY-timedelta(days=10), receiving_color='DG',
            points=[(0, -8), (0, -8), (10, -6), (10, -6), (20, 4)], decay_samples=[], settings=s)
        self.assertEqual(result['inputs']['points'], [[0, -8.0], [10, -6.0]])
        self.assertEqual(result['confidence'], 'med')

    def setUp(self):
        self.s = ModelSettings.get()

    def go(self, points, color=Color.DARK_GREEN, decay=(), receive_days_ago=30, as_of=TODAY):
        return predict(as_of=as_of, receive_date=as_of - timedelta(days=receive_days_ago), receiving_color=color,
                       points=points, decay_samples=decay, settings=self.s)

    def test_ols(self):
        slope, intercept, r2 = ols([0, 10, 20], [-10, -8, -6])
        self.assertAlmostEqual(slope, 0.2)
        self.assertAlmostEqual(intercept, -10)
        self.assertAlmostEqual(r2, 1.0)

    def test_no_points_uses_receiving_color_prior(self):
        r = self.go([], color=Color.LIGHT_GREEN, receive_days_ago=10)
        self.assertEqual(r['confidence'], 'low')
        self.assertEqual(r['drift_per_day'], self.s.prior_drift_lg)
        self.assertAlmostEqual(r['cci_now'], self.s.start_cci_lg + 10 * self.s.prior_drift_lg, places=3)
        self.assertEqual(r['inputs']['method'], 'prior_from_receiving_color')
        self.assertEqual(r['model_version'], MODEL_VERSION)
        self.assertEqual(r['pack_by_date'], r['predicted_yellow_date'] - timedelta(days=self.s.buffer_days))

    def test_one_point_extrapolates_with_prior(self):
        r = self.go([(20, -6.0)], color=Color.DARK_GREEN, receive_days_ago=30)
        self.assertEqual(r['confidence'], 'low')
        self.assertAlmostEqual(r['cci_now'], -6.0 + 10 * self.s.prior_drift_dg, places=3)

    def test_two_points_fit_medium_confidence(self):
        r = self.go([(10, -9.0), (30, -5.0)], receive_days_ago=30)
        self.assertEqual(r['confidence'], 'med')
        self.assertAlmostEqual(r['drift_per_day'], 0.2)
        self.assertAlmostEqual(r['cci_now'], -5.0)
        days = (self.s.yellow_threshold - (-5.0)) / 0.2  # 35 days
        self.assertEqual(r['predicted_yellow_date'], TODAY + timedelta(days=35))
        self.assertEqual(r['pack_by_date'], TODAY + timedelta(days=35 - self.s.buffer_days))
        self.assertEqual(r['stage'], Color.LIGHT_GREEN)

    def test_four_good_points_high_confidence_and_last_five_used(self):
        pts = [(d, -12 + 0.2 * d) for d in (0, 7, 14, 21, 28, 35)]
        r = self.go(pts, receive_days_ago=40)
        self.assertEqual(r['confidence'], 'high')
        self.assertEqual(r['inputs']['fit']['n'], 5)

    def test_flat_or_greening_fit_falls_back_to_prior(self):
        r = self.go([(10, -6.0), (20, -6.5), (30, -6.2)], receive_days_ago=30)
        self.assertEqual(r['confidence'], 'low')
        self.assertEqual(r['drift_per_day'], self.s.prior_drift_dg)
        self.assertEqual(r['inputs']['method'], 'prior_after_flat_fit')
        self.assertAlmostEqual(r['cci_now'], -6.2, places=3)

    def test_already_yellow(self):
        r = self.go([(10, 1.0), (20, 3.0)], receive_days_ago=20)
        self.assertEqual(r['predicted_yellow_date'], TODAY - timedelta(days=5))
        self.assertEqual(r['stage'], Color.YELLOW)
        self.assertIn('at or past yellow threshold; crossing estimate is retained', r['inputs']['notes'])

    def test_horizon_cap(self):
        r = self.go([(0, -30.0), (10, -29.9)], receive_days_ago=10)  # 0.01/day -> ~3000 days
        self.assertIsNone(r['predicted_yellow_date'])
        self.assertIsNone(r['pack_by_date'])
        self.assertTrue(r['inputs']['horizon_exceeded'])

    def test_decay_rules(self):
        self.assertEqual(decay_summary([], 2.0), (0.0, False))
        self.assertEqual(decay_summary([(0, 10)], 2.0), (0.0, False))
        rate, flag = decay_summary([(0, 10), (1, 10)], 2.0)
        self.assertAlmostEqual(rate, 0.05)
        self.assertTrue(flag)
        rate, flag = decay_summary([(1, 10), (0, 10)], 2.0)  # falling but 5% -> flag on rate
        self.assertTrue(flag)
        rate, flag = decay_summary([(0, 100), (1, 100)], 2.0)  # 0.5% but rising -> flag
        self.assertTrue(flag)
        rate, flag = decay_summary([(1, 100), (1, 100)], 2.0)  # 1%, not rising
        self.assertFalse(flag)


@override_settings(FOREMAN_DEFAULT_LANGUAGE='en')
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.plant = Plant.objects.create(code='SLA1', name='Plant 1')
        cls.plant.set_recipients(['gm@example.com', 'foreman@example.com'])
        cls.grower = Grower.objects.create(sunkist_grower_no='10417', name='Sespe')
        cls.settings = ModelSettings.get()

    def make_lot(self, lot_no, days_ago, color=Color.DARK_GREEN, **kw):
        return Lot.objects.create(lot_no=lot_no, plant=self.plant, grower=self.grower, receive_date=date.today() - timedelta(days=days_ago), receiving_color=color, **kw)

    def add_sample(self, lot, days_ago, cci, decay=0, weeks=4, color=Color.LIGHT_GREEN):
        when = timezone.now() - timedelta(days=days_ago)
        s = Sample.objects.create(lot=lot, sampled_at=when, foreman_color=color, foreman_pack_within_weeks=weeks, decay_count=decay)
        SamplePhoto.objects.create(sample=s, image='', status=SamplePhoto.Status.SCORED, card_detected=True, fruit_detected=10, mean_cci=cci, per_fruit_cci=[cci] * 10)
        return s


class ServiceTests(Base):
    def test_holdout_cannot_change_forecast_or_reset_routine_sampling(self):
        from lots.planning import board_rows, plan_lots
        from sampling.views import _picker_rows
        lot = self.make_lot('HOLDOUT-ISOLATION', 40)
        self.add_sample(lot, 21, -8)
        self.add_sample(lot, 14, -7)
        before = rebuild_for_lot(lot)
        holdout = self.add_sample(lot, 0, 9, decay=5)
        holdout.purpose = Sample.Purpose.HOLDOUT
        holdout.marketability = Sample.Marketability.FAIL
        holdout.failure_reason = Sample.FailureReason.DECAY
        holdout.save()
        after = rebuild_for_lot(lot)
        self.assertEqual(before.pack_by_date, after.pack_by_date)
        self.assertEqual(before.inputs['points'], after.inputs['points'])
        self.assertFalse(after.decay_flag)
        row = board_rows(plan_lots(self.plant), timezone.localdate(), self.settings)[0]
        self.assertEqual(row['days_since_sample'], 14)
        self.assertFalse(row['dates_usable'])
        self.assertEqual(row['action'].code, PlanAction.SAMPLE_DUE)
        route, _ = _picker_rows(self.plant)
        self.assertFalse(route[0]['done_today'])

    def test_stale_dates_are_excluded_from_board_report_plan_and_capacity(self):
        from lots.planning import board_rows, plan_lots, capacity_projection
        lot = self.make_lot('STALE-URGENT', 40, bins_received=120)
        for age, cci in [(35, -2), (28, 0), (21, 2), (14, 4)]:
            self.add_sample(lot, age, cci)
        pred = rebuild_for_lot(lot)
        self.assertEqual(pred.confidence, 'low')
        rows = board_rows(plan_lots(self.plant), timezone.localdate(), self.settings)
        self.assertFalse(rows[0]['dates_usable'])
        self.assertIsNone(rows[0]['days_to_pack_by'])
        self.assertEqual(sum(b['lots'] for b in capacity_projection(rows, self.plant, timezone.localdate())), 0)
        self.assertEqual(build_report(self.plant)['to_pack'], [])
        rec = publish_plan(self.plant).recommendations.get()
        self.assertFalse(rec.requires_decision)
        self.assertTrue(rec.evidence_notes)

    def test_same_day_room_moves_use_actual_exposure_and_count_days_once(self):
        lot = self.make_lot('INTRADAY', 2)
        cold = Room.objects.create(plant=self.plant, name='Cold')
        warm = Room.objects.create(plant=self.plant, name='Warm')
        day = timezone.localdate()
        at = lambda hour: timezone.make_aware(datetime.combine(day, time(hour)))
        LotRoomMove.objects.create(lot=lot, room=cold, moved_on=lot.receive_date)
        LotRoomMove.objects.create(lot=lot, room=warm, moved_on=day, occurred_at=at(12))
        LotRoomMove.objects.create(lot=lot, room=cold, moved_on=day, occurred_at=at(18))
        for room, hour, temp in [(cold, 10, 50), (cold, 14, 99), (warm, 14, 70), (warm, 20, 99), (cold, 20, 50)]:
            RoomCondition.objects.create(room=room, recorded_at=at(hour), temperature_f=temp, source='test')
        env = environment_features(lot, day)
        self.assertEqual(env['reading_count'], 3)
        self.assertEqual(env['observed_days'], 1)
        self.assertEqual(env['temperature_f']['max'], 70)
        self.assertAlmostEqual(env['exposure_days'], 3)
        self.assertEqual(env['date_only_move_count'], 1)

    def test_rebuild_writes_and_upserts(self):
        lot = self.make_lot('26-1', 30)
        self.add_sample(lot, 20, -9.0)
        self.add_sample(lot, 10, -7.0)
        pred = rebuild_for_lot(lot)
        self.assertEqual(pred.inputs['points'], [[10, -9.0], [20, -7.0]])
        self.assertEqual(pred.confidence, 'low')  # latest usable point is at the resampling limit
        again = rebuild_for_lot(lot)
        self.assertEqual(again.pk, pred.pk)
        self.assertEqual(Prediction.objects.count(), 1)

    def test_latest_per_lot_prefetches_one_row_per_lot(self):
        from django.db.models import OuterRef, Prefetch

        today = date.today()
        lot = self.make_lot('26-1', 30)
        other = self.make_lot('26-2', 30)
        self.add_sample(lot, 20, -9.0)
        for days_ago in (12, 6, 0):
            rebuild_for_lot(lot, as_of=today - timedelta(days=days_ago))
        rebuild_for_lot(other, as_of=today)
        self.assertEqual(Prediction.objects.count(), 4)

        fetched = Lot.objects.prefetch_related(Prefetch('predictions', queryset=Prediction.objects.latest_per_lot()))
        by_lot = {l.lot_no: [p.as_of_date for p in l.predictions.all()] for l in fetched}
        self.assertEqual(by_lot, {'26-1': [today], '26-2': [today]})

        cutoff = today - timedelta(days=3)
        as_of = Prediction.objects.filter(lot=lot).latest_per_lot(on_or_before=cutoff)
        self.assertEqual([p.as_of_date for p in as_of], [today - timedelta(days=6)])

        Packout.objects.create(lot=lot, packed_date=today - timedelta(days=8), cartons_fancy=10)
        per_lot_date = Prediction.objects.latest_per_lot(on_or_before=OuterRef('lot__packed_date'))
        packed = Lot.objects.filter(pk=lot.pk).prefetch_related(Prefetch('predictions', queryset=per_lot_date)).get()
        self.assertEqual([p.as_of_date for p in packed.predictions.all()], [today - timedelta(days=12)])

    def test_rebuild_as_of_past_ignores_later_samples(self):
        lot = self.make_lot('26-1', 30)
        self.add_sample(lot, 20, -9.0)
        self.add_sample(lot, 5, -7.0)
        pred = rebuild_for_lot(lot, as_of=date.today() - timedelta(days=10))
        self.assertEqual(len(pred.inputs['points']), 1)

    def test_void_sample_is_excluded_from_forecast(self):
        lot = self.make_lot('26-VOID', 30)
        self.add_sample(lot, 20, -9.0)
        bad = self.add_sample(lot, 10, 8.0)
        bad.is_void = True
        bad.void_reason = 'Wrong lot selected during capture.'
        bad.save()
        pred = rebuild_for_lot(lot)
        self.assertEqual(pred.inputs['points'], [[10, -9.0]])

    def test_feature_snapshot_excludes_future_environment_and_treatments(self):
        today = date.today()
        as_of = today - timedelta(days=10)
        lot = self.make_lot('26-FEATURES', 30, intake_cci_mean=-10.2, intake_cci_std=1.1)
        room = Room.objects.create(plant=self.plant, name='Cold 1')
        lot.current_room = room
        lot.save()
        LotRoomMove.objects.create(lot=lot, room=room, moved_on=lot.receive_date)

        def at(day):
            return timezone.make_aware(datetime.combine(day, time(12, 0)))

        RoomCondition.objects.create(
            room=room, recorded_at=at(as_of - timedelta(days=1)),
            temperature_f=55, relative_humidity_pct=92, source='sensor-a',
        )
        RoomCondition.objects.create(
            room=room, recorded_at=at(as_of + timedelta(days=1)),
            temperature_f=80, relative_humidity_pct=20, source='sensor-a',
        )
        LotTreatment.objects.create(
            lot=lot, applied_at=at(as_of - timedelta(days=2)),
            treatment_type=LotTreatment.TreatmentType.WAX, product='Wax A',
        )
        LotTreatment.objects.create(
            lot=lot, applied_at=at(as_of + timedelta(days=2)),
            treatment_type=LotTreatment.TreatmentType.ETHYLENE, product='Future event',
        )
        self.add_sample(lot, 15, -8.0)
        pred = rebuild_for_lot(lot, as_of=as_of)
        features = pred.inputs['features']
        self.assertEqual(features['environment']['reading_count'], 1)
        self.assertEqual(features['environment']['temperature_f']['mean'], 55.0)
        self.assertEqual([event['type'] for event in features['treatments']], ['wax'])
        self.assertEqual(features['intake_cci_mean'], -10.2)

    def test_cci_distribution_skips_unmeasured_fruit(self):
        lot = self.make_lot('26-NONE', 30)
        sample = self.add_sample(lot, 10, -4.0)
        photo = sample.photos.get()
        photo.per_fruit_cci = [-4.0, None, -3.5, -4.5, None, -4.0, -4.1, -3.9, -4.2, -4.0]
        photo.save(update_fields=['per_fruit_cci'])
        distribution = sample.cci_distribution
        self.assertEqual(distribution['n'], 8)
        self.assertEqual(distribution['median'], -4.0)
        pred = rebuild_for_lot(lot)  # used to raise TypeError
        self.assertEqual(pred.inputs['point_sources'][0]['cci_distribution']['n'], 8)

    def test_environment_features_aggregate_in_the_database(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        today = date.today()
        lot = self.make_lot('26-ENV', 20)
        cold = Room.objects.create(plant=self.plant, name='Cold 1')
        warm = Room.objects.create(plant=self.plant, name='Degreen A')
        LotRoomMove.objects.create(lot=lot, room=cold, moved_on=lot.receive_date)
        LotRoomMove.objects.create(lot=lot, room=warm, moved_on=lot.receive_date + timedelta(days=10))

        def at(day, hour):
            return timezone.make_aware(datetime.combine(day, time(hour, 0)))

        d0 = lot.receive_date
        RoomCondition.objects.create(room=cold, recorded_at=at(d0, 6), temperature_f=54, relative_humidity_pct=90, source='s')
        RoomCondition.objects.create(room=cold, recorded_at=at(d0, 18), temperature_f=56, source='s')
        RoomCondition.objects.create(room=cold, recorded_at=at(d0 + timedelta(days=3), 6), temperature_f=52, ethylene_ppm=0.5, source='s')
        RoomCondition.objects.create(room=warm, recorded_at=at(d0 + timedelta(days=12), 6), temperature_f=70, source='s')
        # readings the lot never saw: cold room after it left, and before receipt
        RoomCondition.objects.create(room=cold, recorded_at=at(d0 + timedelta(days=15), 6), temperature_f=30, source='s')
        RoomCondition.objects.create(room=cold, recorded_at=at(d0 - timedelta(days=1), 6), temperature_f=30, source='s')

        with CaptureQueriesContext(connection) as ctx:
            env = environment_features(lot, today)
        self.assertLessEqual(len(ctx), 5)  # moves, interval aggregates, unique-day coverage and precision
        self.assertEqual(env['reading_count'], 4)
        self.assertEqual(env['observed_days'], 3)
        self.assertEqual(env['exposure_days'], 21)
        self.assertEqual(env['temperature_f'], {'mean': 58.0, 'min': 52.0, 'max': 70.0, 'n': 4})
        self.assertEqual(env['relative_humidity_pct'], {'mean': 90.0, 'min': 90.0, 'max': 90.0, 'n': 1})
        self.assertEqual(env['ethylene_ppm']['n'], 1)
        self.assertIsNone(env['co2_pct'])
        self.assertEqual([row['reading_count'] for row in env['intervals']], [3, 1])

    def test_training_rows_include_distribution_and_future_labels_only_as_targets(self):
        today = date.today()
        lot = self.make_lot('26-TRAIN', 30)
        sample = self.add_sample(lot, 20, -7.0)
        photo = sample.photos.get()
        photo.per_fruit_cci = [-10, -9, -8, -7, -6, -5, -4, -3, -2, -1]
        photo.save(update_fields=['per_fruit_cci'])
        Packout.objects.create(
            lot=lot,
            packed_date=today - timedelta(days=2),
            cartons_fancy=80,
            cartons_products=20,
            packout_color=Color.YELLOW,
            decay_pct=3,
            meets_spec=True,
        )
        row = rows_for_lot(lot)[0]
        self.assertEqual(row['sample_cci_median'], -5.5)
        self.assertEqual(row['sample_cci_p10'], -9.1)
        self.assertEqual(row['sample_cci_p90'], -1.9)
        self.assertEqual(row['days_to_final_packout'], 18)
        self.assertEqual(row['fresh_pct'], 80)

    def test_training_risk_set_stops_after_first_holdout_failure(self):
        lot = self.make_lot('26-HOLDOUT', 30)
        before = self.add_sample(lot, 20, -8.0)
        failure = self.add_sample(lot, 10, -5.0)
        failure.purpose = Sample.Purpose.HOLDOUT
        failure.selection_method = Sample.SelectionMethod.FIXED_HOLDOUT
        failure.marketability = Sample.Marketability.FAIL
        failure.failure_reason = Sample.FailureReason.DECAY
        failure.save()
        self.add_sample(lot, 5, -3.0)

        rows = rows_for_lot(lot)

        self.assertEqual([row['as_of_date'] for row in rows], [
            before.sampled_on.isoformat(), failure.sampled_on.isoformat(),
        ])
        self.assertEqual(rows[0]['days_to_holdout_failure'], 10)
        self.assertEqual(rows[1]['days_to_holdout_failure'], 0)


class ReportTests(Base):
    def test_sections(self):
        today = date.today()
        urgent = self.make_lot('26-URG', 40)
        self.add_sample(urgent, 14, -1.0)
        self.add_sample(urgent, 7, 0.5, decay=0)
        rebuild_for_lot(urgent, as_of=today - timedelta(days=7))
        self.add_sample(urgent, 1, 1.5, decay=1)
        rebuild_for_lot(urgent, as_of=today)

        stale = self.make_lot('26-STALE', 30)
        self.add_sample(stale, 15, -9.0)
        rebuild_for_lot(stale, as_of=today)

        old = self.make_lot('26-OLD', 200)
        rebuild_for_lot(old, as_of=today)

        data = build_report(self.plant, today=today)
        self.assertEqual(data['n_lots'], 3)
        self.assertIn(urgent, [t[1] for t in data['to_pack']])
        self.assertIn(urgent, [t[0] for t in data['new_decay']])
        self.assertIn(stale, [t[1] for t in data['unsampled']])
        self.assertIn(old, data['import_gaps'])
        self.assertNotIn(urgent, [t[1] for t in data['unsampled']])

    def test_moved_up(self):
        today = date.today()
        lot = self.make_lot('26-MOVE', 40)
        self.add_sample(lot, 20, -10.0)
        self.add_sample(lot, 10, -9.5)
        rebuild_for_lot(lot, as_of=today - timedelta(days=7))
        self.add_sample(lot, 1, -4.0)
        rebuild_for_lot(lot, as_of=today)
        data = build_report(self.plant, today=today)
        self.assertEqual([t[1] for t in data['moved_up']], [lot])
        self.assertGreater(data['moved_up'][0][0], 7)

    def test_send_report_emails_recipients(self):
        self.make_lot('26-1', 10)
        n = send_report(self.plant)
        self.assertEqual(n, 2)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(sorted(msg.to), ['foreman@example.com', 'gm@example.com'])
        self.assertIn('SLA1', msg.subject)
        self.assertEqual(msg.alternatives[0][1], 'text/html')
        self.assertIn('/?plant=SLA1', msg.alternatives[0][0])
        delivery = ReportDelivery.objects.get(plant=self.plant)
        self.assertEqual(delivery.status, ReportDelivery.Status.SENT)
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(send_report(self.plant), -1)
        self.assertEqual(len(mail.outbox), 1)

    def test_no_recipients_not_sent(self):
        self.plant.set_recipients([])
        self.assertEqual(send_report(self.plant), 0)
        self.assertEqual(len(mail.outbox), 0)


class AccuracyViewTests(Base):
    def test_readiness_is_scoped_and_explicit_about_missing_evidence(self):
        self.make_lot('VISIBLE-LOT', 5)
        other = Plant.objects.create(code='OTHER', name='Other')
        Lot.objects.create(plant=other, grower=self.grower, lot_no='HIDDEN-LOT', receive_date=timezone.localdate())
        self.client.force_login(self.gm)
        response = self.client.get(reverse('forecast:readiness'), {'plant': self.plant.code})
        self.assertContains(response, 'VISIBLE-LOT')
        self.assertNotContains(response, 'HIDDEN-LOT')
        self.assertContains(response, '0 active setups')
        self.assertContains(response, 'do not certify forecast accuracy')
        self.client.force_login(self.foreman)
        self.assertEqual(self.client.get(reverse('forecast:readiness')).status_code, 403)

    def setUp(self):
        self.gm = User.objects.create_user('gm', password='pw')
        self.gm.groups.add(Group.objects.get_or_create(name='gm')[0])
        UserProfile.objects.create(user=self.gm, plant=None)
        self.foreman = User.objects.create_user('fm', password='pw')
        self.foreman.groups.add(Group.objects.get_or_create(name='foreman')[0])
        UserProfile.objects.create(user=self.foreman, plant=self.plant)

    def test_accuracy_rows_use_last_prediction_before_pack(self):
        today = date.today()
        lot = self.make_lot('26-P', 60)
        self.add_sample(lot, 40, -6.0, weeks=3)
        self.add_sample(lot, 30, -4.0, weeks=2)
        rebuild_for_lot(lot, as_of=today - timedelta(days=30))
        packed = today - timedelta(days=10)
        Packout.objects.create(lot=lot, packed_date=packed, cartons_fancy=500, cartons_choice=200, cartons_standard=100, cartons_products=200)
        lot.status = Lot.Status.PACKED
        lot.packed_date = packed
        lot.save()
        rebuild_for_lot(lot, as_of=today)  # after packing; must be ignored

        self.client.force_login(self.gm)
        resp = self.client.get(reverse('forecast:accuracy'))
        self.assertEqual(resp.status_code, 200)
        row = resp.context['rows'][0]
        self.assertEqual(row['pred'].as_of_date, today - timedelta(days=30))
        # foreman said "2 weeks" 30 days ago -> pack by 16 days ago; packed 10 days ago -> 6 days early
        self.assertEqual(row['foreman_err'], -6)
        self.assertEqual(row['fresh_pct'], 80.0)
        self.assertIsNotNone(resp.context['model_mae'])
        self.assertEqual(resp.context['foreman_mae'], 6.0)

    def test_readiness_counts_lots_in_monitored_rooms(self):
        room = Room.objects.create(plant=self.plant, name='Cold 1')
        exposed = self.make_lot('26-EXP', 30, current_room=room)
        LotRoomMove.objects.create(lot=exposed, room=room, moved_on=exposed.receive_date)
        self.make_lot('26-DRY', 30)
        RoomCondition.objects.create(room=room, recorded_at=timezone.now(), temperature_f=55, source='s')
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('forecast:accuracy'))
        exposure = next(item for item in resp.context['readiness'] if item['label'] == 'Room-condition exposure')
        self.assertEqual((exposure['count'], exposure['total']), (1, 2))

    def test_foreman_cannot_open_accuracy(self):
        self.client.force_login(self.foreman)
        self.assertEqual(self.client.get(reverse('forecast:accuracy')).status_code, 403)

    def test_report_preview(self):
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('forecast:report_preview', args=['SLA1']))
        self.assertContains(resp, 'Pack this week')


class PlanTests(Base):
    """Versioned plans and the accepted / deferred / overridden decision record."""

    def setUp(self):
        self.gm = User.objects.create_user('gm', password='pw')
        self.gm.groups.add(Group.objects.get_or_create(name='gm')[0])
        UserProfile.objects.create(user=self.gm, plant=None)
        self.foreman = User.objects.create_user('fm', password='pw')
        self.foreman.groups.add(Group.objects.get_or_create(name='foreman')[0])
        UserProfile.objects.create(user=self.foreman, plant=self.plant)
        self.today = date.today()
        # urgent: already past yellow -> pack overdue, needs a decision
        self.urgent = self.make_lot('26-URG', 40, bins_received=100)
        self.add_sample(self.urgent, 14, 1.0)
        self.add_sample(self.urgent, 7, 3.0)
        rebuild_for_lot(self.urgent, as_of=self.today)
        # calm: far from yellow -> monitor, no decision needed
        self.calm = self.make_lot('26-CALM', 10)
        self.add_sample(self.calm, 7, -12.6)
        self.add_sample(self.calm, 1, -12.0)
        rebuild_for_lot(self.calm, as_of=self.today)

    def publish(self, **kw):
        return publish_plan(self.plant, today=self.today, **kw)

    def rec(self, plan, lot):
        return plan.recommendations.get(lot=lot)

    def test_publish_freezes_ranked_plan_and_versions_increment(self):
        plan = self.publish(user=self.gm)
        self.assertEqual((plan.version, plan.plant, plan.model_version), (1, self.plant, MODEL_VERSION))
        self.assertEqual(plan.settings_snapshot['buffer_days'], self.settings.buffer_days)
        recs = list(plan.recommendations.all())
        self.assertEqual([r.lot for r in recs], [self.urgent, self.calm])
        self.assertEqual([r.rank for r in recs], [1, 2])
        urgent = recs[0]
        self.assertEqual(urgent.action, PlanAction.PACK_OVERDUE)
        self.assertTrue(urgent.requires_decision)
        self.assertEqual(urgent.prediction, self.urgent.predictions.first())
        self.assertEqual(urgent.pack_by_date, urgent.prediction.pack_by_date)
        self.assertEqual(urgent.bins_remaining, 100)
        self.assertEqual(recs[1].action, PlanAction.MONITOR)
        self.assertFalse(recs[1].requires_decision)
        self.assertEqual(self.publish().version, 2)
        other = Plant.objects.create(code='SLA3', name='Plant 3')
        self.assertEqual(publish_plan(other, today=self.today).version, 1)

    def test_decision_validation_rules(self):
        plan = self.publish()
        rec = self.rec(plan, self.urgent)
        with self.assertRaises(ValidationError) as ctx:
            PlanDecision.objects.create(recommendation=rec, status=PlanDecision.Status.DEFERRED)
        self.assertIn('reason', ctx.exception.message_dict)
        self.assertIn('planned_pack_date', ctx.exception.message_dict)
        with self.assertRaises(ValidationError) as ctx:
            PlanDecision.objects.create(recommendation=rec, status=PlanDecision.Status.OVERRIDDEN, reason=PlanDecision.Reason.OTHER)
        self.assertIn('notes', ctx.exception.message_dict)
        with self.assertRaises(ValidationError) as ctx:
            PlanDecision.objects.create(
                recommendation=rec, status=PlanDecision.Status.ACCEPTED,
                planned_pack_date=rec.pack_by_date + timedelta(days=3),
            )
        self.assertIn('planned_pack_date', ctx.exception.message_dict)
        ok = PlanDecision.objects.create(recommendation=rec, status=PlanDecision.Status.ACCEPTED, decided_by=self.gm)
        self.assertFalse(ok.after_lock)
        self.assertTrue(ok.reason_complete)

    def test_coverage_and_scorecard(self):
        plan = self.publish()
        rec = self.rec(plan, self.urgent)
        self.assertEqual(coverage(plan)['actionable'], 1)
        self.assertEqual(coverage(plan)['decided'], 0)
        PlanDecision.objects.create(
            recommendation=rec, status=PlanDecision.Status.DEFERRED,
            reason=PlanDecision.Reason.CUSTOMER_ORDER, planned_pack_date=self.today + timedelta(days=10),
        )
        plan = plans_for(self.plant).get(pk=plan.pk)
        cov = coverage(plan)
        self.assertEqual((cov['decided'], cov['decided_pct'], cov['reasons_needed'], cov['reasons_complete']), (1, 100, 1, 1))
        self.assertEqual(cov['by_status']['deferred'], 1)
        self.assertIsNone(cov['before_lock_pct'])  # not locked
        card = scorecard(list(plans_for(self.plant)))
        self.assertEqual((card['plans'], card['decided_pct'], card['reasons_pct']), (1, 100, 100))
        self.assertIsNone(card['before_lock_pct'])

    def test_latest_decision_wins_and_history_is_kept(self):
        plan = self.publish()
        rec = self.rec(plan, self.urgent)
        first = PlanDecision.objects.create(recommendation=rec, status=PlanDecision.Status.ACCEPTED, decided_at=timezone.now() - timedelta(hours=1))
        second = PlanDecision.objects.create(
            recommendation=rec, status=PlanDecision.Status.OVERRIDDEN, reason=PlanDecision.Reason.CAPACITY,
        )
        rec = PlanRecommendation.objects.prefetch_related('decisions').get(pk=rec.pk)
        self.assertEqual(rec.latest_decision, second)
        self.assertEqual(list(rec.decisions.all()), [second, first])

    def test_lock_flags_late_decisions(self):
        plan = self.publish()
        rec = self.rec(plan, self.urgent)
        self.client.force_login(self.gm)
        resp = self.client.post(reverse('forecast:plan_lock', args=[plan.pk]))
        self.assertRedirects(resp, plan.get_absolute_url())
        plan.refresh_from_db()
        self.assertTrue(plan.is_locked)
        self.assertEqual(plan.locked_by, self.gm)
        late = PlanDecision.objects.create(recommendation=rec, status=PlanDecision.Status.ACCEPTED)
        self.assertTrue(late.after_lock)
        plan = plans_for(self.plant).get(pk=plan.pk)
        self.assertEqual(coverage(plan)['before_lock_pct'], 0)

    def test_gm_records_decision_through_the_screen(self):
        plan = self.publish()
        rec = self.rec(plan, self.urgent)
        self.client.force_login(self.gm)
        url = reverse('forecast:plan_decide', args=[plan.pk, rec.pk])
        prefix = f'rec{rec.pk}-'
        # missing reason for a deferral -> re-rendered with errors
        resp = self.client.post(url, {prefix + 'status': 'deferred', prefix + 'planned_pack_date': ''})
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, 'structured reason is required', status_code=400)
        self.assertEqual(rec.decisions.count(), 0)
        when = (self.today + timedelta(days=9)).isoformat()
        resp = self.client.post(url, {
            prefix + 'status': 'deferred',
            prefix + 'reason': 'customer_order',
            prefix + 'planned_pack_date': when,
            prefix + 'notes': 'Waiting on the Tuesday order.',
        })
        self.assertRedirects(resp, f'{plan.get_absolute_url()}#rec-{rec.pk}', fetch_redirect_response=False)
        decision = rec.decisions.get()
        self.assertEqual((decision.status, decision.reason, decision.decided_by), ('deferred', 'customer_order', self.gm))
        self.assertEqual(decision.planned_pack_date.isoformat(), when)
        detail = self.client.get(plan.get_absolute_url())
        self.assertContains(detail, 'Customer order or ship date')
        self.assertContains(detail, 'Waiting on the Tuesday order.')

    def test_foreman_can_view_but_not_decide_publish_or_lock(self):
        plan = self.publish()
        rec = self.rec(plan, self.urgent)
        self.client.force_login(self.foreman)
        self.assertEqual(self.client.get(reverse('forecast:plan_list')).status_code, 200)
        detail = self.client.get(plan.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, 'Save decision')
        decide = reverse('forecast:plan_decide', args=[plan.pk, rec.pk])
        self.assertEqual(self.client.post(decide, {f'rec{rec.pk}-status': 'accepted'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('forecast:plan_publish', args=['SLA1'])).status_code, 403)
        self.assertEqual(self.client.post(reverse('forecast:plan_lock', args=[plan.pk])).status_code, 403)

    def test_pinned_user_cannot_see_another_plants_plan(self):
        other = Plant.objects.create(code='SLA3', name='Plant 3')
        plan = publish_plan(other, today=self.today)
        self.client.force_login(self.foreman)
        self.assertEqual(self.client.get(plan.get_absolute_url()).status_code, 404)
        pinned_gm = User.objects.create_user('gm3', password='pw')
        pinned_gm.groups.add(Group.objects.get_or_create(name='gm')[0])
        UserProfile.objects.create(user=pinned_gm, plant=other)
        self.client.force_login(pinned_gm)
        self.assertEqual(self.client.post(reverse('forecast:plan_publish', args=['SLA1'])).status_code, 404)
        self.assertEqual(self.client.get(plan.get_absolute_url()).status_code, 200)

    def test_publish_from_board_and_board_shows_decisions(self):
        self.client.force_login(self.gm)
        board = self.client.get(reverse('lots:board') + '?plant=SLA1')
        self.assertContains(board, 'No plan published yet')
        resp = self.client.post(reverse('forecast:plan_publish', args=['SLA1']))
        plan = PackPlan.objects.get()
        self.assertRedirects(resp, plan.get_absolute_url())
        self.assertEqual((plan.source, plan.published_by), (PackPlan.Source.BOARD, self.gm))
        board = self.client.get(reverse('lots:board') + '?plant=SLA1')
        self.assertContains(board, 'Plan v1')
        self.assertEqual(board.context['plan_undecided'], 1)
        PlanDecision.objects.create(recommendation=self.rec(plan, self.urgent), status=PlanDecision.Status.ACCEPTED)
        board = self.client.get(reverse('lots:board') + '?plant=SLA1')
        self.assertEqual(board.context['plan_undecided'], 0)
        self.assertContains(board, 'Accepted')

    def test_lot_detail_lists_decision_history(self):
        plan = self.publish()
        PlanDecision.objects.create(
            recommendation=self.rec(plan, self.urgent), status=PlanDecision.Status.OVERRIDDEN,
            reason=PlanDecision.Reason.QUALITY_DISAGREE, notes='Foreman says still silver.',
        )
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:lot_detail', args=[self.urgent.pk]))
        self.assertContains(resp, 'Foreman says still silver.')
        self.assertContains(resp, 'Overridden')

    def test_outcome_links_recommendation_to_actual_pack(self):
        plan = self.publish()
        rec = self.rec(plan, self.urgent)
        self.assertEqual(rec.outcome(self.today)['status'], 'in_storage')
        packed = self.today + timedelta(days=2)
        self.urgent.status = Lot.Status.PACKED
        self.urgent.packed_date = packed
        self.urgent.save()
        rec = PlanRecommendation.objects.get(pk=rec.pk)
        out = rec.outcome(packed)
        self.assertEqual(out['status'], 'packed')
        self.assertEqual(out['days_after_pack_by'], (packed - rec.pack_by_date).days)

    def test_monday_report_publishes_plan_and_links_to_it(self):
        n = send_report(self.plant, today=self.today)
        self.assertEqual(n, 2)
        plan = PackPlan.objects.get()
        self.assertEqual(plan.source, PackPlan.Source.REPORT)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn(plan.get_absolute_url(), html)
        self.assertIn('Plan v1', html)
        self.assertIn('Plan v1', mail.outbox[0].body)
        # a duplicate send neither emails again nor publishes another version
        self.assertEqual(send_report(self.plant, today=self.today), -1)
        self.assertEqual(PackPlan.objects.count(), 1)

    def test_publish_plan_command(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('publish_plan', plant='sla1', stdout=out)
        self.assertIn('plan v1 published', out.getvalue())
        self.assertEqual(PackPlan.objects.get().source, PackPlan.Source.COMMAND)


class TemperatureResponseTests(TestCase):
    def test_prior_is_scaled_by_room_setpoint_but_fitted_slope_is_not(self):
        from .model import prior_at_temperature, temperature_rate_factor, PRIOR_REFERENCE_C
        s = ModelSettings.get()
        self.assertAlmostEqual(temperature_rate_factor(15.0), 1.0)
        self.assertLess(temperature_rate_factor(5.0), 0.2)
        self.assertLess(temperature_rate_factor(25.0), 0.2)
        self.assertAlmostEqual(prior_at_temperature(0.1, PRIOR_REFERENCE_C), 0.1)
        base = predict(as_of=TODAY, receive_date=TODAY - timedelta(days=10), receiving_color='DG', points=[], decay_samples=[], settings=s)
        warm = predict(as_of=TODAY, receive_date=TODAY - timedelta(days=10), receiving_color='DG', points=[], decay_samples=[], settings=s, room_temp_c=15.0)
        cold = predict(as_of=TODAY, receive_date=TODAY - timedelta(days=10), receiving_color='DG', points=[], decay_samples=[], settings=s, room_temp_c=5.0)
        self.assertGreater(warm['drift_per_day'], base['drift_per_day'])
        self.assertLess(cold['drift_per_day'], base['drift_per_day'])
        self.assertEqual(warm['inputs']['room_temp_c'], 15.0)
        self.assertEqual(base['inputs']['temperature_factor'], None)
        fitted = predict(as_of=TODAY, receive_date=TODAY - timedelta(days=30), receiving_color='DG',
            points=[(10, -9.0), (30, -5.0)], decay_samples=[], settings=s, room_temp_c=5.0)
        self.assertAlmostEqual(fitted['drift_per_day'], 0.2)
        s.temperature_response = False
        off = predict(as_of=TODAY, receive_date=TODAY - timedelta(days=10), receiving_color='DG', points=[], decay_samples=[], settings=s, room_temp_c=15.0)
        self.assertEqual(off['drift_per_day'], base['drift_per_day'])


class QuickDecisionTests(Base):
    def setUp(self):
        self.gm = User.objects.create_user('gm2', password='pw')
        self.gm.groups.add(Group.objects.get_or_create(name='gm')[0])
        UserProfile.objects.create(user=self.gm, plant=None)
        today = timezone.localdate()
        self.lot = Lot.objects.create(lot_no='26-2001', plant=self.plant, grower=self.grower, receive_date=today - timedelta(days=60), bins_received=100)
        self.lot2 = Lot.objects.create(lot_no='26-2002', plant=self.plant, grower=self.grower, receive_date=today - timedelta(days=60), bins_received=100)
        for lot in (self.lot, self.lot2):
            Prediction.objects.create(lot=lot, as_of_date=today, cci_now=3.0, stage=Color.YELLOW, drift_per_day=.2,
                predicted_yellow_date=today, pack_by_date=today - timedelta(days=2),
                confidence='high', model_version=MODEL_VERSION,
                inputs={'points': [[50, 1.0], [58, 3.0]], 'receive_date': lot.receive_date.isoformat()})
            # a fresh routine sample, otherwise the board asks for a sample before a pack decision
            Sample.objects.create(lot=lot, foreman_color=Color.YELLOW, foreman_pack_within_weeks=1)
        self.client.force_login(self.gm)

    def test_publish_records_market_regime_and_copies_it_onto_decisions(self):
        resp = self.client.post(reverse('forecast:plan_publish', args=[self.plant.code]), {'market_regime': 'oversupplied'})
        plan = PackPlan.objects.get()
        self.assertEqual(plan.market_regime, 'oversupplied')
        rec = plan.recommendations.filter(requires_decision=True).first()
        self.assertIsNotNone(rec)
        resp = self.client.post(reverse('forecast:plan_decide', args=[plan.pk, rec.pk]), {f'rec{rec.pk}-status': 'accepted'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('data-decision-for', resp.content.decode())
        self.assertIn('Accepted', resp.content.decode())
        self.assertEqual(rec.decisions.get().market_regime, 'oversupplied')
        self.assertIn('"undecided": 1', resp['X-Plan-Coverage'])
        # a second publish without a regime inherits the previous one
        self.client.post(reverse('forecast:plan_publish', args=[self.plant.code]), {})
        self.assertEqual(PackPlan.objects.order_by('-version').first().market_regime, 'oversupplied')

    def test_in_place_validation_error_returns_the_cell_with_errors(self):
        self.client.post(reverse('forecast:plan_publish', args=[self.plant.code]), {'market_regime': 'tight'})
        plan = PackPlan.objects.get()
        rec = plan.recommendations.filter(requires_decision=True).first()
        resp = self.client.post(reverse('forecast:plan_decide', args=[plan.pk, rec.pk]), {f'rec{rec.pk}-status': 'deferred'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('errorlist', resp.content.decode())
        self.assertFalse(rec.decisions.exists())

    def test_accept_all_remaining_records_one_decision_per_recommendation(self):
        self.client.post(reverse('forecast:plan_publish', args=[self.plant.code]), {})
        plan = PackPlan.objects.get()
        actionable = list(plan.recommendations.filter(requires_decision=True))
        self.assertGreaterEqual(len(actionable), 2)
        first = actionable[0]
        PlanDecision.objects.create(recommendation=first, status='deferred', reason='capacity', planned_pack_date=timezone.localdate() + timedelta(days=3), decided_by=self.gm)
        resp = self.client.post(reverse('forecast:plan_accept_remaining', args=[plan.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(first.decisions.count(), 1)  # untouched
        for rec in actionable[1:]:
            self.assertEqual(rec.latest_decision.status, 'accepted')
            self.assertEqual(rec.latest_decision.decided_by, self.gm)
        self.assertEqual(coverage(plans_for(self.plant).get(pk=plan.pk))['undecided'], 0)

    def test_market_regime_can_change_until_lock(self):
        self.client.post(reverse('forecast:plan_publish', args=[self.plant.code]), {})
        plan = PackPlan.objects.get()
        self.client.post(reverse('forecast:plan_market', args=[plan.pk]), {'market_regime': 'tight'})
        plan.refresh_from_db()
        self.assertEqual(plan.market_regime, 'tight')
        self.client.post(reverse('forecast:plan_lock', args=[plan.pk]))
        self.client.post(reverse('forecast:plan_market', args=[plan.pk]), {'market_regime': 'normal'})
        plan.refresh_from_db()
        self.assertEqual(plan.market_regime, 'tight')

    def test_readiness_reports_capture_time_and_room_setpoints(self):
        Sample.objects.create(lot=self.lot, foreman_color='S', foreman_pack_within_weeks=2, capture_seconds=80)
        Sample.objects.create(lot=self.lot2, foreman_color='S', foreman_pack_within_weeks=2, capture_seconds=100)
        Room.objects.create(plant=self.plant, name='Cold 9', target_temp_f=50)
        Room.objects.create(plant=self.plant, name='Cold 10')
        resp = self.client.get(reverse('forecast:readiness'), {'plant': self.plant.code})
        self.assertContains(resp, '90 s median · 2 samples in 30 days · target 90 s')
        self.assertContains(resp, '1 / 2 rooms')
