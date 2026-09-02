"""Geometry and reference colors of the sampling board.

One source of truth shared by the scoring pipeline (sampling/scoring.py),
the printable design (hardware/make_board.py -> hardware/board.svg) and the
synthetic test images. Change the layout here and both the print file and
the detector move together.

Board: 24 x 18 inch matte black. Four ArUco markers (DICT_4X4_50, ids 0-3)
in the corners, six grey patches along the top edge, three color patches
(green, silver-yellow, yellow) along the bottom edge. Fruit go in the
middle. The detector warps a photo to a 1200 x 900 canvas (50 px per inch).
"""

import math

import numpy as np

DPI = 50
BOARD_W_IN, BOARD_H_IN = 24.0, 18.0
CANVAS_W, CANVAS_H = int(BOARD_W_IN * DPI), int(BOARD_H_IN * DPI)

ARUCO_DICT_NAME = 'DICT_4X4_50'
MARKER_SIZE_IN = 2.0
MARKER_INSET_IN = 0.5
# White margin printed around each marker. ArUco finds a marker by its black
# border, so on a black board the marker MUST sit on a white pad or it is
# invisible to the detector.
MARKER_QUIET_IN = 0.3
# id -> (x, y) of the marker's top-left corner in inches. Order TL, TR, BR, BL.
MARKER_POSITIONS_IN = {
    0: (MARKER_INSET_IN, MARKER_INSET_IN),
    1: (BOARD_W_IN - MARKER_INSET_IN - MARKER_SIZE_IN, MARKER_INSET_IN),
    2: (BOARD_W_IN - MARKER_INSET_IN - MARKER_SIZE_IN, BOARD_H_IN - MARKER_INSET_IN - MARKER_SIZE_IN),
    3: (MARKER_INSET_IN, BOARD_H_IN - MARKER_INSET_IN - MARKER_SIZE_IN),
}

PATCH_W_IN, PATCH_H_IN = 2.0, 1.5
GREY_LSTARS = [20, 35, 50, 65, 80, 95]
GREY_ROW_Y_IN = 0.5
GREY_X0_IN, GREY_STEP_IN = 4.0, 2.8

# Nominal print targets (sRGB 0-255). The printed board will not match these
# exactly; measure the laminated board once under the station light and put
# the measured values here before calibration week.
COLOR_PATCHES = [
    ('green', (70, 130, 60)),
    ('silver_yellow', (205, 205, 140)),
    ('yellow', (240, 210, 40)),
]
COLOR_ROW_Y_IN = BOARD_H_IN - 0.5 - PATCH_H_IN
COLOR_X_IN = [8.0, 11.0, 14.0]

# Where fruit may sit (x0, y0, x1, y1) in inches. Everything outside is ignored
# by the segmenter, so patches and markers never count as fruit.
FRUIT_ZONE_IN = (0.5, GREY_ROW_Y_IN + PATCH_H_IN + 0.5, BOARD_W_IN - 0.5, COLOR_ROW_Y_IN - 0.5)


def px(inches):
    return int(round(inches * DPI))


def lstar_to_srgb8(lstar):
    """Neutral grey with the given CIE L* as an sRGB 8-bit value."""
    fy = (lstar + 16.0) / 116.0
    y = fy ** 3 if fy ** 3 > 0.008856 else (fy - 16.0 / 116.0) / 7.787
    c = 1.055 * (y ** (1 / 2.4)) - 0.055 if y > 0.0031308 else 12.92 * y
    return int(round(max(0.0, min(1.0, c)) * 255))


def marker_corners_canvas(marker_id):
    """Canvas-pixel corners of a marker in ArUco order: TL, TR, BR, BL."""
    x, y = MARKER_POSITIONS_IN[marker_id]
    s = MARKER_SIZE_IN
    return np.array(
        [[px(x), px(y)], [px(x + s), px(y)], [px(x + s), px(y + s)], [px(x), px(y + s)]],
        dtype=np.float32,
    )


def patches():
    """All nine reference patches: dicts with name, rect (x, y, w, h) in
    canvas px and ref_rgb (0-255)."""
    out = []
    for i, lstar in enumerate(GREY_LSTARS):
        g = lstar_to_srgb8(lstar)
        out.append({
            'name': f'grey_{lstar}',
            'rect': (px(GREY_X0_IN + i * GREY_STEP_IN), px(GREY_ROW_Y_IN), px(PATCH_W_IN), px(PATCH_H_IN)),
            'ref_rgb': (g, g, g),
        })
    for (name, rgb), x_in in zip(COLOR_PATCHES, COLOR_X_IN):
        out.append({
            'name': name,
            'rect': (px(x_in), px(COLOR_ROW_Y_IN), px(PATCH_W_IN), px(PATCH_H_IN)),
            'ref_rgb': rgb,
        })
    return out


def fruit_zone_px():
    x0, y0, x1, y1 = FRUIT_ZONE_IN
    return px(x0), px(y0), px(x1), px(y1)


def aruco_dictionary():
    import cv2

    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, ARUCO_DICT_NAME))


def marker_bits(marker_id):
    """The marker as a 6x6 array of 0/1 cells (1 = white), border included."""
    import cv2

    img = cv2.aruco.generateImageMarker(aruco_dictionary(), marker_id, 6)
    return (img > 127).astype(np.uint8)


def render_canvas(fruit=None):
    """Render the ideal board as a BGR canvas. `fruit` is a list of
    (cx_in, cy_in, radius_in, (r, g, b)) circles for synthetic test images."""
    import cv2

    canvas = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)
    canvas[:] = (12, 12, 12)  # matte black is not pure zero
    size = px(MARKER_SIZE_IN)
    q = px(MARKER_QUIET_IN)
    for mid, (x, y) in MARKER_POSITIONS_IN.items():
        marker = cv2.aruco.generateImageMarker(aruco_dictionary(), mid, size)
        x0, y0 = px(x), px(y)
        canvas[max(0, y0 - q):y0 + size + q, max(0, x0 - q):x0 + size + q] = (255, 255, 255)
        canvas[y0:y0 + size, x0:x0 + size] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    for p in patches():
        x, y, w, h = p['rect']
        r, g, b = p['ref_rgb']
        cv2.rectangle(canvas, (x, y), (x + w, y + h), (b, g, r), thickness=-1)
    for cx, cy, rad, (r, g, b) in fruit or []:
        cv2.circle(canvas, (px(cx), px(cy)), px(rad), (b, g, r), thickness=-1)
    return canvas


def default_fruit_layout(n=10, spacing_in=4.0, row_gap_in=4.5):
    """Centers for n fruit in two rows inside the fruit zone, in inches.
    Real lemons are 2-3 in across; 4 in spacing leaves a clear gap."""
    x0, y0, x1, y1 = FRUIT_ZONE_IN
    per_row = math.ceil(n / 2)
    row_w = (per_row - 1) * spacing_in
    cx0 = (x0 + x1) / 2 - row_w / 2
    cy_top = (y0 + y1) / 2 - row_gap_in / 2
    cy_bot = (y0 + y1) / 2 + row_gap_in / 2
    out = []
    for i in range(n):
        row, col = divmod(i, per_row)
        out.append((cx0 + col * spacing_in, cy_top if row == 0 else cy_bot))
    return out
