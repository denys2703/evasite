"""Texture loading, tiling, and procedural EVA-style fallbacks."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def load_texture(path: Path | None, fallback: str, size: int = 256) -> Image.Image:
    """Load a seamless PNG texture or create a procedural fallback."""

    if path is not None and path.exists():
        return Image.open(path).convert("RGBA")
    if fallback == "border":
        return _border_texture(size)
    return _eva_texture(size)


def tile_texture(
    texture: Image.Image,
    size: tuple[int, int],
    offset: tuple[int, int] = (0, 0),
    texture_scale: float = 1.0,
) -> Image.Image:
    """Repeat ``texture`` into an image of ``size`` without UV stretching.

    ``texture_scale`` changes the tile size: ``2.0`` makes texture details twice
    as large, while ``0.5`` repeats them twice as often.
    """

    width, height = size
    base = Image.new("RGBA", size, (255, 255, 255, 0))
    texture = _scale_texture(texture, texture_scale)
    tw, th = texture.size
    start_x = -(offset[0] % tw)
    start_y = -(offset[1] % th)
    for y in range(start_y, height, th):
        for x in range(start_x, width, tw):
            base.alpha_composite(texture, (x, y))
    return base


def _eva_texture(size: int) -> Image.Image:
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 9, (size, size)).astype(np.int16)
    base = np.zeros((size, size, 4), dtype=np.uint8)
    base[..., 0] = np.clip(30 + noise, 0, 255)
    base[..., 1] = np.clip(31 + noise, 0, 255)
    base[..., 2] = np.clip(34 + noise, 0, 255)
    base[..., 3] = 255
    image = Image.fromarray(base, "RGBA").filter(ImageFilter.GaussianBlur(0.35))
    draw = ImageDraw.Draw(image, "RGBA")
    step = max(size // 16, 12)
    radius = max(step // 5, 2)
    for y in range(step // 2, size + step, step):
        for x in range(step // 2, size + step, step):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(12, 13, 15, 55))
            draw.ellipse((x - radius + 1, y - radius + 1, x + radius - 1, y + radius - 1), outline=(78, 79, 83, 45))
    return image


def _border_texture(size: int) -> Image.Image:
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 7, (size, size)).astype(np.int16)
    base = np.zeros((size, size, 4), dtype=np.uint8)
    base[..., 0] = np.clip(54 + noise, 0, 255)
    base[..., 1] = np.clip(55 + noise, 0, 255)
    base[..., 2] = np.clip(58 + noise, 0, 255)
    base[..., 3] = 255
    image = Image.fromarray(base, "RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    for x in range(-size, size * 2, 18):
        draw.line((x, 0, x + size, size), fill=(115, 116, 120, 50), width=2)
    return image.filter(ImageFilter.GaussianBlur(0.2))


def _scale_texture(texture: Image.Image, texture_scale: float) -> Image.Image:
    if texture_scale <= 0:
        texture_scale = 1.0
    if abs(texture_scale - 1.0) < 1e-6:
        return texture
    width = max(1, round(texture.width * texture_scale))
    height = max(1, round(texture.height * texture_scale))
    return texture.resize((width, height), Image.Resampling.LANCZOS)
