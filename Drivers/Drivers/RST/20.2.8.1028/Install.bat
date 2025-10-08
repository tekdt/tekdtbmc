@echo off
call :setting
::=============================================================================================================================================================

Set keyword=iaStorVD.cat
call :uninstalllist

Set keyword=iaStorHsaComponent.cat
call :uninstalllist

Set keyword=iaStorHsa_Ext.cat
call :uninstalllist

::Please do not change below==================================================================================================================================
echo Install driver by pnputil
pnputil /add-driver *.inf /install >OLD_RST\New_Install.log
echo Install ReturnCode [%errorlevel%]

echo Un-Install previous old driver [OLD_RST]
powershell -command "ls -r -path .\OLD_RST -filter oem*.inf | select -exp name | foreach($_) { if((Select-string -path .\OLD_RST\New_Install.log -pattern "$_") -eq $null){$_ >>.\OLD_RST\Del_log.log | pnputil /delete-driver $_ /force /uninstall >>.\OLD_RST\Del_log.log }}  "                                                                                 

echo Un-Install ReturnCode [%errorlevel%]
if exist OLD_RST rd OLD_RST /s /q

SETLOCAL EnableDelayedExpansion

SET Found=0

FOR /F "TOKENS=*" %%a IN ('WMIC.exe /NAMESPACE:\\ROOT\MICROSOFT\WINDOWS\STORAGE PATH MSFT_DISK GET MODEL /FORMAT:LIST ^| FIND /I "="') DO (

	FOR /F "TOKENS=2* DELIMS==" %%A IN ('ECHO %%a') DO (
		IF "%%A"=="WD PC SN740 SDDPNQD-512G-1102" (SET Found=1)
		IF "%%A"=="WD PC SN560 SDDPNQE-1T00-1102" (SET Found=1)
		IF "%%A"=="WD PC SN740 SDDPNQE-2T00-1102" (SET Found=1)
	)
)

IF %Found% EQU 1 (

	SET ModifyKey=HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\iaStorVD\Parameters\Device

	REG QUERY !ModifyKey!
	IF !ERRORLEVEL! EQU 0 (
		REG ADD !ModifyKey! /V NvmeApstEnabled /T REG_DWORD /D 0 /F /REG:64
	)
)

goto :end


:uninstalllist
if %keyword%NOkeyword==NOkeyword goto :skip_u

find /i "%keyword%" C:\Windows\INF\oem*.inf

if %errorlevel% GEQ 1 echo %date% %time% Driver keyword [%keyword%] cannot be found under C:\Windows\INF\oem*.inf on the unit. Skip
if %errorlevel% GEQ 1 goto :skip_u
echo %date% %time% List old driver related with [%keyword%]
powershell -command "ls -r -path C:\windows\inf -filter oem*.inf | ?{$_ | select-string -pattern '%keyword%' } | select -exp name | foreach($_) { copy C:\windows\inf\$_ .\OLD_RST\$_  }"

:skip_u
 
Set keyword=
exit /b


:setting
title %~n0
cd /d "%~dp0"

if exist OLD_RST rd OLD_RST /s /q
if not exist OLD_RST mkdir OLD_RST

exit /b

:end

::1/7/2020