"""US state shapes for the map Reels (owner, Nov 20: "charts that include maps of the US... color coded").

Shapes: us-atlas 3.0.1 states-albers-10m.json (U.S. Census Bureau cartographic boundaries, pre-projected to Albers USA
with Alaska and Hawaii inset; ISC license, see assets/us-atlas-LICENSE.txt). Keys are state FIPS codes, the same as
data.STATES. Decoded once into SVG path strings in the file's own coordinates (about 975 x 610).
"""
import json
import os

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "states-albers-10m.json")
W, H = 975, 610
# Too small for a label inside: listed in a column off the Atlantic coast with a leader line instead.
SMALL = ["50", "33", "25", "44", "09", "34", "10", "24", "11"]       # VT NH MA RI CT NJ DE MD DC
# Label anchor fixes where the area centroid sits badly (in map units).
NUDGE = {"12": (20, 22), "26": (12, 22), "22": (-10, 4), "15": (6, 6), "02": (0, 0), "16": (0, 22), "21": (6, 2),
         "51": (8, 2), "37": (8, 0), "47": (0, 1), "54": (-2, 4), "36": (6, 4), "23": (-4, 18), "42": (0, 2),
         "17": (-10, 24), "18": (2, 12), "28": (-5, 10), "01": (6, 10)}

_cache = {}


def _decode():
    if _cache:
        return _cache
    topo = json.load(open(ASSET))
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    for g in topo["objects"]["states"]["geometries"]:
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        rings = [[ring(r) for r in poly] for poly in polys]
        d = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in r) + "Z" for poly in rings for r in poly)
        # label anchor: area-weighted centroid of the largest outer ring
        best, cx, cy, bw = 0, 0, 0, 0
        for poly in rings:
            r = poly[0]
            a = sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2
            if abs(a) > best and a:
                best = abs(a)
                bw = max(x for x, _ in r) - min(x for x, _ in r)
                cx = sum((r[i][0] + r[i + 1][0]) * (r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]) for i in range(len(r) - 1)) / (6 * a)
                cy = sum((r[i][1] + r[i + 1][1]) * (r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]) for i in range(len(r) - 1)) / (6 * a)
        nx, ny = NUDGE.get(g["id"], (0, 0))
        _cache[g["id"]] = {"d": d, "cx": cx + nx, "cy": cy + ny, "area": best, "w": bw}
    return _cache


def shapes():
    """{fips: dict(d=svg path, cx, cy=label anchor, area)} for all 50 states + DC."""
    return _decode()
