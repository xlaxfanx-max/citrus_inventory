"""Generate hardware/board.svg, the printable 24 x 18 inch sampling board.

    python hardware/make_board.py

Geometry and reference colors come from sampling/board.py so the print and
the detector can never disagree. Markers are drawn cell by cell from
cv2.aruco (DICT_4X4_50, ids 0-3), so the SVG is fully vector: print at 100%
on a matte black substrate, or print the marker and patch strips and mount
them on black board at the positions shown.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sampling import board  # noqa: E402


def rect(x, y, w, h, fill, extra=''):
    return f'<rect x="{x:.3f}in" y="{y:.3f}in" width="{w:.3f}in" height="{h:.3f}in" fill="{fill}" {extra}/>'


def text(x, y, s, size=0.14, fill='#777', anchor='start'):
    return f'<text x="{x:.3f}in" y="{y:.3f}in" font-family="Helvetica, Arial, sans-serif" font-size="{size}in" fill="{fill}" text-anchor="{anchor}">{s}</text>'


def main(out_path):
    W, H = board.BOARD_W_IN, board.BOARD_H_IN
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}in" height="{H}in" viewBox="0 0 {W} {H}">',
        f'<rect x="0" y="0" width="{W}" height="{H}" fill="#0c0c0c"/>',
    ]
    # markers, cell by cell
    cells = 6
    cell = board.MARKER_SIZE_IN / cells
    for mid, (mx, my) in board.MARKER_POSITIONS_IN.items():
        bits = board.marker_bits(mid)
        q = board.MARKER_QUIET_IN
        parts.append(f'<rect x="{mx - q:.3f}" y="{my - q:.3f}" width="{board.MARKER_SIZE_IN + 2 * q:.3f}" height="{board.MARKER_SIZE_IN + 2 * q:.3f}" fill="#fff"/>')
        parts.append(f'<rect x="{mx}" y="{my}" width="{board.MARKER_SIZE_IN}" height="{board.MARKER_SIZE_IN}" fill="#000"/>')
        for r in range(cells):
            for c in range(cells):
                if bits[r, c]:
                    parts.append(f'<rect x="{mx + c * cell:.4f}" y="{my + r * cell:.4f}" width="{cell:.4f}" height="{cell:.4f}" fill="#fff"/>')
        parts.append(f'<text x="{mx + board.MARKER_SIZE_IN / 2:.3f}" y="{my + board.MARKER_SIZE_IN + q + 0.18:.3f}" font-family="Helvetica, Arial, sans-serif" font-size="0.14" fill="#777" text-anchor="middle">id {mid}</text>')
    # patches
    for p in board.patches():
        x, y, w, h = (v / board.DPI for v in p['rect'])
        r, g, b = p['ref_rgb']
        parts.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" fill="rgb({r},{g},{b})"/>')
        label_y = y + h + 0.22 if y < H / 2 else y - 0.1
        parts.append(f'<text x="{x + w / 2:.3f}" y="{label_y:.3f}" font-family="Helvetica, Arial, sans-serif" font-size="0.12" fill="#777" text-anchor="middle">{p["name"]} rgb({r},{g},{b})</text>')
    # fruit zone outline (faint; below the detector's saturation threshold)
    x0, y0, x1, y1 = board.FRUIT_ZONE_IN
    parts.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="#333" stroke-width="0.02" stroke-dasharray="0.2 0.15"/>')
    parts.append(f'<text x="{(x0 + x1) / 2:.3f}" y="{(y0 + y1) / 2:.3f}" font-family="Helvetica, Arial, sans-serif" font-size="0.3" fill="#2a2a2a" text-anchor="middle">place 10 fruit here, not touching</text>')
    parts.append(f'<text x="{W / 2:.3f}" y="{H - 0.15:.3f}" font-family="Helvetica, Arial, sans-serif" font-size="0.14" fill="#777" text-anchor="middle">Saticoy lemon sampling board v1 · {W:g} x {H:g} in · print at 100% · ArUco {board.ARUCO_DICT_NAME} ids 0-3 · matte finish only</text>')
    parts.append('</svg>')
    Path(out_path).write_text('\n'.join(parts), encoding='utf-8')
    print(f'wrote {out_path}')


if __name__ == '__main__':
    main(Path(__file__).resolve().parent / 'board.svg')
