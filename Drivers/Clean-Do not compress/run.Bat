@echo off
REM PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Clean-UnsignedDrivers.ps1" -rootPath "D:\TekDTMakeInstallationMedia\Drivers\Drivers\TouchPad"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Test-Unattend.ps1"
pause