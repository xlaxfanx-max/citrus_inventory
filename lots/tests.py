import io
import time
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .importers import conditions, packout, receiving, room_moves, run_import, treatments
from .importers.base import read_csv
from .models import (
    Color, Grower, ImportBatch, Lot, LotRoomMove, LotTreatment, ModelSettings,
    Packout, Plant, Room, RoomCondition, UserProfile,
)


def csv_rows(text):
    return read_csv(io.BytesIO(text.strip().encode('utf-8')))


def make_user(username, group=None, plant=None, staff=False):
    user = User.objects.create_user(username, password='pw', is_staff=staff)
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    UserProfile.objects.create(user=user, plant=plant)
    return user


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sla1 = Plant.objects.create(code='SLA1', name='Plant 1')
        cls.sla3 = Plant.objects.create(code='SLA3', name='Plant 3')
        cls.settings = ModelSettings.get()

    def make_lot(self, lot_no='26-1001', plant=None, **kw):
        grower = kw.pop('grower', None) or Grower.objects.get_or_create(sunkist_grower_no='10417', defaults={'name': 'Sespe'})[0]
        defaults = {'receive_date': date.today() - timedelta(days=20), 'receiving_color': Color.DARK_GREEN}
        defaults.update(kw)
        return Lot.objects.create(lot_no=lot_no, plant=plant or self.sla1, grower=grower, **defaults)


RECEIVING = """
plant_code,lot_no,grower_no,grower_name,block,variety,receive_date,receiving_color,bins_received,room
SLA1,26-1001,10417,Sespe Creek Ranch,B17,Lisbon,2026-08-11,DG,120,Cold 1
SLA1,26-1002,10422,Las Posas Growers,N4,Eureka,8/13/2026,LG,85,Cold 2
SLA3,26-1001,10417,Sespe Creek Ranch,B12,Lisbon,2026-08-12,S,60,Cold 1
"""


class ReceivingImportTests(Base):
    def test_creates_plants_growers_rooms_lots_and_moves(self):
        ok, errors = receiving.run(csv_rows(RECEIVING))
        self.assertEqual((ok, errors), (3, []))
        self.assertEqual(Lot.objects.count(), 3)
        self.assertEqual(Grower.objects.count(), 2)
        lot = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        self.assertEqual(lot.grower.name, 'Sespe Creek Ranch')
        self.assertEqual(lot.receive_date, date(2026, 8, 11))
        self.assertEqual(lot.receiving_color, Color.DARK_GREEN)
        self.assertEqual(lot.current_room.name, 'Cold 1')
        self.assertEqual(lot.current_room.plant, self.sla1)
        self.assertEqual(lot.room_moves.count(), 1)
        # same lot number at another plant is a different lot
        other = Lot.objects.get(plant=self.sla3, lot_no='26-1001')
        self.assertEqual(other.receiving_color, Color.SILVER)
        # US date format accepted, variety mapped
        self.assertEqual(Lot.objects.get(lot_no='26-1002').variety, Lot.Variety.EUREKA)

    def test_imports_prediction_intake_fields_when_present(self):
        rows = csv_rows(
            'plant_code,lot_no,grower_no,grower_name,block,variety,receive_date,'
            'receiving_color,bins_received,room,harvest_date,intake_cci_mean,intake_cci_std\n'
            'SLA1,26-V2,10417,Sespe,B17,Lisbon,2026-08-11,DG,120,Cold 1,'
            '2026-08-09,-10.4,1.25'
        )
        ok, errors = receiving.run(rows)
        self.assertEqual((ok, errors), (1, []))
        lot = Lot.objects.get(lot_no='26-V2')
        self.assertEqual(lot.harvest_date, date(2026, 8, 9))
        self.assertEqual(lot.intake_cci_mean, -10.4)
        self.assertEqual(lot.intake_cci_std, 1.25)

    def test_reimport_is_idempotent_and_updates(self):
        receiving.run(csv_rows(RECEIVING))
        ok, errors = receiving.run(csv_rows(RECEIVING))
        self.assertEqual((ok, errors), (3, []))
        self.assertEqual(Lot.objects.count(), 3)
        self.assertEqual(LotRoomMove.objects.count(), 3)  # no extra moves
        updated = RECEIVING.replace('B17,Lisbon,2026-08-11,DG,120,Cold 1', 'B17,Lisbon,2026-08-11,DG,125,Cold 1')
        receiving.run(csv_rows(updated))
        lot = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        self.assertEqual(lot.bins_received, 125)
        self.assertEqual(lot.current_room.name, 'Cold 1')
        self.assertEqual(lot.room_moves.count(), 1)

    def test_reimport_returning_to_earlier_room_does_not_abort(self):
        header = 'plant_code,lot_no,grower_no,grower_name,block,variety,receive_date,receiving_color,bins_received,room\n'
        for room in ('Cold 1', 'Cold 2', 'Cold 1'):
            ok, errors = receiving.run(csv_rows(header + f'SLA1,26-1001,10417,Sespe,,Lisbon,2026-08-11,DG,120,{room}'))
            if room == 'Cold 2':
                self.assertEqual(ok, 0)
                self.assertIn('actual room move', errors[0]['error'])
            else:
                self.assertEqual((ok, errors), (1, []), room)
        lot = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        self.assertEqual(lot.current_room.name, 'Cold 1')
        self.assertEqual(lot.room_moves.count(), 1)

    def test_packed_lot_is_not_reopened(self):
        receiving.run(csv_rows(RECEIVING))
        lot = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        lot.status = Lot.Status.PACKED
        lot.packed_date = date(2026, 9, 1)
        lot.save()
        receiving.run(csv_rows(RECEIVING))
        lot.refresh_from_db()
        self.assertEqual(lot.status, Lot.Status.PACKED)

    def test_row_errors_are_reported_not_fatal(self):
        bad = RECEIVING + "\nSLA9,26-2000,10417,,,,2026-08-11,DG,1,\nSLA1,26-2001,10417,,,,not-a-date,DG,1,\nSLA1,26-2002,,,,,2026-08-11,DG,1,\nSLA1,26-1001,10417,,,,2026-08-11,DG,1,\nSLA1,26-2003,10417,,,,2026-08-11,purple,1,"
        ok, errors = receiving.run(csv_rows(bad))
        self.assertEqual(ok, 3)
        messages = [e['error'] for e in errors]
        self.assertEqual(len(errors), 5)
        self.assertTrue(any('unknown plant_code' in m for m in messages))
        self.assertTrue(any('unrecognized date' in m for m in messages))
        self.assertTrue(any('missing grower_no' in m for m in messages))
        self.assertTrue(any('duplicate of row' in m for m in messages))
        self.assertTrue(any('expected DG, LG, S or Y' in m for m in messages))
        self.assertEqual(sorted(e['row'] for e in errors), [5, 6, 7, 8, 9])

    def test_two_thousand_rows_under_sixty_seconds(self):
        lines = ['plant_code,lot_no,grower_no,grower_name,block,variety,receive_date,receiving_color,bins_received,room']
        for i in range(2000):
            plant = 'SLA1' if i % 2 else 'SLA3'
            lines.append(f'{plant},26-{5000 + i},{10400 + i % 40},Grower {i % 40},B{i % 9},Lisbon,2026-08-{1 + i % 28:02d},DG,{50 + i % 100},Cold {1 + i % 4}')
        text = '\n'.join(lines)
        start = time.perf_counter()
        ok, errors = receiving.run(csv_rows(text))
        elapsed = time.perf_counter() - start
        self.assertEqual((ok, errors), (2000, []))
        self.assertLess(elapsed, 60)
        # and the re-import that updates every row
        start = time.perf_counter()
        ok, errors = receiving.run(csv_rows(text.replace(',Lisbon,', ',Eureka,')))
        self.assertLess(time.perf_counter() - start, 60)
        self.assertEqual(ok, 2000)

    def test_receipt_basis_is_locked_after_sampling(self):
        from sampling.models import Sample

        receiving.run(csv_rows(RECEIVING))
        lot = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        Sample.objects.create(lot=lot, foreman_color='LG', foreman_pack_within_weeks=3)
        changed = RECEIVING.replace('2026-08-11,DG', '2026-08-01,S')
        ok, errors = receiving.run(csv_rows(changed))
        lot.refresh_from_db()
        self.assertEqual(ok, 2)
        self.assertEqual(len(errors), 1)
        self.assertIn('locked', errors[0]['error'])
        self.assertEqual(lot.receive_date, date(2026, 8, 11))
        self.assertEqual(lot.receiving_color, Color.DARK_GREEN)


class PackoutImportTests(Base):
    def test_packout_sets_status_and_fresh_pct(self):
        self.make_lot('26-1001', receive_date=date(2026, 8, 1))
        rows = csv_rows("plant_code,lot_no,packed_date,cartons_fancy,cartons_choice,cartons_standard,cartons_products\nSLA1,26-1001,2026-09-10,300,150,50,100")
        ok, errors = packout.run(rows)
        self.assertEqual((ok, errors), (1, []))
        lot = Lot.objects.get(lot_no='26-1001')
        self.assertEqual(lot.status, Lot.Status.PACKED)
        self.assertEqual(lot.packed_date, date(2026, 9, 10))
        po = lot.packouts.get()
        self.assertEqual(po.cartons_total, 600)
        self.assertEqual(float(po.fresh_pct), 83.33)
        # rerun updates in place
        packout.run(csv_rows("plant_code,lot_no,packed_date,cartons_fancy,cartons_choice,cartons_standard,cartons_products\nSLA1,26-1001,2026-09-10,310,150,50,100"))
        self.assertEqual(lot.packouts.count(), 1)
        self.assertEqual(lot.packouts.get().cartons_fancy, 310)

    def test_unknown_lot_and_bad_rows(self):
        self.make_lot('26-1001', receive_date=date(2026, 8, 1))
        rows = csv_rows("plant_code,lot_no,packed_date,cartons_fancy,cartons_choice,cartons_standard,cartons_products\nSLA1,26-9999,2026-09-10,1,0,0,0\nSLA1,26-1001,2026-07-01,1,0,0,0\nSLA1,26-1001,2026-09-10,0,0,0,0")
        ok, errors = packout.run(rows)
        self.assertEqual(ok, 0)
        self.assertEqual(len(errors), 3)
        self.assertIn('unknown lot', errors[0]['error'])
        self.assertIn('before receive_date', errors[1]['error'])
        self.assertIn('zero', errors[2]['error'])

    def test_partial_packout_keeps_inventory_open_and_records_outcome(self):
        lot = self.make_lot('26-1001', receive_date=date(2026, 8, 1), bins_received=120)
        header = ','.join(packout.COLUMNS)
        partial = header + '\nSLA1,26-1001,2026-08-20,100,50,0,10,40,no,S,3.5,color and decay'
        ok, errors = packout.run(csv_rows(partial))
        self.assertEqual((ok, errors), (1, []))
        lot.refresh_from_db()
        self.assertEqual(lot.status, Lot.Status.IN_STORAGE)
        self.assertEqual(float(lot.bins_remaining), 80.0)
        po = lot.packouts.get()
        self.assertFalse(po.is_final)
        self.assertEqual(po.packout_color, Color.SILVER)
        self.assertEqual(float(po.decay_pct), 3.5)

        final = header + '\nSLA1,26-1001,2026-08-27,150,50,0,10,80,yes,Y,5.0,late color'
        packout.run(csv_rows(final))
        lot.refresh_from_db()
        self.assertEqual(lot.status, Lot.Status.PACKED)
        self.assertEqual(lot.packed_date, date(2026, 8, 27))
        self.assertEqual(float(lot.bins_remaining), 0.0)

        extra = header + '\nSLA1,26-1001,2026-08-28,1,0,0,0,1,yes,Y,5.0,duplicate quantity'
        ok, errors = packout.run(csv_rows(extra))
        self.assertEqual(ok, 0)
        self.assertIn('exceed', errors[0]['error'])


class RoomMovesImportTests(Base):
    def test_timestamped_round_trip_in_one_day_is_idempotent(self):
        receiving.run(csv_rows(RECEIVING))
        rows = csv_rows('plant_code,lot_no,room,moved_at\nSLA1,26-1001,Cold 1,2026-08-20T18:00:00-07:00\nSLA1,26-1001,Cold 2,2026-08-20 12:00\nSLA1,26-1001,Cold 1,2026-08-20 08:00')
        self.assertEqual(room_moves.run(rows), (3, []))
        self.assertEqual(room_moves.run(rows), (3, []))
        lot = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        self.assertEqual(lot.current_room.name, 'Cold 1')
        self.assertEqual(lot.room_moves.filter(occurred_at__isnull=False).count(), 3)

    def test_moves_update_current_room(self):
        lot = self.make_lot('26-1001', receive_date=date(2026, 8, 10))
        rows = csv_rows("plant_code,lot_no,room,moved_at\nSLA1,26-1001,Cold 2,2026-08-20\nSLA1,26-1001,Cold 1,2026-08-15")
        ok, errors = room_moves.run(rows)
        self.assertEqual((ok, errors), (2, []))
        lot.refresh_from_db()
        self.assertEqual(lot.current_room.name, 'Cold 2')
        self.assertEqual(Room.objects.filter(plant=self.sla1).count(), 2)
        room_moves.run(rows)
        self.assertEqual(lot.room_moves.count(), 2)


class PredictionDataImportTests(Base):
    def setUp(self):
        self.room = Room.objects.create(plant=self.sla1, name='Cold 1')
        self.lot = self.make_lot(
            '26-V2', receive_date=date(2026, 8, 1), current_room=self.room
        )
        LotRoomMove.objects.create(lot=self.lot, room=self.room, moved_at=date(2026, 8, 1))

    def test_room_conditions_are_idempotent_and_update_values(self):
        header = ','.join(conditions.COLUMNS)
        first = header + '\nSLA1,Cold 1,2026-08-10 08:00,55.2,92.0,0.1,0.2,sensor-a'
        self.assertEqual(conditions.run(csv_rows(first)), (1, []))
        second = header + '\nSLA1,Cold 1,2026-08-10 08:00,56.1,91.0,0.2,0.3,sensor-a'
        self.assertEqual(conditions.run(csv_rows(second)), (1, []))
        self.assertEqual(RoomCondition.objects.count(), 1)
        reading = RoomCondition.objects.get()
        self.assertEqual(float(reading.temperature_f), 56.1)
        self.assertEqual(float(reading.relative_humidity_pct), 91.0)

    def test_room_conditions_import_in_bulk_and_report_bad_rows(self):
        header = ','.join(conditions.COLUMNS)
        base = datetime(2026, 8, 10, 0, 0)
        lines = [header]
        for i in range(2000):  # about three weeks at a 15-minute cadence
            stamp = (base + timedelta(minutes=15 * i)).strftime('%Y-%m-%d %H:%M')
            lines.append(f'SLA1,Cold 1,{stamp},{54 + (i % 4) * 0.5},90,,,logger-1')
        lines.append('SLA1,Cold 1,2026-09-10 00:00,55,150,,,logger-1')  # humidity out of range
        lines.append('SLA1,Cold 1,2026-08-10 00:00,99,90,,,logger-1')   # duplicate of row 2
        with CaptureQueriesContext(connection) as ctx:
            ok, errors = conditions.run(csv_rows('\n'.join(lines)))
        self.assertEqual(ok, 2000)
        self.assertEqual([e['row'] for e in errors], [2002, 2003])
        self.assertIn('100', errors[0]['error'])
        self.assertIn('duplicate', errors[1]['error'])
        self.assertEqual(RoomCondition.objects.count(), 2000)
        self.assertLess(len(ctx), 15, 'readings must be written in bulk, not one query per row')
        # first row kept the first value, not the duplicate's
        first = RoomCondition.objects.order_by('recorded_at').first()
        self.assertEqual(float(first.temperature_f), 54.0)

    def test_treatments_are_idempotent_and_validate_lot_timing(self):
        header = ','.join(treatments.COLUMNS)
        valid = header + '\nSLA1,26-V2,2026-08-05 09:30,ethylene,,5,ppm,48,Degreening cycle'
        self.assertEqual(treatments.run(csv_rows(valid)), (1, []))
        self.assertEqual(treatments.run(csv_rows(valid)), (1, []))
        self.assertEqual(LotTreatment.objects.count(), 1)
        event = LotTreatment.objects.get()
        self.assertEqual(float(event.concentration), 5.0)
        self.assertEqual(float(event.duration_hours), 48.0)

        early = header + '\nSLA1,26-V2,2026-07-31 09:30,wax,Brand X,1,percent,,Too early'
        ok, errors = treatments.run(csv_rows(early))
        self.assertEqual(ok, 0)
        self.assertIn('precede receipt', errors[0]['error'])

    def test_packout_imports_direct_quality_labels(self):
        rows = csv_rows(
            'plant_code,lot_no,packed_date,cartons_fancy,cartons_choice,'
            'cartons_standard,cartons_products,soft_pct,shrivel_pct,'
            'chilling_injury_pct,meets_spec\n'
            'SLA1,26-V2,2026-08-20,100,20,10,5,2.5,1.0,0.5,yes'
        )
        self.assertEqual(packout.run(rows), (1, []))
        result = Packout.objects.get()
        self.assertEqual(float(result.soft_pct), 2.5)
        self.assertEqual(float(result.shrivel_pct), 1.0)
        self.assertEqual(float(result.chilling_injury_pct), 0.5)
        self.assertTrue(result.meets_spec)


class RunImportTests(Base):
    def test_integer_imports_reject_fractional_and_nonfinite_values(self):
        from .importers.base import parse_int, RowError
        for value in ('1.5', 'NaN', 'Infinity', '-3'):
            with self.subTest(value=value), self.assertRaises(RowError):
                parse_int(value, 'bins_received')
        self.assertEqual(parse_int('1,200.0', 'bins_received'), 1200)

    def test_run_import_records_batch(self):
        user = make_user('gm', 'gm')
        batch = run_import(ImportBatch.Kind.RECEIVING, io.BytesIO(RECEIVING.strip().encode()), user=user, original_name='rcv.csv')
        self.assertEqual(batch.rows_ok, 3)
        self.assertEqual(batch.rows_failed, 0)
        self.assertEqual(batch.uploaded_by, user)
        self.assertTrue(batch.file.name)

    def test_unreadable_file_is_a_failed_batch(self):
        batch = run_import(ImportBatch.Kind.RECEIVING, io.BytesIO(b'\xff\xfe garbage'), original_name='x.csv')
        self.assertEqual(batch.rows_ok, 0)
        self.assertEqual(batch.rows_failed, 1)

    def test_wrong_header_is_a_failed_batch(self):
        batch = run_import(
            ImportBatch.Kind.PACKOUT,
            io.BytesIO(b'wrong,columns\n1,2\n'),
            original_name='wrong.csv',
        )
        self.assertEqual((batch.rows_ok, batch.rows_failed), (0, 1))
        self.assertIn('missing required', batch.error_report[0]['error'])


class LotModelTests(Base):
    def test_lots_are_never_deleted(self):
        lot = self.make_lot()
        with self.assertRaises(ValidationError):
            lot.delete()

    def test_days_in_storage_stops_at_pack(self):
        lot = self.make_lot(receive_date=date(2026, 8, 1), status=Lot.Status.PACKED, packed_date=date(2026, 9, 1))
        self.assertEqual(lot.days_in_storage, 31)

    def test_stage_thresholds(self):
        s = self.settings
        self.assertEqual(s.stage_for(-8), Color.DARK_GREEN)
        self.assertEqual(s.stage_for(-7), Color.LIGHT_GREEN)
        self.assertEqual(s.stage_for(-3), Color.LIGHT_GREEN)
        self.assertEqual(s.stage_for(0), Color.SILVER)
        self.assertEqual(s.stage_for(2), Color.SILVER)
        self.assertEqual(s.stage_for(2.1), Color.YELLOW)


class HealthCheckTests(TestCase):
    def test_liveness_and_readiness_do_not_require_login(self):
        live = self.client.get(reverse('healthz'))
        ready = self.client.get(reverse('readyz'))
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {'status': 'ok'})
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json(), {'status': 'ready'})
        self.assertIn('no-cache', live['Cache-Control'])

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r'^healthz/$', r'^readyz/$'])
    def test_health_checks_are_exempt_from_https_redirect(self):
        client = Client()  # fresh handler so SecurityMiddleware reads the overridden settings
        self.assertEqual(client.get(reverse('healthz')).status_code, 200)
        self.assertEqual(client.get(reverse('readyz')).status_code, 200)
        self.assertEqual(client.get(reverse('login')).status_code, 301)

    @patch('config.health.connection.cursor', side_effect=RuntimeError('database down'))
    def test_readiness_fails_closed_without_exposing_the_error(self, _cursor):
        response = self.client.get(reverse('readyz'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotContains(response, 'database down', status_code=503)


class ViewAccessTests(Base):
    def setUp(self):
        self.foreman = make_user('foreman', 'foreman', plant=self.sla1)
        self.gm = make_user('gm', 'gm', staff=True)
        self.admin = make_user('admin', 'admin', staff=True)
        self.make_lot('26-1001', plant=self.sla1)
        self.make_lot('26-3001', plant=self.sla3)

    def test_login_required(self):
        resp = self.client.get(reverse('lots:board'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_foreman_without_plant_fails_closed(self):
        user = User.objects.create_user('unassigned', password='pw')
        user.groups.add(Group.objects.get_or_create(name='foreman')[0])
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('lots:board')).status_code, 403)

    def test_foreman_sees_only_own_plant(self):
        self.client.force_login(self.foreman)
        resp = self.client.get(reverse('lots:board'))
        self.assertContains(resp, '26-1001')
        self.assertNotContains(resp, '26-3001')
        # and cannot open another plant's lot
        other = Lot.objects.get(lot_no='26-3001')
        self.assertEqual(self.client.get(reverse('lots:lot_detail', args=[other.pk])).status_code, 404)

    def test_gm_switches_plants(self):
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:board') + '?plant=SLA3')
        self.assertContains(resp, '26-3001')
        self.assertNotContains(resp, '26-1001')

    def test_packing_plan_searches_operational_fields(self):
        room = Room.objects.create(plant=self.sla1, name='North Cooler')
        lot = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        lot.block = 'Vista B12'
        lot.current_room = room
        lot.save()
        self.client.force_login(self.gm)
        for query in ('Sespe', 'Vista B12', 'North Cooler', '10417'):
            with self.subTest(query=query):
                resp = self.client.get(reverse('lots:board'), {'plant': 'SLA1', 'q': query})
                self.assertContains(resp, '26-1001')

    def test_packing_plan_attention_filter_only_shows_matching_lots(self):
        from forecast.models import Prediction

        urgent = Lot.objects.get(plant=self.sla1, lot_no='26-1001')
        later = self.make_lot('26-1002', plant=self.sla1)
        Prediction.objects.create(
            lot=urgent,
            as_of_date=date.today(),
            cci_now=1.0,
            stage=Color.SILVER,
            drift_per_day=.1,
            predicted_yellow_date=date.today() + timedelta(days=10),
            pack_by_date=date.today() + timedelta(days=3),
            decay_rate=.12,
            decay_flag=True,
            confidence='med',
            model_version='v1.1-linear-cci',
            inputs={'points': [[(date.today()-urgent.receive_date).days-7, 0.3], [(date.today()-urgent.receive_date).days, 1.0]]},
        )
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:board'), {'plant': 'SLA1', 'attention': 'due'})
        self.assertContains(resp, urgent.lot_no)
        self.assertNotContains(resp, later.lot_no)
        self.assertContains(resp, 'Inspect observed decay')
        resp = self.client.get(reverse('lots:board'), {'plant': 'SLA1', 'attention': 'decay'})
        self.assertContains(resp, urgent.lot_no)
        self.assertNotContains(resp, later.lot_no)
        self.assertContains(resp, '12.0% observed decay')

    def test_imports_need_gm(self):
        self.client.force_login(self.foreman)
        self.assertEqual(self.client.get(reverse('lots:imports')).status_code, 403)
        self.client.force_login(self.gm)
        self.assertEqual(self.client.get(reverse('lots:imports')).status_code, 200)

    def test_settings_need_admin(self):
        self.client.force_login(self.gm)
        self.assertEqual(self.client.get(reverse('lots:settings')).status_code, 403)
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('lots:settings'))
        self.assertContains(resp, 'Stage thresholds')
        post = {f: getattr(self.settings, f) for f in [
            'cci_dg_max', 'cci_lg_max', 'cci_s_max', 'prior_drift_dg', 'prior_drift_lg', 'prior_drift_s', 'prior_drift_y',
            'start_cci_dg', 'start_cci_lg', 'start_cci_s', 'start_cci_y', 'buffer_days', 'decay_flag_pct',
            'min_fruit_for_score', 'max_horizon_days', 'sample_overdue_days', 'import_gap_days']}
        post['buffer_days'] = 10
        post.update({'plants-TOTAL_FORMS': '2', 'plants-INITIAL_FORMS': '2', 'plants-MIN_NUM_FORMS': '0', 'plants-MAX_NUM_FORMS': '1000',
                     'plants-0-id': self.sla1.pk, 'plants-0-report_recipients': 'gm@example.com',
                     'plants-1-id': self.sla3.pk, 'plants-1-report_recipients': ''})
        resp = self.client.post(reverse('lots:settings'), post)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(ModelSettings.get().buffer_days, 10)
        self.sla1.refresh_from_db()
        self.assertEqual(self.sla1.recipient_list, ['gm@example.com'])

    def test_upload_and_error_report(self):
        self.client.force_login(self.gm)
        bad = RECEIVING + '\nSLA9,26-2000,10417,,,,2026-08-11,DG,1,'
        f = SimpleUploadedFile('receiving.csv', bad.strip().encode(), content_type='text/csv')
        resp = self.client.post(reverse('lots:imports'), {'kind': 'receiving', 'file': f})
        self.assertEqual(resp.status_code, 302)
        batch = ImportBatch.objects.get()
        self.assertEqual((batch.rows_ok, batch.rows_failed), (3, 1))
        resp = self.client.get(resp['Location'])
        self.assertContains(resp, 'unknown plant_code')

    def test_pinned_gm_cannot_import_another_plant(self):
        pinned = make_user('pinned-gm', 'gm', plant=self.sla1)
        self.client.force_login(pinned)
        f = SimpleUploadedFile('receiving.csv', RECEIVING.strip().encode(), content_type='text/csv')
        resp = self.client.post(reverse('lots:imports'), {'kind': 'receiving', 'file': f})
        self.assertEqual(resp.status_code, 302)
        batch = ImportBatch.objects.get()
        self.assertEqual(batch.plant_scope, self.sla1)
        self.assertEqual((batch.rows_ok, batch.rows_failed), (0, 1))
        self.assertIn('outside your assigned plant', batch.error_report[0]['error'])

    def test_template_download(self):
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:import_template', args=['packout']))
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertTrue(resp.content.decode().startswith('plant_code,lot_no,packed_date'))

    def test_lot_detail_renders_chart(self):
        self.client.force_login(self.gm)
        lot = Lot.objects.get(lot_no='26-1001')
        resp = self.client.get(reverse('lots:lot_detail', args=[lot.pk]))
        self.assertContains(resp, '<svg')
        self.assertContains(resp, 'No scored samples yet')
