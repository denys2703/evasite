"""Batch scanner and multiprocessing orchestration for Templates/ trees."""

from __future__ import annotations

from dataclasses import dataclass, fields
from multiprocessing import Pool, cpu_count
from pathlib import Path
import inspect
import re
from typing import Iterable


@dataclass(frozen=True)
class BatchConfig:
    templates_dir: Path = Path("Templates")
    output_dir: Path = Path("output")
    material_texture: Path | None = None
    border_texture: Path | None = None
    corner_smoothing_px: int = 20
    simplify_tolerance_px: float = 1.5
    material_texture_scale: float = 1.0
    border_texture_scale: float = 1.0
    supersample: int = 3
    workers: int = max(cpu_count() - 1, 1)


@dataclass(frozen=True)
class RenderJob:
    brand: str
    model: str
    variant: str
    set_name: str
    set_dir: Path
    main_dir: Path
    driver_dxf: Path
    passenger_dxf: Path
    output_path: Path


def discover_jobs(config: BatchConfig) -> list[RenderJob]:
    """Find every renderable ``2/`` set with driver and passenger DXF files."""

    jobs: list[RenderJob] = []
    if not config.templates_dir.exists():
        return jobs

    for set_dir in sorted(path for path in config.templates_dir.rglob("2") if path.is_dir()):
        try:
            variant_dir = set_dir.parent
            model_dir = variant_dir.parent
            brand_dir = model_dir.parent
            brand, model, variant = brand_dir.name, model_dir.name, variant_dir.name
        except IndexError:
            continue
        driver = _pick_footrest(set_dir.glob("*.dxf"), "driver")
        passenger = _pick_footrest(set_dir.glob("*.dxf"), "passenger")
        if driver is None or passenger is None:
            continue
        file_name = f"{brand}_{model}_{variant}_{set_dir.name}_driver_passenger.png"
        jobs.append(
            RenderJob(
                brand=brand,
                model=model,
                variant=variant,
                set_name=set_dir.name,
                set_dir=set_dir,
                main_dir=variant_dir / "Main",
                driver_dxf=driver,
                passenger_dxf=passenger,
                output_path=config.output_dir / file_name,
            )
        )
    return jobs


def run_batch(config: BatchConfig) -> list[Path]:
    """Render all discovered jobs and return generated PNG paths."""

    jobs = discover_jobs(config)
    if not jobs:
        return []
    args = [(job, config) for job in jobs]
    if config.workers <= 1 or len(args) == 1:
        return [_render_job(arg) for arg in args]
    with Pool(processes=config.workers) as pool:
        return pool.map(_render_job, args)


def _render_job(args: tuple[RenderJob, BatchConfig]) -> Path:
    from .dxf import extract_main_contour, load_reference_contour
    from .render import RenderConfig, render_pair

    job, config = args
    reference = load_reference_contour(job.main_dir)
    driver = extract_main_contour(job.driver_dxf, reference)
    passenger = extract_main_contour(job.passenger_dxf, reference)
    render_config = _make_render_config(RenderConfig, config)
    render_pair(driver, passenger, job.output_path, render_config)
    return job.output_path


def _pick_footrest(paths: Iterable[Path], side: str) -> Path | None:
    side_pattern = re.compile(rf"(^|[_\-\s]){re.escape(side)}([_\-\s]|$)", re.IGNORECASE)
    matches = [path for path in paths if side_pattern.search(path.stem)]
    if not matches:
        fallback = [path for path in paths if side.lower() in path.stem.lower()]
        matches = fallback
    if not matches:
        return None
    return sorted(matches, key=lambda p: ("footrest" not in p.stem.lower(), len(p.name), p.name.lower()))[0]


def _make_render_config(render_config_cls: type, config: BatchConfig) -> object:
    """Build a RenderConfig while tolerating mixed local file versions.

    On Windows it is common to copy only some project files while a previous
    worker process or editor still sees an older ``render.py``. Filtering the
    keyword arguments keeps multiprocessing from crashing with
    ``unexpected keyword argument`` and makes the batch runner compatible with
    both the current and the initial renderer config shape.
    """

    requested = {
        "material_texture": config.material_texture,
        "border_texture": config.border_texture,
        "corner_smoothing_px": config.corner_smoothing_px,
        "simplify_tolerance_px": config.simplify_tolerance_px,
        "material_texture_scale": config.material_texture_scale,
        "border_texture_scale": config.border_texture_scale,
        "supersample": config.supersample,
    }
    try:
        supported = {field.name for field in fields(render_config_cls)}
    except TypeError:
        supported = set(inspect.signature(render_config_cls).parameters)
    kwargs = {key: value for key, value in requested.items() if key in supported}
    return render_config_cls(**kwargs)
