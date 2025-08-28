@Echo Off

setlocal

py -m nuitka tekdt_bmc.py --standalone --onefile --windows-icon-from-ico=logo.ico --enable-plugin=pyside6 --output-dir=build --windows-console-mode=disable --remove-output --windows-uac-admin


:: Lấy đường dẫn hiện tại (nơi chứa file batch)
set "BASEDIR=%~dp0"

:: Đường dẫn đến signtool và chứng chỉ
set "SIGNTOOL=%BASEDIR%Cert\signtool.exe"
set "CERT=%BASEDIR%Cert\TekDT.pfx"

:: Mật khẩu chứng chỉ
set "PASSWORD=TekDT@391152"

:: File EXE cần ký (bạn thay đổi hoặc kéo-thả file EXE vào batch)
set "TARGET_EXE=%BASEDIR%build\tekdt_bmc.exe"

if "%TARGET_EXE%"=="" (
    echo [!] Vui lòng kéo-thả file EXE vào batch hoặc chỉnh sửa biến TARGET_EXE.
    pause
    exit /b 1
)

:: Thực hiện ký
"%SIGNTOOL%" sign /f "%CERT%" /p %PASSWORD% /tr http://timestamp.digicert.com /td SHA256 /fd SHA256 "%TARGET_EXE%"

if %errorlevel%==0 (
    echo [OK] Ký thành công: %TARGET_EXE%
) else (
    echo [LỖI] Ký thất bại!
)

pause
endlocal