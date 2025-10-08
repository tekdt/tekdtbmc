REM ========================================================
REM   Driver deliverable installation
REM ========================================================

@ECHO OFF
SET "Template=v1.07.cps"
if defined FCC_LOG_FOLDER (SET "APP_LOG_FOLDER=%FCC_LOG_FOLDER%") else (SET "APP_LOG_FOLDER=%~d0\programdata\hp\logs")
SET "APP_LOG=%APP_LOG_FOLDER%\%~n0.log"
if not exist "%APP_LOG_FOLDER%" md "%APP_LOG_FOLDER%"

ECHO ############################################################# >> %APP_LOG%
ECHO  [%DATE%]                                                     >> %APP_LOG%
ECHO  [%TIME%] Beginning of the %~nx0, Ver: %Template%             >> %APP_LOG%
ECHO ############################################################# >> %APP_LOG%

set "ExtensionGuid={e2f84ce7-8efa-411c-aa69-97454ca4cb57}"
set "SoftwareComponenGuid={5c4c3332-344d-483c-8739-259e934c9cc8}"

REM ------------------- Script Entry ------------------------
:DCH_Driver
echo [%TIME%] Search DCH driver >> %APP_LOG%
set "drv_root=%~dp0Driver"
dir /ad "%drv_root%" >nul 2>>&1 
if errorlevel 1 echo [%TIME%] No driver folder found. >> %APP_LOG% & goto IHV_Driver

for /f "delims=" %%a in ('dir /ad /b "%drv_root%"') do (
	if not exist "%drv_root%\%%~a\drvorder.txt" (
		echo [%TIME%] Search BASE driver in "%drv_root%\%%~a\*.inf" >> %APP_LOG%
		if not exist "%drv_root%\%%~a\*.inf" echo [%TIME%] No .inf found. >> %APP_LOG% & goto RESULTFAILED
		for /f "delims=" %%i in ('dir /a-d /b "%drv_root%\%%~a\*.inf"') do (
			echo [%TIME%] Check "%drv_root%\%%~a\%%~i" driver category. >> %APP_LOG%
			call:ChkDrvClassGuid "%drv_root%\%%~a\%%~i" "%ExtensionGuid% %SoftwareComponenGuid%"
			if errorlevel 1 (
				echo [%TIME%] Driver category match, install it. >> %APP_LOG%
				call:DrvInst "%drv_root%\%%~a\%%~i"
				if errorlevel 1 echo [%TIME%] %%~i driver install failed. >> %APP_LOG% & goto RESULTFAILED
				echo [%TIME%] %%~i driver install success. >> %APP_LOG%
			) else (
				echo [%TIME%] Driver category mismatch. >> %APP_LOG%
			)
		)
		echo. >> %APP_LOG%
		echo [%TIME%] Search EXTENSION driver in "%drv_root%\%%~a\*.inf" >> %APP_LOG%
		for /f "delims=" %%i in ('dir /a-d /b "%drv_root%\%%~a\*.inf"') do (
			echo [%TIME%] Check "%drv_root%\%%~a\%%~i" driver category. >> %APP_LOG%
			call:ChkDrvClassGuid "%drv_root%\%%~a\%%~i" "%ExtensionGuid%"
			if not errorlevel 1 (
				echo [%TIME%] Driver category match, install it. >> %APP_LOG%
				call:DrvInst "%drv_root%\%%~a\%%~i"
				if errorlevel 1 echo [%TIME%] %%~i driver install failed. >> %APP_LOG% & goto RESULTFAILED
				echo [%TIME%] %%~i driver install success. >> %APP_LOG%
			) else (
				echo [%TIME%] Driver category mismatch. >> %APP_LOG%
			)
		)
		echo. >> %APP_LOG%
		echo [%TIME%] Search COMPONENT driver in "%drv_root%\%%~a\*.inf" >> %APP_LOG%
		for /f "delims=" %%i in ('dir /a-d /b "%drv_root%\%%~a\*.inf"') do (
			echo [%TIME%] Check "%drv_root%\%%~a\%%~i" driver category. >> %APP_LOG%
			call:ChkDrvClassGuid "%drv_root%\%%~a\%%~i" "%SoftwareComponenGuid%"
			if not errorlevel 1 (
				echo [%TIME%] Driver category match, install it. >> %APP_LOG%
				call:DrvInst "%drv_root%\%%~a\%%~i"
				if errorlevel 1 echo [%TIME%] %%~i driver install failed. >> %APP_LOG% & goto RESULTFAILED
				echo [%TIME%] %%~i driver install success. >> %APP_LOG%
			) else (
				echo [%TIME%] Driver category mismatch. >> %APP_LOG%
			)
		)
	 ) else (
		echo. >> %APP_LOG%
		echo [%TIME%] Install driver by drvorder.txt >> %APP_LOG%
		for /f "delims=" %%i in ('type "%drv_root%\%%~a\drvorder.txt"') do (
			echo [%TIME%] Check "%drv_root%\%%~a\%%~i" >> %APP_LOG%
			if not exist "%drv_root%\%%~a\%%~i" echo could not found the inf file. >> %APP_LOG% & goto RESULTFAILED
			echo [%TIME%] Install "%drv_root%\%%~a\%%~i" >> %APP_LOG%
			call:DrvInst "%drv_root%\%%~a\%%~i"
			if errorlevel 1 echo [%TIME%] %%~i driver install failed. >> %APP_LOG% & goto RESULTFAILED
			echo [%TIME%] Driver install success. >> %APP_LOG%
		)
	 )
)

:Other_Driver
rem Please add addition IHV command below.

if not exist "%~dp0hpup.exe" if not exist "%~dp0..\hpup.exe" GOTO END
echo [%TIME%] Softpaq flow >> %APP_LOG%
if not exist "%~dp0uwp\appxinst.cmd" GOTO END
echo [%TIME%] Call "%~dp0uwp\appxinst.cmd" >> %APP_LOG%
call "%~dp0uwp\appxinst.cmd" >> %APP_LOG%
if not [%errorlevel%] == [0] echo [%TIME%] appxinst.cmd failed >> %APP_LOG% & goto RESULTFAILED
echo [%TIME%] appxinst.cmd success >> %APP_LOG%
GOTO END

:DrvInst
echo %windir%\system32\Pnputil.exe /add-driver "%~1" /install >> %APP_LOG%
%windir%\system32\Pnputil.exe /add-driver "%~1" /install >> %APP_LOG%
echo Result=%errorlevel% >> %APP_LOG%
if /i [%errorlevel%] == [0] exit /b 0
if /i [%errorlevel%] == [259] exit /b 0
if /i [%errorlevel%] == [3010] exit /b 0
exit /b 1
GOTO:EOF

:ChkDrvClassGuid
for /f "eol=; tokens=1,2 delims== " %%i in ('%windir%\system32\find.exe /i "ClassGuid" "%~1" ^| %windir%\system32\findstr.exe /i /r /c:"^ClassGuid"') do (
    echo ClassGuid=%%~j >> %APP_LOG%
    for %%x in (%~2) do (if /i [%%~i^=%%~j] == [ClassGuid^=%%~x]  exit /b 0)
)
exit /b 1
GOTO:EOF

:RESULTFAILED
ECHO ERRRORLEVEL=%ERRORLEVEL% >> %APP_LOG%
EXIT /B 1
GOTO END

:END
EXIT /B 0

