@echo off
setlocal
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller==6.15.0
py -m PyInstaller --noconfirm --clean --onefile --windowed --name SOOP-Quiz-Overlay app.py
if errorlevel 1 exit /b 1
echo.
echo Built: dist\SOOP-Quiz-Overlay.exe
