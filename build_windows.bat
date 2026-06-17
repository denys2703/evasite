@echo off
setlocal
cd /d "%~dp0"
call packaging\build_windows.bat
