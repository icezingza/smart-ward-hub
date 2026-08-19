@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_smart_ward_hub.ps1" %*
exit /b %ERRORLEVEL%
