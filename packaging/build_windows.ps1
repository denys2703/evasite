$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm packaging\eva_renderer_gui.spec

Write-Host ""
Write-Host "Built EXE: dist\EVA_DXF_Renderer.exe" -ForegroundColor Green
