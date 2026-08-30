@echo off
setlocal
title Create Desktop Shortcut - IPD Smart Sentinel

set "TARGET_DIR=%~dp0"
set "TARGET_BAT=%TARGET_DIR%START_WARD_HUB.bat"
set "SHORTCUT_NAME=IPD Smart Sentinel Ward Hub.lnk"

echo [*] Creating Windows Desktop Shortcut for IPD Smart Sentinel...

powershell -NoLogo -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
  "$shortcut = $ws.CreateShortcut((Join-Path $desktop '%SHORTCUT_NAME%')); " ^
  "$shortcut.TargetPath = '%TARGET_BAT%'; " ^
  "$shortcut.WorkingDirectory = '%TARGET_DIR%'; " ^
  "$shortcut.Description = 'Autonomous Ward Hub & Bedside PDA Companion'; " ^
  "$shortcut.Save()"

if %ERRORLEVEL% equ 0 (
    echo [OK] Shortcut created successfully on your Desktop: "%SHORTCUT_NAME%"
) else (
    echo [ERROR] Failed to create desktop shortcut.
)

pause
