"""Pillow-based premium product renderer for extracted mat contours."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from shapely.geometry import Polygon

from .dxf import Contour
from .textures import load_texture, tile_texture


CANVAS_SIZE = 2084
PADDING = 50
GAP = 50
BORDER_PX = 10
CORNER_SMOOTHING_PX = 20
SIMPLIFY_TOLERANCE_PX = 1.5
SHADOW_MARGIN = 90


@dataclass(frozen=True)
class RenderConfig:
    canvas_size: int = CANVAS_SIZE
    padding: int = PADDING
    gap: int = GAP
    border_px: int = BORDER_PX
    corner_smoothing_px: int = CORNER_SMOOTHING_PX
    simplify_tolerance_px: float = SIMPLIFY_TOLERANCE_PX
    material_texture: Path | None = None
    border_texture: Path | None = None


@dataclass(frozen=True)
class RenderedMat:
    image: Image.Image
    body_size: tuple[int, int]
    body_offset: tuple[int, int]


def render_pair(driver: Contour, passenger: Contour, output_path: Path, config: RenderConfig) -> None:
    """Render driver/passenger contours on a white square e-commerce canvas."""

    scale = _pair_scale(driver, passenger, config)
    material = load_texture(config.material_texture, "material")
    border = load_texture(config.border_texture, "border")
    driver_mat = render_single(driver.polygon, scale, material, border, config)
    passenger_mat = render_single(passenger.polygon, scale, material, border, config)

    canvas = Image.new("RGBA", (config.canvas_size, config.canvas_size), (255, 255, 255, 255))
    total_body_width = driver_mat.body_size[0] + config.gap + passenger_mat.body_size[0]
    max_body_height = max(driver_mat.body_size[1], passenger_mat.body_size[1])
    start_body_x = (config.canvas_size - total_body_width) // 2
    center_body_y = config.canvas_size // 2

    driver_body_y = center_body_y - driver_mat.body_size[1] // 2
    passenger_body_y = center_body_y - passenger_mat.body_size[1] // 2
    _paste_by_body(canvas, driver_mat, (start_body_x, driver_body_y))
    _paste_by_body(
        canvas,
        passenger_mat,
        (start_body_x + driver_mat.body_size[0] + config.gap, passenger_body_y),
    )

    if max_body_height > config.canvas_size - config.padding * 2:
        raise ValueError("Rendered mats exceed vertical canvas padding")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, quality=96, optimize=True)


def render_single(
    polygon: Polygon,
    scale: float,
    material_texture: Image.Image,
    border_texture: Image.Image,
    config: RenderConfig,
) -> RenderedMat:
    """Render one contour with repeated material, inner border, embossing, and shadow."""

    polygon = _simplify_polygon(polygon, scale, config.simplify_tolerance_px)
    minx, miny, maxx, maxy = polygon.bounds
    body_width = max(1, round((maxx - minx) * scale))
    body_height = max(1, round((maxy - miny) * scale))
    image_size = (body_width + SHADOW_MARGIN * 2, body_height + SHADOW_MARGIN * 2)
    mask = Image.new("L", image_size, 0)
    draw = ImageDraw.Draw(mask)
    _draw_polygon(draw, polygon, scale, SHADOW_MARGIN, SHADOW_MARGIN)
    mask = _smooth_mask(mask, config.corner_smoothing_px)

    shadow = _drop_shadow(mask)
    material = tile_texture(material_texture, image_size, (round(minx * scale), round(miny * scale)))
    material.putalpha(mask)

    border_mask = _inner_border_mask(mask, config.border_px)
    border = tile_texture(border_texture, image_size)
    border.putalpha(border_mask)

    inner_shadow = _inner_shadow(mask)
    highlight = _inner_highlight(mask)

    result = Image.new("RGBA", image_size, (255, 255, 255, 0))
    result.alpha_composite(shadow)
    result.alpha_composite(material)
    result.alpha_composite(inner_shadow)
    result.alpha_composite(highlight)
    result.alpha_composite(border)
    return RenderedMat(result, (body_width, body_height), (SHADOW_MARGIN, SHADOW_MARGIN))


def _pair_scale(driver: Contour, passenger: Contour, config: RenderConfig) -> float:
    available_width = config.canvas_size - config.padding * 2 - config.gap
    available_height = config.canvas_size - config.padding * 2
    width_scale = available_width / (driver.width + passenger.width)
    height_scale = available_height / max(driver.height, passenger.height)
    return min(width_scale, height_scale)


def _simplify_polygon(polygon: Polygon, scale: float, tolerance_px: float) -> Polygon:
    """Remove tiny CAD artifacts using a pixel-based tolerance before rasterization."""

    if tolerance_px <= 0 or scale <= 0:
        return polygon
    simplified = polygon.simplify(tolerance_px / scale, preserve_topology=True)
    return simplified if isinstance(simplified, Polygon) and not simplified.is_empty else polygon


def _smooth_mask(mask: Image.Image, radius_px: int) -> Image.Image:
    """Round sharp mask corners in pixel space while keeping a crisp product edge."""

    if radius_px <= 0:
        return mask
    blur_radius = max(radius_px / 2.0, 0.1)
    rounded = mask.filter(ImageFilter.GaussianBlur(blur_radius))
    return rounded.point(lambda p: 255 if p >= 128 else 0)


def _draw_polygon(draw: ImageDraw.ImageDraw, polygon: Polygon, scale: float, ox: int, oy: int) -> None:
    exterior = [(round(x * scale) + ox, round(y * scale) + oy) for x, y in polygon.exterior.coords]
    draw.polygon(exterior, fill=255)
    for interior in polygon.interiors:
        hole = [(round(x * scale) + ox, round(y * scale) + oy) for x, y in interior.coords]
        draw.polygon(hole, fill=0)


def _drop_shadow(mask: Image.Image) -> Image.Image:
    offset = ImageChops.offset(mask, 22, 26)
    shadow_alpha = offset.filter(ImageFilter.GaussianBlur(34)).point(lambda p: int(p * 0.26))
    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    return shadow


def _inner_border_mask(mask: Image.Image, width: int) -> Image.Image:
    eroded = mask.filter(ImageFilter.MinFilter(width * 2 + 1))
    return ImageChops.subtract(mask, eroded)


def _inner_shadow(mask: Image.Image) -> Image.Image:
    shifted = ImageChops.offset(mask, -12, -14)
    edge = ImageChops.subtract(mask, shifted).filter(ImageFilter.GaussianBlur(16))
    edge = ImageChops.multiply(edge, mask).point(lambda p: int(p * 0.32))
    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    shadow.putalpha(edge)
    return shadow


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
