@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo cat-trash single-EXE builder
echo ============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://www.python.org/downloads/
    pause
    exit /b 1
)

for %%F in (cat_trash_win.py white_open.png white_closed.png) do (
    if not exist "%%F" (
        echo [ERROR] Missing file: %%F
        pause
        exit /b 1
    )
)

echo [1/4] Installing PyInstaller, PySide6, Pillow ...
py -m pip install --upgrade pyinstaller PySide6 Pillow
echo.

echo [2/4] Generating .ico for the EXE icon ...
py -c "from PIL import Image; img=Image.open('white_closed.png'); img.save('cat_icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
echo.

echo [3/4] Building EXE (this takes 1-3 minutes) ...
echo Using TEMP folder for build artifacts to avoid long-path issues
set BUILD_WORK=%TEMP%\catbuild_work
set BUILD_DIST=%TEMP%\catbuild_dist
if exist "%BUILD_WORK%" rmdir /s /q "%BUILD_WORK%"
if exist "%BUILD_DIST%" rmdir /s /q "%BUILD_DIST%"

py -m PyInstaller --onefile --noconsole --name CatTrash ^
    --workpath "%BUILD_WORK%" ^
    --distpath "%BUILD_DIST%" ^
    --icon "%CD%\cat_icon.ico" ^
    --add-data "%CD%\white_open.png;." ^
    --add-data "%CD%\white_closed.png;." ^
    "%CD%\cat_trash_win.py"
echo.

echo [4/4] Copying result back and cleaning up ...
if exist "%BUILD_DIST%\CatTrash.exe" (
    copy /y "%BUILD_DIST%\CatTrash.exe" "CatTrash.exe" >nul
)
if exist "%BUILD_WORK%" rmdir /s /q "%BUILD_WORK%"
if exist "%BUILD_DIST%" rmdir /s /q "%BUILD_DIST%"
if exist CatTrash.spec del /q CatTrash.spec
if exist cat_icon.ico del /q cat_icon.ico
echo.

echo ============================================================
if exist CatTrash.exe (
    echo SUCCESS: CatTrash.exe created in current folder
    dir CatTrash.exe | findstr CatTrash.exe
    echo.
    echo Distribute this single file to other PCs.
    echo No Python installation required on target machines.
) else (
    echo FAILED: see error messages above
)
echo ============================================================
pause
