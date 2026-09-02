"""Photo scoring pipeline: board detection, color correction, fruit
segmentation, per-fruit CIELAB and Citrus Color Index.

Pure functions on images (score_image) plus one Django-aware wrapper
(score_photo) that reads a SamplePhoto from storage, stores the result and
kicks off a prediction rebuild for the lot. Runs in `manage.py score_photos`,
never inside a request.

    CCI = 1000 * a / (L * b)     (Jimenez-Cuesta et al. 1981)

Negative CCI is green, near zero is the color break, positive is yellow.
"""

import io
import logging
import math

import numpy as np

from . import board

logger = logging.getLogger(__name__)

PIPELINE_VERSION = 'v1-aruco-cci-2026.09'

MAX_DETECT_SIDE = 2400        # downscale huge phone photos before detection
MIN_MARKERS = 3               # homography from 3 markers is plenty; 4 is better
SAT_MIN, VAL_MIN = 60, 70     # HSV thresholds separating fruit from matte black
# One lemon on the 1200x900 canvas is ~0.6-1.7% of the area (2-3 in across).
# Anything above 2.5% is two touching fruit: dropped, so the count comes up
# short and the foreman is asked to retake with the fruit spaced out.
MIN_BLOB_FRAC, MAX_BLOB_FRAC = 0.0025, 0.025
MAX_FRUIT = 10
ERODE_FRACTION = 0.15
THUMB_SIZE = 320


class ScoringError(Exception):
    def __init__(self, message, card_detected=False, fruit_detected=0, **extra):
        super().__init__(message)
        self.card_detected = card_detected
        self.fruit_detected = fruit_detected
        self.extra = extra


def decode_image(data):
    import cv2

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ScoringError('could not decode image')
    h, w = img.shape[:2]
    scale = MAX_DETECT_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def detect_board(img):
    """Find the ArUco markers and return the homography to the canvas plus
    the list of marker ids seen."""
    import cv2

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(board.aruco_dictionary(), params)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None:
        raise ScoringError('reference board not found (no ArUco markers detected)')
    src, dst, seen = [], [], []
    for quad, mid in zip(corners, ids.flatten()):
        mid = int(mid)
        if mid not in board.MARKER_POSITIONS_IN:
            continue
        seen.append(mid)
        src.extend(quad.reshape(4, 2))
        dst.extend(board.marker_corners_canvas(mid))
    if len(seen) < MIN_MARKERS:
        raise ScoringError(f'reference board not found (only markers {sorted(seen)} detected, need {MIN_MARKERS})')
    H, _ = cv2.findHomography(np.array(src, dtype=np.float32), np.array(dst, dtype=np.float32), cv2.RANSAC, 5.0)
    if H is None:
        raise ScoringError('reference board found but could not be rectified')
    return H, sorted(seen)


def warp_to_canvas(img, H):
    import cv2

    return cv2.warpPerspective(img, H, (board.CANVAS_W, board.CANVAS_H), flags=cv2.INTER_AREA)


def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def _patch_mean_linear_rgb(canvas_lin_rgb, rect):
    x, y, w, h = rect
    # central 60% of the patch avoids print edges and lamination glare lines
    mx, my = int(w * 0.2), int(h * 0.2)
    region = canvas_lin_rgb[y + my:y + h - my, x + mx:x + w - mx]
    return region.reshape(-1, 3).mean(axis=0)


def color_correct(canvas_bgr):
    """Fit a 3x3 linear map from measured to reference color on the nine
    patches and apply it to the whole canvas. The fit is done in linear light
    (sRGB de-gammaed), where a camera's white-balance error really is a
    linear operation. Returns (corrected_bgr, info). If the fit is
    degenerate the image is returned uncorrected and info says so."""
    lin = _srgb_to_linear(canvas_bgr[:, :, ::-1].astype(np.float64) / 255.0)
    measured, reference = [], []
    for p in board.patches():
        measured.append(_patch_mean_linear_rgb(lin, p['rect']))
        reference.append(_srgb_to_linear(np.array(p['ref_rgb'], dtype=np.float64) / 255.0))
    M = np.array(measured)
    R = np.array(reference)
    A, _, rank, sv = np.linalg.lstsq(M, R, rcond=None)
    cond = float(sv[0] / sv[-1]) if sv[-1] > 0 else math.inf
    residual = float(np.sqrt(np.mean((M @ A - R) ** 2)))
    info = {
        'patch_measured_srgb': [[round(float(v), 4) for v in row] for row in _linear_to_srgb(M)],
        'matrix_linear': [[round(float(v), 5) for v in row] for row in A.T],
        'condition': round(cond, 2) if math.isfinite(cond) else None,
        'residual_rms_linear': round(residual, 4),
        'applied': bool(rank == 3 and cond < 1e3 and residual < 0.15),
    }
    if not info['applied']:
        return canvas_bgr, info
    corrected = _linear_to_srgb((lin.reshape(-1, 3) @ A).reshape(lin.shape))
    return (corrected[:, :, ::-1] * 255).round().astype(np.uint8), info


def segment_fruit(canvas_bgr):
    """Return a list of (mask, stats) for up to MAX_FRUIT blobs, largest first."""
    import cv2

    hsv = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] >= SAT_MIN) & (hsv[:, :, 2] >= VAL_MIN)).astype(np.uint8) * 255
    zone = np.zeros_like(mask)
    x0, y0, x1, y1 = board.fruit_zone_px()
    zone[y0:y1, x0:x1] = 255
    mask = cv2.bitwise_and(mask, zone)
    # Open only. A close step would bridge fruit that sit close together into
    # one blob; specular holes inside a fruit are handled by the erode + median.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    canvas_area = board.CANVAS_W * board.CANVAS_H
    blobs = []
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if MIN_BLOB_FRAC * canvas_area <= area <= MAX_BLOB_FRAC * canvas_area:
            blobs.append((i, area, centroids[i]))
    blobs.sort(key=lambda b: -b[1])
    blobs = blobs[:MAX_FRUIT]
    # reading order: top row left-to-right, then next row
    blobs.sort(key=lambda b: (round(b[2][1] / (board.DPI * 2.0)), b[2][0]))
    return [((labels == i).astype(np.uint8), {'area': area, 'cx': float(c[0]), 'cy': float(c[1])}) for i, area, c in blobs]


def measure_fruit(canvas_bgr, blobs):
    import cv2

    lab_img = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2Lab).astype(np.float64)
    lab_img[:, :, 0] *= 100.0 / 255.0
    lab_img[:, :, 1] -= 128.0
    lab_img[:, :, 2] -= 128.0
    per_lab, per_cci = [], []
    for mask, st in blobs:
        r_eq = math.sqrt(st['area'] / math.pi)
        k = max(1, int(round(ERODE_FRACTION * r_eq)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
        eroded = cv2.erode(mask, kernel)
        if eroded.sum() == 0:
            eroded = mask
        pix = lab_img[eroded.astype(bool)]
        L, a, b = (float(np.median(pix[:, i])) for i in range(3))
        per_lab.append([round(L, 2), round(a, 2), round(b, 2)])
        if abs(L) < 1e-6 or abs(b) < 1.0:
            per_cci.append(None)
        else:
            per_cci.append(round(1000.0 * a / (L * b), 3))
    return per_lab, per_cci


def make_thumbnail(data, size=THUMB_SIZE):
    from PIL import Image, ImageOps

    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im).convert('RGB')
    im.thumbnail((size, size))
    out = io.BytesIO()
    im.save(out, format='JPEG', quality=80)
    return out.getvalue()


def score_image(data, min_fruit=6):
    """Run the full pipeline on encoded image bytes. Returns the result dict
    or raises ScoringError with whatever was measured before failing."""
    img = decode_image(data)
    H, markers = detect_board(img)
    canvas = warp_to_canvas(img, H)
    corrected, correction = color_correct(canvas)
    blobs = segment_fruit(corrected)
    if len(blobs) < min_fruit:
        raise ScoringError(
            f'only {len(blobs)} fruit found (need {min_fruit}); space the fruit out and retake',
            card_detected=True, fruit_detected=len(blobs), markers=markers, correction=correction,
        )
    per_lab, per_cci = measure_fruit(corrected, blobs)
    valid = [c for c in per_cci if c is not None]
    if len(valid) < min_fruit:
        raise ScoringError(
            f'{len(blobs)} fruit found but only {len(valid)} gave a usable color',
            card_detected=True, fruit_detected=len(blobs), markers=markers, correction=correction,
        )
    return {
        'card_detected': True,
        'markers': markers,
        'fruit_detected': len(blobs),
        'per_fruit_lab': per_lab,
        'per_fruit_cci': per_cci,
        'mean_cci': round(float(np.mean(valid)), 3),
        'std_cci': round(float(np.std(valid)), 3),
        'correction': correction,
        'blob_centers': [[round(st['cx'] / board.DPI, 2), round(st['cy'] / board.DPI, 2)] for _, st in blobs],
    }


def score_photo(photo, settings=None, rebuild=True):
    """Score one SamplePhoto in place. Returns the resulting status."""
    from django.core.files.base import ContentFile

    from lots.models import ModelSettings

    from .models import SamplePhoto

    settings = settings or ModelSettings.get()
    try:
        with photo.image.open('rb') as fh:
            data = fh.read()
    except Exception as e:  # noqa: BLE001
        error = f'could not read photo from storage: {e}'
        if photo.attempt_count < 3:
            photo.mark_retry(error)
        else:
            photo.mark_failed(error, quality_ok=False)
        return photo.status

    try:
        if not photo.thumb:
            photo.thumb.save(f'thumb-{photo.pk}.jpg', ContentFile(make_thumbnail(data)), save=False)
    except Exception as e:  # noqa: BLE001
        logger.warning('thumbnail failed for photo %s: %s', photo.pk, e)

    try:
        result = score_image(data, min_fruit=settings.min_fruit_for_score)
    except ScoringError as e:
        photo.mark_failed(
            str(e),
            card_detected=e.card_detected,
            fruit_detected=e.fruit_detected,
            pipeline_version=PIPELINE_VERSION,
            quality_ok=False,
            quality_warnings=[str(e)],
            scoring_metadata={
                'markers': e.extra.get('markers', []),
                'correction': e.extra.get('correction', {}),
            },
        )
    except Exception as e:  # noqa: BLE001 - never let one bad photo stop the job
        logger.exception('pipeline error on photo %s', photo.pk)
        photo.mark_failed(
            f'pipeline error: {e}',
            pipeline_version=PIPELINE_VERSION,
            quality_ok=False,
            quality_warnings=['unexpected scoring pipeline error'],
        )
    else:
        photo.mark_scored(result, PIPELINE_VERSION)

    if rebuild and photo.status == SamplePhoto.Status.SCORED and photo.quality_ok:
        from forecast.services import rebuild_for_lot

        rebuild_for_lot(photo.sample.lot, settings=settings)
    return photo.status
