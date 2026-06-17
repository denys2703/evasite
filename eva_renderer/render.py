"""Pillow-based premium product renderer for extracted mat contours."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
from shapely.geometry import Polygon

from .dxf import Contour
from .textures import load_texture, tile_texture


CANVAS_SIZE = 2084
PADDING = 100
GAP = 50
BORDER_PX = 10
DROP_SHADOW_OPACITY = 0.26
INNER_SHADOW_OPACITY = 0.14
BORDER_SHADOW_OPACITY = 0.42
CORNER_SMOOTHING_PX = 20
CORNER_MIN_ANGLE_DEG = 30.0
SIMPLIFY_TOLERANCE_PX = 1.5
MATERIAL_TEXTURE_SCALE = 1.0
BORDER_TEXTURE_SCALE = 1.0
STITCH_TEXTURE_SCALE = 1.0
STITCH_OFFSET_PX = 4
STITCH_WIDTH_PX = 3
CENTER_HIGHLIGHT_OPACITY = 0.30
SUPERSAMPLE = 3
AXIS_ALIGN = "top"
SHADOW_MARGIN = 90


@dataclass(frozen=True)
class RenderConfig:
    canvas_size: int = CANVAS_SIZE
    padding: int = PADDING
    gap: int = GAP
    border_px: int = BORDER_PX
    drop_shadow_opacity: float = DROP_SHADOW_OPACITY
    inner_shadow_opacity: float = INNER_SHADOW_OPACITY
    border_shadow_opacity: float = BORDER_SHADOW_OPACITY
    corner_smoothing_px: int = CORNER_SMOOTHING_PX
    corner_min_angle_deg: float = CORNER_MIN_ANGLE_DEG
    simplify_tolerance_px: float = SIMPLIFY_TOLERANCE_PX
    material_texture_scale: float = MATERIAL_TEXTURE_SCALE
    border_texture_scale: float = BORDER_TEXTURE_SCALE
    stitch_texture_scale: float = STITCH_TEXTURE_SCALE
    stitch_offset_px: int = STITCH_OFFSET_PX
    stitch_width_px: int = STITCH_WIDTH_PX
    center_highlight_opacity: float = CENTER_HIGHLIGHT_OPACITY
    supersample: int = SUPERSAMPLE
    axis_align: str = AXIS_ALIGN
    material_texture: Path | None = None
    border_texture: Path | None = None
    stitch_texture: Path | None = None
    mirror_horizontal: bool = True


@dataclass(frozen=True)
class RenderedMat:
    image: Image.Image
    body_size: tuple[int, int]
    body_offset: tuple[int, int]


def render_pair(driver: Contour, passenger: Contour, output_path: Path, config: RenderConfig) -> None:
    """Render driver/passenger contours on a transparent square e-commerce canvas."""

    scale = _pair_scale(driver, passenger, config)
    material = load_texture(config.material_texture, "material")
    border = load_texture(config.border_texture, "border")
    stitch = load_texture(config.stitch_texture, "stitch")
    driver_mat = render_single(driver.polygon, scale, material, border, stitch, config)
    passenger_mat = render_single(passenger.polygon, scale, material, border, stitch, config)

    canvas = Image.new("RGBA", (config.canvas_size, config.canvas_size), (255, 255, 255, 0))
    total_body_width = driver_mat.body_size[0] + config.gap + passenger_mat.body_size[0]
    max_body_height = max(driver_mat.body_size[1], passenger_mat.body_size[1])
    start_body_x = (config.canvas_size - total_body_width) // 2

    driver_body_y = _aligned_body_y(config.padding, driver_mat.body_size[1], max_body_height, config.axis_align)
    passenger_body_y = _aligned_body_y(config.padding, passenger_mat.body_size[1], max_body_height, config.axis_align)
    _paste_by_body(canvas, driver_mat, (start_body_x, driver_body_y))
    _paste_by_body(
        canvas,
        passenger_mat,
        (start_body_x + driver_mat.body_size[0] + config.gap, passenger_body_y),
    )

    if max_body_height > config.canvas_size - config.padding * 2:
        raise ValueError("Rendered mats exceed vertical canvas padding")
    if start_body_x < config.padding:
        raise ValueError("Rendered mats exceed horizontal canvas padding")
    _save_canvas(canvas, output_path)



def render_front_pair(driver: Contour, passenger: Contour, output_path: Path, config: RenderConfig) -> None:
    """Render photo #1: front driver/passenger mats, slightly rotated and tightly grouped."""

    local_config = _replace_config(config, gap=-10)
    scale = _pair_scale(driver, passenger, local_config)
    material, border, stitch = _load_render_textures(config)
    driver_mat = render_single(driver.polygon, scale, material, border, stitch, config)
    passenger_mat = render_single(passenger.polygon, scale, material, border, stitch, config)
    canvas = Image.new("RGBA", (config.canvas_size, config.canvas_size), (255, 255, 255, 0))

    body_gap = -10
    total_body_width = driver_mat.body_size[0] + body_gap + passenger_mat.body_size[0]
    max_body_height = max(driver_mat.body_size[1], passenger_mat.body_size[1])
    start_body_x = (config.canvas_size - total_body_width) // 2
    driver_body_y = _aligned_body_y(config.padding, driver_mat.body_size[1], max_body_height, config.axis_align)
    passenger_body_y = _aligned_body_y(config.padding, passenger_mat.body_size[1], max_body_height, config.axis_align)
    _paste_rotated_by_body(canvas, driver_mat, (start_body_x, driver_body_y), 5)
    _paste_rotated_by_body(
        canvas,
        passenger_mat,
        (start_body_x + driver_mat.body_size[0] + body_gap, passenger_body_y),
        -5,
    )
    _save_canvas(canvas, output_path)


def render_full_set(
    driver: Contour,
    passenger: Contour,
    rear_mats: list[Contour],
    tunnel: Contour | None,
    output_path: Path,
    config: RenderConfig,
    third_row: Contour | None = None,
    scale: float | None = None,
    style_reference_scale: float | None = None,
) -> None:
    """Render photo #2: front row plus available 2nd/3rd row mats and tunnel."""

    if not rear_mats:
        raise ValueError("Full-set render requires at least one rear or 2nd-row mat")

    layout_gap = 10
    row_gap = 20
    if scale is None:
        scale = _full_set_scale(driver, passenger, rear_mats, config, third_row, layout_gap, row_gap)

    material, border, stitch = _load_render_textures(config)
    local_config = _style_scaled_config(config, scale, style_reference_scale)
    driver_mat = render_single(driver.polygon, scale, material, border, stitch, local_config)
    passenger_mat = render_single(passenger.polygon, scale, material, border, stitch, local_config)
    rear_rendered = [render_single(contour.polygon, scale, material, border, stitch, local_config) for contour in rear_mats]
    tunnel_mat = render_single(tunnel.polygon, scale, material, border, stitch, local_config) if tunnel is not None else None
    third_row_mat = render_single(third_row.polygon, scale, material, border, stitch, local_config) if third_row is not None else None

    rendered_front_h = max(driver_mat.body_size[1], passenger_mat.body_size[1])
    rear_max_h = max(mat.body_size[1] for mat in rear_rendered)
    tunnel_h = tunnel_mat.body_size[1] if tunnel_mat is not None else 0
    rear_band_h = max(rear_max_h, tunnel_h)
    third_h = third_row_mat.body_size[1] if third_row_mat is not None else 0
    rendered_total_h = rendered_front_h + row_gap + rear_band_h
    if third_row_mat is not None:
        rendered_total_h += row_gap + third_h

    front_row_w = driver_mat.body_size[0] + layout_gap + passenger_mat.body_size[0]
    rear_row_w = sum(mat.body_size[0] for mat in rear_rendered) + layout_gap * max(0, len(rear_rendered) - 1)
    third_row_w = third_row_mat.body_size[0] if third_row_mat is not None else 0
    canvas_w = max(front_row_w, rear_row_w, third_row_w) + config.padding * 2
    canvas_h = rendered_total_h + config.padding * 2
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
    front_y = config.padding
    _paste_row(canvas, [driver_mat, passenger_mat], front_y, layout_gap, "top")

    rear_band_y = front_y + rendered_front_h + row_gap
    rear_y = rear_band_y + (rear_band_h - rear_max_h) // 2
    rear_positions = _paste_row(canvas, rear_rendered, rear_y, layout_gap, "top")

    if tunnel_mat is not None and rear_positions:
        left_x = rear_positions[0][0]
        right_x = rear_positions[-1][0] + rear_rendered[-1].body_size[0]
        tunnel_x = (left_x + right_x - tunnel_mat.body_size[0]) // 2
        tunnel_y = rear_band_y + (rear_band_h - tunnel_mat.body_size[1]) // 2
        _paste_by_body(canvas, tunnel_mat, (tunnel_x, tunnel_y))

    if third_row_mat is not None:
        third_y = rear_band_y + rear_band_h + row_gap
        _paste_row(canvas, [third_row_mat], third_y, layout_gap, "top")

    _save_canvas(canvas, output_path)


def _full_set_scale(
    driver: Contour,
    passenger: Contour,
    rear_mats: list[Contour],
    config: RenderConfig,
    third_row: Contour | None = None,
    layout_gap: int = 10,
    row_gap: int = 20,
) -> float:
    available_w = config.canvas_size - config.padding * 2
    available_h = config.canvas_size - config.padding * 2
    front_w = driver.width + passenger.width
    rear_w = sum(contour.width for contour in rear_mats) + layout_gap * (len(rear_mats) - 1)
    third_w = third_row.width if third_row is not None else 0
    max_w = max(front_w, rear_w, third_w)
    front_h = max(driver.height, passenger.height)
    rear_h = max(contour.height for contour in rear_mats)
    total_h = front_h + row_gap + rear_h
    if third_row is not None:
        total_h += row_gap + third_row.height
    return min((available_w - layout_gap) / max_w, available_h / total_h)


def render_trunk(
    trunk: Contour,
    output_path: Path,
    config: RenderConfig,
    scale: float | None = None,
    style_reference_scale: float | None = None,
) -> None:
    """Render photo #3: trunk mat from one of the 12/13/14 folders."""

    if scale is None:
        scale = _full_height_scale(trunk.width, trunk.height, config)
    material, border, stitch = _load_render_textures(config)
    local_config = _style_scaled_config(config, scale, style_reference_scale)
    trunk_mat = render_single(trunk.polygon, scale, material, border, stitch, local_config)
    canvas_w = trunk_mat.body_size[0] + config.padding * 2
    canvas_h = trunk_mat.body_size[1] + config.padding * 2
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
    body_x = (canvas_w - trunk_mat.body_size[0]) // 2
    body_y = _aligned_body_y(config.padding, trunk_mat.body_size[1], trunk_mat.body_size[1], config.axis_align)
    _paste_by_body(canvas, trunk_mat, (body_x, body_y))
    _save_canvas(canvas, output_path)


def render_tunnel(
    tunnel: Contour,
    output_path: Path,
    config: RenderConfig,
    driver: Contour | None = None,
    passenger: Contour | None = None,
    rear_mats: list[Contour] | None = None,
    third_row: Contour | None = None,
    scale: float | None = None,
    style_reference_scale: float | None = None,
) -> None:
    """Render photo #4 using the same scale as the full-set rear row when possible."""

    material, border, stitch = _load_render_textures(config)
    if scale is not None:
        pass
    elif driver is not None and passenger is not None and rear_mats:
        scale = _full_set_scale(driver, passenger, rear_mats, config, third_row)
    else:
        scale = _full_height_scale(tunnel.width, tunnel.height, config)
    local_config = _style_scaled_config(config, scale, style_reference_scale)
    tunnel_mat = render_single(tunnel.polygon, scale, material, border, stitch, local_config)
    canvas_w = tunnel_mat.body_size[0] + config.padding * 2
    canvas_h = tunnel_mat.body_size[1] + config.padding * 2
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
    body_x = (canvas_w - tunnel_mat.body_size[0]) // 2
    body_y = (canvas_h - tunnel_mat.body_size[1]) // 2
    _paste_by_body(canvas, tunnel_mat, (body_x, body_y))
    _save_canvas(canvas, output_path)


def render_individual_set(
    contours: list[Contour],
    output_paths: tuple[Path, ...],
    config: RenderConfig,
    scale: float | None = None,
    style_reference_scale: float | None = None,
) -> None:
    """Render every contour from an extra folder as a separate transparent PNG.

    Each output is centered on its own transparent canvas with consistent texture
    and border scale when a shared ``scale`` is provided.
    """

    if len(contours) != len(output_paths):
        raise ValueError("Contour count must match output path count")
    if not contours:
        return
    material, border, stitch = _load_render_textures(config)
    for contour, output_path in zip(contours, output_paths):
        local_scale = scale if scale is not None else _full_height_scale(contour.width, contour.height, config)
        local_config = _style_scaled_config(config, local_scale, style_reference_scale)
        mat = render_single(contour.polygon, local_scale, material, border, stitch, local_config)
        canvas_w = mat.body_size[0] + config.padding * 2
        canvas_h = mat.body_size[1] + config.padding * 2
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
        body_x = (canvas_w - mat.body_size[0]) // 2
        body_y = (canvas_h - mat.body_size[1]) // 2
        _paste_by_body(canvas, mat, (body_x, body_y))
        _save_canvas(canvas, output_path)


def _style_scaled_config(config: RenderConfig, scale: float, reference_scale: float | None) -> RenderConfig:
    """Scale pixel-based styling so it matches a reference render scale.

    Photo #1 defines the visual reference for material tiling, border width,
    stitching, and corner cleanup. Other outputs may use a different geometry
    scale, so their pixel styling is multiplied by ``scale / reference_scale``
    to preserve the same real-world visual size.
    """

    if reference_scale is None or reference_scale <= 0 or scale <= 0:
        return config
    ratio = scale / reference_scale
    if abs(ratio - 1.0) < 1e-6:
        return config
    return _replace_config(
        config,
        border_px=_scaled_int(config.border_px, ratio),
        corner_smoothing_px=_scaled_int(config.corner_smoothing_px, ratio),
        simplify_tolerance_px=max(0.0, config.simplify_tolerance_px * ratio),
        material_texture_scale=max(0.01, config.material_texture_scale * ratio),
        border_texture_scale=max(0.01, config.border_texture_scale * ratio),
        stitch_texture_scale=max(0.01, config.stitch_texture_scale * ratio),
        stitch_offset_px=_scaled_int(config.stitch_offset_px, ratio),
        stitch_width_px=_scaled_int(config.stitch_width_px, ratio),
    )


def _scaled_int(value: int, ratio: float) -> int:
    if value <= 0:
        return 0
    return max(1, round(value * ratio))


def _full_height_scale(width: float, height: float, config: RenderConfig) -> float:
    available = config.canvas_size - config.padding * 2
    return min(available / width, available / height)


def render_single(
    polygon: Polygon,
    scale: float,
    material_texture: Image.Image,
    border_texture: Image.Image,
    stitch_texture: Image.Image,
    config: RenderConfig,
) -> RenderedMat:
    """Render one contour with repeated material, inner border, embossing, and shadow."""

    polygon = _prepare_polygon(polygon, scale, config)
    minx, miny, maxx, maxy = polygon.bounds
    body_width = max(1, round((maxx - minx) * scale))
    body_height = max(1, round((maxy - miny) * scale))
    image_size = (body_width + SHADOW_MARGIN * 2, body_height + SHADOW_MARGIN * 2)

    mask = _raster_mask(polygon, scale, image_size, config.supersample)

    material = tile_texture(
        material_texture,
        image_size,
        (round(minx * scale), round(miny * scale)),
        texture_scale=config.material_texture_scale,
    )
    material.putalpha(mask)

    border_mask = _inner_border_mask(mask, config.border_px)
    border = tile_texture(border_texture, image_size, texture_scale=config.border_texture_scale)
    border.putalpha(border_mask)

    stitch_mask = _stitch_mask(mask, config.border_px, config.stitch_offset_px, config.stitch_width_px)
    stitch = tile_texture(stitch_texture, image_size, texture_scale=config.stitch_texture_scale)
    _apply_alpha_mask(stitch, stitch_mask, preserve_texture_alpha=True)

    inner_shadow = _inner_shadow(mask, config.inner_shadow_opacity)
    surface_shadows = _softbox_surface_shadows(mask, body_width, body_height)
    border_shadow = _border_outer_edge_shadow(mask, border_mask, config.border_px, config.border_shadow_opacity)
    center_highlight = _center_highlight(mask, body_width, body_height, config.center_highlight_opacity)
    softbox_highlights = _softbox_highlights(mask, body_width, body_height)
    highlight = _inner_highlight(mask)

    result = Image.new("RGBA", image_size, (255, 255, 255, 0))
    result.alpha_composite(material)
    result.alpha_composite(surface_shadows)
    result.alpha_composite(inner_shadow)
    result.alpha_composite(center_highlight)
    result.alpha_composite(softbox_highlights)
    result.alpha_composite(border)
    result.alpha_composite(border_shadow)
    result.alpha_composite(highlight)
    result.alpha_composite(stitch)
    if config.mirror_horizontal:
        result = ImageOps.mirror(result)
    return RenderedMat(result, (body_width, body_height), (SHADOW_MARGIN, SHADOW_MARGIN))




def _load_render_textures(config: RenderConfig) -> tuple[Image.Image, Image.Image, Image.Image]:
    return (
        load_texture(config.material_texture, "material"),
        load_texture(config.border_texture, "border"),
        load_texture(config.stitch_texture, "stitch"),
    )


def _replace_config(config: RenderConfig, **overrides: object) -> RenderConfig:
    values = config.__dict__.copy()
    values.update(overrides)
    return RenderConfig(**values)


def _rotate_mat(mat: RenderedMat, degrees: float) -> RenderedMat:
    if degrees % 360 == 0:
        return mat
    rotated = mat.image.rotate(degrees, resample=Image.Resampling.BICUBIC, expand=True)
    return RenderedMat(rotated, rotated.size, (0, 0))


def _paste_rotated_by_body(canvas: Image.Image, mat: RenderedMat, body_top_left: tuple[int, int], degrees: float) -> None:
    if degrees % 360 == 0:
        _paste_by_body(canvas, mat, body_top_left)
        return
    image_x = body_top_left[0] - mat.body_offset[0]
    image_y = body_top_left[1] - mat.body_offset[1]
    center_x = image_x + mat.image.size[0] // 2
    center_y = image_y + mat.image.size[1] // 2
    rotated = mat.image.rotate(degrees, resample=Image.Resampling.BICUBIC, expand=True)
    canvas.alpha_composite(rotated, (center_x - rotated.size[0] // 2, center_y - rotated.size[1] // 2))


def _paste_row(
    canvas: Image.Image, mats: list[RenderedMat], body_y: int, gap: int, axis_align: str
) -> list[tuple[int, int]]:
    total_width = sum(mat.body_size[0] for mat in mats) + gap * (len(mats) - 1)
    max_height = max(mat.body_size[1] for mat in mats)
    x = (canvas.size[0] - total_width) // 2
    positions: list[tuple[int, int]] = []
    for mat in mats:
        y = _aligned_body_y(body_y, mat.body_size[1], max_height, axis_align)
        _paste_by_body(canvas, mat, (x, y))
        positions.append((x, y))
        x += mat.body_size[0] + gap
    return positions


def _save_canvas(canvas: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)

def _aligned_body_y(top_padding: int, body_height: int, max_body_height: int, axis_align: str) -> int:
    mode = axis_align.lower().strip()
    if mode in {"center", "centre", "middle"}:
        return top_padding + (max_body_height - body_height) // 2
    if mode in {"bottom", "down"}:
        return top_padding + max_body_height - body_height
    return top_padding


def _pair_scale(driver: Contour, passenger: Contour, config: RenderConfig) -> float:
    available_width = config.canvas_size - config.padding * 2 - config.gap
    available_height = config.canvas_size - config.padding * 2
    width_scale = available_width / (driver.width + passenger.width)
    height_scale = available_height / max(driver.height, passenger.height)
    return min(width_scale, height_scale)


def _prepare_polygon(polygon: Polygon, scale: float, config: RenderConfig) -> Polygon:
    polygon = _simplify_polygon(polygon, scale, config.simplify_tolerance_px)
    polygon = _round_polygon_corners(polygon, scale, config.corner_smoothing_px, config.corner_min_angle_deg)
    return polygon


def _simplify_polygon(polygon: Polygon, scale: float, tolerance_px: float) -> Polygon:
    """Remove tiny CAD artifacts using a pixel-based tolerance before rasterization."""

    if tolerance_px <= 0 or scale <= 0:
        return polygon
    simplified = polygon.simplify(tolerance_px / scale, preserve_topology=True)
    return simplified if isinstance(simplified, Polygon) and not simplified.is_empty else polygon


def _round_polygon_corners(polygon: Polygon, scale: float, radius_px: int, min_angle_deg: float) -> Polygon:
    """Round only eligible local vertices without globally buffering the shape.

    A morphology-style buffer can close narrow notches and lift nearby straight
    segments. This local Bezier pass keeps the original edges, skips very acute
    corners below ``min_angle_deg``, and limits every rounded corner by adjacent
    segment lengths so tight cutouts remain stable.
    """

    if radius_px <= 0 or scale <= 0:
        return polygon
    radius = radius_px / scale
    exterior = _round_ring_vertices(list(polygon.exterior.coords), radius, min_angle_deg)
    interiors = [_round_ring_vertices(list(ring.coords), radius, min_angle_deg) for ring in polygon.interiors]
    try:
        rounded = Polygon(exterior, interiors).buffer(0)
    except Exception:
        return polygon
    if not isinstance(rounded, Polygon) or rounded.is_empty or rounded.area <= 0:
        return polygon
    return rounded


def _round_ring_vertices(
    coords: list[tuple[float, float]], radius: float, min_angle_deg: float
) -> list[tuple[float, float]]:
    if len(coords) < 4 or radius <= 0:
        return coords
    points = coords[:-1] if coords[0] == coords[-1] else coords
    rounded: list[tuple[float, float]] = []
    threshold = max(0.0, min(float(min_angle_deg), 180.0))
    for index, current in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        angle = _corner_angle_degrees(previous, current, following)
        prev_len = _distance(current, previous)
        next_len = _distance(current, following)
        cut = min(radius, prev_len * 0.35, next_len * 0.35)
        if angle < threshold or cut <= 0:
            rounded.append(current)
            continue
        start = _point_toward(current, previous, cut)
        end = _point_toward(current, following, cut)
        if not rounded or rounded[-1] != start:
            rounded.append(start)
        steps = max(4, min(16, round(angle / 10)))
        for step in range(1, steps + 1):
            t = step / steps
            rounded.append(_quadratic_point(start, current, end, t))
    if rounded and rounded[0] != rounded[-1]:
        rounded.append(rounded[0])
    return rounded or coords


def _corner_angle_degrees(
    previous: tuple[float, float], current: tuple[float, float], following: tuple[float, float]
) -> float:
    ax, ay = previous[0] - current[0], previous[1] - current[1]
    bx, by = following[0] - current[0], following[1] - current[1]
    length_a = math.hypot(ax, ay)
    length_b = math.hypot(bx, by)
    if length_a <= 0 or length_b <= 0:
        return 0.0
    cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / (length_a * length_b)))
    return math.degrees(math.acos(cosine))


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _point_toward(
    origin: tuple[float, float], target: tuple[float, float], distance: float
) -> tuple[float, float]:
    total = _distance(origin, target)
    if total <= 0:
        return origin
    ratio = min(distance / total, 1.0)
    return (origin[0] + (target[0] - origin[0]) * ratio, origin[1] + (target[1] - origin[1]) * ratio)


def _quadratic_point(
    start: tuple[float, float], control: tuple[float, float], end: tuple[float, float], t: float
) -> tuple[float, float]:
    inv = 1.0 - t
    return (
        inv * inv * start[0] + 2 * inv * t * control[0] + t * t * end[0],
        inv * inv * start[1] + 2 * inv * t * control[1] + t * t * end[1],
    )


def _raster_mask(polygon: Polygon, scale: float, image_size: tuple[int, int], supersample: int) -> Image.Image:
    """Draw the mask at high resolution and downsample for anti-aliased edges."""

    ss = max(int(supersample), 1)
    high_size = (image_size[0] * ss, image_size[1] * ss)
    mask = Image.new("L", high_size, 0)
    draw = ImageDraw.Draw(mask)
    _draw_polygon(draw, polygon, scale * ss, SHADOW_MARGIN * ss, SHADOW_MARGIN * ss)
    if ss == 1:
        return mask
    return mask.resize(image_size, Image.Resampling.LANCZOS)


def _draw_polygon(draw: ImageDraw.ImageDraw, polygon: Polygon, scale: float, ox: int, oy: int) -> None:
    exterior = [(round(x * scale) + ox, round(y * scale) + oy) for x, y in polygon.exterior.coords]
    draw.polygon(exterior, fill=255)
    for interior in polygon.interiors:
        hole = [(round(x * scale) + ox, round(y * scale) + oy) for x, y in interior.coords]
        draw.polygon(hole, fill=0)


def _drop_shadow(mask: Image.Image, opacity: float) -> Image.Image:
    offset = ImageChops.offset(mask, 22, 26)
    shadow_alpha = offset.filter(ImageFilter.GaussianBlur(34)).point(lambda p: int(p * max(opacity, 0.0)))
    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    return shadow


def _inner_border_mask(mask: Image.Image, width: int) -> Image.Image:
    eroded = mask.filter(ImageFilter.MinFilter(width * 2 + 1))
    return ImageChops.subtract(mask, eroded)


def _border_outer_edge_shadow(
    mask: Image.Image, border_mask: Image.Image, border_width: int, opacity: float
) -> Image.Image:
    """Add upholstery depth only on the border, falling in from the outer edge."""

    outer_edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(5)))
    edge_depth = outer_edge.filter(ImageFilter.GaussianBlur(max(border_width * 0.9, 3)))
    shifted_depth = ImageChops.offset(edge_depth, 2, 3)
    alpha = ImageChops.multiply(shifted_depth, border_mask).point(lambda p: int(p * max(opacity, 0.0)))
    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    shadow.putalpha(alpha)
    return shadow


def _stitch_mask(mask: Image.Image, border_width: int, offset_px: int, stitch_width_px: int) -> Image.Image:
    """Create a stitched seam ring near the inner contour of the border."""

    seam_distance = max(border_width - offset_px, 1)
    half_width = max(stitch_width_px // 2, 1)
    outer = mask.filter(ImageFilter.MinFilter(max((seam_distance - half_width) * 2 + 1, 3)))
    inner = mask.filter(ImageFilter.MinFilter(max((seam_distance + half_width) * 2 + 1, 3)))
    return ImageChops.subtract(outer, inner).filter(ImageFilter.GaussianBlur(0.35))


def _apply_alpha_mask(image: Image.Image, mask: Image.Image, preserve_texture_alpha: bool) -> None:
    if preserve_texture_alpha:
        alpha = ImageChops.multiply(image.getchannel("A"), mask)
    else:
        alpha = mask
    image.putalpha(alpha)



def _softbox_surface_shadows(mask: Image.Image, body_width: int, body_height: int) -> Image.Image:
    """Two clipped soft shadows that add volume without a floor shadow."""

    alpha = Image.new("L", mask.size, 0)
    draw = ImageDraw.Draw(alpha)
    x0 = SHADOW_MARGIN
    y0 = SHADOW_MARGIN
    draw.ellipse(
        (
            x0 + int(body_width * 0.08),
            y0 + int(body_height * 0.58),
            x0 + int(body_width * 1.18),
            y0 + int(body_height * 1.18),
        ),
        fill=88,
    )
    draw.ellipse(
        (
            x0 + int(body_width * 0.55),
            y0 + int(body_height * 0.12),
            x0 + int(body_width * 1.05),
            y0 + int(body_height * 0.58),
        ),
        fill=64,
    )
    large = alpha.filter(ImageFilter.GaussianBlur(max(70, min(body_width, body_height) // 5))).point(lambda p: int(p * 0.16))

    small_alpha = Image.new("L", mask.size, 0)
    small_draw = ImageDraw.Draw(small_alpha)
    small_draw.ellipse(
        (
            x0 - int(body_width * 0.08),
            y0 + int(body_height * 0.62),
            x0 + int(body_width * 0.42),
            y0 + int(body_height * 1.02),
        ),
        fill=120,
    )
    small = small_alpha.filter(ImageFilter.GaussianBlur(max(28, min(body_width, body_height) // 12))).point(lambda p: int(p * 0.20))
    combined = ImageChops.lighter(large, small)
    combined = ImageChops.multiply(combined, mask)
    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    shadow.putalpha(combined)
    return shadow


def _softbox_highlights(mask: Image.Image, body_width: int, body_height: int) -> Image.Image:
    """Several broad white reflections clipped to the mat surface."""

    alpha = Image.new("L", mask.size, 0)
    draw = ImageDraw.Draw(alpha)
    x0 = SHADOW_MARGIN
    y0 = SHADOW_MARGIN
    draw.ellipse(
        (
            x0 - int(body_width * 0.10),
            y0 - int(body_height * 0.08),
            x0 + int(body_width * 0.65),
            y0 + int(body_height * 0.38),
        ),
        fill=120,
    )
    draw.ellipse(
        (
            x0 + int(body_width * 0.35),
            y0 + int(body_height * 0.24),
            x0 + int(body_width * 1.10),
            y0 + int(body_height * 0.72),
        ),
        fill=80,
    )
    draw.rounded_rectangle(
        (
            x0 + int(body_width * 0.18),
            y0 + int(body_height * 0.42),
            x0 + int(body_width * 0.82),
            y0 + int(body_height * 0.56),
        ),
        radius=max(12, body_height // 18),
        fill=70,
    )
    alpha = alpha.filter(ImageFilter.GaussianBlur(max(45, min(body_width, body_height) // 6))).point(lambda p: int(p * 0.22))
    alpha = ImageChops.multiply(alpha, mask)
    glow = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    glow.putalpha(alpha)
    return glow

def _inner_shadow(mask: Image.Image, opacity: float) -> Image.Image:
    shifted = ImageChops.offset(mask, -10, -12)
    edge = ImageChops.subtract(mask, shifted).filter(ImageFilter.GaussianBlur(18))
    edge = ImageChops.multiply(edge, mask).point(lambda p: int(p * max(opacity, 0.0)))
    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    shadow.putalpha(edge)
    return shadow


def _center_highlight(mask: Image.Image, body_width: int, body_height: int, opacity: float) -> Image.Image:
    if opacity <= 0:
        return Image.new("RGBA", mask.size, (255, 255, 255, 0))
    glow_alpha = Image.new("L", mask.size, 0)
    draw = ImageDraw.Draw(glow_alpha)
    cx = SHADOW_MARGIN + body_width // 2
    cy = SHADOW_MARGIN + body_height // 2
    draw.rounded_rectangle((cx - 50, cy - 25, cx + 50, cy + 25), radius=25, fill=255)
    glow_alpha = glow_alpha.filter(ImageFilter.GaussianBlur(250)).point(lambda p: int(p * min(opacity, 1.0)))
    glow_alpha = ImageChops.multiply(glow_alpha, mask)
    glow = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    glow.putalpha(glow_alpha)
    return glow


def _inner_highlight(mask: Image.Image) -> Image.Image:
    shifted = ImageChops.offset(mask, 10, 12)
    edge = ImageChops.subtract(mask, shifted).filter(ImageFilter.GaussianBlur(10))
    edge = ImageChops.multiply(edge, mask).point(lambda p: int(p * 0.12))
    highlight = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    highlight.putalpha(edge)
    return highlight


def _paste_by_body(canvas: Image.Image, mat: RenderedMat, body_top_left: tuple[int, int]) -> None:
    image_x = body_top_left[0] - mat.body_offset[0]
    image_y = body_top_left[1] - mat.body_offset[1]
    canvas.alpha_composite(mat.image, (image_x, image_y))
