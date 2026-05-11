# EVA DXF Batch Renderer

Automatic renderer for premium e-commerce visuals of automotive EVA footrest mat pairs.

## Input layout

```text
Templates/
  <Brand>/
    <Model>/
      <Variant>/
        Main/
          *.dxf
        2/
          driver_*.dxf
          passenger_*.dxf
```

For every `2/` directory containing driver and passenger DXF files, the renderer creates:

```text
output/<Brand>_<Model>_<Variant>_2_driver_passenger.png
```

Example: `output/Audi_EVA1_art-2_2_driver_passenger.png`.

## Rendering behavior

- Extracts the dominant closed mat contour and ignores DXF text, dimensions, hatches, inserts, and guide entities.
- Uses the sibling `Main/` DXF as a high-quality reference for polygonization tolerances on dirty companion files.
- Renders a `2084 x 2084` px white canvas with `50` px padding and an exact `50` px gap between the driver and passenger mat bodies.
- Keeps both mats at the same scale and preserves original geometry proportions.
- Fills shapes with a repeated seamless material texture, applies a `10` px inner textured border, subtle inner shadow/highlight, and a soft studio drop shadow.
- Simplifies tiny CAD artifacts and rounds rasterized shape corners by `20` px by default, making the mats look softer and more natural.
- If texture PNGs are not supplied, deterministic procedural EVA-like fallback textures are generated.

## Install

Python 3.10+ is recommended.

```bash
python -m pip install -r requirements.txt
```

## Run

### Windows PowerShell

PowerShell does **not** use the Bash `\` continuation character. Run the command on one line:

```powershell
python -m eva_renderer.cli --templates Templates --output output --material-texture textures/eva_black.png --border-texture textures/border_black.png --corner-smoothing-px 20
```

Or split it with PowerShell backticks. The backtick must be the final character on the line, with no spaces after it:

```powershell
python -m eva_renderer.cli --templates Templates --output output `
  --material-texture textures/eva_black.png `
  --border-texture textures/border_black.png `
  --corner-smoothing-px 20
```

If you paste only a continuation line such as `--border-texture textures/border_black.png`, PowerShell treats `--` as an operator and raises `MissingExpressionAfterOperator`. Always include the initial `python -m eva_renderer.cli ...` part of the command.

### macOS, Linux, Git Bash, or WSL

```bash
python -m eva_renderer.cli --templates Templates --output output \
  --material-texture textures/eva_black.png \
  --border-texture textures/border_black.png \
  --corner-smoothing-px 20
```

For Windows without multiprocessing or for easier debugging:

```powershell
python -m eva_renderer.cli --templates Templates --output output --workers 1
```

Preview discovered jobs without rendering:

```powershell
python -m eva_renderer.cli --templates Templates --output output --dry-run
```

### Shape smoothing controls

By default, the renderer removes small CAD artifacts with `--simplify-tolerance-px 1.5` and rounds the final mask with `--corner-smoothing-px 20`. Increase `--corner-smoothing-px` for softer corners, or set either option to `0` to disable that step.

### Troubleshooting

If Windows shows `TypeError: RenderConfig.__init__() got an unexpected keyword argument 'corner_smoothing_px'`, the folder likely contains mixed file versions: newer `batch.py`/`cli.py` with an older `render.py`, or stale bytecode from a previous copy. Replace the whole `eva_renderer/` folder with the latest version, close old Python processes, and optionally delete `eva_renderer/__pycache__/`. For easier debugging you can rerun with `--workers 1`.

A quick PowerShell cleanup command is:

```powershell
Remove-Item -Recurse -Force .\eva_renderer\__pycache__ -ErrorAction SilentlyContinue
```
