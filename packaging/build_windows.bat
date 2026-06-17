@echo off
setlocal
cd /d "%~dp0.."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm packaging\eva_renderer_gui.spec
echo.
echo Built EXE: dist\EVA_DXF_Renderer.exe
pause
