@echo off
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt pyinstaller
rem spec เดียวกับที่ GitHub Actions ใช้ (.github/workflows/release.yml) — แก้ตัวเลือก build ที่ RobloxToolkit.spec ที่เดียว
python -m PyInstaller --clean --distpath dist --workpath "%TEMP%\rtk_build" RobloxToolkit.spec
echo.
echo Build done: dist\RobloxToolkit.exe
