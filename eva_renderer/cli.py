"""Command-line entry point for EVA DXF batch rendering."""

from __future__ import annotations

import argparse
from pathlib import Path

from .batch import BatchConfig, discover_jobs, run_batch_detailed

CLI_VERSION = "0.7.8"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render premium EVA mat visuals from Templates/**/*.dxf")
    parser.add_argument("--version", action="version", version=f"eva_renderer {CLI_VERSION}")
    parser.add_argument("--templates", type=Path, default=Path("Templates"), help="Templates root directory")
    parser.add_argument("--folder", type=Path, default=None, help="Render only this folder: a Templates subfolder, variant folder, or exact set")
    parser.add_argument("--set-folder", default="2", help="Folder name that contains front driver/passenger DXF files; default: 2")
    parser.add_argument("--rear-set-folder", default="7", help="Folder name that contains rear left/right DXF files; default: 7")
    parser.add_argument("--tunnel-set-folder", default="8", help="Folder name that contains tunnel DXF files; default: 8")
    parser.add_argument("--trunk-set-folders", default="12,13,14", help="Comma-separated trunk/category folder names; default: 12,13,14")
    parser.add_argument("--second-row-set-folder", default="17", help="Folder name that contains one-piece 2nd row mat; default: 17")
    parser.add_argument("--third-row-set-folder", default="18", help="Folder name that contains one-piece 3rd row mat; default: 18")
    parser.add_argument("--extra-set-folders", default="", help="Comma-separated additional folder names to render one-by-one, e.g. 20,21")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Output directory for transparent PNG renders")
    parser.add_argument("--log-file", type=Path, default=None, help="Batch log file path; defaults to output/render.log")
    parser.add_argument("--material-texture", type=Path, default=None, help="Seamless PNG for main EVA material")
    parser.add_argument("--border-texture", type=Path, default=None, help="Seamless PNG for inner border")
    parser.add_argument("--stitch-texture", type=Path, default=None, help="Optional transparent PNG texture for stitched thread overlay")
    parser.add_argument("--padding", type=int, default=100, help="Canvas padding in pixels; default 100")
    parser.add_argument("--gap", type=int, default=50, help="Horizontal gap between driver and passenger mats in pixels")
    parser.add_argument("--axis-align", choices=["top", "center", "bottom"], default="top", help="Vertical alignment for the pair: top, center, or bottom")
    parser.add_argument("--border-px", type=int, default=10, help="Inner border width in pixels")
    parser.add_argument("--drop-shadow-opacity", type=float, default=0.26, help="Drop shadow opacity multiplier")
    parser.add_argument("--inner-shadow-opacity", type=float, default=0.14, help="Main mat inner shadow opacity multiplier")
    parser.add_argument("--border-shadow-opacity", type=float, default=0.42, help="Border-only outer-edge shadow opacity multiplier")
    parser.add_argument(
        "--corner-smoothing-px",
        type=int,
        default=20,
        help="Pixel radius for natural geometric corner rounding; use 0 to disable",
    )
    parser.add_argument(
        "--corner-min-angle-deg",
        type=float,
        default=30.0,
        help="Minimum local corner angle to round; sharper corners are preserved, default 30",
    )
    parser.add_argument(
        "--simplify-tolerance-px",
        type=float,
        default=1.5,
        help="Pixel tolerance for removing tiny CAD artifacts before drawing; use 0 to disable",
    )
    parser.add_argument(
        "--material-texture-scale",
        type=float,
        default=1.0,
        help="Main material texture scale: 2.0 makes details larger, 0.5 repeats them more often",
    )
    parser.add_argument(
        "--border-texture-scale",
        type=float,
        default=1.0,
        help="Border texture scale: 2.0 makes details larger, 0.5 repeats them more often",
    )
    parser.add_argument(
        "--stitch-texture-scale",
        type=float,
        default=1.0,
        help="Stitch texture scale: 2.0 makes stitches larger, 0.5 repeats them more often",
    )
    parser.add_argument(
        "--stitch-offset-px",
        type=int,
        default=4,
        help="Distance in pixels from the border inner contour toward the outer edge for stitch placement",
    )
    parser.add_argument(
        "--stitch-width-px",
        type=int,
        default=3,
        help="Width in pixels of the stitch seam mask",
    )
    parser.add_argument(
        "--center-highlight-opacity",
        type=float,
        default=0.30,
        help="Opacity for the soft white 100x50 center highlight; use 0 to disable",
    )
    parser.add_argument(
        "--supersample",
        type=int,
        default=3,
        help="High-resolution mask multiplier for smoother edges; use 1 to disable",
    )
    parser.add_argument("--workers", type=int, default=None, help="Parallel worker count; use 1 to disable multiprocessing")
    parser.add_argument("--no-mirror-horizontal", action="store_true", help="Do not mirror each rendered mat horizontally")
    parser.add_argument("--dry-run", action="store_true", help="Print discovered jobs without rendering")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    render_dir = _resolve_render_dir(args.templates, args.folder)
    config = BatchConfig(
        templates_dir=args.templates,
        output_dir=args.output,
        render_dir=render_dir,
        set_folder_name=args.set_folder,
        rear_set_folder_name=args.rear_set_folder,
        tunnel_set_folder_name=args.tunnel_set_folder,
        trunk_set_folder_names=tuple(part.strip() for part in args.trunk_set_folders.split(",") if part.strip()),
        second_row_set_folder_name=args.second_row_set_folder,
        third_row_set_folder_name=args.third_row_set_folder,
        extra_set_folder_names=tuple(part.strip() for part in args.extra_set_folders.split(",") if part.strip()),
        log_file=args.log_file,
        material_texture=args.material_texture,
        border_texture=args.border_texture,
        stitch_texture=args.stitch_texture,
        padding=args.padding,
        gap=args.gap,
        border_px=args.border_px,
        drop_shadow_opacity=args.drop_shadow_opacity,
        inner_shadow_opacity=args.inner_shadow_opacity,
        border_shadow_opacity=args.border_shadow_opacity,
        corner_smoothing_px=args.corner_smoothing_px,
        corner_min_angle_deg=args.corner_min_angle_deg,
        simplify_tolerance_px=args.simplify_tolerance_px,
        material_texture_scale=args.material_texture_scale,
        border_texture_scale=args.border_texture_scale,
        stitch_texture_scale=args.stitch_texture_scale,
        stitch_offset_px=args.stitch_offset_px,
        stitch_width_px=args.stitch_width_px,
        center_highlight_opacity=args.center_highlight_opacity,
        supersample=args.supersample,
        mirror_horizontal=not args.no_mirror_horizontal,
        axis_align=args.axis_align,
        workers=args.workers if args.workers is not None else BatchConfig.workers,
    )
    jobs = discover_jobs(config)
    if args.dry_run:
        for job in jobs:
            print(f"{job.driver_dxf} + {job.passenger_dxf} -> {job.photo1_output_path}")
            if job.photo2_output_path:
                print(f"  full set -> {job.photo2_output_path}")
            if job.photo3_output_path:
                print(f"  trunk -> {job.photo3_output_path}")
            if job.photo4_output_path:
                print(f"  tunnel -> {job.photo4_output_path}")
            for extra_set in job.extra_sets:
                print(f"  extra {extra_set.folder_name}/ -> {extra_set.output_dir} ({len(extra_set.dxf_paths)} file(s))")
        print(f"Discovered {len(jobs)} job(s)")
        return 0
    results = run_batch_detailed(config, status_callback=print)
    for result in results:
        if result.ok:
            print("\n".join(str(path) for path in result.rendered_paths))
    ok_count = sum(1 for result in results if result.ok)
    image_count = sum(len(result.rendered_paths) for result in results if result.ok)
    print(f"Rendered {ok_count}/{len(results)} EVA folder(s), {image_count} image(s)")
    print(f"Log: {config.log_file or (config.output_dir / 'render.log')}")
    return 0


def _resolve_render_dir(templates_dir: Path, folder: Path | None) -> Path | None:
    if folder is None:
        return None
    if folder.exists():
        return folder
    return templates_dir / folder


if __name__ == "__main__":
    raise SystemExit(main())
