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

For every renderable variant, the renderer creates an EVA/model output folder with transparent PNG product photos:

```text
output/<Model>/<Variant>_01_driver_passenger.png
output/<Model>/<Variant>_02_full_set.png
output/<Model>/<Variant>_03_trunk_<folder>.png
output/<Model>/<Variant>_04_tunnel.png
```

Example: `output/EVA1/art-2_01_driver_passenger.png`.

## Rendering behavior

- Extracts the dominant closed mat contour and ignores DXF text, dimensions, hatches, inserts, and guide entities.
- Uses the sibling `Main/` DXF as a high-quality reference for polygonization tolerances on dirty companion files.
- Renders photo `#1` on a fixed `2084 x 2084` transparent canvas with `100` px padding by default, an exact configurable gap between the driver and passenger mat bodies, and top-aligned mats.
- Keeps both mats at the same scale and preserves original geometry proportions.
- Fills shapes with a repeated seamless material texture, applies a `10` px inner textured border, a border-only outer-edge rim shadow for upholstery depth, a stitched thread overlay, two clipped softbox-style volume shadows, several soft highlights, and no floor/drop shadow under the mats.
- Simplifies tiny CAD artifacts, uses local smart corner rounding by `20` px, skips very acute notches below `--corner-min-angle-deg 30`, and renders masks with `3x` supersampling by default so edges look smoother and less jagged.
- Supports independent material, border, and stitch texture scaling without stretching the mat geometry; non-`#1` outputs automatically scale material tiling, border width, stitch width/offset, and corner cleanup against photo `#1` so the visual finish matches when the kit is assembled.
- If texture PNGs are not supplied, deterministic procedural EVA-like fallback textures are generated.
- Batch rendering uses a bounded worker pool by default so several cars are rendered at once without using every CPU core.
- A batch log is written to `output/render.log` by default with discovered brands/models/variants, rendered folders, output files, timings, and errors.

## Install

Python 3.10+ is recommended.

```bash
python -m pip install -r requirements.txt
```

## Run

### Windows PowerShell

PowerShell does **not** use the Bash `\` continuation character. Run the command on one line:

```powershell
python -m eva_renderer.cli --templates Templates --output output --folder Audi/EVA1/art-2 --material-texture textures/eva_black.png --border-texture textures/border_black.png --stitch-texture textures/stitch_threads.png --padding 100 --gap 50 --border-px 10 --border-shadow-opacity 0.42 --corner-smoothing-px 20 --material-texture-scale 1.0 --border-texture-scale 1.0 --stitch-offset-px 4
```

Or split it with PowerShell backticks. The backtick must be the final character on the line, with no spaces after it:

```powershell
python -m eva_renderer.cli --templates Templates --output output `
  --folder Audi/EVA1/art-2 `
  --material-texture textures/eva_black.png `
  --border-texture textures/border_black.png `
  --stitch-texture textures/stitch_threads.png `
  --padding 100 `
  --gap 50 `
  --border-px 10 `
  --border-shadow-opacity 0.42 `
  --corner-smoothing-px 20 `
  --material-texture-scale 1.0 `
  --border-texture-scale 1.0 `
  --stitch-offset-px 4
```

If you paste only a continuation line such as `--border-texture textures/border_black.png`, PowerShell treats `--` as an operator and raises `MissingExpressionAfterOperator`. Always include the initial `python -m eva_renderer.cli ...` part of the command.

### macOS, Linux, Git Bash, or WSL

```bash
python -m eva_renderer.cli --templates Templates --output output \
  --folder Audi/EVA1/art-2 \
  --material-texture textures/eva_black.png \
  --border-texture textures/border_black.png \
  --stitch-texture textures/stitch_threads.png \
  --padding 100 \
  --gap 50 \
  --border-px 10 \
  --border-shadow-opacity 0.42 \
  --corner-smoothing-px 20 \
  --material-texture-scale 1.0 \
  --border-texture-scale 1.0 \
  --stitch-offset-px 4
```

For Windows without multiprocessing or for easier debugging:

```powershell
python -m eva_renderer.cli --templates Templates --output output --workers 1
```

Preview discovered jobs without rendering:

```powershell
python -m eva_renderer.cli --templates Templates --output output --dry-run
```

Render only one subtree or exact `2/` set with `--folder`. The value can be an absolute/relative path or a path relative to `--templates`, for example `--folder Audi/EVA1/art-2` or `--folder Templates/Audi/EVA1/art-2/2`.

### Batch speed and logs

By default, the renderer uses a safe worker count: half of CPU cores, capped at 4. This renders several images at the same time without trying to consume the whole machine. Tune it with `--workers`; use `--workers 1` for debugging or low-memory PCs.

Every run writes a log file. By default it is `output/render.log`; override it with `--log-file logs/my_run.log`. The log includes discovered jobs, brand/model/variant/set folders, driver/passenger DXF names, output PNG paths, render time per image, and tracebacks for failed DXFs.

Example:

```powershell
python -m eva_renderer.cli --templates Templates --output output --workers 3 --log-file output/render.log
```

## Windows GUI app

A PySide6 desktop app is included and can be launched without packaging:

```powershell
python -m eva_renderer.gui
```

The GUI follows the provided desktop mockup as a pure Python PySide6/QSS interface: compact 820px-style layout, `#f2f2f7` background, white 20px-radius cards, centered section titles, 106px labels, compact 24px rounded input fields, blue primary buttons, gray secondary buttons, a two-column render settings grid, an in-window real batch render process, a compact progress bar, a selectable DXF source folder, Left/Right DXF pair detection, top/center/bottom axis alignment, automatic horizontal mat mirroring, brandless output filenames, a Stop control, persisted GUI settings, and a large flexible live status panel. It provides:

- Templates folder picker.
- Optional single-folder picker for one brand/model/variant/set scope.
- DXF set folder picker/name field, defaulting to `2`, with Left/Right pair detection for folders like `7`.
- Output folder picker.
- Material, border, and stitch texture pickers.
- Worker count and key render options.
- Determinate status/progress bar based on completed jobs.
- Top/center/bottom axis alignment for the rendered pair.
- Automatic horizontal mirroring for every rendered mat.
- Output filenames without the leading brand folder segment.
- Real in-window render launch through the batch pipeline, with compact progress bar and Stop button for running work.
- Saved GUI configuration so paths and settings persist after restart.
- Live batch messages in a soft status panel.
- Buttons to open the output folder and `render.log`.

### Build one Windows EXE

On Windows, from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm packaging\eva_renderer_gui.spec
```

The one-file GUI executable will be created at:

```text
dist/EVA_DXF_Renderer.exe
```

Alternatively, use the root helper script from PowerShell. This is the simplest option:

```powershell
.\build_windows.bat
```

Or use the root PowerShell helper:

```powershell
& .\build_windows.ps1
```

The older helper scripts still exist under `packaging/`, but if PowerShell says `ObjectNotFound` for `./packaging/build_windows.ps1`, you are either not in the project root or the `packaging` folder was not copied. Check your location with:

```powershell
Get-Location
Test-Path .\packaging\build_windows.ps1
Test-Path .\build_windows.bat
```

If `Test-Path .\packaging\build_windows.ps1` prints `False`, copy the full updated project folder again or just use the root `build_windows.bat` from this version.

If PowerShell blocks `.ps1` scripts by execution policy, use the `.bat` command above or run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

### Shape smoothing controls

By default, the renderer removes small CAD artifacts with `--simplify-tolerance-px 1.5`, rounds eligible vector corners with `--corner-smoothing-px 20`, and rasterizes at `--supersample 3` for anti-aliased edges. The corner rounder is local and angle-aware: `--corner-min-angle-deg 30` preserves very sharp cutouts/notches instead of closing or lifting them when the radius is increased. Increase `--corner-smoothing-px` for softer eligible corners, raise `--supersample` to `4` for even cleaner edges, or set smoothing/simplification to `0` to disable that step.

### Texture and stitch controls

Use `--material-texture-scale`, `--border-texture-scale`, and `--stitch-texture-scale` to control visual texture size. `2.0` makes details twice as large, while `0.5` makes the pattern repeat twice as often. These settings only change UV tiling; they do not stretch the DXF shape.

The stitch overlay uses `--stitch-texture` when supplied, otherwise a procedural transparent thread texture is generated. By default it is placed `4` px from the inner contour of the border toward the outer edge (`--stitch-offset-px 4`) with a `3` px seam mask (`--stitch-width-px 3`).

The center highlight is a white `100 x 50` px soft patch blurred by `250` px at `30%` opacity. Use `--center-highlight-opacity 0` to disable it or lower the value for a subtler reflection.

### Layout, border, and shadow controls

Mats are top-aligned by default and use `--padding 100` so the first visible body point starts 100 px from the top canvas edge. Horizontal layout remains centered as a pair, and `--gap` controls the space between mats. Use `--border-px` to change the inner border width, `--drop-shadow-opacity` for the studio floor shadow, `--inner-shadow-opacity` for the mat surface depth, and `--border-shadow-opacity` for the upholstery rim shadow.

### Troubleshooting

If Windows shows `error: unrecognized arguments: --supersample 4`, Python is running an older `eva_renderer/cli.py`. The current CLI must show `--supersample`, `--material-texture-scale`, and `--border-texture-scale` in help output. Verify the version and help with:

```powershell
python -m eva_renderer.cli --version
python -m eva_renderer.cli --help
```

If `--version` crashes with `ImportError: cannot import name '__version__'`, Python is running a mixed copy where `cli.py` is newer than `__init__.py`. In version `0.2.1+`, the CLI no longer imports `__version__` from `__init__.py`, so replacing at least `eva_renderer/cli.py` fixes that specific crash. Best practice is still to replace the whole `eva_renderer/` folder and clear stale bytecode. A quick PowerShell cleanup command is:

```powershell
Remove-Item -Recurse -Force .\eva_renderer\__pycache__ -ErrorAction SilentlyContinue
```

If Windows shows `TypeError: RenderConfig.__init__() got an unexpected keyword argument 'corner_smoothing_px'`, the folder likely contains mixed file versions: newer `batch.py`/`cli.py` with an older `render.py`, or stale bytecode from a previous copy. Replace the whole `eva_renderer/` folder with the latest version, close old Python processes, and rerun the cleanup command above. For easier debugging you can rerun with `--workers 1`.

## EVA photo set output

The batch renderer now creates one output folder per EVA/model number, for example `output/EVA1/`, instead of placing a single flat PNG in `output/`.

For each renderable variant it can produce up to four images:

1. `<variant>_01_driver_passenger.png` — front driver + passenger mats from folder `2`. The left mat is rotated by `5°`, the right mat by `-5°`/`355°`, and the pair uses a tight `-10px` gap for a denser product-photo composition.
2. `<variant>_02_full_set.png` — the full kit is vertically centered on the transparent canvas: front driver + passenger from folder `2`, then either a one-piece 2nd-row mat from folder `17` or rear left + rear right from folder `7`; a 3rd-row mat from folder `18` is added below when present. Folder `8` is not placed here anymore.
3. `<variant>_03_trunk_<folder>.png` — trunk/category mat from the first available folder among `12`, `13`, and `14`.
4. `<variant>_04_tunnel.png` — tunnel mat from folder `8` as a separate transparent PNG, rendered with the same shared kit scale as the other non-`#1` outputs so Photoshop assembly matches.

### Extra one-by-one DXF folders

Use `--extra-set-folders` for any additional folder numbers you want to render separately for manual Photoshop assembly. For example, `--extra-set-folders 20,21` creates subfolders inside the existing EVA/model output folder:

```text
output/<Model>/20/<dxf-stem>.png
output/<Model>/21/<dxf-stem>.png
```

Every DXF in those folders is rendered as its own transparent PNG using the shared non-`#1` kit scale, so trunk/tunnel/extra elements match each other for Photoshop assembly. Material tiling, border width, stitch details, and corner cleanup are normalized to photo `#1` scale so the finish stays consistent across differently sized outputs. The GUI has the same setting as `Extra folders`.

The GUI exposes separate folder fields for front `2`, rear `7`, tunnel `8`, trunk/category `12/13/14`, 2nd-row `17`, and 3rd-row `18` folders. The file/folder card and Render Settings card use tighter row spacing and the Live status card is intentionally shorter so all controls remain visible in the default window. Folder `7` supports files named with `Left`/`Right` as well as `Driver`/`Passenger` naming. If folder `17` exists, it replaces the two separate back mats in the full-set layout. CLI users can override these with:

```powershell
python -m eva_renderer.cli --templates Templates --output output `
  --set-folder 2 --rear-set-folder 7 --tunnel-set-folder 8 `
  --trunk-set-folders 12,13,14 --second-row-set-folder 17 --third-row-set-folder 18
```

Corner smoothing is local and angle-aware: `--corner-smoothing-px` controls the radius, while `--corner-min-angle-deg 30` preserves very sharp cutouts/notches so narrow features are not lifted or closed when the radius is increased.
