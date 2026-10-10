@echo off
rem Piano Sheet launcher: start the local server and open the app window.
cd /d "%~dp0app"
set "PY=%LOCALAPPDATA%\PianoSheet\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Setup is not finished yet. Double-click setup.bat first.
  pause
  exit /b 1
)
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8790/api/scores -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Starting Piano Sheet ... please wait.
  start "Piano Sheet server (close this window to quit)" /min "%PY%" server.py
  powershell -NoProfile -Command "for($i=0;$i -lt 90;$i++){ try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8790/api/scores -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep 1 } }; exit 1"
  if errorlevel 1 (
    echo The app did not start. Run setup.bat again, then try once more.
    pause
    exit /b 1
  )
)
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%EDGE%" (
  start "" "%EDGE%" --app=http://127.0.0.1:8790 --window-size=1400,900
) else (
  start "" http://127.0.0.1:8790
)
exit /b 0
