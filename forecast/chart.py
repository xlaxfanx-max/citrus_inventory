"""Server-rendered SVG of a lot's CCI over time: stage bands, the scored
points, the model's line and the pack-by / today markers. No JS."""

from django.utils.html import escape
from django.utils.safestring import mark_safe

W, H = 760, 300
ML, MR, MT, MB = 46, 16, 14, 30
BAND_FILL = {'DG': '#2e5d2a', 'LG': '#7ba05b', 'S': '#c9d1b8', 'Y': '#e3c545'}


def _scale(domain, rng):
    d0, d1 = domain
    r0, r1 = rng
    span = (d1 - d0) or 1

    def f(v):
        return r0 + (v - d0) / span * (r1 - r0)

    return f


def cci_chart_svg(lot, points, prediction, settings, today):
    day_today = (today - lot.receive_date).days
    xs = [p['day'] for p in points]
    ys = [p['cci'] for p in points]
    x_max = max([day_today + 14, 60] + [x + 14 for x in xs])
    pack_day = yellow_day = None
    if prediction:
        if prediction.pack_by_date:
            pack_day = (prediction.pack_by_date - lot.receive_date).days
        if prediction.predicted_yellow_date:
            yellow_day = (prediction.predicted_yellow_date - lot.receive_date).days
            x_max = max(x_max, yellow_day + 7)
    x_max = min(x_max, day_today + 400)
    y_min = min([-14.0] + [y - 2 for y in ys])
    y_max = max([6.0] + [y + 2 for y in ys])

    sx = _scale((0, x_max), (ML, W - MR))
    sy = _scale((y_min, y_max), (H - MB, MT))

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="CCI over time for lot {escape(lot.lot_no)}" '
           f'style="max-width:{W}px;font:12px system-ui,sans-serif">']
    # stage bands
    edges = [y_min, settings.cci_dg_max, settings.cci_lg_max, settings.cci_s_max, y_max]
    for (lo, hi), code in zip(zip(edges, edges[1:]), ['DG', 'LG', 'S', 'Y']):
        lo_c, hi_c = max(lo, y_min), min(hi, y_max)
        if hi_c <= lo_c:
            continue
        out.append(f'<rect x="{ML}" y="{sy(hi_c):.1f}" width="{W - ML - MR}" height="{sy(lo_c) - sy(hi_c):.1f}" fill="{BAND_FILL[code]}" opacity="0.16"/>')
        out.append(f'<text x="{W - MR - 4}" y="{sy(hi_c) + 13:.1f}" text-anchor="end" fill="#555">{code}</text>')
    # axes
    out.append(f'<line x1="{ML}" y1="{H - MB}" x2="{W - MR}" y2="{H - MB}" stroke="#888"/>')
    out.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{H - MB}" stroke="#888"/>')
    step = 14 if x_max <= 200 else 28
    for d in range(0, int(x_max) + 1, step):
        out.append(f'<text x="{sx(d):.1f}" y="{H - MB + 16}" text-anchor="middle" fill="#666">{d}d</text>')
    ystep = 2 if (y_max - y_min) <= 24 else 4
    v = int(y_min // ystep * ystep)
    while v <= y_max:
        if v >= y_min:
            out.append(f'<text x="{ML - 6}" y="{sy(v) + 4:.1f}" text-anchor="end" fill="#666">{v}</text>')
        v += ystep
    out.append(f'<text x="{ML - 36}" y="{MT + 2}" fill="#666">CCI</text>')
    # threshold lines
    for t in (settings.cci_dg_max, settings.cci_lg_max, settings.cci_s_max):
        if y_min < t < y_max:
            out.append(f'<line x1="{ML}" y1="{sy(t):.1f}" x2="{W - MR}" y2="{sy(t):.1f}" stroke="#999" stroke-dasharray="3 4"/>')
    # model line
    if prediction:
        inputs = prediction.inputs or {}
        fit = inputs.get('fit')
        if fit and inputs.get('method') == 'ols':
            x0 = min(xs) if xs else 0
            y0 = fit['intercept'] + fit['slope'] * x0
            y1 = fit['intercept'] + fit['slope'] * x_max
        else:
            x0 = day_today
            y0 = prediction.cci_now
            y1 = y0 + prediction.drift_per_day * (x_max - x0)
        out.append(f'<line x1="{sx(x0):.1f}" y1="{sy(y0):.1f}" x2="{sx(x_max):.1f}" y2="{sy(y1):.1f}" stroke="#3a6b35" stroke-width="2"/>')
    # today and pack by
    out.append(f'<line x1="{sx(day_today):.1f}" y1="{MT}" x2="{sx(day_today):.1f}" y2="{H - MB}" stroke="#333" stroke-dasharray="4 3"/>')
    out.append(f'<text x="{sx(day_today) + 4:.1f}" y="{MT + 12}" fill="#333">today</text>')
    if pack_day is not None and 0 <= pack_day <= x_max:
        out.append(f'<line x1="{sx(pack_day):.1f}" y1="{MT}" x2="{sx(pack_day):.1f}" y2="{H - MB}" stroke="#a13c2a" stroke-width="2"/>')
        out.append(f'<text x="{sx(pack_day) + 4:.1f}" y="{MT + 26}" fill="#a13c2a">pack by</text>')
    if yellow_day is not None and 0 <= yellow_day <= x_max:
        out.append(f'<circle cx="{sx(yellow_day):.1f}" cy="{sy(settings.cci_s_max):.1f}" r="5" fill="#e3c545" stroke="#333"/>')
    # points
    for p in points:
        out.append(f'<circle cx="{sx(p["day"]):.1f}" cy="{sy(p["cci"]):.1f}" r="5" fill="#22301f"><title>day {p["day"]}: CCI {p["cci"]:.2f}</title></circle>')
    if not points:
        out.append(f'<text x="{(ML + W - MR) / 2:.0f}" y="{(MT + H - MB) / 2:.0f}" text-anchor="middle" fill="#666">No scored samples yet. Line uses the prior drift for a {lot.get_receiving_color_display().lower()} lot.</text>')
    out.append('</svg>')
    return mark_safe(''.join(out))
