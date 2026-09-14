import io
import time
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from forecast.model import MODEL_VERSION
from .importers import conditions, packout, receiving, room_moves, run_import, treatments
from .importers.base import read_csv
from .forms import PlantSettingsForm
from .planning import board_rows
from .models import (
    Color, Grower, ImportBatch, Lot, LotRoomMove, LotTreatment, ModelSettings,
    Packout, Plant, PlantReportRecipient, Room, RoomCondition, UserProfile,
)


def csv_rows(text):
    return read_csv(io.BytesIO(text.strip().encode('utf-8')))


def make_user(username, group=None, plant=None, staff=False):
    user = User.objects.create_user(username, password='pw', is_staff=staff)
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    UserProfile.objects.create(user=user, plant=plant)
    return user


@override_settings(FOREMAN_DEFAULT_LANGUAGE='en')
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
        LotRoomMove.objects.create(lot=self.lot, room=self.room, moved_on=date(2026, 8, 1))

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

    def test_plant_switch_discards_a_room_from_the_previous_plant(self):
        room = Room.objects.create(plant=self.sla1, name='Old plant cooler')
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:board'), {'plant': 'SLA3', 'room': room.pk})
        self.assertContains(resp, '26-3001')
        self.assertNotContains(resp, '26-1001')
        self.assertEqual(resp.context['room_id'], '')

    def test_room_filter_keeps_valid_selection_and_clears_invalid_values(self):
        room = Room.objects.create(plant=self.sla1, name='Selected cooler')
        self.make_lot('26-ROOM', current_room=room)
        self.client.force_login(self.foreman)
        resp = self.client.get(reverse('lots:board'), {'room': room.pk})
        self.assertContains(resp, '26-ROOM')
        self.assertNotContains(resp, '26-1001')
        for value in ('bad-room', '999999999'):
            with self.subTest(room=value):
                resp = self.client.get(reverse('lots:board'), {'room': value})
                self.assertContains(resp, '26-1001')
                self.assertEqual(resp.context['room_id'], '')

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
            model_version=MODEL_VERSION,
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
            'min_fruit_for_score', 'max_horizon_days', 'sample_overdue_days', 'import_gap_days',
            'sample_fruit_count', 'warm_storage_temp_c', 'warm_weeks_flag', 'temperature_response', 'color_correction_method']}
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


@override_settings(FOREMAN_DEFAULT_LANGUAGE='es')
class LanguageTests(Base):
    def setUp(self):
        self.foreman = make_user('foreman_es', 'foreman', self.sla1)
        self.gm = make_user('gm_en', 'gm')

    def test_foreman_defaults_to_spanish_until_they_choose(self):
        self.client.force_login(self.foreman)
        resp = self.client.get(reverse('sampling:picker'))
        self.assertContains(resp, 'Ruta de muestreo de hoy')
        self.assertContains(resp, 'lang="es"')
        self.client.cookies['django_language'] = 'en'
        resp = self.client.get(reverse('sampling:picker'))
        self.assertContains(resp, 'Today’s sample route')

    def test_gm_stays_in_english_by_default(self):
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:board'))
        self.assertContains(resp, 'Packing plan')
        self.assertNotContains(resp, 'Plan de empaque')

    def test_language_toggle_sets_cookie(self):
        self.client.force_login(self.gm)
        resp = self.client.post(reverse('set_language'), {'language': 'es', 'next': '/'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.cookies['django_language'].value, 'es')
        self.assertContains(self.client.get(reverse('lots:board')), 'Plan de empaque')


class WarmStorageClockTests(Base):
    def test_warm_clock_counts_only_rooms_at_or_above_threshold(self):
        from forecast.features import warm_exposure
        warm = Room.objects.create(plant=self.sla1, name='Warm', target_temp_f=56)   # 13.3 C
        cool = Room.objects.create(plant=self.sla1, name='Cool', target_temp_f=50)   # 10 C
        unset = Room.objects.create(plant=self.sla1, name='Unset')
        lot = self.make_lot(receive_date=date.today() - timedelta(days=70), current_room=warm)
        LotRoomMove.objects.create(lot=lot, room=warm, moved_on=lot.receive_date)
        LotRoomMove.objects.create(lot=lot, room=cool, moved_on=lot.receive_date + timedelta(days=21))
        LotRoomMove.objects.create(lot=lot, room=unset, moved_on=lot.receive_date + timedelta(days=28))
        LotRoomMove.objects.create(lot=lot, room=warm, moved_on=lot.receive_date + timedelta(days=35))
        result = warm_exposure(lot, date.today(), self.settings)
        self.assertEqual(result['warm_days'], 21 + 36)
        self.assertEqual(result['cool_days'], 7)
        self.assertEqual(result['unknown_days'], 7)
        self.assertTrue(result['flag'])
        self.assertTrue(result['has_history'])
        rows = board_rows([Lot.objects.prefetch_related('room_moves__room').get(pk=lot.pk)], date.today(), self.settings)
        self.assertTrue(rows[0]['warm_flag'])
        self.assertEqual(rows[0]['warm_weeks'], round(57 / 7, 1))

    def test_no_room_history_means_no_clock(self):
        from forecast.features import warm_exposure
        lot = self.make_lot()
        result = warm_exposure(lot, date.today(), self.settings)
        self.assertFalse(result['has_history'])
        self.assertFalse(result['flag'])


class LotDetailAndPackoutQualityTests(Base):
    def setUp(self):
        self.gm = make_user('gm_q', 'gm')
        self.foreman = make_user('foreman_q', 'foreman', self.sla1)

    def test_lot_detail_shows_overdue_days_in_red_tile(self):
        from forecast.models import Prediction
        lot = self.make_lot(receive_date=date.today() - timedelta(days=100), bins_received=120)
        Prediction.objects.create(lot=lot, as_of_date=date.today(), cci_now=5.0, stage=Color.YELLOW, drift_per_day=.2,
            predicted_yellow_date=date.today() - timedelta(days=5), pack_by_date=date.today() - timedelta(days=12),
            confidence='high', model_version=MODEL_VERSION, inputs={'points': [[80, 1.0], [90, 3.0]]})
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:lot_detail', args=[lot.pk]))
        self.assertContains(resp, '12 days overdue')
        self.assertContains(resp, 'tile red')
        self.assertContains(resp, '>120<')  # whole bins, no decimal
        self.assertNotContains(resp, '120.0')

    def test_gm_records_packout_quality_labels_and_foreman_cannot(self):
        lot = self.make_lot(bins_received=100)
        packout = Packout.objects.create(lot=lot, packed_date=date.today(), cartons_fancy=100, cartons_products=20, bins_packed=40, is_final=False)
        url = reverse('lots:packout_quality', args=[lot.pk, packout.pk])
        self.client.force_login(self.foreman)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.gm)
        resp = self.client.post(url, {
            f'po{packout.pk}-packout_color': 'Y', f'po{packout.pk}-decay_pct': '3.5',
            f'po{packout.pk}-meets_spec': 'false', f'po{packout.pk}-downgrade_reason': 'Color',
        })
        self.assertEqual(resp.status_code, 302)
        packout.refresh_from_db()
        self.assertEqual((packout.packout_color, float(packout.decay_pct), packout.meets_spec, packout.downgrade_reason), ('Y', 3.5, False, 'Color'))
        self.assertEqual(packout.cartons_fancy, 100)  # counts untouched
        resp = self.client.get(reverse('lots:lot_detail', args=[lot.pk]))
        self.assertContains(resp, 'Edit quality labels')
        self.assertContains(resp, 'decay 3.50%')

    def test_board_uses_whole_bins_and_no_chip_row(self):
        self.make_lot(bins_received=150)
        self.client.force_login(self.gm)
        resp = self.client.get(reverse('lots:board'), {'plant': 'SLA1'})
        self.assertContains(resp, '150 bins')
        self.assertNotContains(resp, '150.0 bins')
        self.assertNotContains(resp, 'class="filters"')
        self.assertContains(resp, 'aria-current="page" href="?plant=SLA1&amp;attention=all"')


class DatabaseRuleTests(Base):
    """Rules the database enforces on its own, without going through clean()."""

    def test_harvest_after_receipt_rejected_by_check_constraint(self):
        lot = self.make_lot(receive_date=date(2026, 8, 1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Lot.objects.filter(pk=lot.pk).update(harvest_date=date(2026, 8, 2))

    def test_user_with_history_is_protected_not_deleted(self):
        user = make_user('mover', 'foreman', self.sla1)
        lot = self.make_lot()
        room = Room.objects.create(plant=self.sla1, name='Cold 1')
        LotRoomMove.objects.create(lot=lot, room=room, moved_on=lot.receive_date, moved_by=user)
        with self.assertRaises(ProtectedError):
            user.delete()
        user.is_active = False
        user.save()
        self.assertEqual(LotRoomMove.objects.get().moved_by, user)

    def test_lot_dependents_block_a_hard_delete(self):
        lot = self.make_lot()
        Packout.objects.create(lot=lot, packed_date=lot.receive_date, cartons_fancy=1, is_final=False)
        with self.assertRaises(ProtectedError):
            Lot.objects.filter(pk=lot.pk).hard_delete()

    def test_report_recipients_are_atomic_rows(self):
        self.sla1.set_recipients(['gm@example.com', ' gm@example.com ', 'foreman@example.com'])
        self.assertEqual(self.sla1.recipient_list, ['foreman@example.com', 'gm@example.com'])
        self.sla1.set_recipients(['gm@example.com'])
        self.assertEqual(self.sla1.recipient_list, ['gm@example.com'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlantReportRecipient.objects.create(plant=self.sla1, email='gm@example.com')

    def test_settings_form_validates_each_recipient(self):
        form = PlantSettingsForm({'report_recipients': 'gm@example.com, not-an-email', 'weekly_pack_capacity_bins': ''}, instance=self.sla1)
        self.assertFalse(form.is_valid())
        self.assertIn('not-an-email', form.errors['report_recipients'][0])

    def test_packout_totals_are_generated_by_the_database(self):
        lot = self.make_lot()
        po = Packout.objects.create(
            lot=lot, packed_date=lot.receive_date, cartons_fancy=1, cartons_choice=1,
            cartons_standard=1, cartons_products=1, is_final=False,
        )
        self.assertEqual((po.cartons_total, float(po.fresh_pct)), (4, 75.0))
        Packout.objects.filter(pk=po.pk).update(cartons_products=0)  # bypasses save(); the database still recomputes
        po.refresh_from_db()
        self.assertEqual((po.cartons_total, float(po.fresh_pct)), (3, 100.0))
        Packout.objects.filter(pk=po.pk).update(cartons_fancy=0, cartons_choice=0, cartons_standard=0)
        po.refresh_from_db()
        self.assertEqual((po.cartons_total, po.fresh_pct), (0, None))

    def test_bin_balance_annotation_matches_python_property(self):
        lot = self.make_lot(bins_received=100)
        Packout.objects.create(lot=lot, packed_date=lot.receive_date, cartons_fancy=1, bins_packed=Decimal('30.5'), is_final=False)
        Packout.objects.create(lot=lot, packed_date=lot.receive_date + timedelta(days=1), cartons_fancy=1, bins_packed=Decimal('10'), is_final=False)
        annotated = Lot.objects.with_bin_balance().get(pk=lot.pk)
        self.assertEqual(annotated.bins_remaining, Decimal('59.5'))
        self.assertEqual(annotated.bins_remaining, Lot.objects.get(pk=lot.pk).bins_remaining)
        Packout.objects.create(lot=lot, packed_date=lot.receive_date + timedelta(days=2), cartons_fancy=1, bins_packed=None, is_final=False)
        self.assertIsNone(Lot.objects.with_bin_balance().get(pk=lot.pk).bins_remaining)
        self.assertIsNone(Lot.objects.get(pk=lot.pk).bins_remaining)


class StaleForecastBoardTests(Base):
    """F1 from the 10 September review: a stale forecast degrades on the
    board instead of vanishing, and still counts toward bins due."""

    def test_stale_forecast_keeps_its_date_greyed_and_counts_bins(self):
        from forecast.models import Prediction
        from sampling.models import Sample
        gm = make_user('gm-stale', 'gm', None)
        lot = self.make_lot('26-STALE', receive_date=date.today() - timedelta(days=40), bins_received=80)
        Sample.objects.create(lot=lot, sampled_at=timezone.now() - timedelta(days=12), foreman_color=Color.SILVER, foreman_pack_within_weeks=1)
        Prediction.objects.create(
            lot=lot, as_of_date=date.today() - timedelta(days=5), cci_now=1.0, stage=Color.SILVER, drift_per_day=0.2,
            predicted_yellow_date=date.today() + timedelta(days=9), pack_by_date=date.today() + timedelta(days=2),
            confidence='med', model_version=MODEL_VERSION,
            inputs={'points': [[20, -2.0], [28, 0.0]], 'receive_date': lot.receive_date.isoformat()},
        )
        rows = board_rows(Lot.objects.filter(pk=lot.pk).with_bin_balance().prefetch_related('predictions', 'samples__photos', 'packouts', 'room_moves__room'), date.today(), self.settings)
        row = rows[0]
        self.assertFalse(row['dates_usable'])
        self.assertTrue(row['date_stale'])
        self.assertEqual(row['days_to_pack_by'], 2)
        self.assertEqual(row['urgency'], '')
        self.assertNotIn(row['priority_code'], ('pack_this_week', 'pack_overdue'))
        self.client.force_login(gm)
        resp = self.client.get(reverse('lots:board'), {'plant': 'SLA1'})
        self.assertContains(resp, (date.today() + timedelta(days=2)).strftime('%b %-d') if False else (date.today() + timedelta(days=2)).strftime('%b ') + str((date.today() + timedelta(days=2)).day))
        self.assertContains(resp, 'from a sample 12d ago')
        self.assertNotContains(resp, 'Not available')
        self.assertEqual(resp.context['due_bins_7'], Decimal('80'))


class LotChangeTests(Base):
    def test_direct_edit_is_logged_with_user_and_source(self):
        from .audit import acting_as
        from .models import LotChange
        user = make_user('editor', 'gm', None)
        lot = self.make_lot(bins_received=100)
        self.assertEqual(list(lot.changes.values_list('field', 'new_value')), [('created', lot.lot_no)])
        with acting_as(user, 'web:/admin/'):
            lot.bins_received = 90
            lot.notes = 'recount'
            lot.save()
        changes = {c.field: c for c in LotChange.objects.filter(lot=lot).exclude(field='created')}
        self.assertEqual(set(changes), {'bins_received', 'notes'})
        self.assertEqual((changes['bins_received'].old_value, changes['bins_received'].new_value), ('100', '90'))
        self.assertEqual((changes['notes'].changed_by, changes['notes'].source), (user, 'web:/admin/'))

    def test_packout_status_change_and_reimport_are_logged(self):
        lot = self.make_lot(receive_date=date(2026, 8, 11), bins_received=120)
        Packout.objects.create(lot=lot, packed_date=date(2026, 9, 1), cartons_fancy=10)
        status = lot.changes.get(field='status')
        self.assertEqual((status.old_value, status.new_value, status.source), ('in_storage', 'packed', 'packout'))
        self.assertEqual(lot.changes.get(field='packed_date').new_value, '2026-09-01')
        receiving.run(csv_rows(RECEIVING.replace('2026-08-11,DG,120', '2026-08-11,DG,115')))
        change = lot.changes.get(field='bins_received')
        self.assertEqual((change.old_value, change.new_value, change.source), ('120', '115', 'import:receiving'))
        self.assertEqual(lot.changes.filter(field='created').count(), 1)
