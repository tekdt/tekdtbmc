@echo off
setlocal EnableDelayedExpansion
REM =============================
REM Khởi tạo biến TekDTMenu và SDIO
REM =============================
CD /D X:\
set "TekDTMenu="
set "SDIO="

REM Phát hiện kiến trúc hệ thống an toàn cho WinPE (sử dụng wmic)
for /f "tokens=*" %%a in ('wmic os get osarchitecture 2^>nul') do (
    for %%b in (%%a) do (
        if /i "%%b"=="64-bit" (
            set "arch=64"
        ) else if /i "%%b"=="32-bit" (
            set "arch=32"
        )
    )
)

REM Kiểm tra phiên bản TekDTMenu và SDIO tương ứng
if defined arch (
    if "!arch!"=="32" (
        if exist "%~dp0TekDTMenu32.exe" set "TekDTMenu=%~dp0TekDTMenu32.exe"
        if exist "%~dp0Tools\SDIO32\SDIO_R816.exe" set "SDIO=%~dp0Tools\SDIO32\SDIO_R816.exe"
    ) else if "!arch!"=="64" (
        if exist "%~dp0TekDTMenu64.exe" set "TekDTMenu=%~dp0TekDTMenu64.exe"
        if exist "%~dp0Tools\SDIO64\SDIO_R816.exe" set "SDIO=%~dp0Tools\SDIO64\SDIO_R816.exe"
    ) else (
        echo [ERROR] Invalid or unknown architecture detected: !arch!
    )
) else (
    echo [ERROR] Could not determine system architecture. Cannot proceed with specific executables.
)

REM goto RENAME_WINDOWS_SETUP
goto FILLTER_COMPATITABLE_DRIVERS



:RENAME_WINDOWS_SETUP
REM =============================
REM Đổi tên tất cả file setup.exe sang _setup.exe
REM =============================
if exist "%~dp0setup.exe" (
    REN "%~dp0setup.exe" "_setup.exe"
    echo Renamed "%~dp0setup.exe" to "_setup.exe"
)
if exist "%~dp0sources\setup.exe" (
    REN "%~dp0sources\setup.exe" "_setup.exe"
    echo Renamed "%~dp0sources\setup.exe" to "%~dp0sources\_setup.exe"
)
goto FILLTER_COMPATITABLE_DRIVERS



:PNPUTIL_INSTALL
REM =============================
REM TỰ ĐỘNG NẠP DRIVER BẰNG PNPUTIL
REM =============================

REM Ghi lại log để kiểm tra nếu có lỗi
set LOGFILE=%~dp0VentoyDrivers.log
echo Starting automatic driver installation from Ventoy at %date% %time% >> %LOGFILE%

REM Định nghĩa đường dẫn tới thư mục Drivers (ngang hàng với file batch)
set "DriverFolderPath=%~dp0Drivers"

REM Kiểm tra xem thư mục Drivers có tồn tại không
if not exist "%DriverFolderPath%\" (
    echo [ERROR] Driver folder not found at "%DriverFolderPath%\" >> %LOGFILE%
    echo [ERROR] Driver installation skipped.
    goto :ACTIVE_TEKDTMENU
)

echo Driver folder found: "%DriverFolderPath%" >> %LOGFILE%

REM Chạy PnPUtil để thêm và cài đặt tất cả driver
REM /add-driver: Thêm driver vào kho driver.
REM /recurse: Quét các thư mục con trong DriverFolderPath.
REM /install: Cố gắng cài đặt driver phù hợp với phần cứng hiện tại.
REM /limitaccess: Hạn chế truy cập vào một số tệp hệ thống khi cài đặt driver.
REM 2>&1: Chuyển hướng cả stdout và stderr vào file log.
echo Running PnPUtil /add-driver "%DriverFolderPath%\*.inf" /subdirs /install >> %LOGFILE%
pnputil.exe /add-driver "%DriverFolderPath%\*.inf" /subdirs /install >> %LOGFILE% 2>&1

REM Kiểm tra kết quả của PnPUtil
if %errorlevel% neq 0 (
    echo [ERROR] PnPUtil returned errorlevel %errorlevel%. Please check %LOGFILE% for details. >> %LOGFILE%
) else (
    echo PnPUtil completed successfully. >> %LOGFILE%
)



:FILLTER_COMPATITABLE_DRIVERS
echo Installing drivers by SDIO...
CD /D X:\
"%SDIO%" -autoinstall -nogui -norestorepnt -PATH Drivers -license:1>nul
REM goto RECOVER_WINDOWS_SETUP_NAME
goto ACTIVE_TEKDTMENU



:RECOVER_WINDOWS_SETUP_NAME
REM =============================
REM Đổi lại tên tất cả file setup.exe
REM =============================
if exist "%~dp0_setup.exe" (
    REN "%~dp0_setup.exe" "setup.exe"
    echo Recovered "%~dp0_setup.exe" to "%~dp0setup.exe"
)
if exist "%~dp0sources\_setup.exe" (
    REN "%~dp0sources\_setup.exe" "setup.exe"
    echo Recovered "%~dp0sources\_setup.exe" to "%~dp0sources\setup.exe"
)
goto ACTIVE_TEKDTMENU



:ACTIVE_TEKDTMENU
REM =============================
REM Gọi giao diện TekDTMenu.exe
REM =============================
IF DEFINED TekDTMenu (
    echo Starting TekDTMenu... at "%TekDTMenu%"
    start "" "%TekDTMenu%"
) else (
    echo [ERROR] TekDTMenu executable not found or architecture not determined correctly.
    echo Please ensure either TekDTMenu64.exe or TekDTMenu32.exe is present in the same directory.
)
endlocal
exit /b