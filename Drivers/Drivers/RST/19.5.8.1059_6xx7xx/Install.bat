@ECHO off

ECHO.
ECHO Intel(R) Rapid Storage Technology Driver for Windows 10/11 64bit -WW-  
ECHO.

:: BatchGotAdmin
:-------------------------------------
REM  --> Check for permissions
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

REM --> If error flag set, we do not have admin.
if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"

    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"
:--------------------------------------


CALL pnputil.exe -a "%~dp0VMD\*.inf" /install
CALL pnputil.exe -a "%~dp0HsaExtension\*.inf" /install
CALL pnputil.exe -a "%~dp0HsaComponent\*.inf" /install


:END