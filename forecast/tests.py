from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from lots.models import (
    Color, Grower, Lot, LotRoomMove, LotTreatment, ModelSettings, Packout,
    Plant, Room, RoomCondition, UserProfile,
)
from sampling.models import Sample, SamplePhoto

from .features import environment_features
from .model import MODEL_VERSION, decay_summary, ols, predict
from .models import Prediction, ReportDelivery
from .report import build_report, send_report
from .services import rebuild_for_lot
from .training import rows_for_lot

TODAY = date(2026, 10, 5)


class ModelTests(TestCase):
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
        r = self.go([(10, -9.0), (20, -7.0)], receive_days_ago=30)
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
        self.assertEqual(r['predicted_yellow_date'], TODAY)
        self.assertEqual(r['stage'], Color.YELLOW)
        self.assertIn('already at or past yellow threshold', r['inputs']['notes'])

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


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.plant = Plant.objects.create(code='SLA1', name='Plant 1', report_recipients='gm@example.com, foreman@example.com')
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
    def test_rebuild_writes_and_upserts(self):
        lot = self.make_lot('26-1', 30)
        self.add_sample(lot, 20, -9.0)
        self.add_sample(lot, 10, -7.0)
        pred = rebuild_for_lot(lot)
        self.assertEqual(pred.inputs['points'], [[10, -9.0], [20, -7.0]])
        self.assertEqual(pred.confidence, 'med')
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
        LotRoomMove.objects.create(lot=lot, room=room, moved_at=lot.receive_date)

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
        LotRoomMove.objects.create(lot=lot, room=cold, moved_at=lot.receive_date)
        LotRoomMove.objects.create(lot=lot, room=warm, moved_at=lot.receive_date + timedelta(days=10))

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
        self.assertLessEqual(len(ctx), 3)  # moves + one aggregate per interval
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
        self.plant.report_recipients = ''
        self.plant.save()
        self.assertEqual(send_report(self.plant), 0)
        self.assertEqual(len(mail.outbox), 0)


class AccuracyViewTests(Base):
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
        LotRoomMove.objects.create(lot=exposed, room=room, moved_at=exposed.receive_date)
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
