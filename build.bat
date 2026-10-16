@echo off
rem Crea dist\WPdf.exe (un solo file). Serve: python -m pip install pyinstaller
cd /d %~dp0
python -m PyInstaller --noconfirm --clean --onefile --name WPdf ^
  --icon wpdf\assets\favicon.ico ^
  --add-data "wpdf\index.html;wpdf" ^
  --add-data "wpdf\assets;wpdf\assets" ^
  wpdf_exe.py
if errorlevel 1 (pause & exit /b 1)
echo.
echo Pronto: dist\WPdf.exe
