"""Command-line entry point for EVA DXF batch rendering."""

from __future__ import annotations

import argparse
from pathlib import Path

from .batch import BatchConfig, discover_jobs, run_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render premium EVA mat visuals from Templates/**/*.dxf")
    parser.add_argument("--templates", type=Path, default=Path("Templates"), help="Templates root directory")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Output directory for PNG renders")
    parser.add_argument("--material-texture", type=Path, default=None, help="Seamless PNG for main EVA material")
    parser.add_argument("--border-texture", type=Path, default=None, help="Seamless PNG for inner border")
    parser.add_argument(
        "--corner-smoothing-px",
        type=int,
        default=20,
        help="Pixel radius for natural corner rounding after rasterization; use 0 to disable",
    )
    parser.add_argument(
        "--simplify-tolerance-px",
        type=float,
        default=1.5,
        help="Pixel tolerance for removing tiny CAD artifacts before drawing; use 0 to disable",
    )
    parser.add_argument("--workers", type=int, default=None, help="Parallel worker count; use 1 to disable multiprocessing")
    parser.add_argument("--dry-run", action="store_true", help="Print discovered jobs without rendering")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = BatchConfig(
        templates_dir=args.templates,
        output_dir=args.output,
        material_texture=args.material_texture,
        border_texture=args.border_texture,
        corner_smoothing_px=args.corner_smoothing_px,
        simplify_tolerance_px=args.simplify_tolerance_px,
        workers=args.workers if args.workers is not None else BatchConfig.workers,
    )
    jobs = discover_jobs(config)
    if args.dry_run:
        for job in jobs:
            print(f"{job.driver_dxf} + {job.passenger_dxf} -> {job.output_path}")
        print(f"Discovered {len(jobs)} job(s)")
        return 0
    outputs = run_batch(config)
    for output in outputs:
        print(output)
    print(f"Rendered {len(outputs)} image(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
