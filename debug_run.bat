@echo off
echo === STEP 1: current folder ===
cd /d "%~dp0"
cd
pause

echo.
echo === STEP 2: list files in folder ===
dir /b
pause

echo.
echo === STEP 3: python check ===
py --version
if errorlevel 1 (
    echo py command failed, trying python
    python --version
)
pause

echo.
echo === STEP 4: install PySide6 if missing ===
py -m pip show PySide6 >nul 2>nul
if errorlevel 1 (
    echo Installing PySide6 ...
    py -m pip install PySide6
) else (
    echo PySide6 already installed
)
pause

echo.
echo === STEP 5: install send2trash if missing ===
py -m pip show send2trash >nul 2>nul
if errorlevel 1 (
    echo Installing send2trash ...
    py -m pip install send2trash
) else (
    echo send2trash already installed
)
pause

echo.
echo === STEP 6: delete old position config ===
if exist cat_trash_config.txt del /q cat_trash_config.txt
echo done
pause

echo.
echo === STEP 7: launch widget (errors will show below) ===
py cat_trash_win.py
echo.
echo widget exited
pause
