"""DXF contour extraction utilities.

The extractor is intentionally conservative: it ignores annotations and helper
entities, flattens CAD curves into linework, polygonizes dirty drawings, and
returns the largest usable closed contour as the mat outline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
from typing import Iterable, Sequence

import ezdxf
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union


@dataclass(frozen=True)
class Contour:
    """A normalized 2D mat contour."""

    polygon: Polygon
    source: Path

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.polygon.bounds

    @property
    def width(self) -> float:
        minx, _, maxx, _ = self.bounds
        return maxx - minx

    @property
    def height(self) -> float:
        _, miny, _, maxy = self.bounds
        return maxy - miny


def extract_main_contour(path: Path, reference: Contour | None = None) -> Contour:
    """Extract the dominant mat contour from a DXF file.

    Parameters
    ----------
    path:
        DXF file to read.
    reference:
        Optional high-quality contour from ``Main/``. Its size is used to tune
        polygonization tolerances for dirtier companion files.
    """

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    segments: list[LineString] = []
    closed_polygons: list[Polygon] = []

    for entity in msp:
        if _is_annotation_or_dimension(entity):
            continue
        try:
            entity_segments, entity_polygons = _entity_to_geometry(entity)
        except Exception:
            continue
        segments.extend(entity_segments)
        closed_polygons.extend(entity_polygons)

    candidates = _clean_polygons(closed_polygons)
    candidates.extend(_polygonize_segments(segments, reference))
    if not candidates:
        raise ValueError(f"No closed mat contour found in {path}")

    polygon = max(candidates, key=lambda p: (p.area, _compactness_score(p)))
    polygon = _normalize_polygon(polygon)
    return Contour(polygon=polygon, source=path)


def load_reference_contour(main_dir: Path) -> Contour | None:
    """Load the largest contour from a sibling ``Main/`` directory if present."""

    if not main_dir.is_dir():
        return None
    best: Contour | None = None
    for dxf_path in sorted(main_dir.glob("*.dxf")):
        try:
            contour = extract_main_contour(dxf_path)
        except Exception:
            continue
        if best is None or contour.polygon.area > best.polygon.area:
            best = contour
    return best


def _is_annotation_or_dimension(entity: object) -> bool:
    ignored_types = {
        "TEXT",
        "MTEXT",
        "DIMENSION",
        "LEADER",
        "MLEADER",
        "HATCH",
        "INSERT",
        "POINT",
        "XLINE",
        "RAY",
    }
    return getattr(entity, "dxftype", lambda: "")() in ignored_types


def _entity_to_geometry(entity: object) -> tuple[list[LineString], list[Polygon]]:
    dxftype = entity.dxftype()
    if dxftype == "LINE":
        points = _dedupe_points([_xy(entity.dxf.start), _xy(entity.dxf.end)])
        if len(points) < 2:
            return [], []
        return [LineString(points)], []
    if dxftype == "LWPOLYLINE":
        points = [(float(p[0]), float(p[1])) for p in entity.get_points()]
        return _polyline_to_geometry(points, bool(entity.closed))
    if dxftype == "POLYLINE":
        points = [_xy(vertex.dxf.location) for vertex in entity.vertices]
        return _polyline_to_geometry(points, bool(entity.is_closed))
    if dxftype in {"SPLINE", "ARC", "CIRCLE", "ELLIPSE"}:
        points = _curve_points(entity)
        closed = dxftype in {"CIRCLE", "ELLIPSE"} or _is_closed(points)
        return _polyline_to_geometry(points, closed)
    return [], []


def _polyline_to_geometry(
    points: Sequence[tuple[float, float]], closed: bool
) -> tuple[list[LineString], list[Polygon]]:
    points = _dedupe_points(points)
    if len(points) < 2:
        return [], []
    if closed and points[0] != points[-1]:
        points = [*points, points[0]]
    line = LineString(points)
    polygons: list[Polygon] = []
    if closed and len(points) >= 4:
        polygon = Polygon(points)
        if polygon.area > 0:
            polygons.append(polygon)
    return [line], polygons


def _curve_points(entity: object) -> list[tuple[float, float]]:
    try:
        flattened = entity.flattening(0.5)
        return [_xy(point) for point in flattened]
    except Exception:
        try:
            return [_xy(point) for point in entity.construction_tool().flattening(0.5)]
        except Exception:
            return []


def _polygonize_segments(
    segments: Iterable[LineString], reference: Contour | None
) -> list[Polygon]:
    valid_segments = [segment for segment in segments if not segment.is_empty and segment.length > 0]
    if not valid_segments:
        return []

    merged = unary_union(MultiLineString(valid_segments))
    polygons = _clean_polygons(list(polygonize(merged)))
    if polygons:
        return polygons

    tolerance = _reference_tolerance(reference, valid_segments)
    buffered = unary_union([segment.buffer(tolerance, cap_style=2, join_style=2) for segment in valid_segments])
    if isinstance(buffered, Polygon):
        return _clean_polygons([buffered])
    if isinstance(buffered, MultiPolygon):
        return _clean_polygons(list(buffered.geoms))
    return []


def _reference_tolerance(reference: Contour | None, segments: Sequence[LineString]) -> float:
    if reference is not None:
        diag = math.hypot(reference.width, reference.height)
    else:
        minx, miny, maxx, maxy = unary_union(segments).bounds
        diag = math.hypot(maxx - minx, maxy - miny)
    return max(diag * 0.0015, 0.1)


def _clean_polygons(polygons: Iterable[Polygon]) -> list[Polygon]:
    cleaned: list[Polygon] = []
    for polygon in polygons:
        if polygon.is_empty or polygon.area <= 0:
            continue
        fixed = polygon.buffer(0)
        if isinstance(fixed, MultiPolygon):
            cleaned.extend(_clean_polygons(fixed.geoms))
        elif isinstance(fixed, Polygon) and fixed.area > 0:
            cleaned.append(fixed)
    if not cleaned:
        return []
    max_area = max(poly.area for poly in cleaned)
    return [poly for poly in cleaned if poly.area >= max_area * 0.05]


def _normalize_polygon(polygon: Polygon) -> Polygon:
    """Translate to origin and flip Y so CAD coordinates render upright in images."""

    minx, miny, maxx, maxy = polygon.bounds

    def transform_ring(coords: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(x - minx, maxy - y) for x, y in coords]

    exterior = transform_ring(polygon.exterior.coords)
    holes = [transform_ring(ring.coords) for ring in polygon.interiors]
    return Polygon(exterior, holes).buffer(0)


def _compactness_score(polygon: Polygon) -> float:
    perimeter = polygon.length
    return 0.0 if perimeter == 0 else 4.0 * math.pi * polygon.area / (perimeter * perimeter)


def _dedupe_points(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for x, y in points:
        point = (float(x), float(y))
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    return deduped


def _xy(point: object) -> tuple[float, float]:
    return float(point[0]), float(point[1])


def _is_closed(points: Sequence[tuple[float, float]]) -> bool:
    if len(points) < 3:
        return False
    return math.dist(points[0], points[-1]) <= 1e-6
