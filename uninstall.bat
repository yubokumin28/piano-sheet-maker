@echo off
rem Piano Sheet uninstall: removes the AI parts that setup.bat installed.
echo ============================================
echo  Piano Sheet uninstall
echo  This deletes the AI parts (about 3GB) in:
echo    %LOCALAPPDATA%\PianoSheet
echo  and the voice separation model in your torch cache.
echo  Your scores in this folder (data) are NOT deleted.
echo ============================================
choice /c YN /m "Delete now"
if errorlevel 2 exit /b 0
taskkill /fi "WINDOWTITLE eq Piano Sheet server*" /f >nul 2>&1
if exist "%LOCALAPPDATA%\PianoSheet" rmdir /s /q "%LOCALAPPDATA%\PianoSheet"
if exist "%USERPROFILE%\.cache\torch\hub\checkpoints\955717e8-8726e21a.th" del /q "%USERPROFILE%\.cache\torch\hub\checkpoints\955717e8-8726e21a.th"
echo.
echo Done. To remove everything, delete this piano-sheet-maker folder too.
echo (If setup.bat installed Python 3.11, you can remove it from Settings - Apps.)
pause
