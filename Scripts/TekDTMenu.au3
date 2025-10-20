#RequireAdmin
#include <GUIConstantsEx.au3>
#include <WindowsConstants.au3>
#include <StaticConstants.au3>
#include <WinAPI.au3>
#include <Array.au3>
#include <File.au3>
#include <ButtonConstants.au3>
#include <GDIPlus.au3>
#include <Math.au3>
#include <WinAPIFiles.au3>
#include <WinAPIHObj.au3>
#include <WinAPISys.au3>
#include <Memory.au3>
#include <Crypt.au3>
#include "secret_key.a3x"

Opt("WinTitleMatchMode", 2)

If ProcessList("TekDTMenu64.exe")[0][0] > 1 OR ProcessList("TekDTMenu32.exe")[0][0] > 1 Then
	MsgBox(16,'Thông báo',"Chương trình đã đang chạy")
	Exit
EndIf

; --- Cài đặt và Biến toàn cục ---
Global Const $g_sIniFile = @ScriptDir & "\TekDTMenu.ini"
Global $g_sTitle = IniRead($g_sIniFile, "Settings", "Title", "TekDT BMC")
Global $RecordLog = True
Global $RootDevice = SearchRootDevice()
Global $g_iMainWidth = _Scale(260)
Global $g_iMaxButtonsVisible = 5 ; Số nút tối đa hiển thị cùng lúc
Global $g_iButtonHeight = _Scale(50)
Global $g_iTitleHeight = _Scale(40)
Global $g_iFooterHeight = _Scale(20)
Global $g_iMainHeight = $g_iTitleHeight ; Sẽ được tính toán lại sau
Global $g_iShrinkSize = _Scale(50)
Global $g_iTransparency = 230 ; Độ trong suốt (0-255)

Global $g_aButtons_All[0][8] ; Mảng chứa TẤT CẢ các nút từ INI
Global $g_hGUI, $g_hShrinkLabel, $hTitleBar, $hTitleText, $g_hFooterLabel
Global $g_hScrollUp, $g_hScrollDown
Global $g_iScrollOffset = 0 ; Vị trí cuộn hiện tại (index của nút đầu tiên)
Global $CPU = RegRead("HKEY_LOCAL_MACHINE\HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")

Global $g_bIsShrunken = False
Global $g_bIsAnimating = False
Global $g_bMouseOver = False
Global $g_bDragging = False
Global $g_iDragOffsetX, $g_iDragOffsetY

; --- Màu sắc (loại bỏ kênh alpha để tương thích WinPE) ---
Global $g_iButtonHoverColor = 0x00C0FF ; Màu xanh khi rê chuột
Global $g_iTextColor = 0xFFFFFF ; Màu trắng
Global $g_iTitleBarColor = 0x0070C0 ; Màu xanh dương đậm cho title bar

; Mảng màu pastel (hoàn toàn không trong suốt)
Global $aPastelColors = [0xFFD700, 0xFF6347, 0x98FB98, 0xDDA0DD, 0xAFEEEE, 0xF0E68C, 0xFFB6C1, 0xE6E6FA]

_Main()

Func _Main()
	Local $SplashInfo = SplashTextOn('Thông tin', 'Cập nhật tác vụ thực hiện...', @DesktopWidth, @DesktopHeight, default, default, 33, '', 15)
	If $SplashInfo Then ControlSetText($SplashInfo, '', 'Static1', 'Trích xuất trình điều khiển...')
	_AutoExtractDrivers()
	
	If $SplashInfo Then ControlSetText($SplashInfo, '', 'Static1', 'Đọc cấu hình cho TekDT Menu...')
	_ReadButtonsInfoFromINI()
	
	If $SplashInfo Then ControlSetText($SplashInfo, '', 'Static1', 'Tạo giao diện...')
    _CreateGUI()
	
	If $SplashInfo Then ControlSetText($SplashInfo, '', 'Static1', 'Tạo các nút nhấn cho giao diện TekDT Menu...')
	_CreateButtons()
	
	If $SplashInfo Then ControlSetText($SplashInfo, '', 'Static1', 'Hiển thị hoàn tất...')
    _UpdateVisibleButtons() ; Hiển thị các nút ban đầu
	
    GUISetState(@SW_SHOW, $g_hGUI)
    AdlibRegister("_CheckMousePosition", 100)
    AdlibRegister("_InitialShrink", 2000) ; Thu nhỏ sau 2 giây
	
	FileWrite("Done.txt","Done")
	
	If $SplashInfo Then ControlSetText($SplashInfo, '', 'Static1', 'Chờ hệ thống khởi động đầy đủ...')
	_WaitForWinPEBootComplete()
	
	ControlSetText($SplashInfo, '', 'Static1', 'Xác nhận thiết bị hợp lệ...')
	If Not _VerifyUSBSignature() Then
		If $SplashInfo Then SplashOff()
        _ShowFatalErrorAndReboot() ; Gọi màn hình lỗi và reboot
        Exit
    EndIf
	
	ControlSetText($SplashInfo, '', 'Static1', 'Chạy các tính năng được cấu hình sẵn')
	DirCreate('Driver_Installed_Logs')
	_RunAutoRunButtons() ; Chạy các button AutoRun
	
	ControlSetText($SplashInfo, '', 'Static1', 'Đang lọc driver tốt nhất cho hệ điều hành...')
	Do
		Sleep(1000); Chờ cho đến khi tiến trình SDIO biến mất, mục đích là để chắc chắn có file .log bên trong thư mục X:\Driver_Installed_Logs
	Until ProcessExists("SDIO_R816.exe") = 0
	SDIO_FilterDriversByLog("X:\Drivers", "X:\Driver_Installed_Logs", False)
	
	If $SplashInfo Then SplashOff()

	Local $iLastCheck = TimerInit()

    While 1
        Local $iMsg = GUIGetMsg()
		If $iMsg = 0 Then ContinueLoop
        Switch $iMsg
            ; Đã loại bỏ Case $GUI_EVENT_CLOSE để không thể tắt
            Case $g_hScrollUp
                _Scroll(-1)
            Case $g_hScrollDown
                _Scroll(1)
            Case Else
                ; Xử lý sự kiện cho các nút chức năng
                For $i = 0 To UBound($g_aButtons_All) - 1
                    If $iMsg = $g_aButtons_All[$i][0] Then
                        _HandleButtonPress($iMsg)
                        ExitLoop
                    EndIf
                Next
        EndSwitch

        If $g_bDragging Then
            Local $aMousePos = MouseGetPos()
            WinMove($g_hGUI, "", $aMousePos[0] - $g_iDragOffsetX, $aMousePos[1] - $g_iDragOffsetY)
        EndIf

		If TimerDiff($iLastCheck) > 1000 Then
			_CheckFocus()
			$iLastCheck = TimerInit()
		EndIf
    WEnd
    Exit
EndFunc

; --- Các hàm khởi tạo và giao diện ---

Func _CreateGUI()
    Local $iTotalButtons = UBound($g_aButtons_All)
    Local $iVisibleButtons = _Min($iTotalButtons, $g_iMaxButtonsVisible)
    $g_iMainHeight = $g_iTitleHeight + ($iVisibleButtons * $g_iButtonHeight)
    If $iTotalButtons > $iVisibleButtons Then $g_iMainHeight += $g_iFooterHeight

	Local $iScrollAreaHeight = 0
    If $iTotalButtons > $iVisibleButtons Then
        $iScrollAreaHeight = _Scale(30)
        $g_iMainHeight += $g_iFooterHeight + $iScrollAreaHeight
    EndIf

    RecordLogforDebug("Creating GUI: Width=" & $g_iMainWidth & ", Height=" & $g_iMainHeight & ", TotalButtons=" & $iTotalButtons & ", VisibleButtons=" & $iVisibleButtons)

    $g_hGUI = GUICreate($g_sTitle, $g_iMainWidth, $g_iMainHeight, 0, 0, $WS_POPUP, BitOR($WS_EX_TOPMOST, $WS_EX_WINDOWEDGE))
    GUISetBkColor(0xFFFFFF)
	
	; Set icon default AutoIt (từ EXE hoặc file icon nếu có)
    GUISetIcon(@AutoItExe)  ; Sử dụng icon của chính script/EXE (AutoIt default nếu không custom)
    ; Nếu có file icon riêng: GUISetIcon(@ScriptDir & "\autoit.ico")  ; Thêm icon file nếu cần

	If @OSVersion = "WIN_7" Or @OSVersion = "WIN_8" Or @OSVersion = "WIN_81" Or @OSVersion = "WIN_10" Or @OSVersion = "WIN_11" Then
		_GDIPlus_Startup()
		GUISetBkColor(0xABCDEF) ; Màu nền tạm để tạo trong suốt
		_WinAPI_SetLayeredWindowAttributes($g_hGUI, 0xABCDEF, $g_iTransparency)
	EndIf

    ; Tạo các điều khiển khác trước
    $g_hShrinkLabel = GUICtrlCreatePic("", 0, 0, $g_iShrinkSize, $g_iShrinkSize)  ; Tạo Pic rỗng
    GUICtrlSetImage($g_hShrinkLabel, @AutoItExe, -1)  ; Set icon từ AutoIt EXE (default icon A xanh)
	; Nếu có icon file riêng: GUICtrlSetImage($g_hShrinkLabel, @ScriptDir & "\shrink.ico")
	GUICtrlSetFont(-1, _Scale(30), 800, 0, "Segoe UI Symbol")
	GUICtrlSetColor(-1, $g_iTextColor)
	GUICtrlSetBkColor(-1, $g_iTitleBarColor)
	GUICtrlSetState(-1, $GUI_HIDE)
	GUICtrlSetCursor(-1, 9)

	; Kiểm tra xem biểu tượng cờ lê có hiển thị đúng không
	Local $sTestLabel = GUICtrlCreateLabel("🔧", -100, -100, 10, 10) ; Tạo label ẩn để kiểm tra
	Local $sFontName = _WinAPI_GetFontName(GUICtrlGetHandle($sTestLabel))
	GUICtrlDelete($sTestLabel)
	If $sFontName <> "Segoe UI Symbol" Then
		GUICtrlSetData($g_hShrinkLabel, "W") ; Fallback nếu không hỗ trợ cờ lê
		GUICtrlSetFont($g_hShrinkLabel, _Scale(24), 800, 0, "Segoe UI")
	EndIf

	; Tạo nút cuộn lên/xuống (thay cho thanh cuộn dọc)
    If $iTotalButtons > $iVisibleButtons Then
	Local $iScrollY = $g_iMainHeight - $g_iFooterHeight - $iScrollAreaHeight
		; $g_hScrollUp = GUICtrlCreateLabel("▲", $g_iMainWidth - _Scale(30), $g_iMainHeight - $g_iFooterHeight - _Scale(50), _Scale(25), _Scale(25), $SS_CENTER)
		$g_hScrollUp = GUICtrlCreateLabel("▲", _Scale(5), $iScrollY + _Scale(2.5), _Scale(25), _Scale(25), $SS_CENTER)
		$g_hScrollDown = GUICtrlCreateLabel("▼", $g_iMainWidth - _Scale(30), $g_iMainHeight - $g_iFooterHeight - _Scale(25), _Scale(25), _Scale(25), $SS_CENTER)
		GUICtrlSetFont($g_hScrollUp, _Scale(12), 600, 0, "Segoe UI")
		GUICtrlSetFont($g_hScrollDown, _Scale(12), 600, 0, "Segoe UI")
		GUICtrlSetColor($g_hScrollUp, 0x000000)
		GUICtrlSetColor($g_hScrollDown, 0x000000)
		GUICtrlSetBkColor($g_hScrollUp, 0xCCCCCC)
		GUICtrlSetBkColor($g_hScrollDown, 0xCCCCCC)
		GUICtrlSetCursor($g_hScrollUp, 0)
		GUICtrlSetCursor($g_hScrollDown, 0)
	EndIf

    ; Tạo dòng chữ chú thích nếu cần
    If $iTotalButtons > $iVisibleButtons Then
        $g_hFooterLabel = GUICtrlCreateLabel("Cuộn để xem thêm", 0, $g_iMainHeight - $g_iFooterHeight, $g_iMainWidth, $g_iFooterHeight, $SS_CENTER)
        GUICtrlSetFont(-1, _Scale(8), 400, 0, "Segoe UI")
        GUICtrlSetColor(-1, 0x000000)
        GUICtrlSetBkColor(-1, 0xF0F0F0)
    EndIf

    ; Tạo title bar và text sau cùng để tránh che khuất
    $hTitleBar = GUICtrlCreateLabel("", 0, 0, $g_iMainWidth, $g_iTitleHeight)
    GUICtrlSetBkColor(-1, $g_iTitleBarColor)
    GUICtrlSetState(-1, $GUI_DROPACCEPTED)
    GUICtrlSetCursor(-1, 9)

    $hTitleText = GUICtrlCreateLabel($g_sTitle, 0, 0, $g_iMainWidth, $g_iTitleHeight, $SS_CENTER)
    GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
    GUICtrlSetFont(-1, _Scale(11), 600, 0, "Segoe UI")
    GUICtrlSetColor(-1, $g_iTextColor)

    ; Đảm bảo GUI ở trạng thái mở rộng
    $g_bIsShrunken = False
    _UpdateVisibleButtons() ; Gọi lại để hiển thị nút

    GUIRegisterMsg($WM_LBUTTONDOWN, "_WM_LBUTTONDOWN")
    GUIRegisterMsg($WM_LBUTTONUP, "_WM_LBUTTONUP")
    GUIRegisterMsg($WM_MOUSEWHEEL, "_WM_MOUSEWHEEL")
EndFunc

Func _ReadButtonsInfoFromINI()
    Local $iButtonIndex = 1
    Local $iColorIndex = 0

    While 1
        Local $sSection = "Button" & $iButtonIndex
        Local $sText = _IniReadUTF8($g_sIniFile, $sSection, "Text", "")
        If $sText = "" Then ExitLoop

        Local $sAction = _IniReadUTF8($g_sIniFile, $sSection, "Action", "")
        Local $sTooltip = _IniReadUTF8($g_sIniFile, $sSection, "Tooltip", "")
        Local $bWait = StringToBool(_IniReadUTF8($g_sIniFile, $sSection, "Wait", "False"))
		Local $bAutoRun = StringToBool(_IniReadUTF8($g_sIniFile, $sSection, "AutoRun", "False"))

        Local $iIndex = UBound($g_aButtons_All)
        ReDim $g_aButtons_All[$iIndex + 1][8] ; [0]:ID, [1]:Text, [2]:Action, [3]:Wait, [4]:Running, [5]:Color, [6]:Tooltip, [7]:AutoRun

        $g_aButtons_All[$iIndex][1] = $sText
        $g_aButtons_All[$iIndex][2] = $sAction
        $g_aButtons_All[$iIndex][3] = $bWait
        $g_aButtons_All[$iIndex][5] = $aPastelColors[$iColorIndex]
        $g_aButtons_All[$iIndex][6] = $sTooltip
		$g_aButtons_All[$iIndex][7] = $bAutoRun ; Lưu trạng thái AutoRun

        $iButtonIndex += 1
        $iColorIndex = Mod($iColorIndex + 1, UBound($aPastelColors))
    WEnd
EndFunc

Func _CreateButtons()
    Local $iButtonWidth = $g_iMainWidth - _Scale(10)
    Local $iButtonX = _Scale(5)

    For $i = 0 To UBound($g_aButtons_All) - 1
        Local $yPos = $g_iTitleHeight + ($i * $g_iButtonHeight) ; Vị trí tạm thời

        ; Tạo control thực sự
        $g_aButtons_All[$i][0] = GUICtrlCreateLabel( _
            $g_aButtons_All[$i][1], _
            $iButtonX, _
            $yPos, _
            $iButtonWidth, _
            $g_iButtonHeight - _Scale(10), _
            BitOR($SS_CENTER, $SS_CENTERIMAGE) _
        )

        ; Thiết lập thuộc tính
        GUICtrlSetFont(-1, _Scale(10), 600, 0, "Segoe UI")
        GUICtrlSetTip(-1, $g_aButtons_All[$i][6])
        GUICtrlSetBkColor(-1, $g_aButtons_All[$i][5])
        GUICtrlSetColor(-1, 0x000000)
        GUICtrlSetCursor(-1, 0)
        GUICtrlSetState(-1, $GUI_HIDE)
    Next
EndFunc

; --- Các hàm xử lý sự kiện ---

Func _HandleButtonPress($iCtrlID)
    For $i = 0 To UBound($g_aButtons_All) - 1
        If $g_aButtons_All[$i][0] = $iCtrlID Then
            If $g_aButtons_All[$i][4] Then Return ; Nếu đang chạy thì không làm gì

            _SetButtonState($iCtrlID, True) ; Chuyển sang trạng thái "Đang thực hiện..."

            Local $sAction = $g_aButtons_All[$i][2]
            Local $bWait = $g_aButtons_All[$i][3]

			; Kiểm tra action hợp lệ
            If $sAction = "" Then
                _SetButtonState($iCtrlID, False)
                Return
            EndIf

            Switch $sAction
                Case "ANALYZE_PARTITIONS"
                    _AnalyzePartitions()
                Case "AUTO_CLEAN_PARTITIONS"
                    _AutoCleanPartitions()
				Case Else
					If StringInStr($CPU, "AMD") AND StringInStr($sAction, "%ScriptDir%\Tools\SDIO%ARCH%\SDIO_R816.exe") Then Return
					_RunTool($sAction)
					If WinExists("Setup","") = 1 Then
						ControlClick("Setup","","[CLASS:Button; INSTANCE:1]")
						ControlSend("Setup","","[CLASS:Button; INSTANCE:1]","!r")
						; Send('!r')
					EndIf
            EndSwitch

            If Not $bWait Then Sleep(500)
            _SetButtonState($iCtrlID, False) ; Trả về trạng thái bình thường
            Return
        EndIf
    Next
EndFunc

Func _SetButtonState($hButton, $bIsLoading)
    For $i = 0 To UBound($g_aButtons_All) - 1
        If $g_aButtons_All[$i][0] = $hButton Then
            If $bIsLoading Then
                GUICtrlSetData($hButton, "Đang thực hiện...")
                GUICtrlSetBkColor($hButton, $g_iButtonHoverColor)
                $g_aButtons_All[$i][4] = True
            Else
                GUICtrlSetData($hButton, $g_aButtons_All[$i][1])
                GUICtrlSetBkColor($hButton, $g_aButtons_All[$i][5]) ; Trả về màu pastel gốc
                $g_aButtons_All[$i][4] = False
            EndIf
            ExitLoop
        EndIf
    Next
EndFunc

Func _CheckMousePosition()
    Local $aMPos = MouseGetPos()
    Local $aWinPos = WinGetPos($g_hGUI)
    If Not IsArray($aWinPos) Then Return

    Local $bOver = ($aMPos[0] >= $aWinPos[0] And $aMPos[0] <= $aWinPos[0] + $aWinPos[2] And _
            $aMPos[1] >= $aWinPos[1] And $aMPos[1] <= $aWinPos[1] + $aWinPos[3])

    If $bOver And Not $g_bMouseOver Then
        $g_bMouseOver = True
        If $g_bIsShrunken Then _AnimateGUI("expand")
    ElseIf Not $bOver And $g_bMouseOver Then
        $g_bMouseOver = False
        If Not $g_bIsShrunken Then _AnimateGUI("shrink")
    EndIf
EndFunc

Func _WM_MOUSEWHEEL($hWnd, $iMsg, $wParam, $lParam)
    Local $iDelta = BitShift($wParam, 16) / 120
    If $iDelta > 0 Then
        _Scroll(-1) ; Cuộn lên
    Else
        _Scroll(1)  ; Cuộn xuống
    EndIf
    Return $GUI_RUNDEFMSG
EndFunc

; --- Các hàm tiện ích ---
Func _RunTool($sTool)
    If $sTool = "" Then
        RecordLogforDebug("Error: Empty tool path in _RunTool")
        Return
    EndIf

    ; Xử lý các lệnh đặc biệt (giữ nguyên)
    Switch StringLower($sTool)
        Case "cmd", "command", "commandprompt"
            Run(@ComSpec & " /k echo Công cụ Command Prompt", "", @SW_SHOW)
            Return
        Case "powershell"
            Run("powershell.exe", "", @SW_SHOW)
            Return
        Case "explorer", "fileexplorer"
            Run("explorer.exe", "", @SW_SHOW)
            Return
    EndSwitch

    ; Xử lý lệnh shutdown với xác nhận (giữ nguyên)
    If StringInStr($sTool, "wpeutil.exe") OR StringInStr($sTool, "dism.exe") Then
		If StringInStr($sTool, "/Y") Then
			Run(@ComSpec & " /c " & StringReplace($sTool," /Y",""), "", @SW_HIDE)
			Return
		EndIf
        Local $sMsg = StringInStr($sTool, "reboot") ? "Bạn có chắc chắn muốn khởi động lại máy tính?" : "Bạn có chắc chắn muốn tắt máy tính?"
        If MsgBox(36, "Xác Nhận", $sMsg) = 6 Then ; 6 = Yes
            Run(@ComSpec & " /c " & $sTool, "", @SW_HIDE)
        EndIf
        Return
    EndIf

    ; Thay thế %ScriptDir% và %ARCH% (giữ nguyên)
    $sTool = StringReplace($sTool, "%ScriptDir%", @ScriptDir)
    $sTool = StringReplace($sTool, "%ARCH%", @OSArch = "X64" ? "64" : "32")

    ; Tách đường dẫn chính và tham số (giữ nguyên)
    Local $sExePath, $sParams = ""
    If StringLeft($sTool, 1) = '"' Then
        Local $iEndQuote = StringInStr($sTool, '"', 0, 2)
        If $iEndQuote Then
            $sExePath = StringMid($sTool, 2, $iEndQuote - 2)
            $sParams = StringTrimLeft($sTool, $iEndQuote)
        EndIf
    Else
        Local $iFirstSpace = StringInStr($sTool, " ")
        If $iFirstSpace Then
            $sExePath = StringLeft($sTool, $iFirstSpace - 1)
            $sParams = StringTrimLeft($sTool, $iFirstSpace)
        Else
            $sExePath = $sTool
        EndIf
    EndIf

    ; Nếu file thực thi chưa tồn tại, hãy thử giải nén
    If Not FileExists($sExePath) Then
        ; Lấy đường dẫn thư mục của file exe mục tiêu
		Local $ExeFile_Drive, $ExeFile_Dir, $ExeFile_FileName, $ExeFile_Extension
        Local $sTargetDir = StringTrimRight(_PathSplit($sExePath, $ExeFile_Drive, $ExeFile_Dir, $ExeFile_FileName, $ExeFile_Extension)[1]&_PathSplit($sExePath, $ExeFile_Drive, $ExeFile_Dir, $ExeFile_FileName, $ExeFile_Extension)[2],1)

        ; Tìm các file .7z trong thư mục đó
        Local $aArchives = _FileListToArray($sTargetDir, "*.7z")
        If Not @error And $aArchives[0] > 0 Then
            ; Xác định đường dẫn tới 7za.exe dựa trên kiến trúc hệ thống
            Local $s7zPath = @ScriptDir & "\Tools\7z" & (@OSArch = "X64" ? "64" : "32") & "\7za.exe"

            If FileExists($s7zPath) Then
                RecordLogforDebug("Attempting to extract archives in: " & $sTargetDir)
                ; Lặp qua từng file .7z tìm thấy và giải nén
                For $i = 1 To $aArchives[0]
                    Local $sArchivePath = $sTargetDir & "\" & $aArchives[$i]
                    ; Lệnh giải nén: x (giải nén với đường dẫn đầy đủ), -o (chỉ định thư mục đầu ra), -y (tự động đồng ý)
                    Local $sCommand = '"' & $s7zPath & '" x "' & $sArchivePath & '" -o"' & $sTargetDir & '" -y'
                    RunWait($sCommand, "", @SW_HIDE)
                Next
            Else
                MsgBox(16, "Lỗi", "Không tìm thấy công cụ giải nén:" & @CRLF & $s7zPath)
            EndIf
        EndIf
    EndIf

    ; Kiểm tra và chạy tệp thực thi (kiểm tra lại sau khi đã giải nén)
    If FileExists($sExePath) Then
        Run('"' & $sExePath & '" ' & $sParams, "", @SW_SHOW)
    Else
        ; Thử tìm trong System32 nếu không phải đường dẫn tương đối
        Local $sSystemPath = @WindowsDir & "\System32\" & $sTool
        If FileExists($sSystemPath) Then
            Run($sSystemPath, $sParams, @SW_SHOW)
        Else
            MsgBox(16, "Lỗi", "Không tìm thấy tệp: " & @CRLF & $sExePath & @CRLF & "Vui lòng kiểm tra thư mục Tools trong thư mục chứa script.")
        EndIf
    EndIf
EndFunc

Func _RunAutoRunButtons()
    For $i = 0 To UBound($g_aButtons_All) - 1
        If $g_aButtons_All[$i][7] Then ; Nếu AutoRun=True
            ; Bắt chước click button
            _HandleButtonPress($g_aButtons_All[$i][0])
        EndIf
    Next
EndFunc

Func _CheckFocus()
    Local $hActive = WinGetHandle("[ACTIVE]")
    If $hActive <> $g_hGUI And Not $g_bIsShrunken Then
        _AnimateGUI("shrink")
    EndIf
EndFunc

Func _IniReadUTF8($sFile, $sSection, $sKey, $sDefault)
    Local $sValue = IniRead($sFile, $sSection, $sKey, $sDefault)
    If $sValue = $sDefault Then
        RecordLogforDebug("IniRead: Section=" & $sSection & ", Key=" & $sKey & ", Value=" & $sValue & " (default)")
        Return $sValue
    EndIf
    Local $sConverted = BinaryToString(StringToBinary($sValue, 1), 4) ; ANSI sang Unicode
    RecordLogforDebug("IniRead: Section=" & $sSection & ", Key=" & $sKey & ", Original=" & $sValue & ", Converted=" & $sConverted)
    Return $sConverted
EndFunc

Func _Scale($iValue, $sAxis = "y")
    Local $fScale
    If $sAxis = "y" Then
        $fScale = @DesktopHeight / 1080
    Else
        $fScale = @DesktopWidth / 1920
    EndIf
    Local $iScaledValue = Round($iValue * $fScale)
    RecordLogforDebug("Scaling: Input=" & $iValue & ", Axis=" & $sAxis & ", ScaleFactor=" & $fScale & ", Output=" & $iScaledValue)
    Return $iScaledValue
EndFunc

Func StringToBool($sString)
    Return StringLower($sString) = "true"
EndFunc

Func _AnalyzePartitions()
    Local $oWMI = ObjGet("winmgmts:\\.\root\cimv2")
    If Not IsObj($oWMI) Then
        MsgBox(16, "Lỗi WMI", "Không thể kết nối tới dịch vụ Windows Management Instrumentation.")
        Return
    EndIf

    Local $sMsg = "Các phân vùng hiện có (Phân tích bằng WMI):" & @CRLF & @CRLF
    Local $bFoundBitLocker = False

    Local $colDisks = $oWMI.ExecQuery("SELECT * FROM Win32_DiskDrive")
    If Not IsObj($colDisks) Or $colDisks.Count = 0 Then Return

    For $oDisk In $colDisks
        $sMsg &= StringFormat("Disk %i (%s GB - %s):\n", $oDisk.Index, Round($oDisk.Size / (1024^3), 2), $oDisk.Model)

        ; === SỬA LỖI TẠI ĐÂY: Truy vấn trực tiếp Partition bằng DiskIndex ===
        Local $sQuery = "SELECT * FROM Win32_DiskPartition WHERE DiskIndex = " & $oDisk.Index
        Local $colPartitions = $oWMI.ExecQuery($sQuery)

        If IsObj($colPartitions) And $colPartitions.Count > 0 Then
            For $oPartition In $colPartitions
                Local $iSizeMB = Round($oPartition.Size / (1024^2))
                Local $sUnit = "MB"
                Local $iDisplaySize = $iSizeMB
                If $iSizeMB >= 1024 Then
                    $sUnit = "GB"
                    $iDisplaySize = Round($iSizeMB / 1024, 2)
                EndIf

                Local $sNotes = ""
                If $oPartition.BootPartition Then $sNotes &= " 🚀 Khởi động"
                If $oPartition.Type = "EFI System Partition" Or StringInStr($oPartition.Type, "Recovery") Or StringInStr($oPartition.Type, "MSR") Then $sNotes &= " ⚠️ Hệ thống"
                If $iSizeMB < 1000 Then $sNotes &= " ⚠️ Nhỏ (<1GB)"

                ; === SỬ DỤNG HÀM _IsWindowsPartition PHIÊN BẢN WMI ===
                If _IsWindowsPartition($oWMI, $oPartition.DiskIndex, $oPartition.Index) Then
                    $sNotes &= " 💻 Có thể là Windows cũ!"
                Else
                    ; Nếu không phải Win cũ và có ký tự -> khả năng là data
                    If _GetDriveLetterFromPartition($oWMI, $oPartition.DeviceID) <> "" Then
                         $sNotes &= " 👤 Dữ liệu người dùng?"
                    EndIf
                EndIf

                $sMsg &= StringFormat("  Partition %i (%s, %s %s)%s\n", $oPartition.Index, $oPartition.Type, $iDisplaySize, $sUnit, $sNotes)
            Next
        Else
             $sMsg &= "  (Không tìm thấy phân vùng nào trên ổ đĩa này)\n"
        EndIf
        $sMsg &= @CRLF
    Next
    MsgBox(64, "Phân Tích Phân Vùng", $sMsg)
EndFunc

Func _AutoCleanPartitions()
    Local $iConfirm = MsgBox(36, "Cảnh Báo Nâng Cao", "Tính năng này sẽ tự động xoá các phân vùng không cần thiết." & @CRLF & "BẠN CÓ CHẮC CHẮN MUỐN TIẾP TỤC KHÔNG?")
    If $iConfirm <> 6 Then Return

    Local $oWMI = ObjGet("winmgmts:\\.\root\cimv2")
    If Not IsObj($oWMI) Then Return

    Local $aToDelete[0][5] ; [DiskIndex, PartIndex, Type, SizeStr, Reason]
    Local $sConfirmMsg = "Các phân vùng sau sẽ bị xóa:" & @CRLF & @CRLF

    Local $colDisks = $oWMI.ExecQuery("SELECT * FROM Win32_DiskDrive")
    If Not IsObj($colDisks) Then Return

    For $oDisk In $colDisks
        ; === SỬA LỖI TẠI ĐÂY: Truy vấn trực tiếp Partition bằng DiskIndex ===
        Local $sQuery = "SELECT * FROM Win32_DiskPartition WHERE DiskIndex = " & $oDisk.Index
        Local $colPartitions = $oWMI.ExecQuery($sQuery)

        If IsObj($colPartitions) And $colPartitions.Count > 0 Then
            For $oPartition In $colPartitions
                Local $iSizeMB = Round($oPartition.Size / (1024^2))
                Local $bIsSmall = ($iSizeMB < 1000)
                Local $bIsSystem = ($oPartition.Type = "EFI System Partition" Or StringInStr($oPartition.Type, "Recovery") Or StringInStr($oPartition.Type, "MSR"))
                Local $bIsOldWindows = _IsWindowsPartition($oWMI, $oPartition.DiskIndex, $oPartition.Index)

                Local $sReason = ""
                Local $bShouldDelete = False

                If $bIsOldWindows Then
                    $sReason = "Chứa hệ điều hành cũ"
                    $bShouldDelete = True
                ElseIf ($bIsSmall Or $bIsSystem) And Not $oPartition.BootPartition Then
                    $sReason = $bIsSmall ? "Phân vùng nhỏ không cần thiết" : "Phân vùng hệ thống"
                    $bShouldDelete = True
                EndIf

                If $bShouldDelete Then
                    Local $sSizeStr = Round($iSizeMB, 2) & " MB"
                    If $iSizeMB >= 1024 Then $sSizeStr = Round($iSizeMB / 1024, 2) & " GB"
                    Local $iIdx = UBound($aToDelete)
                    ReDim $aToDelete[$iIdx + 1][5]
                    $aToDelete[$iIdx][0] = $oPartition.DiskIndex
                    $aToDelete[$iIdx][1] = $oPartition.Index
                    $aToDelete[$iIdx][2] = $oPartition.Type
                    $aToDelete[$iIdx][3] = $sSizeStr
                    $aToDelete[$iIdx][4] = $sReason
                    $sConfirmMsg &= StringFormat("- Disk %s, Partition %s: %s (%s) - Lý do: %s", _
                        $oPartition.DiskIndex, $oPartition.Index, $oPartition.Type, $sSizeStr, $sReason) & @CRLF
                EndIf
            Next
        EndIf
    Next

    If UBound($aToDelete) <= 0 Then
        MsgBox(64, "Thông báo", "Không tìm thấy phân vùng nào phù hợp để xóa tự động.")
        Return
    EndIf

    $sConfirmMsg &= @CRLF & "BẠN CÓ CHẮC CHẮN MUỐN XÓA CÁC PHÂN VÙNG TRÊN?"
    $iConfirm = MsgBox(52, "XÁC NHẬN LẦN CUỐI", $sConfirmMsg)
    If $iConfirm <> 6 Then Return

    ; Tạo và thực thi script DiskPart để xóa
    Local $sCleanScriptFile = @TempDir & "\cleanpart.txt"
    Local $hFile = FileOpen($sCleanScriptFile, 2)
    For $i = 0 To UBound($aToDelete) - 1
        FileWriteLine($hFile, "select disk " & $aToDelete[$i][0])
        FileWriteLine($hFile, "select partition " & $aToDelete[$i][1])
        FileWriteLine($hFile, "delete partition override")
    Next
    FileClose($hFile)
    RunWait('diskpart /s "' & $sCleanScriptFile & '"', "", @SW_HIDE)
    FileDelete($sCleanScriptFile)
	If WinExists("Setup","") = 1 Then
		ControlClick("Setup","","[CLASS:Button; INSTANCE:1]")
		ControlSend("Setup","","[CLASS:Button; INSTANCE:1]","!r")
		;Send('!r')
	EndIf
    MsgBox(64, "Hoàn Tất", "Đã xoá " & UBound($aToDelete) & " phân vùng.")
EndFunc

;===============================================================================
; HÀM HỖ TRỢ WMI: _GetDriveLetterFromPartition
; Mục đích: Tìm ký tự ổ đĩa (C:, D:...) tương ứng với một đối tượng
;           phân vùng WMI.
;===============================================================================
Func _GetDriveLetterFromPartition($oWMIService, $sPartitionDeviceID)
    Local $sQuery = "ASSOCIATORS OF {Win32_DiskPartition.DeviceID='" & $sPartitionDeviceID & "'} WHERE AssocClass = Win32_LogicalDiskToPartition"
    Local $colLogicalDisks = $oWMIService.ExecQuery($sQuery)
    If IsObj($colLogicalDisks) And $colLogicalDisks.Count > 0 Then
        For $oLogicalDisk In $colLogicalDisks
            Return $oLogicalDisk.DeviceID ; Trả về ký tự đầu tiên tìm thấy (ví dụ: "C:")
        Next
    EndIf
    Return ""
EndFunc

;===============================================================================
; Hàm: _IsWindowsPartition
; Mục đích: Kiểm tra xem một phân vùng có chứa hệ điều hành Windows hay không
;           bằng cách tạm thời gán ký tự và kiểm tra các tệp/thư mục hệ thống.
; Tham số:
;    $iDiskNum  - Chỉ số của ổ đĩa.
;    $iPartNum  - Chỉ số của phân vùng trên ổ đĩa đó.
; Trả về:
;    True      - Nếu có vẻ là phân vùng Windows.
;    False     - Nếu không phải hoặc có lỗi.
;===============================================================================

Func _IsWindowsPartition($oWMIService, $iDiskIndex, $iPartitionIndex)
    ; Lấy DeviceID của Partition
    Local $oPartition = $oWMIService.Get("Win32_DiskPartition.DeviceID='Disk #" & $iDiskIndex & ", Partition #" & $iPartitionIndex & "'")
    If Not IsObj($oPartition) Then Return False

    ; Dùng hàm hỗ trợ để lấy ký tự ổ đĩa từ Partition
    Local $sDriveLetter = _GetDriveLetterFromPartition($oWMIService, $oPartition.DeviceID)

    ; Nếu không có ký tự ổ đĩa (ví dụ: phân vùng EFI, Recovery...) thì chắc chắn không phải phân vùng Windows chính
    If $sDriveLetter = "" Then
        Return False
    EndIf

    ; Gọi hàm kiểm tra file (hàm này vốn đã an toàn về ngôn ngữ)
    Return _CheckWindowsFiles($sDriveLetter)
EndFunc

;===============================================================================
; Hàm kiểm tra chuyên sâu cho Windows
;===============================================================================
Func _CheckWindowsFiles($sDriveLetter)
    ; Đảm bảo đường dẫn có dạng "X:"
    $sDriveLetter = StringUpper(StringLeft($sDriveLetter, 2))
    If StringRight($sDriveLetter, 1) <> ":" Then $sDriveLetter &= ":"

    ; Kiểm tra sự tồn tại của thư mục "Windows" và "Program Files"
    If Not FileExists($sDriveLetter & "\Windows") Then Return False
    If Not FileExists($sDriveLetter & "\Program Files") Then Return False

    ; Kiểm tra các tệp hệ thống quan trọng
    Local $aCriticalFiles = [ _
        $sDriveLetter & "\Windows\System32\ntoskrnl.exe", _
        $sDriveLetter & "\Windows\System32\kernel32.dll", _
        $sDriveLetter & "\Windows\System32\user32.dll", _
        $sDriveLetter & "\Windows\System32\winload.efi", _
        $sDriveLetter & "\Windows\System32\cmd.exe" _
    ]

    Local $iFound = 0
    For $sFile In $aCriticalFiles
        If FileExists($sFile) Then $iFound += 1
    Next

    ; Yêu cầu có thư mục Windows và ít nhất 2 tệp hệ thống quan trọng
    Return $iFound >= 2
EndFunc

Func _WaitForWinPEBootComplete()
    ; Chờ tối đa 10 giây cho tiến trình explorer.exe hoặc setup.exe xuất hiện
    Local $hTimer = TimerInit()
    While Not ProcessExists("explorer.exe") = 1 OR ProcessExists("setup.exe") = 1 OR WinExists('Setup') = 1
        If TimerDiff($hTimer) > 5000 Then
            RecordLogforDebug("Wait for explorer.exe or setup.exe timeout, proceeding anyway...")
            ExitLoop
        EndIf
        Sleep(500)
    WEnd
    RecordLogforDebug("WinPE explorer.exe or setup.exe detected. Proceeding...")

    ; Chờ thêm một chút để các thành phần giao diện ổn định
    Sleep(1000)
EndFunc

; Hàm kiểm tra BitLocker qua metadata sector
Func _CheckBitLockerMetadata($iDiskNum, $iPartNum)
    Local $hDisk = _WinAPI_CreateFile("\\.\PhysicalDrive" & $iDiskNum, 2, 6, 6)
    If $hDisk = -1 Then
        RecordLogforDebug("Không thể mở PhysicalDrive" & $iDiskNum & ". Thử phương pháp khác.")
        Return _CheckBitLockerViaDiskpart($iDiskNum, $iPartNum)
    EndIf

    Local $tBuffer = DllStructCreate("byte[512]")
    Local $iBytesRead = 0

    ; Đọc sector đầu tiên của partition
    _WinAPI_SetFilePointer($hDisk, 512 * _GetPartitionStartSector($iDiskNum, $iPartNum))
    Local $bSuccess = _WinAPI_ReadFile($hDisk, DllStructGetPtr($tBuffer), 512, $iBytesRead)
    _WinAPI_CloseHandle($hDisk)

    If Not $bSuccess Or $iBytesRead <> 512 Then
        RecordLogforDebug("Đọc sector thất bại. Thử qua diskpart.")
        Return _CheckBitLockerViaDiskpart($iDiskNum, $iPartNum)
    EndIf

    Local $sData = BinaryToString(DllStructGetData($tBuffer, 1))
    Return (StringInStr($sData, "-FVE-FS") > 0)
EndFunc

; Hàm dự phòng kiểm tra BitLocker qua diskpart
Func _CheckBitLockerViaDiskpart($iDiskNum, $iPartNum)
    Local $sTempFile = @TempDir & "\sector_dump_" & $iDiskNum & "_" & $iPartNum & ".bin"
    Local $sScript = @TempDir & "\read_sector.txt"

    ; Tạo script diskpart
    FileWrite($sScript, "select disk " & $iDiskNum & @CRLF & _
                      "select partition " & $iPartNum & @CRLF & _
                      "dump sector 0 1 """ & $sTempFile & """" & @CRLF & _
                      "exit")

    ; Chạy diskpart
    RunWait('diskpart /s "' & $sScript & '"', "", @SW_HIDE)

    ; Kiểm tra nếu file tồn tại và có dữ liệu
    If Not FileExists($sTempFile) Or FileGetSize($sTempFile) < 512 Then
        FileDelete($sScript)
        Return False
    EndIf

    Local $hFile = FileOpen($sTempFile, 16)
    Local $sData = FileRead($hFile, 512)
    FileClose($hFile)

    ; Dọn dẹp
    FileDelete($sScript)
    FileDelete($sTempFile)

    Return (StringInStr($sData, "-FVE-FS") > 0)
EndFunc

; Hàm hỗ trợ lấy sector bắt đầu của partition
Func _GetPartitionStartSector($iDiskNum, $iPartNum)
    Local $sOutput = "", $sScript = @TempDir & "\get_offset.txt"

    FileWrite($sScript, "select disk " & $iDiskNum & @CRLF & _
                      "select partition " & $iPartNum & @CRLF & _
                      "detail partition" & @CRLF & _
                      "exit")

    RunWait('diskpart /s "' & $sScript & '" > "' & @TempDir & '"\part_info.txt"', "", @SW_HIDE)
    $sOutput = FileRead(@TempDir & "\part_info.txt")
    FileDelete($sScript)
    FileDelete(@TempDir & "\part_info.txt")

    Local $aMatches = StringRegExp($sOutput, "Offset\s*:\s*(\d+)\s*KB", 1)
    If Not @error Then
        Return Number($aMatches[0]) * 2 ; Convert KB to sectors (512B)
    EndIf

    Return 0 ; Mặc định sector 0 nếu không xác định được
EndFunc

; --- Các hàm về giao diện và hiệu ứng ---

Func _AnimateGUI($sDirection)
    If $g_bIsAnimating Then Return
    $g_bIsAnimating = True

    Local $iSteps = 15
    Local $aCurrentPos = WinGetPos($g_hGUI)
	Local $iTotalButtons = UBound($g_aButtons_All)

    If $sDirection = "shrink" Then
		$g_bIsShrunken = True
		GUICtrlSetState($hTitleBar, $GUI_HIDE)
		GUICtrlSetState($hTitleText, $GUI_HIDE)
		GUICtrlSetState($g_hScrollUp, $GUI_HIDE)
		GUICtrlSetState($g_hScrollDown, $GUI_HIDE)
		GUICtrlSetState($g_hFooterLabel, $GUI_HIDE)
		_UpdateVisibleButtons(True) ; Ẩn tất cả nút

		For $i = 1 To $iSteps
			Local $iNewHeight = $g_iMainHeight - (($g_iMainHeight - $g_iShrinkSize) * ($i / $iSteps))
			Local $iNewWidth = $g_iMainWidth - (($g_iMainWidth - $g_iShrinkSize) * ($i / $iSteps))
			WinMove($g_hGUI, "", -1, -1, $iNewWidth, $iNewHeight)
			Sleep(10)
		Next
		WinMove($g_hGUI, "", -1, -1, $g_iShrinkSize, $g_iShrinkSize)
		GUICtrlSetState($g_hShrinkLabel, $GUI_SHOW)

    ElseIf $sDirection = "expand" Then
        $g_bIsShrunken = False
		GUICtrlSetState($g_hShrinkLabel, $GUI_HIDE)

		For $i = 1 To $iSteps
			Local $iNewHeight = $g_iShrinkSize + (($g_iMainHeight - $g_iShrinkSize) * ($i / $iSteps))
			Local $iNewWidth = $g_iShrinkSize + (($g_iMainWidth - $g_iShrinkSize) * ($i / $iSteps))
			WinMove($g_hGUI, "", -1, -1, $iNewWidth, $iNewHeight)
			Sleep(10)
		Next
		WinMove($g_hGUI, "", -1, -1, $g_iMainWidth, $g_iMainHeight)
		GUICtrlSetState($hTitleBar, $GUI_SHOW)
		GUICtrlSetState($hTitleText, $GUI_SHOW)
		If $iTotalButtons > $g_iMaxButtonsVisible Then
			GUICtrlSetState($g_hFooterLabel, $GUI_SHOW)
			GUICtrlSetState($g_hScrollUp, $GUI_SHOW)
			GUICtrlSetState($g_hScrollDown, $GUI_SHOW)
		EndIf
		_UpdateVisibleButtons()
    EndIf

    $g_bIsAnimating = False
EndFunc

Func _InitialShrink()
    AdlibUnRegister("_InitialShrink")
    If Not $g_bIsShrunken And Not $g_bMouseOver Then
        _AnimateGUI("shrink")
    EndIf
EndFunc

; --- Các hàm kéo thả cửa sổ ---

Func _WM_LBUTTONDOWN($hWnd, $iMsg, $wParam, $lParam)
    If $hWnd <> $g_hGUI Then Return $GUI_RUNDEFMSG

    Local $hCtrl = GUICtrlGetHandle(GUIGetMsg(1)[1])
    If $hCtrl = $hTitleBar Or $hCtrl = $hTitleText Or $hCtrl = $g_hShrinkLabel Then
        _StartDrag()
    EndIf
    Return $GUI_RUNDEFMSG
EndFunc

Func _WM_LBUTTONUP($hWnd, $iMsg, $wParam, $lParam)
    _StopDrag()
    Return $GUI_RUNDEFMSG
EndFunc

Func _StartDrag()
    Local $aWinPos = WinGetPos($g_hGUI)
    Local $aMousePos = MouseGetPos()
    $g_iDragOffsetX = $aMousePos[0] - $aWinPos[0]
    $g_iDragOffsetY = $aMousePos[1] - $aWinPos[1]
    $g_bDragging = True
EndFunc

Func _StopDrag()
    $g_bDragging = False
EndFunc

; --- Hệ thống cuộn mới ---
Func _Scroll($iDirection)
    Local $iTotalButtons = UBound($g_aButtons_All)
    Local $iNewOffset = $g_iScrollOffset + ($iDirection * 1)

    ; Giới hạn cuộn
    If $iNewOffset < 0 Then $iNewOffset = 0
    If $iNewOffset > $iTotalButtons - $g_iMaxButtonsVisible Then $iNewOffset = $iTotalButtons - $g_iMaxButtonsVisible

    $g_iScrollOffset = $iNewOffset
    _UpdateVisibleButtons()
EndFunc

Func _UpdateVisibleButtons($bHideAll = False)
    Local $iTotalButtons = UBound($g_aButtons_All) ; Use UBound directly
    RecordLogforDebug("Total buttons: " & $iTotalButtons & ", ScrollOffset: " & $g_iScrollOffset)

    For $i = 0 To $iTotalButtons - 1
        If $bHideAll Or $i < $g_iScrollOffset Or $i >= ($g_iScrollOffset + $g_iMaxButtonsVisible) Then
            GUICtrlSetState($g_aButtons_All[$i][0], $GUI_HIDE)
            RecordLogforDebug("Button " & $i & " (" & $g_aButtons_All[$i][1] & ") set to HIDE")
        Else
            Local $yPos = $g_iTitleHeight + (($i - $g_iScrollOffset) * $g_iButtonHeight)
            GUICtrlSetPos($g_aButtons_All[$i][0], -1, $yPos)
            GUICtrlSetState($g_aButtons_All[$i][0], $GUI_SHOW)
            RecordLogforDebug("Button " & $i & " (" & $g_aButtons_All[$i][1] & ") set to SHOW at yPos: " & $yPos)
        EndIf
    Next

    ; Ensure scroll buttons are shown/hidden correctly
    If IsHWnd($g_hScrollUp) And IsHWnd($g_hScrollDown) And Not $bHideAll Then
        If $iTotalButtons > $g_iMaxButtonsVisible Then
            If $g_iScrollOffset > 0 Then
                GUICtrlSetState($g_hScrollUp, $GUI_SHOW)
                RecordLogforDebug("ScrollUp button set to SHOW")
            Else
                GUICtrlSetState($g_hScrollUp, $GUI_HIDE)
                RecordLogforDebug("ScrollUp button set to HIDE")
            EndIf

            If $g_iScrollOffset + $g_iMaxButtonsVisible < $iTotalButtons Then
                GUICtrlSetState($g_hScrollDown, $GUI_SHOW)
                RecordLogforDebug("ScrollDown button set to SHOW")
            Else
                GUICtrlSetState($g_hScrollDown, $GUI_HIDE)
                RecordLogforDebug("ScrollDown button set to HIDE")
            EndIf
        Else
            GUICtrlSetState($g_hScrollUp, $GUI_HIDE)
            GUICtrlSetState($g_hScrollDown, $GUI_HIDE)
            RecordLogforDebug("Scroll buttons hidden (not enough buttons)")
        EndIf
    Else
        RecordLogforDebug("Scroll buttons not created or hidden due to bHideAll")
    EndIf

    If IsHWnd($g_hFooterLabel) And Not $bHideAll Then
        If $iTotalButtons > $g_iMaxButtonsVisible Then
            GUICtrlSetState($g_hFooterLabel, $GUI_SHOW)
            RecordLogforDebug("Footer label set to SHOW")
        Else
            GUICtrlSetState($g_hFooterLabel, $GUI_HIDE)
            RecordLogforDebug("Footer label set to HIDE")
        EndIf
    EndIf
EndFunc

;===============================================================================
;
; Hàm: _VerifyUSBSignature
; Mục đích: Kiểm tra xem USB đang chạy có phải là USB gốc được tạo bởi chương trình không.
; Trả về: True nếu hợp lệ, False nếu không.
; ;===============================================================================
Func _VerifyUSBSignature()
    RecordLogforDebug("--- Bắt đầu kiểm tra chữ ký (phương pháp WMI) ---")
    Local $aDisks = _GetAllPhysicalDiskNumbers()
    If @error Then
        RecordLogforDebug("Lỗi: Không thể liệt kê các ổ đĩa vật lý.")
        Return False
    EndIf

    For $iPhysicalDriveNum In $aDisks
        RecordLogforDebug("--- Đang kiểm tra trên PhysicalDrive" & $iPhysicalDriveNum & " ---")

        ; BƯỚC 1 & 2: Lấy Disk ID và Tổng kích thước đĩa (giữ nguyên)
        Local $aDiskInfo = _GetDiskInfo_WinPE($iPhysicalDriveNum)
        If @error Then
            RecordLogforDebug("Lỗi: Không thể lấy dữ liệu cho PhysicalDrive" & $iPhysicalDriveNum & ". Đã bỏ qua.")
            ContinueLoop
        EndIf

        Local $sDiskIdentifier = $aDiskInfo[0]  ; Disk ID/GUID
        Local $iDiskSize = $aDiskInfo[1]        ; Tổng kích thước disk (bytes)

        If $sDiskIdentifier = "" Or $iDiskSize <= 0 Then
            RecordLogforDebug("Lỗi: Disk ID hoặc kích thước đĩa không hợp lệ. Đã bỏ qua.")
            ContinueLoop
        EndIf

        RecordLogforDebug("Disk ID: " & $sDiskIdentifier)
        RecordLogforDebug("Kích thước đĩa (Tổng): " & $iDiskSize & " bytes")

        ; BƯỚC 3: Lấy offset của phân vùng ẩn (LOGIC MỚI)
        RecordLogforDebug("Đang tìm kiếm offset của phân vùng 16MB dành riêng...")
        Local $iTargetOffset = _GetReservedPartitionOffset($iPhysicalDriveNum)

        If @error Or $iTargetOffset <= 0 Then
            RecordLogforDebug("Lỗi: Không tìm thấy phân vùng chữ ký hợp lệ. Đã bỏ qua.")
            ContinueLoop
        EndIf

        RecordLogforDebug("Đã tìm thấy phân vùng chữ ký tại offset: " & $iTargetOffset & " bytes")

        ; Kiểm tra xem offset tính được có hợp lệ không
        If $iTargetOffset + 512 > $iDiskSize Then
            RecordLogforDebug("Lỗi: Offset được tính toán nằm ngoài ranh giới ổ đĩa. Đã bỏ qua.")
            ContinueLoop
        EndIf

        ; BƯỚC 4: Tạo hash mong đợi (giữ nguyên)
        Local $sStringToHash = $sDiskIdentifier & $g_sSecretKey
        Local $sExpectedHash = StringLower(_Crypt_HashData($sStringToHash, $CALG_SHA_256))
        RecordLogforDebug("Hash mong đợi: " & $sExpectedHash)

        ; BƯỚC 5: Đọc dữ liệu từ sector tại offset đã tính (giữ nguyên)
        Local $sStoredData = _ReadSectorData("\\.\PhysicalDrive" & $iPhysicalDriveNum, $iTargetOffset, 512)
        If $sStoredData = "" Then
            RecordLogforDebug("Lỗi: Không thể đọc dữ liệu tại offset.")
            ContinueLoop
        EndIf

        ; BƯỚC 6: Trích xuất hash từ dữ liệu đọc được (giữ nguyên)
        Local $sStoredHash = StringLeft($sStoredData, 64)
        $sStoredHash = "0x" & StringLower(StringRegExpReplace($sStoredHash, "[^a-f0-9]", ""))
        RecordLogforDebug("Hash lưu trữ:   " & $sStoredHash)

        ; BƯỚC 7: So sánh (giữ nguyên)
        If $sExpectedHash = $sStoredHash And StringLen($sStoredHash) = 66 Then
            RecordLogforDebug(">>> KIỂM TRA THÀNH CÔNG trên PhysicalDrive" & $iPhysicalDriveNum & " <<<")
            Return True
        Else
            RecordLogforDebug("Hash không khớp trên PhysicalDrive" & $iPhysicalDriveNum)
        EndIf
    Next

    RecordLogforDebug("--- KIỂM TRA THẤT BẠI trên tất cả các ổ đĩa ---")
    Return False
EndFunc

;===============================================================================
; HÀM: _GetDiskInfo_WinPE
; Mục đích: Lấy Disk ID và Tổng kích thước đĩa một cách đáng tin cậy trong WinPE.
;           Ưu tiên WMI cho kích thước, nếu thất bại sẽ dùng diskpart.
; Trả về: Array[Disk ID, Disk Size in Bytes]. SetError nếu thất bại.
;===============================================================================
Func _GetDiskInfo_WinPE($iDiskNum)
    Local $aResult[2] = ["", 0]
    Local $sDiskID = ""
    Local $iDiskSize = 0

    ; --- BƯỚC 1: Lấy Disk ID từ 'detail disk' (Phương pháp này vẫn ổn định) ---
    Local $sDetailScriptFile = @TempDir & "\get_disk_detail.txt"
    Local $sDetailOutputFile = @TempDir & "\disk_detail_out.txt"

    FileWrite($sDetailScriptFile, "select disk " & $iDiskNum & @CRLF & "detail disk" & @CRLF & "exit")
    RunWait(@ComSpec & ' /c diskpart /s "' & $sDetailScriptFile & '" > "' & $sDetailOutputFile & '"', "", @SW_HIDE)

    Local $sDetailOutput = FileRead($sDetailOutputFile)
    FileDelete($sDetailScriptFile)
    FileDelete($sDetailOutputFile)

    If $sDetailOutput = "" Then
        RecordLogforDebug("Diskpart 'detail disk' output is empty for disk " & $iDiskNum)
        Return SetError(1, 0, 0)
    EndIf

    Local $aMatchGUID = StringRegExp($sDetailOutput, "Disk ID\s*:\s*\{([A-F0-9-]+)\}", 1)
    If Not @error Then
        $sDiskID = $aMatchGUID[0]
    Else
        Local $aMatchMBR = StringRegExp($sDetailOutput, "Disk ID\s*:\s*([A-F0-9]{8})", 1)
        If Not @error Then $sDiskID = $aMatchMBR[0]
    EndIf

    If $sDiskID = "" Then
        RecordLogforDebug("Could not parse Disk ID for disk " & $iDiskNum)
        Return SetError(2, 0, 0)
    EndIf
    $aResult[0] = $sDiskID

    ; --- BƯỚC 2: Lấy dung lượng đĩa ---
    ; Ưu tiên phương pháp API trực tiếp vì độ tin cậy cao nhất
    $iDiskSize = _GetDiskSizeViaAPI($iDiskNum)

    ; Nếu API thất bại, thử phương pháp WMIC làm dự phòng
    If @error Or $iDiskSize <= 0 Then
        RecordLogforDebug("API call failed for disk " & $iDiskNum & ". Trying WMIC as fallback...")

        ; Khởi động dịch vụ WMI
        RunWait(@ComSpec & " /c net start winmgmt", "", @SW_HIDE)
        Sleep(500)

        Local $sWmicOutputFile = @TempDir & "\wmic_size_out.txt"
        Local $sCommand = 'wmic diskdrive where index=' & $iDiskNum & ' get size'
        RunWait(@ComSpec & ' /c ' & $sCommand & ' > "' & $sWmicOutputFile & '"', "", @SW_HIDE)

        If Not FileExists($sWmicOutputFile) Or FileGetSize($sWmicOutputFile) = 0 Then
             RecordLogforDebug("Fallback WMIC also failed for disk " & $iDiskNum)
             FileDelete($sWmicOutputFile)
             Return SetError(3, 0, 0)
        EndIf

        Local $hFile = FileOpen($sWmicOutputFile, 16)
        Local $sFileContent = FileRead($hFile)
        FileClose($hFile)
        FileDelete($sWmicOutputFile)

        Local $sConvertedContent = BinaryToString($sFileContent, 4)
        Local $aLines = StringSplit($sConvertedContent, @CRLF, 1)
        If @error Or UBound($aLines) < 2 Then
            RecordLogforDebug("Could not parse WMIC fallback output for disk " & $iDiskNum)
            Return SetError(4, 0, 0)
        EndIf

        $iDiskSize = Number(StringStripWS($aLines[1], 3))
    EndIf

    If $iDiskSize <= 0 Then
        RecordLogforDebug("All methods failed to get a valid size for disk " & $iDiskNum)
        Return SetError(5, 0, 0)
    EndIf

    $aResult[1] = $iDiskSize
    Return $aResult
EndFunc

;===============================================================================
; HÀM: _GetDiskSizeViaAPI
; Mục đích: Lấy tổng dung lượng vật lý của ổ đĩa bằng cách gọi trực tiếp
;            Windows API (DeviceIoControl), đảm bảo kết quả chính xác nhất.
; Tham số:
;    $iDiskNum  - Chỉ số của ổ đĩa vật lý (ví dụ: 0 cho PhysicalDrive0)
; Trả về:
;    Tổng dung lượng đĩa bằng byte nếu thành công.
;    SetError và trả về 0 nếu thất bại.
;===============================================================================
Func _GetDiskSizeViaAPI($iDiskNum)
    Local $sDevicePath = "\\.\PhysicalDrive" & $iDiskNum
    Local Const $GENERIC_READ = 0x80000000
    Local Const $FILE_SHARE_READ = 0x1
    Local Const $FILE_SHARE_WRITE = 0x2
    Local Const $OPEN_EXISTING = 3
    Local Const $IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C

    ; Mở một handle tới ổ đĩa vật lý
    Local $hDevice = DllCall("kernel32.dll", "handle", "CreateFileW", _
            "wstr", $sDevicePath, _
            "dword", $GENERIC_READ, _
            "dword", BitOR($FILE_SHARE_READ, $FILE_SHARE_WRITE), _
            "ptr", 0, _
            "dword", $OPEN_EXISTING, _
            "dword", 0, _
            "ptr", 0)

    If @error Or $hDevice[0] = -1 Or $hDevice[0] = 0 Then
        RecordLogforDebug("API Error: Could not create a handle to " & $sDevicePath)
        Return SetError(1, 0, 0)
    EndIf

    ; Chuẩn bị buffer để nhận kết quả (một số 64-bit)
    Local $tLengthInfo = DllStructCreate("int64")
    Local $aBytesReturned = DllCall("kernel32.dll", "dword*", 0)

    ; Gọi API để lấy thông tin dung lượng
    Local $aResult = DllCall("kernel32.dll", "bool", "DeviceIoControl", _
            "handle", $hDevice[0], _
            "dword", $IOCTL_DISK_GET_LENGTH_INFO, _
            "ptr", 0, _
            "dword", 0, _
            "ptr", DllStructGetPtr($tLengthInfo), _
            "dword", DllStructGetSize($tLengthInfo), _
            "ptr", DllStructGetPtr($aBytesReturned), _
            "ptr", 0)

    ; Đóng handle ngay sau khi dùng xong
    DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hDevice[0])

    If @error Or $aResult[0] = 0 Then
        RecordLogforDebug("API Error: DeviceIoControl call failed for " & $sDevicePath)
        Return SetError(2, 0, 0)
    EndIf

    ; Lấy giá trị từ buffer và trả về
    Local $iDiskSizeBytes = DllStructGetData($tLengthInfo, 1)
    Return $iDiskSizeBytes
EndFunc

;===============================================================================
; HÀM: _GetAllPhysicalDiskNumbers
;===============================================================================
Func _GetAllPhysicalDiskNumbers()
    Local $aDiskNumbers[0]
    Local $oWMIService = ObjGet("winmgmts:\\.\root\cimv2")

    If @error Or Not IsObj($oWMIService) Then
        RecordLogforDebug("! Lỗi: Không thể kết nối tới dịch vụ WMI.")
        Return SetError(1, 0, 0)
    EndIf

    ; Tên thuộc tính 'Index' là cố định, không thay đổi theo ngôn ngữ
    Local $colItems = $oWMIService.ExecQuery("SELECT Index FROM Win32_DiskDrive", "WQL", 48)

    If @error Or Not IsObj($colItems) Then
        RecordLogforDebug("! Lỗi: Truy vấn WMI để lấy danh sách ổ đĩa thất bại.")
        Return SetError(2, 0, 0)
    EndIf

    For $oItem In $colItems
        _ArrayAdd($aDiskNumbers, $oItem.Index)
    Next

    If UBound($aDiskNumbers) = 0 Then Return SetError(3, 0, 0)

    RecordLogforDebug("* Thông tin: Các ổ đĩa vật lý được tìm thấy: " & _ArrayToString($aDiskNumbers, ", "))
    Return $aDiskNumbers
EndFunc

;===============================================================================
; HÀM: _ReadSectorData
; Đọc dữ liệu từ offset cụ thể của ổ đĩa vật lý
;===============================================================================
Func _ReadSectorData($sDevicePath, $iOffset, $iBytesToRead)
    ; Mở file với quyền đọc
    Local $hFile = DllCall("kernel32.dll", "handle", "CreateFileW", _
        "wstr", $sDevicePath, _
        "dword", 0x80000000, _  ; GENERIC_READ
        "dword", 3, _            ; FILE_SHARE_READ | FILE_SHARE_WRITE
        "ptr", 0, _
        "dword", 3, _            ; OPEN_EXISTING
        "dword", 0, _
        "ptr", 0)

    If @error Or $hFile[0] = -1 Or $hFile[0] = 0 Then
        RecordLogforDebug("Lỗi: Không thể mở " & $sDevicePath)
        Return ""
    EndIf

    ; Di chuyển file pointer đến offset
    Local $iOffsetLow = BitAND($iOffset, 0xFFFFFFFF)
    ; ======================= SỬA LỖI TẠI ĐÂY =======================
    ; Dùng phép chia số học để lấy 32-bit cao một cách chính xác cho offset 64-bit
    ; thay vì dùng BitShift không đáng tin cậy. 2^32 = 4294967296
    Local $iOffsetHigh = Int($iOffset / 4294967296)
    ; ===============================================================

    Local $aResult = DllCall("kernel32.dll", "dword", "SetFilePointer", _
        "handle", $hFile[0], _
        "long", $iOffsetLow, _
        "long*", $iOffsetHigh, _
        "dword", 0) ; FILE_BEGIN

    If @error Or $aResult[0] = 0xFFFFFFFF Then
        RecordLogforDebug("Lỗi: Không thể SetFilePointer")
        DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hFile[0])
        Return ""
    EndIf

    ; Đọc dữ liệu
    Local $tBuffer = DllStructCreate("byte[" & $iBytesToRead & "]")
    Local $aBytesRead = DllCall("kernel32.dll", "bool", "ReadFile", _
        "handle", $hFile[0], _
        "ptr", DllStructGetPtr($tBuffer), _
        "dword", $iBytesToRead, _
        "dword*", 0, _
        "ptr", 0)

    DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hFile[0])

    If @error Or Not $aBytesRead[0] Or $aBytesRead[4] = 0 Then
        RecordLogforDebug("Lỗi: Không đọc được dữ liệu")
        Return ""
    EndIf

    RecordLogforDebug("Đã đọc " & $aBytesRead[4] & " bytes từ offset " & $iOffset)

    ; Chuyển đổi sang string (ASCII/ANSI encoding)
    ; Flag 1 là đúng vì Python ghi chuỗi ASCII, không phải UTF-8
    Return BinaryToString(DllStructGetData($tBuffer, 1), 1)
EndFunc

;===============================================================================
; Hàm: _ShowFatalErrorAndReboot
; Mục đích: Hiển thị một thông báo lỗi toàn màn hình, không thể bỏ qua.
;           Buộc khởi động lại máy tính khi nhấn OK hoặc khi script bị đóng.
;===============================================================================
Func _ShowFatalErrorAndReboot()
    ; Đăng ký hàm _ForceReboot sẽ được gọi khi script này bị tắt đột ngột
    OnAutoItExitRegister("_ForceReboot")

    Local $sMsg = "LỖI" & @CRLF & @CRLF & "USB không hợp lệ hoặc đã bị sao chép." & @CRLF & _
                   "Vui lòng sử dụng công cụ TekDT BMC để tạo USB chính thức." & @CRLF & @CRLF & _
                   "Hệ thống sẽ khởi động lại sau khi bạn nhấn OK."

    ; Tạo một GUI toàn màn hình
    Local $hErrorGUI = GUICreate("Lỗi nghiêm trọng", @DesktopWidth, @DesktopHeight, 0, 0, $WS_POPUP, $WS_EX_TOPMOST)
    GUISetBkColor(0xFF0000) ; Nền màu đỏ

    ; Tạo Label thông báo
    Local $iLabelWidth = @DesktopWidth * 0.8
    Local $iLabelHeight = @DesktopHeight * 0.5
    Local $iLabelX = (@DesktopWidth - $iLabelWidth) / 2
    Local $iLabelY = (@DesktopHeight - $iLabelHeight) / 3
    GUICtrlCreateLabel($sMsg, $iLabelX, $iLabelY, $iLabelWidth, $iLabelHeight, $SS_CENTER)
    GUICtrlSetFont(-1, 24, 800, 0, "Segoe UI")
    GUICtrlSetColor(-1, 0xFFFFFF) ; Chữ trắng
    GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)

    ; Tạo nút OK
    Local $iBtnWidth = 200
    Local $iBtnHeight = 60
    Local $iBtnX = (@DesktopWidth - $iBtnWidth) / 2
    Local $iBtnY = $iLabelY + $iLabelHeight + 20
    Local $hOkButton = GUICtrlCreateButton("OK", $iBtnX, $iBtnY, $iBtnWidth, $iBtnHeight)
    GUICtrlSetFont(-1, 18, 600)

    GUISetState(@SW_SHOW, $hErrorGUI)

    While 1
        Local $iMsg = GUIGetMsg()
        Switch $iMsg
            Case $GUI_EVENT_CLOSE, $hOkButton
                _ForceReboot()
        EndSwitch
    WEnd
EndFunc

;===============================================================================
; Hàm: _ForceReboot
; Mục đích: Hàm được gọi để khởi động lại máy tính.
;===============================================================================
Func _ForceReboot()
	; Exit
	_RunTool("wpeutil.exe reboot /Y")
	Shutdown(2) ; 2 = Reboot
EndFunc

Func _AutoExtractDrivers()
    Local Const $sRelativeArchivePath = "\ventoy\Drivers.7z"
    Local Const $sDestDir = "X:\Drivers"
    Local Const $sTempDir = "X:\TempExtract"
    Local $s7zPath = @ScriptDir & "\Tools\7z" & (@OSArch = "X64" ? "64" : "32") & "\7za.exe"
    Local $sCpuFolder = "", $sOsFolder = "", $sIsoPath = ""

    Local $sArchivePath = _FindFileOnDrives($sRelativeArchivePath)
    If $sArchivePath = "" Or Not FileExists($s7zPath) Then
        RecordLogforDebug("! Cảnh báo: Không tìm thấy Drivers.7z hoặc 7za.exe. Bỏ qua.")
        Return False
    EndIf
    If FileExists($sDestDir & "\Intel") Or FileExists($sDestDir & "\AMD") Then
        RecordLogforDebug("* Thông tin: Thư mục Drivers đã tồn tại. Bỏ qua.")
        Return True
    EndIf

    If StringInStr($CPU, "Intel") Then
        $sCpuFolder = "Intel"
    ElseIf StringInStr($CPU, "AMD") Then
        $sCpuFolder = "AMD"
    Else
        $sCpuFolder = "*"
    EndIf
    RecordLogforDebug("* Thông tin: Đã xác định CPU là " & $sCpuFolder)

    ; --- Bước 3: Xác định phiên bản Windows từ Ventoy ISO ---
    $sIsoPath = EnvGet("VTOY_ISO_PATH")
    If $sIsoPath = "" Then
        RecordLogforDebug("! Cảnh báo: Không tìm thấy biến VTOY_ISO_PATH. Default OS folder là WIN_10_11.")
        $sOsFolder = "WIN_10_11"  ; Default phổ biến cho WinPE/Win10/11
    Else
        RecordLogforDebug("* Thông tin: Tìm thấy Ventoy ISO tại: " & $sIsoPath)
        DirCreate($sTempDir)
        Local $sWimInfoFile = $sTempDir & "\wiminfo.txt"
        Local $sImagePath = ""

        ; Ưu tiên tìm install.wim, sau đó mới đến install.esd
        Local $sCheckWim = 'sources\install.wim'
        RunWait('"' & $s7zPath & '" t "' & $sIsoPath & '" "' & $sCheckWim & '"', "", @SW_HIDE)
        If @error = 0 Then
             $sImagePath = $sCheckWim
        Else
             $sImagePath = 'sources\install.esd'
        EndIf

        ; Trích xuất và đọc thông tin
        RunWait('"' & $s7zPath & '" e "' & $sIsoPath & '" -o"' & $sTempDir & '" "' & $sImagePath & '" -y', "", @SW_HIDE)
        Local $sExtractedFile = $sTempDir & "\" & StringRegExpReplace($sImagePath, ".+\\", "")
        If FileExists($sExtractedFile) Then
            RunWait(@ComSpec & ' /c Dism /Get-WimInfo /WimFile:"' & $sExtractedFile & '" > "' & $sWimInfoFile & '"', "", @SW_HIDE)
            Local $sWimInfo = FileRead($sWimInfoFile)

            If StringInStr($sWimInfo, "Windows 7") Then
                $sOsFolder = "WIN_7"
            ElseIf StringInStr($sWimInfo, "Windows 11") Or StringInStr($sWimInfo, "Windows 10") Then
                $sOsFolder = "WIN_10_11"
            ElseIf StringInStr($sWimInfo, "Server") Then
                $sOsFolder = "WIN_SERVER"
            Else
                $sOsFolder = "WIN_10_11"  ; Default nếu parse fail
            EndIf
            RecordLogforDebug("* Thông tin: Đã xác định HĐH là " & $sOsFolder)
        Else
            $sOsFolder = "WIN_10_11"  ; Default nếu extract fail
        EndIf
        DirRemove($sTempDir, 1) ; Dọn dẹp thư mục tạm
    EndIf

    ; --- Bước 4: Thực thi giải nén ---
    Local $sExtractPath = $sCpuFolder & "/" & $sOsFolder & "/*"  ; Sửa dùng "/" cho 7z path
    RecordLogforDebug("* Thông tin: Chuẩn bị giải nén '" & $sExtractPath & "' từ " & $sArchivePath & " vào " & $sDestDir)
    DirCreate($sDestDir)
    Local $sCommand = '"' & $s7zPath & '" x "' & $sArchivePath & '" -o"' & $sDestDir & '" "' & $sExtractPath & '" -y -r'  ; Thêm -r recursive
    Local $iPID = RunWait($sCommand, "", @SW_HIDE, $STDERR_CHILD + $STDOUT_CHILD)  ; Capture output
    Local $sOutput = "", $sError = ""
    While 1
        $sOutput &= StdoutRead($iPID)
        $sError &= StderrRead($iPID)
        If @error Then ExitLoop
        Sleep(10)
    WEnd
    ProcessWaitClose($iPID)
    Local $iRet = @extended  ; Return code

    If $iRet <> 0 Or Not DirGetSize($sDestDir) > 0 Then  ; Check return và folder tồn tại
        RecordLogforDebug("! Lỗi: 7z fail với code " & $iRet & ". Output: " & $sOutput & " Error: " & $sError & ". Command: " & $sCommand)
        Return False
    EndIf

    RecordLogforDebug("* Thành công: Quá trình giải nén driver đã hoàn tất. Output: " & $sOutput)
    Return True
EndFunc

;===============================================================================
; Hàm: _FindFileOnDrives
; Mục đích: Tìm kiếm một file hoặc thư mục theo một đường dẫn tương đối
;           trên tất cả các ổ đĩa.
; Tham số:
;    $sRelativePath - Đường dẫn tương đối cần tìm (ví dụ: "\ventoy\Drivers.7z")
; Trả về:
;    Đường dẫn tuyệt đối đầy đủ nếu tìm thấy (ví dụ: "E:\ventoy\Drivers.7z").
;    Chuỗi rỗng "" nếu không tìm thấy.
;===============================================================================
Func _FindFileOnDrives($sRelativePath)
    Local $aDrives = DriveGetDrive("ALL")
    If @error Then Return ""
    For $i = 1 To $aDrives[0]
        Local $sFullPath = $aDrives[$i] & $sRelativePath
        If FileExists($sFullPath) Then
            RecordLogforDebug("* Thông tin: Tìm thấy file tại: " & $sFullPath)
            Return $sFullPath
        EndIf
    Next
    RecordLogforDebug("! Lỗi: Không thể tìm thấy '" & $sRelativePath & "' trên bất kỳ ổ đĩa nào.")
    Return ""
EndFunc

Func RecordLogforDebug($Data)
	If $RecordLog = True Then
		FileWrite($RootDevice&'\ventoy\DebugLog.txt',$Data&@CRLF)
		ConsoleWrite($Data&@CRLF)
	EndIf
	Return
EndFunc

Func SearchRootDevice()
	$aString = StringSplit('A,B,C,D,F,G,H,J,K,L,M,N,P,Q,R,S,T,V,X,Z,W,Y',',')
	For $t = 1 To $aString[0]
		If FileExists($aString[$t]&":\ventoy\TekDT_PE.7z") Then Return $aString[$t]&":"
	Next
EndFunc

Func _GetReservedPartitionOffset($iDiskNum)
    RecordLogforDebug("Bắt đầu tìm offset partition reserved cho Disk " & $iDiskNum)
    
    ; Khởi động WMI dependencies (cần cho WinPE)
    RunWait(@ComSpec & " /c net start rpcss & net start winmgmt", "", @SW_HIDE)
    Sleep(500)  ; Đợi khởi động

    Local $oWMIService = ObjGet("winmgmts:\\.\root\cimv2")
    If @error Or Not IsObj($oWMIService) Then
        RecordLogforDebug("! Lỗi: Không thể kết nối WMI. Fallback diskpart.")
        Return _GetReservedPartitionOffset_DiskPart($iDiskNum)
    EndIf

    Local $colPartitions = $oWMIService.ExecQuery("SELECT * FROM Win32_DiskPartition WHERE DiskIndex = " & $iDiskNum)
    If @error Or Not IsObj($colPartitions) Or $colPartitions.Count = 0 Then
        RecordLogforDebug("! Lỗi: Query WMI partitions thất bại hoặc rỗng. Fallback diskpart.")
        Return _GetReservedPartitionOffset_DiskPart($iDiskNum)
    EndIf

    RecordLogforDebug("Partitions found: " & $colPartitions.Count)
    
    ; Thu thập tất cả partitions vào array để sort bằng offset descending (tìm cuối cùng)
    Local $aPartitions[0][5]  ; [0]: Offset, [1]: Size, [2]: Type, [3]: DeviceID, [4]: HasDriveLetter (log only)
    For $oPartition In $colPartitions
        Local $iOffset = Number($oPartition.StartingOffset)
        Local $iSize = Number($oPartition.Size)
        Local $sType = $oPartition.Type
        Local $sDeviceID = $oPartition.DeviceID
        
        ; Kiểm tra drive letter (chỉ để log, không dùng để filter nữa)
        Local $colLogical = $oWMIService.ExecQuery("ASSOCIATORS OF {Win32_DiskPartition.DeviceID='" & $sDeviceID & "'} WHERE AssocClass=Win32_LogicalDiskToPartition")
        Local $bHasDriveLetter = False
        For $oLogical In $colLogical
            If StringLen($oLogical.DeviceID) > 0 Then $bHasDriveLetter = True
        Next
        
        ; Log chi tiết partition
        RecordLogforDebug("Partition: Offset=" & $iOffset & ", Size=" & $iSize & " (" & Round($iSize / 1048576, 2) & " MB), Type=" & $sType & ", DeviceID=" & $sDeviceID & ", HasDriveLetter=" & $bHasDriveLetter)
        
        ; Thêm vào array nếu size hợp lệ (15-17MB) – bỏ check drive letter và type
        If $iSize >= 15*1048576 And $iSize <= 17*1048576 Then
            Local $iIndex = UBound($aPartitions)
            ReDim $aPartitions[$iIndex + 1][5]
            $aPartitions[$iIndex][0] = $iOffset
            $aPartitions[$iIndex][1] = $iSize
            $aPartitions[$iIndex][2] = $sType
            $aPartitions[$iIndex][3] = $sDeviceID
            $aPartitions[$iIndex][4] = $bHasDriveLetter
        EndIf
    Next

    ; Nếu có candidates, sort bằng offset descending và lấy cái đầu (cuối cùng trên disk)
    If UBound($aPartitions) > 0 Then
        _ArraySort($aPartitions, 1, 0, 0, 0)  ; Sort descending offset (cột 0)
        Local $iOffset = $aPartitions[0][0]
        Local $iSize = $aPartitions[0][1]
        RecordLogforDebug("Tìm thấy candidate partition tại offset: " & $iOffset & " (size: " & Round($iSize / 1048576, 2) & " MB). Sẽ đọc hash để verify.")
        Return $iOffset
    Else
        RecordLogforDebug("Không tìm thấy partition size hợp lệ qua WMI. Fallback diskpart.")
        Return _GetReservedPartitionOffset_DiskPart($iDiskNum)
    EndIf
EndFunc

; Fallback diskpart
Func _GetReservedPartitionOffset_DiskPart($iDiskNum)
    Local $sScriptFile = @TempDir & "\diskpart_list.txt"
    Local $sOutputFile = @TempDir & "\partition_out.txt"
    
    FileWrite($sScriptFile, "select disk " & $iDiskNum & @CRLF & "list partition" & @CRLF & "exit")
    RunWait(@ComSpec & ' /c diskpart /s "' & $sScriptFile & '" > "' & $sOutputFile & '"', "", @SW_HIDE)
    
    Local $sOutput = FileRead($sOutputFile)
    FileDelete($sScriptFile)
    FileDelete($sOutputFile)
    
    If $sOutput = "" Then 
        RecordLogforDebug("! Lỗi: Diskpart output rỗng.")
        Return SetError(1, 0, 0)
    EndIf
    
    RecordLogforDebug("Diskpart output: " & @CRLF & $sOutput)
    
    Local $aLines = StringSplit($sOutput, @CRLF, 1)
    Local $aCandidates[0][2]  ; [0]: Offset bytes, [1]: Size bytes
    For $i = 1 To $aLines[0]
        Local $sLine = StringStripWS($aLines[$i], 3)
        If StringRegExp($sLine, "(?i)partition\s+\d+") Then  ; Tìm line partition
            ; Extract size: number + unit
            Local $aSizeMatch = StringRegExp($sLine, "(\d+)\s*(MB|GB|KB|TB)", 1)
            If Not @error Then
                Local $iValue = Number($aSizeMatch[0])
                Local $sUnit = StringUpper($aSizeMatch[1])
                Local $iSizeBytes = $iValue * ( _
                    $sUnit = "TB" ? 1099511627776 : _
                    $sUnit = "GB" ? 1073741824 : _
                    $sUnit = "MB" ? 1048576 : _
                    $sUnit = "KB" ? 1024 : 1 _
                )
                
                ; Kiểm tra size ~15-17MB (bỏ check drive letter)
                If $iSizeBytes >= 15*1048576 And $iSizeBytes <= 17*1048576 Then
                    ; Extract offset: Thường ở cuối line
                    Local $aOffsetMatch = StringRegExp($sLine, "(\d+)\s*(MB|GB|KB|TB|bytes?)$", 1)
                    If Not @error Then
                        $iValue = Number($aOffsetMatch[0])
                        $sUnit = StringUpper($aOffsetMatch[1])
                        Local $iOffsetBytes = $iValue * ( _
                            $sUnit = "TB" ? 1099511627776 : _
                            $sUnit = "GB" ? 1073741824 : _
                            $sUnit = "MB" ? 1048576 : _
                            $sUnit = "KB" ? 1024 : 1 _
                        )
                        ; Thêm vào candidates
                        Local $iIndex = UBound($aCandidates)
                        ReDim $aCandidates[$iIndex + 1][2]
                        $aCandidates[$iIndex][0] = $iOffsetBytes
                        $aCandidates[$iIndex][1] = $iSizeBytes
                    EndIf
                EndIf
            EndIf
        EndIf
    Next
    
    If UBound($aCandidates) > 0 Then
        ; Sort candidates descending offset, lấy cái cuối
        _ArraySort($aCandidates, 1, 0, 0, 0)
        Local $iOffset = $aCandidates[0][0]
        Local $iSize = $aCandidates[0][1]
        RecordLogforDebug("Tìm thấy candidate partition tại offset: " & $iOffset & " (size: " & Round($iSize / 1048576, 2) & " MB). Sẽ đọc hash để verify.")
        Return $iOffset
    Else
        RecordLogforDebug("! Lỗi: Không tìm thấy partition size hợp lệ qua diskpart.")
        Return SetError(2, 0, 0)
    EndIf
EndFunc

; SDIO_FilterDriversByLog
; $sDriversRoot  - ví dụ "X:\Drivers"
; $sLogDir       - ví dụ "X:\Driver_Installed_Logs"
; $bDryRun       - True = chỉ liệt kê (mặc định), False = xóa thật
; Trả về mảng: [ keptArray, deletedArray, errorsArray ]
Func SDIO_FilterDriversByLog($sDriversRoot, $sLogDir, $bDryRun = False)
    ; Normalize paths
    If StringRight($sDriversRoot, 1) <> "\" Then $sDriversRoot &= "\"
    If StringRight($sLogDir, 1) <> "\" Then $sLogDir &= "\"
    If Not FileExists($sDriversRoot) Then Return SetError(1, 0, "Drivers root not found")
    If Not FileExists($sLogDir) Then Return SetError(2, 0, "Log dir not found")

    ; Read all .log files into one string using _FileListToArrayRec (non-recursive)
    Local $aLogFiles = _FileListToArrayRec($sLogDir, "*.log", 1, 0, 0, 2) ; 1=files, 0=non-recursive, 0=no sort, 2=full path
    If @error Then Return SetError(3, 0, "No .log files found")
    Local $sAll = ""
    For $i = 1 To $aLogFiles[0]
        Local $sContent = FileRead($aLogFiles[$i])
        $sAll &= $sContent & @CRLF & "----LOGSEP----" & @CRLF
    Next

    ; Extract "drivers\..." occurrences ending with .inf (case-insensitive, allow spaces, dots, etc. in path)
    Local $aMatches = StringRegExp($sAll, '(?i)drivers[\\ /][^\r\n"]+\.inf', 3)
    If Not IsArray($aMatches) Then $aMatches = []
    RecordLogforDebug("Matches: " & _ArrayToString($aMatches, "|"))

    ; Collect leaf directories (parents of .inf files) to keep all files in them, and ancestors for directories
    Local $aKeepLeafDirs[0], $aAllAncestors[0]
    For $i = 0 To UBound($aMatches) - 1
        Local $m = $aMatches[$i]
        Local $rel = StringRegExpReplace($m, '(?i)^drivers[\\ /]', '')
        $rel = StringReplace($rel, "/", "\")
        Local $fullInf = $sDriversRoot & $rel
        If FileExists($fullInf) Then
            ; Get parent dir of .inf
            Local $sParent = StringRegExpReplace($fullInf, '[^\\]+$', '')
            If StringRight($sParent, 1) = "\" Then $sParent = StringTrimRight($sParent, 1) ; Trim trailing \
            If _InArray($aKeepLeafDirs, $sParent) = -1 Then
                _ArrayAdd($aKeepLeafDirs, $sParent)
            EndIf
            ; Get all ancestors
            Local $sDir = $sParent
            While StringLen($sDir) > StringLen($sDriversRoot) And $sDir <> ""
                If _InArray($aAllAncestors, $sDir) = -1 Then
                    _ArrayAdd($aAllAncestors, $sDir)
                EndIf
                $sDir = StringRegExpReplace($sDir, '[^\\]+$', '')
                If StringRight($sDir, 1) = "\" Then $sDir = StringTrimRight($sDir, 1)
            WEnd
        EndIf
    Next
    ; Add root if needed
    If UBound($aKeepLeafDirs) > 0 And _InArray($aAllAncestors, $sDriversRoot) = -1 Then
        _ArrayAdd($aAllAncestors, $sDriversRoot)
    EndIf
    Local $aKeepDirs = _ArrayUnique($aAllAncestors) ; Remove duplicates
    RecordLogforDebug("Keep Leaf Dirs (keep all files in these): " & _ArrayToString($aKeepLeafDirs, "|"))
    RecordLogforDebug("Keep Ancestor Dirs: " & _ArrayToString($aKeepDirs, "|"))

    ; Get all files and folders recursively under $sDriversRoot
    Local $aAllFiles = _FileListToArrayRec($sDriversRoot, "*.*", 1, 1, 0, 2) ; 1=files, 1=recursive, 0=no sort, 2=full path
    Local $aAllDirs = _FileListToArrayRec($sDriversRoot, "*", 2, 1, 0, 2) ; 2=folders, 1=recursive, 2=full path

    ; Prepare results
    Local $aKept[0], $aDeleted[0], $aErrors[0]

    ; Delete unnecessary files (only if not in a keep leaf dir)
    If IsArray($aAllFiles) Then
        For $i = 1 To $aAllFiles[0]
            Local $sFile = $aAllFiles[$i]
            ; Get parent dir of file
            Local $sFileParent = StringRegExpReplace($sFile, '[^\\]+$', '')
            If StringRight($sFileParent, 1) = "\" Then $sFileParent = StringTrimRight($sFileParent, 1)
            If _InArray($aKeepLeafDirs, $sFileParent) <> -1 Then
                _ArrayAdd($aKept, $sFile)
            Else
                RecordLogforDebug("Attempting to delete file: " & $sFile)
                If $bDryRun Then
                    _ArrayAdd($aDeleted, $sFile & " (DRYRUN)")
                Else
                    If FileDelete($sFile) Then
                        _ArrayAdd($aDeleted, $sFile)
                    Else
                        _ArrayAdd($aErrors, $sFile & " (failed)")
                    EndIf
                EndIf
            EndIf
        Next
    EndIf

    ; Delete empty directories from bottom-up (reverse order to handle nested)
    If IsArray($aAllDirs) Then
        _ArrayReverse($aAllDirs, 1, $aAllDirs[0]) ; Reverse to start from deepest
        For $i = 1 To $aAllDirs[0]
            Local $sDir = $aAllDirs[$i]
            If _InArray($aKeepDirs, $sDir) = -1 And _InArray($aKeepLeafDirs, $sDir) = -1 Then ; Not a keep dir or leaf dir
                ; Check if empty
                Local $aContents = _FileListToArrayRec($sDir, "*", 0, 0, 0, 0) ; 0=files+folders, 0=non-recursive
                If @error Or $aContents[0] = 0 Then ; Empty or error (assume empty if not accessible)
                    RecordLogforDebug("Attempting to delete dir: " & $sDir)
                    If $bDryRun Then
                        _ArrayAdd($aDeleted, $sDir & " (DRYRUN)")
                    Else
                        If DirRemove($sDir, 0) Then ; 0 = remove only if empty
                            _ArrayAdd($aDeleted, $sDir)
                        Else
                            _ArrayAdd($aErrors, $sDir & " (failed)")
                        EndIf
                    EndIf
                Else
                    _ArrayAdd($aKept, $sDir) ; Has contents, keep for now
                EndIf
            Else
                _ArrayAdd($aKept, $sDir)
            EndIf
        Next
    EndIf

    ; Sort results for readability
    _ArraySort($aKept)
    _ArraySort($aDeleted)
    _ArraySort($aErrors)

    ; Return [kept, deleted, errors]
    Local $aResult[3]
    $aResult[0] = $aKept
    $aResult[1] = $aDeleted
    $aResult[2] = $aErrors
    Return $aResult
EndFunc

; Helper: return index or -1 (case-insensitive)
Func _InArray(ByRef $aArray, $sVal)
    If Not IsArray($aArray) Then Return -1
    For $i = 0 To UBound($aArray) - 1
        If StringLower($aArray[$i]) = StringLower($sVal) Then Return $i
    Next
    Return -1
EndFunc