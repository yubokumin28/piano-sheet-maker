@echo off
rem Piano Sheet setup (first time only). About 10-20 minutes. Internet is required.
cd /d "%~dp0"
echo ============================================
echo  Piano Sheet setup  (first time only)
echo  Please wait 10-20 minutes. Do not close this window.
echo ============================================

set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%ProgramFiles%\Python311\python.exe" set "PY=%ProgramFiles%\Python311\python.exe"
if not defined PY (
  echo.
  echo [1/5] Installing Python 3.11 ...
  winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
  echo [1/5] Python 3.11 found.
)
if not defined PY (
  echo.
  echo ERROR: Python 3.11 could not be installed automatically.
  echo Install "Python 3.11" from https://www.python.org/downloads/ and run setup.bat again.
  pause
  exit /b 1
)

echo.
echo [2/5] Creating a private Python environment (.venv) ...
if not exist ".venv\Scripts\python.exe" "%PY%" -m venv .venv
set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: could not create .venv
  pause
  exit /b 1
)
"%VPY%" -m pip install --upgrade pip --quiet

echo.
echo [3/5] Installing AI parts. This is the longest step ...
"%VPY%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto fail
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto fail
"%VPY%" -m pip install --no-deps demucs==4.1.0 dora-search openunmix julius lameenc einops treetable submitit retrying omegaconf antlr4-python3-runtime==4.9.3
if errorlevel 1 goto fail

echo.
echo [4/5] Downloading the screen parts and piano sounds ...
"%VPY%" app\tools\fetch_vendor.py
if errorlevel 1 goto fail

echo.
echo [5/5] Downloading the AI model that separates voice and music ...
"%VPY%" app\tools\prefetch_model.py
if errorlevel 1 goto fail

echo.
echo ============================================
echo  Setup finished.
echo  Double-click start_piano_sheet.bat to launch.
echo ============================================
pause
exit /b 0

:fail
echo.
echo ERROR: setup stopped. Check your internet connection and run setup.bat again.
echo (Finished parts are kept, so the second run is faster.)
pause
exit /b 1
