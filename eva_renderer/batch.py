"""Batch scanner and multiprocessing orchestration for Templates/ trees."""

from __future__ import annotations

from dataclasses import dataclass, fields
from multiprocessing import Pool, cpu_count
from pathlib import Path
import inspect
import re
import time
import traceback
from typing import Callable, Iterable


@dataclass(frozen=True)
class BatchConfig:
    templates_dir: Path = Path("Templates")
    output_dir: Path = Path("output")
    render_dir: Path | None = None
    set_folder_name: str = "2"
    rear_set_folder_name: str = "7"
    tunnel_set_folder_name: str = "8"
    trunk_set_folder_names: tuple[str, ...] = ("12", "13", "14")
    second_row_set_folder_name: str = "17"
    third_row_set_folder_name: str = "18"
    extra_set_folder_names: tuple[str, ...] = ()
    log_file: Path | None = None
    material_texture: Path | None = None
    border_texture: Path | None = None
    stitch_texture: Path | None = None
    padding: int = 100
    gap: int = 50
    border_px: int = 10
    drop_shadow_opacity: float = 0.26
    inner_shadow_opacity: float = 0.14
    border_shadow_opacity: float = 0.42
    corner_smoothing_px: int = 20
    corner_min_angle_deg: float = 30.0
    simplify_tolerance_px: float = 1.5
    material_texture_scale: float = 1.0
    border_texture_scale: float = 1.0
    stitch_texture_scale: float = 1.0
    stitch_offset_px: int = 4
    stitch_width_px: int = 3
    center_highlight_opacity: float = 0.30
    supersample: int = 3
    mirror_horizontal: bool = True
    axis_align: str = "top"
    workers: int = max(min(cpu_count() // 2, 4), 1)


@dataclass(frozen=True)
class ExtraDxfSet:
    folder_name: str
    set_dir: Path
    dxf_paths: tuple[Path, ...]
    output_dir: Path


@dataclass(frozen=True)
class RenderJob:
    brand: str
    model: str
    variant: str
    set_name: str
    variant_dir: Path
    main_dir: Path
    front_dir: Path
    driver_dxf: Path
    passenger_dxf: Path
    output_dir: Path
    photo1_output_path: Path
    photo2_output_path: Path | None = None
    photo3_output_path: Path | None = None
    photo4_output_path: Path | None = None
    back_left_dxf: Path | None = None
    back_right_dxf: Path | None = None
    tunnel_dxf: Path | None = None
    trunk_dxf: Path | None = None
    second_row_dxf: Path | None = None
    third_row_dxf: Path | None = None
    extra_sets: tuple[ExtraDxfSet, ...] = ()

    @property
    def set_dir(self) -> Path:
        return self.front_dir

    @property
    def output_path(self) -> Path:
        return self.photo1_output_path


@dataclass(frozen=True)
class JobResult:
    job: RenderJob
    output_path: Path
    ok: bool
    elapsed_seconds: float
    rendered_paths: tuple[Path, ...] = ()
    error: str | None = None
    traceback_text: str | None = None


StatusCallback = Callable[[str], None]


def discover_jobs(config: BatchConfig) -> list[RenderJob]:
    """Find variants that can produce the EVA photo set."""

    jobs: list[RenderJob] = []
    search_root = config.render_dir or config.templates_dir
    front_set_name = (config.set_folder_name or "2").strip()
    if not search_root.exists() or not front_set_name:
        return jobs

    front_dirs = _candidate_set_dirs(search_root, front_set_name)
    for front_dir in sorted(path for path in front_dirs if path.is_dir()):
        try:
            variant_dir = front_dir.parent
            model_dir = variant_dir.parent
            brand_dir = model_dir.parent
            brand, model, variant = brand_dir.name, model_dir.name, variant_dir.name
        except IndexError:
            continue

        front_files = list(front_dir.glob("*.dxf"))
        driver = _pick_footrest(front_files, "driver", fallback_side="left")
        passenger = _pick_footrest(front_files, "passenger", fallback_side="right")
        if driver is None or passenger is None:
            continue

        rear_dir = variant_dir / config.rear_set_folder_name
        rear_files = list(rear_dir.glob("*.dxf")) if rear_dir.is_dir() else []
        back_left = _pick_footrest(rear_files, "back_left", fallback_side="left") or _pick_footrest(
            rear_files, "rear_left", fallback_side="left"
        )
        back_right = _pick_footrest(rear_files, "back_right", fallback_side="right") or _pick_footrest(
            rear_files, "rear_right", fallback_side="right"
        )

        tunnel_dir = variant_dir / config.tunnel_set_folder_name
        tunnel = _pick_single_dxf(list(tunnel_dir.glob("*.dxf")) if tunnel_dir.is_dir() else [], ("tunnel", "tonnel"))

        second_row_dir = variant_dir / config.second_row_set_folder_name
        second_row = _pick_single_dxf(
            list(second_row_dir.glob("*.dxf")) if second_row_dir.is_dir() else [],
            ("second", "2nd", "row", "rear", "back"),
        )
        third_row_dir = variant_dir / config.third_row_set_folder_name
        third_row = _pick_single_dxf(
            list(third_row_dir.glob("*.dxf")) if third_row_dir.is_dir() else [],
            ("third", "3rd", "row"),
        )

        trunk = None
        trunk_set = None
        for trunk_name in config.trunk_set_folder_names:
            trunk_dir = variant_dir / trunk_name
            candidate = _pick_single_dxf(list(trunk_dir.glob("*.dxf")) if trunk_dir.is_dir() else [], ("trunk", "bag", "cargo"))
            if candidate is not None:
                trunk = candidate
                trunk_set = trunk_name
                break

        eva_folder = config.output_dir / model
        prefix = _safe_filename(variant)
        photo1 = eva_folder / f"{prefix}_01_driver_passenger.png"
        has_rear_layout = second_row is not None or (back_left is not None and back_right is not None) or third_row is not None
        photo2 = eva_folder / f"{prefix}_02_full_set.png" if has_rear_layout else None
        photo3 = eva_folder / f"{prefix}_03_trunk_{trunk_set}.png" if trunk and trunk_set else None
        photo4 = eva_folder / f"{prefix}_04_tunnel.png" if tunnel else None
        extra_sets = _discover_extra_sets(variant_dir, eva_folder, config.extra_set_folder_names)
        jobs.append(
            RenderJob(
                brand=brand,
                model=model,
                variant=variant,
                set_name=front_dir.name,
                variant_dir=variant_dir,
                main_dir=variant_dir / "Main",
                front_dir=front_dir,
                driver_dxf=driver,
                passenger_dxf=passenger,
                output_dir=eva_folder,
                photo1_output_path=photo1,
                photo2_output_path=photo2,
                photo3_output_path=photo3,
                photo4_output_path=photo4,
                back_left_dxf=back_left,
                back_right_dxf=back_right,
                tunnel_dxf=tunnel,
                trunk_dxf=trunk,
                second_row_dxf=second_row,
                third_row_dxf=third_row,
                extra_sets=extra_sets,
            )
        )
    return jobs


def run_batch(config: BatchConfig, status_callback: StatusCallback | None = None) -> list[Path]:
    results = run_batch_detailed(config, status_callback=status_callback)
    return [path for result in results if result.ok for path in result.rendered_paths]


def run_batch_detailed(config: BatchConfig, status_callback: StatusCallback | None = None) -> list[JobResult]:
    """Render all jobs and return success/error details for logging or UI use."""

    jobs = discover_jobs(config)
    log_file = _resolve_log_file(config)
    _write_log_header(log_file, config, jobs)
    _emit(status_callback, f"Discovered {len(jobs)} EVA folder job(s)")
    if not jobs:
        return []

    workers = _effective_workers(config.workers, len(jobs))
    _append_log(log_file, f"Workers: {workers}\n")
    args = [(job, config) for job in jobs]
    results: list[JobResult] = []

    pool: Pool | None = None
    if workers <= 1 or len(args) == 1:
        iterator = (_render_job_result(arg) for arg in args)
    else:
        pool = Pool(processes=workers, maxtasksperchild=10)
        iterator = pool.imap_unordered(_render_job_result, args)

    completed = 0
    try:
        for result in iterator:
            completed += 1
            results.append(result)
            _log_result(log_file, result, completed, len(jobs))
            status = "OK" if result.ok else "ERROR"
            _emit(status_callback, f"[{completed}/{len(jobs)}] {status}: {result.job.model}/{result.job.variant}")
    except BaseException:
        if pool is not None:
            pool.terminate()
            pool.join()
            pool = None
        raise
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    ok_count = sum(1 for result in results if result.ok)
    image_count = sum(len(result.rendered_paths) for result in results if result.ok)
    _append_log(log_file, f"Summary: {ok_count}/{len(results)} EVA folders rendered, {image_count} image(s)\n")
    _emit(status_callback, f"Done: {ok_count}/{len(results)} EVA folders rendered, {image_count} image(s)")
    return results


def _render_job(args: tuple[RenderJob, BatchConfig]) -> Path:
    result = _render_job_result(args)
    if not result.ok:
        raise RuntimeError(result.error or "Render failed")
    return result.output_path


def _render_job_result(args: tuple[RenderJob, BatchConfig]) -> JobResult:
    from .dxf import extract_main_contour, load_reference_contour
    from .render import (
        RenderConfig,
        render_front_pair,
        render_full_set,
        render_trunk,
        render_tunnel,
        render_individual_set,
        _full_set_scale,
        _pair_scale,
        _replace_config,
    )

    job, config = args
    start = time.perf_counter()
    rendered: list[Path] = []
    try:
        reference = load_reference_contour(job.main_dir)
        driver = extract_main_contour(job.driver_dxf, reference)
        passenger = extract_main_contour(job.passenger_dxf, reference)
        render_config = _make_render_config(RenderConfig, config)
        front_style_scale = _pair_scale(driver, passenger, _replace_config(render_config, gap=-10))

        render_front_pair(driver, passenger, job.photo1_output_path, render_config)
        rendered.append(job.photo1_output_path)

        rear_contours = []
        third_row = None
        if job.photo2_output_path or job.photo4_output_path:
            if job.second_row_dxf:
                rear_contours.append(extract_main_contour(job.second_row_dxf, reference))
            elif job.back_left_dxf and job.back_right_dxf:
                rear_contours.extend([
                    extract_main_contour(job.back_left_dxf, reference),
                    extract_main_contour(job.back_right_dxf, reference),
                ])
            third_row = extract_main_contour(job.third_row_dxf, reference) if job.third_row_dxf else None
            if not rear_contours and third_row is not None:
                rear_contours.append(third_row)
                third_row = None

        if rear_contours:
            shared_scale = _full_set_scale(driver, passenger, rear_contours, render_config, third_row, 10, 20)
        else:
            shared_scale = _pair_scale(driver, passenger, _replace_config(render_config, gap=-10))

        if job.photo2_output_path and rear_contours:
            render_full_set(
                driver,
                passenger,
                rear_contours,
                None,
                job.photo2_output_path,
                render_config,
                third_row,
                shared_scale,
                front_style_scale,
            )
            rendered.append(job.photo2_output_path)

        if job.photo3_output_path and job.trunk_dxf:
            trunk = extract_main_contour(job.trunk_dxf, reference)
            render_trunk(trunk, job.photo3_output_path, render_config, shared_scale, front_style_scale)
            rendered.append(job.photo3_output_path)

        if job.photo4_output_path and job.tunnel_dxf:
            tunnel = extract_main_contour(job.tunnel_dxf, reference)
            render_tunnel(
                tunnel,
                job.photo4_output_path,
                render_config,
                driver,
                passenger,
                rear_contours,
                third_row,
                shared_scale,
                front_style_scale,
            )
            rendered.append(job.photo4_output_path)

        for extra_set in job.extra_sets:
            contours = [extract_main_contour(path, reference) for path in extra_set.dxf_paths]
            output_paths = tuple(extra_set.output_dir / f"{_safe_filename(path.stem)}.png" for path in extra_set.dxf_paths)
            render_individual_set(contours, output_paths, render_config, shared_scale, front_style_scale)
            rendered.extend(output_paths)

        return JobResult(
            job=job,
            output_path=job.photo1_output_path,
            ok=True,
            elapsed_seconds=time.perf_counter() - start,
            rendered_paths=tuple(rendered),
        )
    except Exception as exc:
        return JobResult(
            job=job,
            output_path=job.photo1_output_path,
            ok=False,
            elapsed_seconds=time.perf_counter() - start,
            rendered_paths=tuple(rendered),
            error=str(exc),
            traceback_text=traceback.format_exc(),
        )


def _discover_extra_sets(variant_dir: Path, eva_folder: Path, folder_names: tuple[str, ...]) -> tuple[ExtraDxfSet, ...]:
    sets: list[ExtraDxfSet] = []
    for folder_name in folder_names:
        clean_name = folder_name.strip()
        if not clean_name:
            continue
        set_dir = variant_dir / clean_name
        if not set_dir.is_dir():
            continue
        dxf_paths = tuple(sorted(set_dir.glob("*.dxf"), key=lambda path: path.name.lower()))
        if not dxf_paths:
            continue
        sets.append(
            ExtraDxfSet(
                folder_name=clean_name,
                set_dir=set_dir,
                dxf_paths=dxf_paths,
                output_dir=eva_folder / _safe_filename(clean_name),
            )
        )
    return tuple(sets)


def _candidate_set_dirs(search_root: Path, set_folder_name: str) -> list[Path]:
    if search_root.is_dir() and search_root.name == set_folder_name:
        return [search_root]
    if search_root.is_dir() and (search_root / set_folder_name).is_dir():
        return [search_root / set_folder_name]
    return list(search_root.rglob(set_folder_name))


def _pick_footrest(paths: Iterable[Path], side: str, fallback_side: str | None = None) -> Path | None:
    path_list = list(paths)
    matches = _side_matches(path_list, side)
    if not matches and fallback_side:
        matches = _side_matches(path_list, fallback_side)
    if not matches:
        return None
    return sorted(matches, key=lambda p: ("footrest" not in p.stem.lower(), len(p.name), p.name.lower()))[0]


def _pick_single_dxf(paths: Iterable[Path], preferred_words: tuple[str, ...] = ()) -> Path | None:
    path_list = sorted(paths, key=lambda p: p.name.lower())
    if not path_list:
        return None
    for word in preferred_words:
        matches = _side_matches(path_list, word)
        if matches:
            return sorted(matches, key=lambda p: (len(p.name), p.name.lower()))[0]
    return path_list[0]


def _side_matches(paths: Iterable[Path], side: str) -> list[Path]:
    tokens = [token for token in re.split(r"[_\-\s]+", side.lower()) if token]
    patterns = [re.compile(rf"(^|[_\-\s]){re.escape(token)}([_\-\s]|$)", re.IGNORECASE) for token in tokens]
    matches = [path for path in paths if all(pattern.search(path.stem) for pattern in patterns)]
    if matches:
        return matches
    return [path for path in paths if all(token in path.stem.lower() for token in tokens)]


def _make_render_config(render_config_cls: type, config: BatchConfig) -> object:
    """Build a RenderConfig while tolerating mixed local file versions."""

    requested = {
        "material_texture": config.material_texture,
        "border_texture": config.border_texture,
        "stitch_texture": config.stitch_texture,
        "padding": config.padding,
        "gap": config.gap,
        "border_px": config.border_px,
        "drop_shadow_opacity": config.drop_shadow_opacity,
        "inner_shadow_opacity": config.inner_shadow_opacity,
        "border_shadow_opacity": config.border_shadow_opacity,
        "corner_smoothing_px": config.corner_smoothing_px,
        "corner_min_angle_deg": config.corner_min_angle_deg,
        "simplify_tolerance_px": config.simplify_tolerance_px,
        "material_texture_scale": config.material_texture_scale,
        "border_texture_scale": config.border_texture_scale,
        "stitch_texture_scale": config.stitch_texture_scale,
        "stitch_offset_px": config.stitch_offset_px,
        "stitch_width_px": config.stitch_width_px,
        "center_highlight_opacity": config.center_highlight_opacity,
        "supersample": config.supersample,
        "mirror_horizontal": config.mirror_horizontal,
        "axis_align": config.axis_align,
    }
    try:
        supported = {field.name for field in fields(render_config_cls)}
    except TypeError:
        supported = set(inspect.signature(render_config_cls).parameters)
    kwargs = {key: value for key, value in requested.items() if key in supported}
    return render_config_cls(**kwargs)


def _effective_workers(requested_workers: int, job_count: int) -> int:
    safe_max = max(min(cpu_count() // 2, 4), 1)
    requested = requested_workers if requested_workers and requested_workers > 0 else safe_max
    return max(1, min(requested, safe_max, job_count))


def _resolve_log_file(config: BatchConfig) -> Path:
    return config.log_file or (config.output_dir / "render.log")


def _write_log_header(log_file: Path, config: BatchConfig, jobs: list[RenderJob]) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "EVA renderer batch log\n",
        f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"Templates: {config.templates_dir}\n",
        f"Selected folder: {config.render_dir or '<all>'}\n",
        f"Front DXF folder: {config.set_folder_name}\n",
        f"Rear DXF folder: {config.rear_set_folder_name}\n",
        f"Tunnel DXF folder: {config.tunnel_set_folder_name}\n",
        f"Trunk DXF folders: {', '.join(config.trunk_set_folder_names)}\n",
        f"2nd row DXF folder: {config.second_row_set_folder_name}\n",
        f"3rd row DXF folder: {config.third_row_set_folder_name}\n",
        f"Extra DXF folders: {', '.join(config.extra_set_folder_names) or '<none>'}\n",
        f"Output: {config.output_dir}\n",
        f"Jobs discovered: {len(jobs)}\n",
        "\nDiscovered jobs:\n",
    ]
    for job in jobs:
        extras = []
        if job.photo2_output_path:
            extras.append("photo2")
        if job.photo3_output_path:
            extras.append("photo3")
        if job.photo4_output_path:
            extras.append("photo4")
        if job.extra_sets:
            extras.append("extra=" + "+".join(extra.folder_name for extra in job.extra_sets))
        lines.append(
            f"- {job.brand}/{job.model}/{job.variant}: front={job.driver_dxf.name}+{job.passenger_dxf.name}, "
            f"output_folder={job.output_dir}, extra={','.join(extras) or 'none'}\n"
        )
    lines.append("\nRender results:\n")
    log_file.write_text("".join(lines), encoding="utf-8")


def _log_result(log_file: Path, result: JobResult, completed: int, total: int) -> None:
    status = "OK" if result.ok else "ERROR"
    rendered = ", ".join(str(path) for path in result.rendered_paths) or "<none>"
    line = (
        f"[{completed}/{total}] {status} {result.job.brand}/{result.job.model}/{result.job.variant} "
        f"-> {rendered} ({result.elapsed_seconds:.2f}s)\n"
    )
    if result.error:
        line += f"  Error: {result.error}\n"
    if result.traceback_text:
        line += result.traceback_text + "\n"
    _append_log(log_file, line)


def _append_log(log_file: Path, text: str) -> None:
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _emit(callback: StatusCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-zА-Яа-я0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "EVA"
