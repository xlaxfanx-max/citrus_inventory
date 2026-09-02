"""The v1 drift model: a straight line through a lot's mean CCI over time.

Pure functions, no database. `predict` takes the points and settings and
returns everything a Prediction row needs, including the inputs used.

Rules (docs/v1-build-spec.md, "Drift and prediction") plus two gaps the
spec leaves open, resolved here:

* A fitted slope at or below MIN_SLOPE (flat or greening) cannot cross the
  yellow threshold. We fall back to the prior drift for the receiving color,
  anchored at the latest observed CCI, and mark confidence low.
* If the line takes longer than settings.max_horizon_days to reach yellow,
  the yellow date is capped at that horizon and the inputs say so.
"""

from datetime import timedelta

MODEL_VERSION = 'v1-linear-cci'
MIN_SLOPE = 0.005          # CCI per day; below this the line is treated as flat
MAX_FIT_POINTS = 5
HIGH_CONF_MIN_POINTS = 4
HIGH_CONF_MIN_R2 = 0.7


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


def predict(*, as_of, receive_date, receiving_color, points, decay_samples, settings):
    """points: [(days_since_receive, mean_cci), ...] in any order.
    Returns a dict with the Prediction fields plus 'inputs'."""
    day_now = (as_of - receive_date).days
    yellow = settings.yellow_threshold
    prior = settings.prior_drift(receiving_color)
    pts = sorted(points)
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
            cci_now = last_cci + prior * (day_now - last_day)
            confidence = 'low'
            method = 'prior_after_flat_fit'
            notes.append(f'fitted slope {slope:.4f}/day at or below {MIN_SLOPE}; using prior {prior}')
        fit = {'slope': round(slope, 5), 'intercept': round(intercept, 4), 'r2': round(r2, 4), 'n': n}
    elif len(pts) == 1:
        last_day, last_cci = pts[0]
        drift = prior
        cci_now = last_cci + prior * (day_now - last_day)
        confidence = 'low'
        method = 'prior_from_one_point'
        fit = None
    else:
        drift = prior
        cci_now = settings.start_cci(receiving_color) + prior * day_now
        confidence = 'low'
        method = 'prior_from_receiving_color'
        fit = None
        notes.append('no scored samples yet; start CCI assumed from receiving color')

    horizon_exceeded = False
    if cci_now >= yellow:
        days_to_yellow = 0
        notes.append('already at or past yellow threshold')
    else:
        days_to_yellow = (yellow - cci_now) / drift if drift > 0 else float('inf')
        if days_to_yellow > settings.max_horizon_days:
            notes.append(f'yellow is beyond the {settings.max_horizon_days}-day forecast horizon')
            horizon_exceeded = True
    if horizon_exceeded:
        predicted_yellow = None
        pack_by = None
    else:
        predicted_yellow = as_of + timedelta(days=int(round(days_to_yellow)))
        pack_by = predicted_yellow - timedelta(days=settings.buffer_days)

    decay_rate, decay_flag = decay_summary(decay_samples, settings.decay_flag_pct)

    return {
        'cci_now': round(cci_now, 3),
        'stage': settings.stage_for(cci_now),
        'drift_per_day': round(drift, 5),
        'predicted_yellow_date': predicted_yellow,
        'pack_by_date': pack_by,
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
            'start_cci': settings.start_cci(receiving_color),
            'thresholds': settings.thresholds_dict(),
            'buffer_days': settings.buffer_days,
            'max_horizon_days': settings.max_horizon_days,
            'decay_samples': [[d, f] for d, f in list(decay_samples)[-2:]],
            'decay_flag_pct': settings.decay_flag_pct,
            'horizon_exceeded': horizon_exceeded,
            'notes': notes,
        },
    }
