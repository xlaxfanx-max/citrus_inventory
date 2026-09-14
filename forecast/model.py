"""The v1 drift model: a straight line through a lot's mean CCI over time.

Pure functions, no database. `predict` takes the points and settings and
returns everything a Prediction row needs, including the inputs used.

Rules (docs/v1-build-spec.md, "Drift and prediction") plus two gaps the
spec leaves open, resolved here:

* A fitted slope at or below MIN_SLOPE (flat or greening) cannot cross the
  yellow threshold. We fall back to the prior drift for the receiving color,
  anchored at the latest observed CCI, and mark confidence low.
* Threshold dates are anchored to receipt/observations, including crossings
  in the past. Passing time alone must never move a deadline forward.
* Forecasts beyond the horizon have no date. Old observations lower support.
* Prior drift rates were set for a 55 F (12.8 C) room. When the lot's room
  setpoint is known, the prior is scaled by the bell-shaped temperature
  response of lemon degreening (Mitalo et al. 2020, J Exp Bot: fastest near
  15 C, suppressed at 5 C, halted near 25 C). A fitted slope already reflects
  the room the lot sat in and is never scaled.
* The elapsed term of a prior path integrates that factor over the lot's
  recorded room history (`exposure`), so a room move with no new sample never
  changes cci_now. Days with no recorded room use the 55 F reference; the
  current room's factor applies only from today forward.
* Hold budget. Every color stage has a budget of days a lot can be held
  there and stay marketable (ModelSettings.hold_days_*). The budget starts on
  the day the CCI path entered the stage, is spent one day per day, faster in
  warm rooms (hold_warm_multiplier) and by observed decay
  (hold_decay_days_per_pct). Once a lot is yellow the pack-by date is in the
  past by construction, so the hold budget becomes the operative date; before
  yellow, whichever of pack-by and hold-until comes first is binding.
"""

import math
from datetime import timedelta

MODEL_VERSION = 'v1.4-hold-budget'
MIN_SLOPE = 0.005          # CCI per day; below this the line is treated as flat
MAX_FIT_POINTS = 5
HIGH_CONF_MIN_POINTS = 4
HIGH_CONF_MIN_R2 = 0.7

TEMP_PEAK_C = 15.0         # fastest degreening
TEMP_WIDTH_C = 7.0         # Gaussian width: ~0.13x at 5 C and 25 C, ~0.9x at 12.8 C
PRIOR_REFERENCE_C = 12.8   # the room temperature the priors in ModelSettings describe (55 F)


def temperature_rate_factor(temp_c):
    """Relative degreening speed at temp_c, 1.0 at the 15 C peak."""
    return math.exp(-((temp_c - TEMP_PEAK_C) / TEMP_WIDTH_C) ** 2)


def prior_at_temperature(prior, temp_c):
    """Scale a 55 F prior to the room the lot is actually in."""
    if temp_c is None:
        return prior
    return prior * temperature_rate_factor(temp_c) / temperature_rate_factor(PRIOR_REFERENCE_C)


def _reference_factor(temp_c):
    return temperature_rate_factor(temp_c) / temperature_rate_factor(PRIOR_REFERENCE_C)


def exposure_segments(exposure, use_temperature):
    """(start_day, end_day, factor) pieces from [(start_day, end_day, temp_c)].
    Unknown setpoints and disabled temperature response both give factor 1."""
    segments = []
    for start, end, temp_c in exposure or []:
        if end <= start:
            continue
        factor = _reference_factor(temp_c) if (use_temperature and temp_c is not None) else 1.0
        segments.append((float(start), float(end), factor))
    return sorted(segments)


def _rate_pieces(base_prior, start, end, segments, day_now, current_factor):
    """Piecewise-constant CCI/day between start and end: recorded history up
    to day_now (gaps at the reference rate), then the current room's rate."""
    pieces = []
    cursor = start
    hist_end = min(end, day_now)
    for seg_start, seg_end, factor in segments:
        seg_start, seg_end = max(seg_start, cursor), min(seg_end, hist_end)
        if seg_end <= seg_start:
            continue
        if seg_start > cursor:
            pieces.append((cursor, seg_start, base_prior))
        pieces.append((seg_start, seg_end, base_prior * factor))
        cursor = seg_end
    if hist_end > cursor:
        pieces.append((cursor, hist_end, base_prior))
        cursor = hist_end
    if end > max(cursor, day_now):
        pieces.append((max(cursor, day_now), end, base_prior * current_factor))
    return pieces


def prior_gain(base_prior, start, end, segments, day_now, current_factor):
    """CCI added by the prior between two days since receipt."""
    if end <= start:
        return 0.0
    return sum((b - a) * rate for a, b, rate in _rate_pieces(base_prior, start, end, segments, day_now, current_factor))


def prior_crossing_day(base_prior, anchor_day, anchor_cci, target, segments, day_now, current_factor):
    """Day since receipt on which the prior path reaches target. Walks the
    recorded history forward from the anchor and then extends at the current
    room's rate; inf when that rate is zero. An anchor already past the
    target extrapolates backward at the rate in force at the anchor."""
    need = target - anchor_cci
    if need <= 0:
        rate = next((r for a, b, r in _rate_pieces(base_prior, anchor_day, anchor_day + 1, segments, day_now, current_factor)), base_prior)
        return anchor_day + need / rate if rate > 0 else anchor_day
    for a, b, rate in _rate_pieces(base_prior, anchor_day, day_now, segments, day_now, current_factor):
        if rate > 0 and rate * (b - a) >= need:
            return a + need / rate
        need -= rate * (b - a)
    forward = base_prior * current_factor
    return max(anchor_day, day_now) + need / forward if forward > 0 else float('inf')


def hold_budget(*, stage, day_now, settings, method, slope, intercept, pts, base_prior,
                segments, current_factor, start_cci, exposure, decay_rate):
    """Days of hold budget left at day_now for a lot at `stage`.

    stage_entry_day is where the same CCI path (fitted line or walked prior)
    crossed the lower boundary of the current stage; a lot received at or
    above that boundary entered on day 0. Warm days in the stage spend
    (multiplier - 1) extra days each; observed decay removes a fixed number
    of days per percent."""
    thresholds = settings.thresholds_dict()
    boundary = {'LG': thresholds['dg_max'], 'S': thresholds['lg_max'], 'Y': thresholds['s_max']}.get(str(stage))
    if boundary is None:
        entry = 0.0
    elif method == 'ols':
        entry = (boundary - intercept) / slope if slope > 0 else 0.0
    else:
        anchor_day, anchor_cci = pts[-1] if pts else (0, start_cci)
        entry = prior_crossing_day(base_prior, anchor_day, anchor_cci, boundary, segments, day_now, current_factor)
    entry = min(max(0.0, float(entry)), float(day_now))
    warm_threshold = float(getattr(settings, 'warm_storage_temp_c', 13.0))
    warm_days = sum(
        max(0.0, min(float(end), float(day_now)) - max(float(start), entry))
        for start, end, temp_c in (exposure or [])
        if temp_c is not None and temp_c >= warm_threshold
    )
    multiplier = max(1.0, float(getattr(settings, 'hold_warm_multiplier', 1.0)))
    warm_extra = warm_days * (multiplier - 1.0)
    decay_penalty = decay_rate * 100.0 * float(getattr(settings, 'hold_decay_days_per_pct', 0.0))
    budget = settings.hold_days(stage)
    days_in_stage = day_now - entry
    remaining = budget - days_in_stage - warm_extra - decay_penalty
    return {
        'budget_days': budget,
        'stage_entry_day': round(entry, 2),
        'days_in_stage': round(days_in_stage, 1),
        'warm_days_in_stage': round(warm_days, 1),
        'warm_multiplier': multiplier,
        'warm_extra_days': round(warm_extra, 1),
        'decay_penalty_days': round(decay_penalty, 1),
        'days_remaining': int(math.floor(remaining)),
    }


def ols(xs, ys):
    """Ordinary least squares y = intercept + slope * x. Returns
    (slope, intercept, r2). r2 is 1.0 when there are exactly two points."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return 0.0, my, 0.0
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 if ss_tot == 0 else max(0.0, 1.0 - ss_res / ss_tot)
    return slope, intercept, r2


def decay_summary(samples, flag_pct):
    """samples: [(decay_count, fruit_count), ...] oldest to newest, at most
    the last two. Returns (rate 0-1, flag)."""
    samples = list(samples)[-2:]
    if not samples:
        return 0.0, False
    total_fruit = sum(f for _, f in samples)
    rate = sum(d for d, _ in samples) / total_fruit if total_fruit else 0.0
    rising = len(samples) == 2 and samples[1][0] > samples[0][0]
    return rate, bool(rate * 100 >= flag_pct or rising)


def predict(*, as_of, receive_date, receiving_color, points, decay_samples, settings, room_temp_c=None, exposure=None):
    """points: [(days_since_receive, mean_cci), ...] in any order.
    room_temp_c: current room setpoint; scales the prior drift from today forward.
    exposure: [(start_day, end_day, setpoint_c), ...] recorded room history in
    days since receipt; scales the prior over the elapsed term. Without it the
    elapsed term runs at the 55 F reference rate.
    Returns a dict with the Prediction fields plus 'inputs'."""
    day_now = (as_of - receive_date).days
    yellow = settings.yellow_threshold
    base_prior = settings.prior_drift(receiving_color)
    temperature_on = bool(getattr(settings, 'temperature_response', False))
    use_temperature = temperature_on and room_temp_c is not None
    current_factor = _reference_factor(room_temp_c) if use_temperature else 1.0
    prior = round(base_prior * current_factor, 5) if use_temperature else base_prior
    segments = exposure_segments(exposure, temperature_on)

    def elapsed_gain(anchor_day):
        return prior_gain(base_prior, anchor_day, day_now, segments, day_now, current_factor)

    # One independent visit-day per point. Extra photos/visits on the same day
    # must not increase support or overweight that day in the regression.
    by_day = {}
    for day, cci in points:
        if 0 <= day <= day_now:
            by_day.setdefault(day, []).append(cci)
    pts = sorted((day, sum(values) / len(values)) for day, values in by_day.items())
    notes = []

    if len(pts) >= 2:
        fit_pts = pts[-MAX_FIT_POINTS:]
        slope, intercept, r2 = ols([p[0] for p in fit_pts], [p[1] for p in fit_pts])
        n = len(fit_pts)
        if slope > MIN_SLOPE:
            drift = slope
            cci_now = intercept + slope * day_now
            confidence = 'high' if (n >= HIGH_CONF_MIN_POINTS and r2 > HIGH_CONF_MIN_R2) else 'med'
            method = 'ols'
        else:
            drift = prior
            last_day, last_cci = pts[-1]
            cci_now = last_cci + elapsed_gain(last_day)
            confidence = 'low'
            method = 'prior_after_flat_fit'
            notes.append(f'fitted slope {slope:.4f}/day at or below {MIN_SLOPE}; using prior {prior}')
        fit = {'slope': round(slope, 5), 'intercept': round(intercept, 4), 'r2': round(r2, 4), 'n': n}
    elif len(pts) == 1:
        last_day, last_cci = pts[0]
        drift = prior
        cci_now = last_cci + elapsed_gain(last_day)
        confidence = 'low'
        method = 'prior_from_one_point'
        fit = None
    else:
        drift = prior
        cci_now = settings.start_cci(receiving_color) + elapsed_gain(0)
        confidence = 'low'
        method = 'prior_from_receiving_color'
        fit = None
        notes.append('no scored samples yet; start CCI assumed from receiving color')

    last_sample_age = day_now - pts[-1][0] if pts else None
    stale = last_sample_age is not None and last_sample_age >= settings.sample_overdue_days
    if stale:
        confidence = 'low'
        notes.append(f'latest usable observation is {last_sample_age} days old; resample before acting')
    if use_temperature and method != 'ols':
        notes.append(f'prior drift scaled for a {room_temp_c:g} C room from today (x{prior / base_prior:.2f} vs 12.8 C)')
    if segments and method != 'ols':
        notes.append('elapsed prior integrated over recorded room history')
    # Compute a fixed crossing relative to receipt, rather than setting it to
    # today once yellow. For priors, walk the recorded history from the same
    # fixed observation anchor, then extend at the current room's rate.
    if method == 'ols':
        crossing_day = (yellow - intercept) / drift
    elif base_prior > 0:
        anchor_day, anchor_cci = pts[-1] if pts else (0, settings.start_cci(receiving_color))
        crossing_day = prior_crossing_day(base_prior, anchor_day, anchor_cci, yellow, segments, day_now, current_factor)
    else:
        crossing_day = float('inf')
    crossing_day = max(0, crossing_day)
    horizon_exceeded = crossing_day - day_now > settings.max_horizon_days
    if cci_now >= yellow:
        notes.append('at or past yellow threshold; crossing estimate is retained')
    if horizon_exceeded:
        notes.append(f'yellow is beyond the {settings.max_horizon_days}-day forecast horizon')
    if horizon_exceeded:
        predicted_yellow = None
        pack_by = None
    else:
        predicted_yellow = receive_date + timedelta(days=int(round(crossing_day)))
        pack_by = predicted_yellow - timedelta(days=settings.buffer_days)

    decay_rate, decay_flag = decay_summary(decay_samples, settings.decay_flag_pct)

    stage = settings.stage_for(cci_now)
    hold = hold_budget(
        stage=stage, day_now=day_now, settings=settings, method=method,
        slope=slope if method == 'ols' else 0.0, intercept=intercept if method == 'ols' else 0.0,
        pts=pts, base_prior=base_prior, segments=segments, current_factor=current_factor,
        start_cci=settings.start_cci(receiving_color), exposure=exposure, decay_rate=decay_rate,
    )
    stage_entry_date = receive_date + timedelta(days=int(round(hold['stage_entry_day'])))
    hold_until = as_of + timedelta(days=hold['days_remaining'])
    if cci_now >= yellow:
        notes.append(f"yellow since about {stage_entry_date.isoformat()}; {hold['days_remaining']} days of hold budget remain")

    return {
        'cci_now': round(cci_now, 3),
        'stage': stage,
        'drift_per_day': round(drift, 5),
        'predicted_yellow_date': predicted_yellow,
        'pack_by_date': pack_by,
        'stage_entry_date': stage_entry_date,
        'hold_days_remaining': hold['days_remaining'],
        'hold_until_date': hold_until,
        'decay_rate': round(decay_rate, 4),
        'decay_flag': decay_flag,
        'confidence': confidence,
        'model_version': MODEL_VERSION,
        'inputs': {
            'as_of': as_of.isoformat(),
            'receive_date': receive_date.isoformat(),
            'day_now': day_now,
            'receiving_color': str(receiving_color),
            'points': [[d, round(c, 3)] for d, c in pts],
            'fit': fit,
            'method': method,
            'prior_drift': prior,
            'prior_drift_at_55f': base_prior,
            'room_temp_c': room_temp_c,
            'temperature_factor': round(current_factor, 4) if use_temperature else None,
            'exposure': [[round(s, 3), round(e, 3), t] for s, e, t in (exposure or [])],
            'elapsed_prior_gain': round(elapsed_gain(pts[-1][0] if pts else 0), 4) if method != 'ols' else None,
            'hold': hold,
            'start_cci': settings.start_cci(receiving_color),
            'thresholds': settings.thresholds_dict(),
            'buffer_days': settings.buffer_days,
            'max_horizon_days': settings.max_horizon_days,
            'decay_samples': [[d, f] for d, f in list(decay_samples)[-2:]],
            'decay_flag_pct': settings.decay_flag_pct,
            'horizon_exceeded': horizon_exceeded,
            'last_usable_sample_age_days': last_sample_age,
            'sample_stale': stale,
            'sample_overdue_days': settings.sample_overdue_days,
            'support_definition': 'Heuristic trend support, not a calibrated probability of quality or shelf life.',
            'notes': notes,
        },
    }
