"""Score pending sample photos. Run every minute from cron / Task Scheduler
so a photo is scored within two minutes of upload:

    python manage.py score_photos

Options:
    --limit N      score at most N photos this run (default 50)
    --rescore      re-score every photo, including already scored/failed ones
                   (use after a pipeline or threshold change; raw photos are kept)
    --lot LOT_NO   only photos for this lot number
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from lots.models import ModelSettings

from ...models import SamplePhoto
from ...scoring import PIPELINE_VERSION, score_photo


class Command(BaseCommand):
    help = 'Score pending sample photos (board detection + CCI).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximum photos. Pending runs default to 50; --rescore defaults to all photos.',
        )
        parser.add_argument('--rescore', action='store_true')
        parser.add_argument('--lot', default='')

    def handle(self, *args, **options):
        if options['limit'] is not None and options['limit'] < 1:
            raise CommandError('--limit must be at least 1')
        stale_before = timezone.now() - timedelta(minutes=20)
        SamplePhoto.objects.filter(
            status=SamplePhoto.Status.PROCESSING,
            processing_started_at__lt=stale_before,
        ).update(
            status=SamplePhoto.Status.PENDING,
            processing_started_at=None,
            error='Recovered after a scoring worker stopped before completion.',
        )

        qs = SamplePhoto.objects.select_related('sample__lot__plant').order_by('uploaded_at')
        if not options['rescore']:
            qs = qs.filter(status=SamplePhoto.Status.PENDING)
        else:
            qs = qs.exclude(status=SamplePhoto.Status.PROCESSING)
        if options['lot']:
            qs = qs.filter(sample__lot__lot_no=options['lot'])
        limit = options['limit'] if options['limit'] is not None else (None if options['rescore'] else 50)
        candidate_ids = list(qs.values_list('pk', flat=True)[:limit] if limit else qs.values_list('pk', flat=True))
        if not candidate_ids:
            self.stdout.write('No photos to score.')
            return
        settings = ModelSettings.get()
        counts = {'scored': 0, 'failed': 0, 'pending': 0, 'skipped': 0}
        for photo_id in candidate_ids:
            with transaction.atomic():
                photo = (
                    SamplePhoto.objects.select_for_update(skip_locked=True)
                    .select_related('sample__lot__plant')
                    .filter(pk=photo_id)
                    .first()
                )
                if photo is None or photo.status == SamplePhoto.Status.PROCESSING:
                    counts['skipped'] += 1
                    continue
                if not options['rescore'] and photo.status != SamplePhoto.Status.PENDING:
                    counts['skipped'] += 1
                    continue
                SamplePhoto.objects.filter(pk=photo.pk).update(
                    status=SamplePhoto.Status.PROCESSING,
                    processing_started_at=timezone.now(),
                    attempt_count=F('attempt_count') + 1,
                )
                photo.refresh_from_db()
            status = score_photo(photo, settings=settings)
            counts[status] = counts.get(status, 0) + 1
            line = f'{photo.sample.lot} photo {photo.pk}: {status}'
            if status == SamplePhoto.Status.SCORED:
                line += f' mean CCI {photo.mean_cci} from {photo.fruit_detected} fruit'
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stdout.write(self.style.WARNING(f'{line}: {photo.error}'))
        self.stdout.write(
            f'{PIPELINE_VERSION}: {counts["scored"]} scored, {counts["failed"]} failed, '
            f'{counts["pending"]} queued for retry, {counts["skipped"]} claimed elsewhere.'
        )
