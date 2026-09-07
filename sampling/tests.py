from datetime import date, timedelta

import numpy as np
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from forecast.models import Prediction
from lots.models import Color, Grower, Lot, ModelSettings, Plant, Room, UserProfile

from . import board, scoring
from .models import BoardCalibration, Sample, SamplePhoto

GREEN = (110, 150, 50)
YELLOW = (240, 205, 40)


def synthetic_photo(n_fruit=10, color=GREEN, tilt=0.06, cast=(1.0, 1.0, 1.0), size=(1600, 1200)):
    """Render the ideal board with n fruit, photograph it from a slightly
    off-axis phone (perspective + color cast) and JPEG-encode it."""
    import cv2

    centers = board.default_fruit_layout(n_fruit)
    canvas = board.render_canvas([(cx, cy, 1.2, color) for cx, cy in centers])
    W, H = size
    src = np.float32([[0, 0], [board.CANVAS_W, 0], [board.CANVAS_W, board.CANVAS_H], [0, board.CANVAS_H]])
    dx, dy = tilt * W, tilt * H
    dst = np.float32([[W * 0.12 + dx, H * 0.14], [W * 0.88, H * 0.12 + dy], [W * 0.86 - dx, H * 0.86], [W * 0.14, H * 0.88 - dy]])
    M = cv2.getPerspectiveTransform(src, dst)
    photo = cv2.warpPerspective(canvas, M, (W, H), borderValue=(30, 30, 30))
    if cast != (1.0, 1.0, 1.0):
        # a white-balance error is a per-channel gain in linear light, before the camera's gamma
        b, g, r = cast[2], cast[1], cast[0]
        lin = scoring._srgb_to_linear(photo.astype(np.float64) / 255.0) * np.array([b, g, r])
        photo = (scoring._linear_to_srgb(lin) * 255).round().astype(np.uint8)
    ok, buf = cv2.imencode('.jpg', photo, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    return buf.tobytes()


class PipelineTests(TestCase):
    def test_green_fruit_scores_negative_cci(self):
        result = scoring.score_image(synthetic_photo(color=GREEN))
        self.assertTrue(result['card_detected'])
        self.assertEqual(result['markers'], [0, 1, 2, 3])
        self.assertEqual(result['fruit_detected'], 10)
        self.assertEqual(len(result['per_fruit_cci']), 10)
        self.assertLess(result['mean_cci'], -4)
        self.assertLess(result['std_cci'], 1.0)

    def test_yellow_fruit_scores_higher_than_green(self):
        green = scoring.score_image(synthetic_photo(color=GREEN))['mean_cci']
        yellow = scoring.score_image(synthetic_photo(color=YELLOW))['mean_cci']
        self.assertGreater(yellow, green + 5)
        self.assertGreater(yellow, -1.5)

    def test_color_cast_is_corrected(self):
        neutral = scoring.score_image(synthetic_photo(color=GREEN))
        warm = scoring.score_image(synthetic_photo(color=GREEN, cast=(1.15, 1.0, 0.85)))
        self.assertTrue(warm['correction']['applied'])
        self.assertLess(abs(warm['mean_cci'] - neutral['mean_cci']), 1.0)
        # and the correction is doing real work: the same cast uncorrected is far off
        import cv2

        raw = scoring.decode_image(synthetic_photo(color=GREEN, cast=(1.15, 1.0, 0.85)))
        H, _ = scoring.detect_board(raw)
        canvas = scoring.warp_to_canvas(raw, H)
        blobs = scoring.segment_fruit(canvas)
        _, cci_uncorrected = scoring.measure_fruit(canvas, blobs)
        uncorrected_mean = float(np.mean([c for c in cci_uncorrected if c is not None]))
        self.assertGreater(abs(uncorrected_mean - neutral['mean_cci']), abs(warm['mean_cci'] - neutral['mean_cci']))

    def test_too_few_fruit_reports_count(self):
        with self.assertRaises(scoring.ScoringError) as ctx:
            scoring.score_image(synthetic_photo(n_fruit=4))
        self.assertTrue(ctx.exception.card_detected)
        self.assertEqual(ctx.exception.fruit_detected, 4)

    def test_no_board_fails_cleanly(self):
        import cv2

        blank = np.full((600, 800, 3), 90, dtype=np.uint8)
        ok, buf = cv2.imencode('.jpg', blank)
        with self.assertRaises(scoring.ScoringError) as ctx:
            scoring.score_image(buf.tobytes())
        self.assertFalse(ctx.exception.card_detected)

    def test_garbage_bytes_fail_cleanly(self):
        with self.assertRaises(scoring.ScoringError):
            scoring.score_image(b'not an image')

    def test_board_svg_generator_matches_layout(self):
        bits = board.marker_bits(0)
        self.assertEqual(bits.shape, (6, 6))
        self.assertEqual(bits[0].sum(), 0)  # black border row
        self.assertEqual(len(board.patches()), 9)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sla1 = Plant.objects.create(code='SLA1', name='Plant 1')
        cls.sla3 = Plant.objects.create(code='SLA3', name='Plant 3')
        cls.grower = Grower.objects.create(sunkist_grower_no='10417', name='Sespe')
        cls.lot = Lot.objects.create(lot_no='26-1001', plant=cls.sla1, grower=cls.grower, receive_date=date.today() - timedelta(days=21), receiving_color=Color.LIGHT_GREEN)
        cls.other = Lot.objects.create(lot_no='26-3001', plant=cls.sla3, grower=cls.grower, receive_date=date.today() - timedelta(days=5))
        ModelSettings.get()
        cls.foreman = User.objects.create_user('foreman', password='pw')
        cls.foreman.groups.add(Group.objects.get_or_create(name='foreman')[0])
        UserProfile.objects.create(user=cls.foreman, plant=cls.sla1)


@override_settings(MEDIA_ROOT=None)
class ScorePhotoTests(Base):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def test_score_photo_end_to_end(self):
        sample = Sample.objects.create(lot=self.lot, sampled_by=self.foreman, foreman_color=Color.LIGHT_GREEN, foreman_pack_within_weeks=4)
        photo = SamplePhoto.objects.create(sample=sample, image=SimpleUploadedFile('p.jpg', synthetic_photo(), content_type='image/jpeg'))
        self.assertEqual(photo.status, SamplePhoto.Status.PENDING)
        status = scoring.score_photo(photo)
        photo.refresh_from_db()
        self.assertEqual(status, SamplePhoto.Status.SCORED)
        self.assertTrue(photo.card_detected)
        self.assertEqual(photo.fruit_detected, 10)
        self.assertIsNotNone(photo.mean_cci)
        self.assertEqual(photo.pipeline_version, scoring.PIPELINE_VERSION)
        self.assertTrue(photo.quality_ok)
        self.assertEqual(photo.scoring_metadata['markers'], [0, 1, 2, 3])
        self.assertIn('matrix_linear', photo.scoring_metadata['correction'])
        self.assertTrue(photo.thumb.name)
        self.assertEqual(len(photo.per_fruit_lab), 10)
        # scoring rebuilt today's prediction for the lot from the new point
        pred = Prediction.objects.get(lot=self.lot, as_of_date=date.today())
        self.assertEqual(pred.model_version, 'v1.1-linear-cci')
        self.assertEqual(len(pred.inputs['points']), 1)
        self.assertEqual(sample.mean_cci, photo.mean_cci)

    def test_failed_photo_keeps_sample_and_records_error(self):
        sample = Sample.objects.create(lot=self.lot, foreman_color=Color.SILVER, foreman_pack_within_weeks=2)
        photo = SamplePhoto.objects.create(sample=sample, image=SimpleUploadedFile('p.jpg', synthetic_photo(n_fruit=3), content_type='image/jpeg'))
        status = scoring.score_photo(photo)
        photo.refresh_from_db()
        self.assertEqual(status, SamplePhoto.Status.FAILED)
        self.assertTrue(photo.card_detected)
        self.assertEqual(photo.fruit_detected, 3)
        self.assertIn('retake', photo.error)
        self.assertEqual(Sample.objects.count(), 1)

    def test_worker_claims_and_scores_pending_photo_once(self):
        import io

        sample = Sample.objects.create(
            lot=self.lot,
            foreman_color=Color.LIGHT_GREEN,
            foreman_pack_within_weeks=4,
        )
        photo = SamplePhoto.objects.create(
            sample=sample,
            image=SimpleUploadedFile('p.jpg', synthetic_photo(), content_type='image/jpeg'),
        )
        call_command('score_photos', limit=1, stdout=io.StringIO())
        photo.refresh_from_db()
        self.assertEqual(photo.status, SamplePhoto.Status.SCORED)
        self.assertEqual(photo.attempt_count, 1)
        self.assertIsNone(photo.processing_started_at)


class CaptureFlowTests(Base):
    def test_today_and_calibration_survive_capture_and_scoring(self):
        references = {p['name']: list(p['ref_rgb']) for p in board.patches()}
        calibration = BoardCalibration.objects.create(plant=self.sla1, board_id='TEST-BOARD', phone_id='TEST-PHONE',
            light_id='TEST-LIGHT', measured_at=timezone.now(), instrument='Synthetic test fixture only', reference_rgb=references)
        response = self.client.post(reverse('sampling:capture', args=[self.lot.pk]), {
            'foreman_color': 'S', 'foreman_pack_within_weeks': '0', 'decay_count': '0',
            'calibration': calibration.pk,
            'photo': SimpleUploadedFile('p.jpg', synthetic_photo(), content_type='image/jpeg'),
        })
        self.assertEqual(response.status_code, 302)
        sample = Sample.objects.get()
        self.assertEqual(sample.foreman_pack_by_date, sample.sampled_on)
        self.assertEqual(sample.foreman_pack_label, 'Today')
        photo = sample.photos.get()
        self.assertEqual(photo.calibration_snapshot['board_id'], 'TEST-BOARD')
        scoring.score_photo(photo)
        photo.refresh_from_db()
        self.assertEqual(photo.scoring_metadata['calibration']['reference_rgb'], references)
        self.assertFalse(any('No instrument' in w for w in photo.quality_warnings))

    def test_packed_lot_accepts_only_holdout_and_does_not_rebuild(self):
        self.lot.status = Lot.Status.PACKED
        self.lot.packed_date = timezone.localdate()
        self.lot.save()
        def payload():
            return {'foreman_color': 'Y', 'foreman_pack_within_weeks': '0', 'decay_count': '0',
                'photo': SimpleUploadedFile('p.jpg', synthetic_photo(), content_type='image/jpeg')}
        response = self.client.post(reverse('sampling:capture', args=[self.lot.pk]), payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Sample.objects.count(), 0)
        data = {**payload(), 'is_holdout': 'on', 'marketability': 'pass'}
        self.assertEqual(self.client.post(reverse('sampling:capture', args=[self.lot.pk]), data).status_code, 302)
        sample = Sample.objects.get()
        self.assertEqual(sample.purpose, Sample.Purpose.HOLDOUT)
        scoring.score_photo(sample.photos.get())
        self.assertFalse(Prediction.objects.filter(lot=self.lot).exists())

    def test_calibration_cannot_be_selected_across_plants_or_rewritten(self):
        from .forms import CaptureForm
        from django.core.exceptions import ValidationError
        calibration = BoardCalibration.objects.create(plant=self.sla3, board_id='OTHER', phone_id='P', light_id='L',
            measured_at=timezone.localtime(timezone.now()), instrument='Synthetic test fixture only',
            reference_rgb={p['name']: list(p['ref_rgb']) for p in board.patches()})
        calibration.active = False
        calibration.save()
        calibration.active = True
        calibration.save()
        with self.assertRaises(ValidationError):
            CaptureForm(plant=self.sla1).fields['calibration'].clean(calibration.pk)
        calibration.reference_rgb['yellow'] = [1, 2, 3]
        with self.assertRaises(ValidationError):
            calibration.save()
        calibration.refresh_from_db()
        calibration.active = False
        calibration.save()
        self.assertFalse(CaptureForm(plant=self.sla3).fields['calibration'].queryset.exists())

    def test_unassigned_foreman_cannot_access_capture_directly(self):
        UserProfile.objects.filter(user=self.foreman).update(plant=None)
        self.assertEqual(self.client.get(reverse('sampling:capture', args=[self.lot.pk])).status_code, 403)

    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.override.enable()
        self.client.force_login(self.foreman)

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def test_picker_lists_plant_lots_longest_first_and_searches(self):
        Lot.objects.create(lot_no='26-1002', plant=self.sla1, grower=self.grower, receive_date=date.today() - timedelta(days=60))
        resp = self.client.get(reverse('sampling:picker'))
        body = resp.content.decode()
        self.assertLess(body.index('26-1002'), body.index('26-1001'))
        self.assertNotIn('26-3001', body)
        resp = self.client.get(reverse('sampling:picker') + '?q=1002', HTTP_HX_REQUEST='true')
        self.assertContains(resp, '26-1002')
        self.assertNotContains(resp, '26-1001')
        self.assertNotContains(resp, '<html')

    def test_picker_searches_grower_block_and_room(self):
        grower = Grower.objects.create(sunkist_grower_no='20422', name='Mesa Citrus')
        room = Room.objects.create(plant=self.sla1, name='South Tunnel')
        Lot.objects.create(
            lot_no='26-1777',
            plant=self.sla1,
            grower=grower,
            block='Ridge 7',
            current_room=room,
            receive_date=date.today() - timedelta(days=30),
        )
        for query in ('Mesa Citrus', 'Ridge 7', 'South Tunnel', '20422'):
            with self.subTest(query=query):
                resp = self.client.get(reverse('sampling:picker'), {'q': query}, HTTP_HX_REQUEST='true')
                self.assertContains(resp, '26-1777')
                self.assertNotContains(resp, '26-1001')

    def test_picker_prioritizes_due_work_and_uses_configured_interval(self):
        settings = ModelSettings.get()
        settings.sample_overdue_days = 14
        settings.save()
        Sample.objects.create(
            lot=self.lot,
            sampled_at=timezone.now() - timedelta(days=5),
            foreman_color=Color.LIGHT_GREEN,
            foreman_pack_within_weeks=3,
        )
        due = Lot.objects.create(
            lot_no='26-1999',
            plant=self.sla1,
            grower=self.grower,
            receive_date=date.today() - timedelta(days=45),
        )
        resp = self.client.get(reverse('sampling:picker'))
        self.assertEqual(resp.context['next_row']['lot'], due)
        self.assertEqual(resp.context['route_remaining'], 1)
        self.assertContains(resp, '1 check left')
        self.assertContains(resp, 'Checked recently (1)')

    def test_search_does_not_change_the_daily_route_progress(self):
        baseline = self.client.get(reverse('sampling:picker'))
        response = self.client.get(reverse('sampling:picker'), {'q': 'no-matching-lot'})
        self.assertEqual(response.context['rows'], [])
        for key in ('route_total', 'route_done', 'route_remaining', 'route_percent', 'next_row'):
            self.assertEqual(response.context[key], baseline.context[key])
        self.assertContains(response, 'No lots in storage match.')

    def test_submit_creates_sample_and_pending_photos(self):
        resp = self.client.post(reverse('sampling:capture', args=[self.lot.pk]), {
            'photo': SimpleUploadedFile('a.jpg', synthetic_photo(), content_type='image/jpeg'),
            'photo2': SimpleUploadedFile('b.jpg', synthetic_photo(), content_type='image/jpeg'),
            'foreman_color': 'S', 'foreman_pack_within_weeks': '3', 'decay_count': '1',
            'selection_method': 'across_bins', 'sampled_bins_count': '4',
            'soft_count': '2', 'shrivel_count': '1', 'chilling_injury_count': '0',
            'rind_breakdown_count': '1', 'firmness_score': '3', 'notes': 'soft ends',
        })
        sample = Sample.objects.get()
        self.assertRedirects(resp, reverse('sampling:sample_status', args=[sample.pk]))
        self.assertEqual(sample.sampled_by, self.foreman)
        self.assertEqual(sample.foreman_color, Color.SILVER)
        self.assertEqual(sample.foreman_pack_within_weeks, 3)
        self.assertEqual(sample.decay_count, 1)
        self.assertEqual(sample.selection_method, Sample.SelectionMethod.ACROSS_BINS)
        self.assertEqual(sample.sampled_bins_count, 4)
        self.assertEqual(sample.soft_count, 2)
        self.assertEqual(sample.shrivel_count, 1)
        self.assertEqual(sample.rind_breakdown_count, 1)
        self.assertEqual(sample.firmness_score, 3)
        self.assertEqual(sample.fruit_count, 10)
        self.assertEqual(sample.photos.count(), 2)
        self.assertTrue(all(p.status == SamplePhoto.Status.PENDING for p in sample.photos.all()))
        resp = self.client.get(reverse('sampling:picker'))
        self.assertContains(resp, 'Sampled today')

    def test_holdout_requires_result_and_failure_reason(self):
        base = {
            'photo': SimpleUploadedFile('a.jpg', synthetic_photo(), content_type='image/jpeg'),
            'foreman_color': 'S', 'foreman_pack_within_weeks': '3', 'decay_count': '0',
            'is_holdout': 'on', 'marketability': 'fail',
        }
        resp = self.client.post(reverse('sampling:capture', args=[self.lot.pk]), base)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Select the limiting reason')
        self.assertEqual(Sample.objects.count(), 0)

        base['photo'] = SimpleUploadedFile('b.jpg', synthetic_photo(), content_type='image/jpeg')
        base['failure_reason'] = 'decay'
        resp = self.client.post(reverse('sampling:capture', args=[self.lot.pk]), base)
        sample = Sample.objects.get()
        self.assertRedirects(resp, reverse('sampling:sample_status', args=[sample.pk]))
        self.assertEqual(sample.purpose, Sample.Purpose.HOLDOUT)
        self.assertEqual(sample.marketability, Sample.Marketability.FAIL)
        self.assertEqual(sample.failure_reason, Sample.FailureReason.DECAY)
        self.assertEqual(sample.selection_method, Sample.SelectionMethod.UNKNOWN)

    def test_missing_photo_or_taps_is_rejected(self):
        resp = self.client.post(reverse('sampling:capture', args=[self.lot.pk]), {'foreman_color': 'S', 'foreman_pack_within_weeks': '3', 'decay_count': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Sample.objects.count(), 0)

    def test_fake_image_is_rejected_before_storage(self):
        resp = self.client.post(reverse('sampling:capture', args=[self.lot.pk]), {
            'photo': SimpleUploadedFile('attack.html', b'<script>alert(1)</script>', content_type='image/jpeg'),
            'foreman_color': 'S', 'foreman_pack_within_weeks': '3', 'decay_count': '0',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'not a readable image')
        self.assertEqual(Sample.objects.count(), 0)

    def test_other_plant_lot_is_hidden(self):
        self.assertEqual(self.client.get(reverse('sampling:capture', args=[self.other.pk])).status_code, 404)

    def test_packed_lot_opens_holdout_assessment(self):
        self.lot.status = Lot.Status.PACKED
        self.lot.packed_date = date.today()
        self.lot.save()
        resp = self.client.get(reverse('sampling:capture', args=[self.lot.pk]))
        self.assertContains(resp, 'Record only the retained shelf-life holdout group')

    def test_photo_view_requires_login_and_plant(self):
        sample = Sample.objects.create(lot=self.lot, foreman_color='S', foreman_pack_within_weeks=1)
        photo = SamplePhoto.objects.create(sample=sample, image=SimpleUploadedFile('a.jpg', synthetic_photo(n_fruit=2), content_type='image/jpeg'))
        resp = self.client.get(reverse('sampling:photo', args=[photo.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/jpeg')
        body = b''.join(resp.streaming_content)  # consume so the file handle closes (Windows tempdir cleanup)
        resp.close()
        self.assertTrue(body.startswith(b'\xff\xd8'))
        self.client.logout()
        self.assertEqual(self.client.get(reverse('sampling:photo', args=[photo.pk])).status_code, 302)
