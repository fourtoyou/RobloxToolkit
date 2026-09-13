@echo off
cd /d "%~dp0"
python -m pip install --quiet customtkinter pystray pillow requests psutil pycaw pyinstaller
python -m PyInstaller --clean --onefile --noconsole --name RobloxToolkit --icon "%~dp0icon.ico" ^
  --collect-all customtkinter --hidden-import pystray._win32 --collect-all comtypes --hidden-import pycaw ^
  --distpath dist --workpath "%TEMP%\rtk_build" --specpath "%TEMP%\rtk_build" app.py
echo.
echo Build done: dist\RobloxToolkit.exe
