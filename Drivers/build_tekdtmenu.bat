@Echo Off

setlocal

:: Lấy đường dẫn hiện tại (nơi chứa file batch)
set "BASEDIR=%~dp0"

set "AUT2EXE=C:\Program Files (x86)\AutoIt3\Aut2Exe\Aut2exe.exe"
set "LOGO=D:\Github\tekdtbmc\logo.ico"
set "TEKDTMENUAU3=D:\Github\tekdtbmc\Scripts\TekDTMenu.au3"

:: Đường dẫn đến signtool và chứng chỉ
set "SIGNTOOL=D:\Github\tekdtbmc\Cert\signtool.exe"
set "CERT=D:\Github\tekdtbmc\Cert\TekDT.pfx"

:: Mật khẩu chứng chỉ
set "PASSWORD=TekDT@391152"

:: File EXE cần ký (bạn thay đổi hoặc kéo-thả file EXE vào batch)
set "TARGET_EXE1=TekDTMenu32.exe"
set "TARGET_EXE2=TekDTMenu64.exe"

del %TARGET_EXE1%
del %TARGET_EXE2%

if "%TARGET_EXE1%"=="" (
    echo [!] Please drag-drop the EXE file into the batch or edit the TekDTMenu32.exe variable.
    pause
    exit /b 1
)
if "%TARGET_EXE2%"=="" (
    echo [!] Please drag-drop the EXE file into the batch or edit the TekDTMenu64.exe variable.
    pause
    exit /b 1
)

:: Build sang exe
"%AUT2EXE%" /in "%TEKDTMENUAU3%" /out "%TARGET_EXE1%" /icon "%LOGO%" /compression 4 /pack /unicode /execlevel requireadministrator /companyname "TekDT" /filedescription "TekDT Menu for Windows PE" /internalname "TekDT Menu" /legalcopyright "TekDT" /originalfilename "%TARGET_EXE1%" /productname "TekDT Menu"
"%AUT2EXE%" /in "%TEKDTMENUAU3%" /out "%TARGET_EXE2%" /icon "%LOGO%" /compression 4 /pack /unicode /execlevel requireadministrator /companyname "TekDT" /filedescription "TekDT Menu for Windows PE" /internalname "TekDT Menu" /legalcopyright "TekDT" /originalfilename "%TARGET_EXE1%" /productname "TekDT Menu" /x64

REM Aut2Exe.exe /in <infile.au3> [/out <outfile.exe>] [/icon <iconfile.ico>] [/comp 0-4] [/ignoredirectives] [/nopack] [/pack] [/ansi] [/unicode] [/x64] [/console] [/gui] [/execlevel <asinvoker | highestavailable | requireadministrator | none>] [/compatibility <vista | win7 | win8>] [/comments <>] [/companyname <>] [/filedescription <>] [/internalname <>] [/legalcopyright <>] [/legaltrademarks <>] [/originalfilename <>] [/productname <>] [/fileversion <fixednum[,num]>] [/productversion <fixednum[,num]>]

:: Thực hiện ký
"%SIGNTOOL%" sign /f "%CERT%" /p %PASSWORD% /tr http://timestamp.digicert.com /td SHA256 /fd SHA256 "%TARGET_EXE1%"
"%SIGNTOOL%" sign /f "%CERT%" /p %PASSWORD% /tr http://timestamp.digicert.com /td SHA256 /fd SHA256 "%TARGET_EXE2%"
echo ==========================================
echo ==========================================
echo ==========================================
if %errorlevel%==0 (
    echo [OK] Signed successfully: %TARGET_EXE1% and %TARGET_EXE2%
) else (
    echo [ERROR] Signing failed!
)
pause
endlocal