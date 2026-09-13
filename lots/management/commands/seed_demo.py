"""Populate a demo season across the three plants so every screen has
something on it before real exports flow. Wipes lot data first, so it
refuses to run outside DEBUG unless --force is given.

    python manage.py seed_demo [--with-users]

--with-users also creates foreman1 (pinned to SLA1), gm1 and admin1 and prints
a random password unless --demo-password is supplied. Local development only.
"""

import random
import secrets
from datetime import date, timedelta

from django.conf import settings as django_settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from forecast.models import PackPlan, Prediction
from forecast.services import rebuild_for_lot
from sampling.models import Sample, SamplePhoto

from ...models import Color, Grower, Lot, LotRoomMove, LotTreatment, ModelSettings, Packout, Plant, Room, UserProfile
from .seed_plants import PLANTS

GROWERS = [
    ('10417', 'Sespe Creek Ranch'), ('10422', 'Las Posas Growers'), ('10508', 'Ojai Valley Orchards'),
    ('10611', 'Santa Clara River Farms'), ('10633', 'Limoneira Associates'), ('10702', 'Rancho Camulos'),
]
BLOCKS = ['B12', 'B17', 'N4', 'N7', 'E1', 'W5', 'S3', '']
ROOMS = [('Cold 1', 'storage', 55), ('Cold 2', 'storage', 55), ('Cold 3', 'storage', 52), ('Degreen A', 'degreening', 68)]


class Command(BaseCommand):
    help = 'Create demo plants, rooms, lots, samples, packouts and predictions.'

    def add_arguments(self, parser):
        parser.add_argument('--with-users', action='store_true')
        parser.add_argument(
            '--demo-password',
            default='',
            help='Optional local demo password. A random password is generated when omitted.',
        )
        parser.add_argument('--force', action='store_true', help='Allow running with DEBUG off.')

    def handle(self, *args, **options):
        if not django_settings.DEBUG and not options['force']:
            raise CommandError('seed_demo wipes lot data; refusing with DEBUG off (use --force).')
        rng = random.Random(7)
        today = date.today()
        cfg = ModelSettings.get()

        # Every reference to a lot is PROTECT, so dependents go first, in
        # dependency order. This is the only place lots are hard-deleted.
        PackPlan.objects.all().delete()  # cascades recommendations and decisions
        Prediction.objects.all().delete()
        SamplePhoto.objects.all().delete()
        Sample.objects.all().delete()
        Packout.objects.all().delete()
        LotTreatment.objects.all().delete()
        LotRoomMove.objects.all().delete()
        Lot.objects.all().hard_delete()  # explicit demo-only escape hatch
        Room.objects.all().delete()
        Grower.objects.all().delete()

        plants = []
        for code, name, city in PLANTS:
            plant, _ = Plant.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'city': city,
                    'weekly_pack_capacity_bins': 650,
                },
            )
            plants.append(plant)
        growers = [Grower.objects.create(sunkist_grower_no=no, name=name) for no, name in GROWERS]

        n_lots = 0
        for plant in plants:
            rooms = [Room.objects.create(plant=plant, name=n, room_type=t, target_temp_f=temp) for n, t, temp in ROOMS]
            cold = rooms[:3]
            seq = 1000 * int(plant.code[-1])
            # in-storage lots
            for _ in range(28):
                seq += 1
                n_lots += self._make_lot(rng, plant, growers, cold, seq, today, cfg, packed=False)
            # packed lots (history for the accuracy page)
            for _ in range(14):
                seq += 1
                n_lots += self._make_lot(rng, plant, growers, cold, seq, today, cfg, packed=True)

        if options['with_users']:
            self._make_users(plants[0], options['demo_password'] or secrets.token_urlsafe(15))

        self.stdout.write(self.style.SUCCESS(f'Seeded {n_lots} lots across {len(plants)} plants with samples, packouts and predictions.'))

    def _make_lot(self, rng, plant, growers, rooms, seq, today, cfg, packed):
        receiving_color = rng.choices([Color.DARK_GREEN, Color.LIGHT_GREEN, Color.SILVER], weights=[5, 3, 1])[0]
        if packed:
            receive_date = today - timedelta(days=rng.randint(60, 150))
        else:
            receive_date = today - timedelta(days=rng.randint(3, 110))
        lot = Lot.objects.create(
            plant=plant, lot_no=f'{today.year % 100}-{seq}', grower=rng.choice(growers), block=rng.choice(BLOCKS),
            variety=rng.choice([Lot.Variety.LISBON, Lot.Variety.LISBON, Lot.Variety.EUREKA]),
            receive_date=receive_date, receiving_color=receiving_color, bins_received=rng.randint(40, 180),
            current_room=rng.choice(rooms),
        )
        LotRoomMove.objects.create(lot=lot, room=lot.current_room, moved_on=receive_date)

        # a hidden "true" trajectory for this lot
        true_start = cfg.start_cci(receiving_color) + rng.uniform(-1.5, 1.5)
        true_drift = cfg.prior_drift(receiving_color) * rng.uniform(0.6, 1.5)
        days_to_yellow = max(1, (cfg.yellow_threshold - true_start) / true_drift)

        if packed:
            pack_offset = int(days_to_yellow * rng.uniform(0.6, 1.3))
            packed_date = min(today - timedelta(days=1), receive_date + timedelta(days=max(10, pack_offset)))
        else:
            packed_date = None
        end = packed_date or today

        sample_days = list(range(7, (end - receive_date).days + 1, 7))
        decay_prev = 0
        for d in sample_days:
            when = receive_date + timedelta(days=d)
            cci_true = true_start + true_drift * d
            cci_meas = cci_true + rng.gauss(0, 0.6)
            stage = cfg.stage_for(cci_true + rng.gauss(0, 1.2))
            remaining_weeks = max(1, min(8, int(round((days_to_yellow - d) / 7 + rng.uniform(-1, 1)))))
            decay = max(0, min(10, decay_prev + rng.choices([0, 0, 0, 1, -1], weights=[6, 6, 6, 3, 1])[0])) if d > 21 else 0
            decay_prev = decay
            sample = Sample.objects.create(
                lot=lot, sampled_at=timezone.make_aware(timezone.datetime(when.year, when.month, when.day, 9, 30)),
                foreman_color=stage, foreman_pack_within_weeks=remaining_weeks, decay_count=decay, fruit_count=10,
            )
            per_cci = [round(cci_meas + rng.gauss(0, 0.9), 3) for _ in range(10)]
            per_lab = [[round(60 + rng.uniform(-5, 5), 2), round(c * 60 * 45 / 1000, 2), round(45 + rng.uniform(-5, 5), 2)] for c in per_cci]
            SamplePhoto.objects.create(
                sample=sample, image='', status=SamplePhoto.Status.SCORED, card_detected=True, fruit_detected=10,
                per_fruit_lab=per_lab, per_fruit_cci=per_cci, mean_cci=round(sum(per_cci) / 10, 3),
                std_cci=round((sum((c - sum(per_cci) / 10) ** 2 for c in per_cci) / 10) ** 0.5, 3),
                processed_at=timezone.now(), pipeline_version='demo',
            ).sync_fruit_measurements()
            rebuild_for_lot(lot, as_of=when, settings=cfg)

        if not packed and sample_days and rng.random() < 0.12:
            # one lot in ~8 had a visit whose only photo failed, so the "retake" flag shows
            when = today - timedelta(days=rng.randint(0, 2))
            retake = Sample.objects.create(
                lot=lot, sampled_at=timezone.make_aware(timezone.datetime(when.year, when.month, when.day, 10, 0)),
                foreman_color=cfg.stage_for(true_start + true_drift * (when - receive_date).days) or Color.SILVER,
                foreman_pack_within_weeks=rng.randint(1, 4), decay_count=decay_prev, fruit_count=10,
            )
            SamplePhoto.objects.create(sample=retake, image='', status=SamplePhoto.Status.FAILED, card_detected=False,
                                       error='reference board not found (no ArUco markers detected)', processed_at=timezone.now())

        if packed:
            cci_at_pack = true_start + true_drift * (packed_date - receive_date).days
            over = max(0.0, cci_at_pack - cfg.yellow_threshold)
            fresh_share = max(0.35, 0.93 - 0.08 * over - rng.uniform(0, 0.05))
            total = lot.bins_received * 9
            fresh = int(total * fresh_share)
            Packout.objects.create(
                lot=lot, packed_date=packed_date,
                bins_packed=lot.bins_received,
                is_final=True,
                packout_color=cfg.stage_for(cci_at_pack),
                decay_pct=decay_prev * 10,
                downgrade_reason='color' if over > 0.5 else '',
                cartons_fancy=int(fresh * 0.55), cartons_choice=int(fresh * 0.3), cartons_standard=fresh - int(fresh * 0.55) - int(fresh * 0.3),
                cartons_products=total - fresh,
            )
            lot.status = Lot.Status.PACKED
            lot.packed_date = packed_date
            lot.save(update_fields=['status', 'packed_date'])
        else:
            rebuild_for_lot(lot, as_of=today - timedelta(days=7), settings=cfg)
            rebuild_for_lot(lot, as_of=today, settings=cfg)
        return 1

    def _make_users(self, plant, password):
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in django_settings.ROLE_GROUPS}
        for username, group, staff, pinned in (('foreman1', 'foreman', False, plant), ('gm1', 'gm', False, None), ('admin1', 'admin', True, None)):
            user, created = User.objects.get_or_create(username=username, defaults={'is_staff': staff})
            user.set_password(password)
            user.is_staff = staff
            user.is_active = True
            user.save()
            user.groups.set([groups[group]])
            UserProfile.objects.update_or_create(user=user, defaults={'plant': pinned})
        self.stdout.write(f'Users foreman1 (SLA1), gm1, admin1 - demo password: {password}')
