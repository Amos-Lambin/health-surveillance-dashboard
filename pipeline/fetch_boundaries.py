"""Download district boundaries from the DHIS2 demo and save a small GeoJSON for the map.

Output: ../public/data/districts.geojson  (13 districts, simplified, coordinates rounded)
Run from the pipeline folder:  python fetch_boundaries.py
"""
import json
import math
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

TOLERANCE = 0.003  # degrees, about 330 m: plenty for a district-level map


def _dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def simplify(pts, tol):
    """Douglas-Peucker, iterative so large rings cannot overflow the stack."""
    n = len(pts)
    if n < 5:
        return pts
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        s, e = stack.pop()
        far, idx = 0.0, -1
        for i in range(s + 1, e):
            d = _dist(pts[i], pts[s], pts[e])
            if d > far:
                far, idx = d, i
        if idx != -1 and far > tol:
            keep[idx] = True
            stack += [(s, idx), (idx, e)]
    return [p for p, k in zip(pts, keep) if k]


def simplify_polygon(rings, tol):
    out = []
    for i, ring in enumerate(rings):
        pts = [(round(x, 3), round(y, 3)) for x, y in ring]
        pts = simplify(pts, tol)
        if len(pts) < 4:
            if i == 0:
                return None  # exterior ring collapsed: drop this polygon
            continue
        out.append([list(p) for p in pts])
    return out


def build_collection(units, tol=TOLERANCE):
    feats = []
    for u in units:
        g = u.get("geometry")
        if not g or g["type"] not in ("Polygon", "MultiPolygon"):
            print("Skipping (no polygon):", u.get("name"))
            continue
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        polys = [p for p in (simplify_polygon(p, tol) for p in polys) if p]
        if not polys:
            continue
        geom = ({"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1
                else {"type": "MultiPolygon", "coordinates": polys})
        feats.append({"type": "Feature", "properties": {"uid": u["id"], "name": u["name"]},
                      "geometry": geom})
    return {"type": "FeatureCollection", "features": feats}


def main():
    load_dotenv()
    base = os.environ["DHIS2_URL"].rstrip("/")
    auth = (os.environ["DHIS2_USER"], os.environ["DHIS2_PASSWORD"])
    r = requests.get(f"{base}/api/organisationUnits", auth=auth, timeout=180, params={
        "fields": "id,name,geometry", "filter": "level:eq:2", "paging": "false"})
    r.raise_for_status()
    fc = build_collection(r.json()["organisationUnits"])
    out = Path(__file__).resolve().parent.parent / "public" / "data" / "districts.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fc, separators=(",", ":")))
    print(f"{len(fc['features'])} districts, {out.stat().st_size / 1024:.0f} KB -> {out}")
    print("Names:", sorted(f["properties"]["name"] for f in fc["features"]))


if __name__ == "__main__":
    main()
