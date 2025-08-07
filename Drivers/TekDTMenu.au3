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

Opt("WinTitleMatchMode", 2)

If ProcessList("TekDTMenu64.exe")[0][0] > 1 OR ProcessList("TekDTMenu32.exe")[0][0] > 1 Then
	MsgBox(16,'Thông báo',"Chương trình đã đang chạy")
	Exit
EndIf

; --- Cài đặt và Biến toàn cục ---
Global Const $g_sIniFile = @ScriptDir & "\TekDTMenu.ini"
Global $g_sTitle = IniRead($g_sIniFile, "Settings", "Title", "TekDT BMC")
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
	_WaitForWinPEBootComplete()
	_ReadButtonsInfoFromINI()
    _CreateGUI()
	_CreateButtons()
    _UpdateVisibleButtons() ; Hiển thị các nút ban đầu
    GUISetState(@SW_SHOW, $g_hGUI)

	_RunAutoRunButtons() ; Chạy các button AutoRun

    AdlibRegister("_CheckMousePosition", 100)
    AdlibRegister("_InitialShrink", 2000) ; Thu nhỏ sau 2 giây

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

    ConsoleWrite("Creating GUI: Width=" & $g_iMainWidth & ", Height=" & $g_iMainHeight & ", TotalButtons=" & $iTotalButtons & ", VisibleButtons=" & $iVisibleButtons & @CRLF)

    $g_hGUI = GUICreate($g_sTitle, $g_iMainWidth, $g_iMainHeight, 0, 0, $WS_POPUP, BitOR($WS_EX_TOPMOST, $WS_EX_WINDOWEDGE))
    GUISetBkColor(0xFFFFFF)

	If @OSVersion = "WIN_7" Or @OSVersion = "WIN_8" Or @OSVersion = "WIN_81" Or @OSVersion = "WIN_10" Or @OSVersion = "WIN_11" Then
		_GDIPlus_Startup()
		GUISetBkColor(0xABCDEF) ; Màu nền tạm để tạo trong suốt
		_WinAPI_SetLayeredWindowAttributes($g_hGUI, 0xABCDEF, $g_iTransparency)
	EndIf

    ; Tạo các điều khiển khác trước
    $g_hShrinkLabel = GUICtrlCreateLabel("🔧", 0, 0, $g_iShrinkSize, $g_iShrinkSize, BitOR($SS_CENTER, $SS_CENTERIMAGE))
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
                    _RunTool($sAction)
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
        ConsoleWrite("Error: Empty tool path in _RunTool" & @CRLF)
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
    If StringInStr($sTool, "wpeutil.exe") Then
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
                ConsoleWrite("Attempting to extract archives in: " & $sTargetDir & @CRLF)
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

    ; Kiểm tra và chạy tệp thực thi (giữ nguyên logic cũ, nhưng bây giờ nó sẽ kiểm tra lại sau khi đã giải nén)
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
        ConsoleWrite("IniRead: Section=" & $sSection & ", Key=" & $sKey & ", Value=" & $sValue & " (default)" & @CRLF)
        Return $sValue
    EndIf
    Local $sConverted = BinaryToString(StringToBinary($sValue, 1), 4) ; ANSI sang Unicode
    ConsoleWrite("IniRead: Section=" & $sSection & ", Key=" & $sKey & ", Original=" & $sValue & ", Converted=" & $sConverted & @CRLF)
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
    ConsoleWrite("Scaling: Input=" & $iValue & ", Axis=" & $sAxis & ", ScaleFactor=" & $fScale & ", Output=" & $iScaledValue & @CRLF)
    Return $iScaledValue
EndFunc

Func StringToBool($sString)
    Return StringLower($sString) = "true"
EndFunc

Func _AnalyzePartitions()
    Local $sTempDir = @TempDir
    Local $sScriptFile = $sTempDir & "\listdisk.txt"
    Local $sOutputFile = $sTempDir & "\disklist.txt"

    ; Tạo script để lấy danh sách disk
    Local $hFile = FileOpen($sScriptFile, 2)
    FileWriteLine($hFile, "list disk")
    FileWriteLine($hFile, "exit")
    FileClose($hFile)

    ; Chạy diskpart và lưu kết quả
	RunWait(@ComSpec & ' /c diskpart /s "' & $sScriptFile & '" > "' & $sOutputFile & '"', "", @SW_HIDE)

    ; Đọc danh sách disk
    Local $aLines = FileReadToArray($sOutputFile)
    If @error Then
        MsgBox(16, "Lỗi", "Không thể lấy danh sách ổ đĩa.")
        FileDelete($sScriptFile)
        FileDelete($sOutputFile)
        Return
    EndIf

    Local $aDisks[0]
    For $sLine In $aLines
        Local $aMatch = StringRegExp($sLine, "Disk\s+(\d+)", 1)
        If Not @error Then
            _ArrayAdd($aDisks, $aMatch[0])
        EndIf
    Next

    Local $sMsg = "Các phân vùng hiện có (theo Disk/Partition):" & @CRLF & @CRLF
    For $sDiskNum In $aDisks
        Local $sPartScriptFile = $sTempDir & "\listpart" & $sDiskNum & ".txt"
        Local $sPartOutputFile = $sTempDir & "\partitions" & $sDiskNum & ".txt"

        ; Tạo script để lấy danh sách partition của disk
        Local $hFile = FileOpen($sPartScriptFile, 2)
        FileWriteLine($hFile, "select disk " & $sDiskNum)
        FileWriteLine($hFile, "list partition")
        FileWriteLine($hFile, "exit")
        FileClose($hFile)

        ; Chạy diskpart và lưu kết quả
		RunWait(@ComSpec & ' /c diskpart /s "' & $sPartScriptFile & '" > "' & $sPartOutputFile & '"', "", @SW_HIDE)

        ; Đọc và phân tích danh sách partition
        Local $aPartLines = FileReadToArray($sPartOutputFile)
        If @error Then
            $sMsg &= "Disk " & $sDiskNum & ": Không thể lấy danh sách phân vùng." & @CRLF & @CRLF
            ContinueLoop
        EndIf

        $sMsg &= "Disk " & $sDiskNum & ":" & @CRLF
        For $sLine In $aPartLines
			Local $aMatch = StringRegExp($sLine, "Partition\s+(\d+)\s+([^\d]+?)\s+(\d+)\s*([KMGTP]?B)", 3)
			If Not @error Then
				Local $sPartNum = $aMatch[0]
				Local $sType = StringStripWS($aMatch[1], 3)  ; Xóa khoảng trắng thừa
				Local $iSizeValue = Number($aMatch[2])
				Local $sUnit = $aMatch[3]
				Local $iSizeMB = 0

				; SỬA ĐỔI: Quy đổi dung lượng về MB để kiểm tra thống nhất
				Switch $sUnit
					Case "GB"
						$iSizeMB = $iSizeValue * 1024
					Case "TB"
						$iSizeMB = $iSizeValue * 1024 * 1024
					Case "MB"
						$iSizeMB = $iSizeValue
					Case "KB"
						$iSizeMB = $iSizeValue / 1024
					Case Else
						$iSizeMB = $iSizeValue / (1024 * 1024) ; Cho B
				EndSwitch

			Local $sNotes = ""
			Local $bIsBitLocker = False
			Local $bFoundBitLocker = False

                ; Kiểm tra BitLocker trước khi kiểm tra các điều kiện khác
                If $iSizeMB > 100 Then ; Chỉ kiểm tra phân vùng đủ lớn
                    $bIsBitLocker = _CheckBitLockerMetadata($sDiskNum, $sPartNum)
                    If $bIsBitLocker Then
                        $sNotes &= " 🔒 BITLOCKER ĐÃ BẬT!"
                        $bFoundBitLocker = True
                    EndIf
                EndIf

				; Kiểm tra các loại phân vùng đặc biệt
				If $iSizeMB < 1000 Then $sNotes &= " ⚠️ Nhỏ (<1GB)"
				If StringRegExp($sType, "(?i)Recovery|EFI|MSR|System") Then $sNotes &= " ⚠️ Hệ thống"

				; Phân tích sâu hơn cho các phân vùng dữ liệu cơ bản (Primary/Basic)
				If StringRegExp($sType, "(?i)Primary|Basic") Then
					Local $bIsWin = _IsWindowsPartition($sDiskNum, $sPartNum)
					If $bIsWin Then
						 $sNotes &= " 💻 Có thể là Windows cũ!"
					Else
						$sNotes &= " 👤 Dữ liệu người dùng?"
					EndIf
				EndIf

				$sMsg &= "  Partition " & $sPartNum & " (" & $sType & ", " & $iSizeValue & " " & $sUnit & ")" & $sNotes & @CRLF
			EndIf
		Next
        $sMsg &= @CRLF
    Next

    ; Thêm cảnh báo đặc biệt nếu phát hiện BitLocker
    If $bFoundBitLocker Then
        $sMsg &= @CRLF & "--- CẢNH BÁO QUAN TRỌNG ---" & @CRLF
        $sMsg &= "🔒 Phát hiện phân vùng được mã hóa BitLocker!" & @CRLF
        $sMsg &= "Nếu bạn cài đặt Windows lên phân vùng này mà không mở khóa trước," & @CRLF
        $sMsg &= "TẤT CẢ DỮ LIỆU SẼ BỊ MẤT VĨNH VIỄN!" & @CRLF & @CRLF
        $sMsg &= "👉 HÃY: Mở khóa BitLocker trước khi tiếp tục, hoặc sao lưu dữ liệu!" & @CRLF
    EndIf

    $sMsg &= "--- Chú thích ---" & @CRLF
    $sMsg &= "💻 Windows cũ: Phát hiện có thư mục hệ thống (Windows, Program Files)." & @CRLF
    $sMsg &= "👤 Dữ liệu người dùng: Phân vùng dữ liệu." & @CRLF
    $sMsg &= "⚠️ Hệ thống: Phân vùng EFI, Recovery... quan trọng cho việc khởi động." & @CRLF & @CRLF
    $sMsg &= "👉 KHUYẾN CÁO: KHÔNG XOÁ các phân vùng có ký hiệu 💻, 👤, ⚠️ nếu không chắc chắn!"
    MsgBox(64, "Phân Tích Phân Vùng", $sMsg)

    ; Xóa file tạm
    FileDelete($sScriptFile)
    FileDelete($sOutputFile)
    For $sDiskNum In $aDisks
        FileDelete($sTempDir & "\listpart" & $sDiskNum & ".txt")
        FileDelete($sTempDir & "\partitions" & $sDiskNum & ".txt")
    Next
EndFunc

Func _AutoCleanPartitions()
    ; Bước 1: Xác nhận ban đầu
    Local $iConfirm = MsgBox(36, "Cảnh Báo Nâng Cao", "Tính năng này sẽ tự động xoá các phân vùng:" & @CRLF & _
        "- Phân vùng nhỏ (<1GB)" & @CRLF & _
        "- Phân vùng hệ thống (Recovery, MSR...)" & @CRLF & _
        "- Phân vùng chứa Windows cũ" & @CRLF & @CRLF & _
        "BẠN CÓ CHẮC CHẮN MUỐN TIẾP TỤC KHÔNG?")
    If $iConfirm <> 6 Then Return ; 6 = Yes

    ; Bước 2: Phân tích disk và partition
    Local $sTempDir = @TempDir
    Local $sScriptFile = $sTempDir & "\listdisk.txt"
    Local $sOutputFile = $sTempDir & "\disklist.txt"
    ; Tạo script để lấy danh sách disk
    Local $hFile = FileOpen($sScriptFile, 2)
    FileWriteLine($hFile, "list disk")
    FileWriteLine($hFile, "exit")
    FileClose($hFile)

    ; Chạy diskpart và lưu kết quả
    RunWait(@ComSpec & ' /c diskpart /s "' & $sScriptFile & '" > "' & $sOutputFile & '"', "", @SW_HIDE)

    ; Đọc danh sách disk
    Local $aLines = FileReadToArray($sOutputFile)
    If @error Then
        MsgBox(16, "Lỗi", "Không thể lấy danh sách ổ đĩa.")
        FileDelete($sScriptFile)
        FileDelete($sOutputFile)
        Return
    EndIf

    Local $aDisks[0]
    For $sLine In $aLines
        Local $aMatch = StringRegExp($sLine, "Disk\s+(\d+)", 1)
        If Not @error Then
            _ArrayAdd($aDisks, $aMatch[0])
        EndIf
    Next

    Local $sCleanScriptFile = $sTempDir & "\cleanpart.txt"
    $hFile = FileOpen($sCleanScriptFile, 2)

    ; Bước 3: Thu thập thông tin phân vùng sẽ xóa
    Local $aToDelete[0][5] ; [Disk, Partition, Type, Size, Reason]
    Local $sMsg = "Các phân vùng sau sẽ bị xóa:" & @CRLF & @CRLF

    For $sDiskNum In $aDisks
        Local $sPartScriptFile = $sTempDir & "\listpart" & $sDiskNum & ".txt"
        Local $sPartOutputFile = $sTempDir & "\partitions" & $sDiskNum & ".txt"

        ; Tạo script để lấy danh sách partition của disk
        Local $hPartFile = FileOpen($sPartScriptFile, 2)
        FileWriteLine($hPartFile, "select disk " & $sDiskNum)
        FileWriteLine($hPartFile, "list partition")
        FileWriteLine($hPartFile, "exit")
        FileClose($hPartFile)

        ; Chạy diskpart và lưu kết quả
        RunWait(@ComSpec & ' /c diskpart /s "' & $sPartScriptFile & '" > "' & $sPartOutputFile & '"', "", @SW_HIDE)

        ; Đọc và phân tích danh sách partition
        Local $aPartLines = FileReadToArray($sPartOutputFile)
        If @error Then
            $sMsg &= "Disk " & $sDiskNum & ": Không thể lấy danh sách phân vùng." & @CRLF & @CRLF
            ContinueLoop
        EndIf

        For $sLine In $aPartLines
            Local $sPartNum = ""
            Local $sType = ""
            Local $iSizeValue = 0
            Local $sUnit = ""
            Local $iSizeMB = 0
            Local $aMatch = StringRegExp($sLine, "Partition\s+(\d+)\s+([^\d]+?)\s+(\d+)\s*([KMGTP]?B)", 3)
            If Not @error Then
                Local $sPartNum = $aMatch[0]
                Local $sType = StringStripWS($aMatch[1], 3)  ; Xóa khoảng trắng thừa
                Local $iSizeValue = Number($aMatch[2])
                Local $sUnit = $aMatch[3]
                Local $iSizeMB = 0

                ; Quy đổi dung lượng về MB
                Switch $sUnit
                    Case "GB"
                        $iSizeMB = $iSizeValue * 1024
                    Case "TB"
                        $iSizeMB = $iSizeValue * 1024 * 1024
                    Case "MB"
                        $iSizeMB = $iSizeValue
                    Case "KB"
                        $iSizeMB = $iSizeValue / 1024
                    Case Else
                        $iSizeMB = $iSizeValue / (1024 * 1024) ; Cho B
                EndSwitch
				; Kiểm tra điều kiện xóa
				Local $bIsSmall = False
				If $iSizeMB < 1000 Then $bIsSmall = True
				Local $bIsSystem = StringRegExp($sType, "(?i)Recovery|EFI|MSR|System")
				Local $bIsPrimaryBasic = StringRegExp($sType, "(?i)Primary|Basic")
				Local $bIsOldWindows = _IsWindowsPartition($sDiskNum, $sPartNum)

				Local $sReason = ""
				Local $bShouldDelete = False

				If $bIsOldWindows Then
					$sReason = "Chứa hệ điều hành cũ"
					$bShouldDelete = True
				ElseIf ($bIsSmall Or $bIsSystem) And Not $bIsPrimaryBasic Then
					; $sReason = $bIsSmall ? "Không cần thiết sẽ được tự tạo lại khi cài đặt Windows mới" : "Hệ thống"
					If $bIsSmall Then
						$sReason = "Không cần thiết sẽ được tự tạo lại khi cài đặt Windows mới"
					Else
						$sReason = "Hệ thống"
					EndIf
					$bShouldDelete = True
				EndIf

				If $bShouldDelete Then
					; Thêm vào danh sách xóa và thông báo
					Local $iIdx = UBound($aToDelete)
					ReDim $aToDelete[$iIdx + 1][5]
					$aToDelete[$iIdx][0] = $sDiskNum
					$aToDelete[$iIdx][1] = $sPartNum
					$aToDelete[$iIdx][2] = $sType
					$aToDelete[$iIdx][3] = $iSizeValue & " " & $sUnit
					$aToDelete[$iIdx][4] = $sReason

					$sMsg &= StringFormat("- Disk %s, Partition %s: %s (%s) - Lý do: %s", _
						$sDiskNum, $sPartNum, $sType, $iSizeValue & " " & $sUnit, $sReason) & @CRLF
				EndIf
			EndIf
        Next
    Next

    ; Bước 4: Xác nhận lần 2 với danh sách chi tiết
    If UBound($aToDelete) > 0 Then
        $sMsg &= @CRLF & "BẠN CÓ CHẮC CHẮN MUỐN XÓA CÁC PHÂN VÙNG TRÊN?"
        $iConfirm = MsgBox(52, "XÁC NHẬN LẦN CUỐI", $sMsg) ; 52 = Yes/No + Question icon
        If $iConfirm <> 6 Then Return
    Else
        MsgBox(64, "Thông báo", "Không tìm thấy phân vùng nào để xóa tự động")
        Return
    EndIf

    ; Bước 5: Thực hiện xóa
    Local $sCleanScriptFile = $sTempDir & "\cleanpart.txt"
    Local $hFile = FileOpen($sCleanScriptFile, 2)

    For $i = 0 To UBound($aToDelete) - 1
        FileWriteLine($hFile, "select disk " & $aToDelete[$i][0])
        FileWriteLine($hFile, "select partition " & $aToDelete[$i][1])
        FileWriteLine($hFile, "delete partition override")
    Next

    FileClose($hFile)
    RunWait('diskpart /s "' & $sCleanScriptFile & '"', "", @SW_HIDE)
    MsgBox(64, "Hoàn Tất", "Đã xoá " & UBound($aToDelete) & " phân vùng")
	If WinExists("Setup","") Then
		ControlClick("Setup","","[CLASS:Button; INSTANCE:1]")
		ControlSend("Setup","","[CLASS:Button; INSTANCE:1]","!r")

    ; Xóa file tạm
    FileDelete($sScriptFile)
    FileDelete($sOutputFile)
    FileDelete($sCleanScriptFile)
    For $sDiskNum In $aDisks
        FileDelete($sTempDir & "\listpart" & $sDiskNum & ".txt")
        FileDelete($sTempDir & "\partitions" & $sDiskNum & ".txt")
    Next
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
Func _IsWindowsPartition($iDiskNum, $iPartNum)
    Local $sTempDir = @TempDir
    Local $sExistingLetter = ""
    Local $sDetailScript = $sTempDir & "\detail_part.txt"
    Local $sDetailOutput = $sTempDir & "\detail_part_out.txt"
	Local $bIsBootPartition = False ; Biến để đánh dấu phân vùng khởi động
	; Tạo script để lấy thông tin chi tiết phân vùng
    Local $hFile = FileOpen($sDetailScript, 2)
    FileWriteLine($hFile, "select disk " & $iDiskNum)
    FileWriteLine($hFile, "select partition " & $iPartNum)
    FileWriteLine($hFile, "detail partition")
    FileWriteLine($hFile, "exit")
    FileClose($hFile)
    RunWait(@ComSpec & ' /c diskpart /s "' & $sDetailScript & '" > "' & $sDetailOutput & '"', "", @SW_HIDE)

    Local $aLines = FileReadToArray($sDetailOutput)
    FileDelete($sDetailScript)
    FileDelete($sDetailOutput)

    ; If Not @error Then
        ; For $sLine In $aLines
            ; ; Tìm dòng có dạng "Volume ###  Ltr  ..."
            ; Local $aMatch = StringRegExp($sLine, '(?i)Volume\s+\d+\s+([A-Z])\s+', 1)
            ; If Not @error Then
                ; $sExistingLetter = $aMatch[0]
                ; ExitLoop
            ; EndIf
        ; Next
    ; EndIf
	If Not @error Then
        For $sLine In $aLines
            ; Tìm dòng có dạng "Volume ### Ltr Label Fs Type Size Status Info"
            Local $aMatchVolume = StringRegExp($sLine, '(?i)Volume\s+\d+\s+([A-Z]?)\s+.*?(\s+Boot)?$', 1)
            If Not @error Then
                If UBound($aMatchVolume) > 0 Then
                    $sExistingLetter = StringStripWS($aMatchVolume[0], 3) ; Lấy ký tự ổ đĩa (nếu có)
                EndIf
                If UBound($aMatchVolume) > 1 And StringStripWS($aMatchVolume[1], 3) = "Boot" Then
                    $bIsBootPartition = True ; Đặt cờ nếu tìm thấy "Boot" trong cột Info
                EndIf
                ; Nếu đã tìm thấy cả ký tự và thông tin Boot, có thể thoát sớm
                If $sExistingLetter <> "" And $bIsBootPartition Then ExitLoop
            EndIf
        Next
    EndIf

    ; Nếu phân vùng được đánh dấu là "Boot", thì đây gần như chắc chắn là phân vùng Windows
    If $bIsBootPartition Then
        ConsoleWrite("Disk " & $iDiskNum & ", Partition " & $iPartNum & " identified as BOOT partition." & @CRLF)
        Return True
    EndIf

    ; =================================================================================

    ; Nếu đã có ký tự, chỉ cần kiểm tra trực tiếp
    If $sExistingLetter <> "" Then
        Return _CheckWindowsFiles($sExistingLetter)
    EndIf

    ; Nếu không có ký tự (trường hợp trong WinPE), thực hiện gán tạm thời như cũ
    Local $sDriveLetter = ""
    For $i = 90 To 68 Step -1 ; Z -> D
        $sDriveLetter = Chr($i)
        If DriveStatus($sDriveLetter & ":\") = 'INVALID' Then ExitLoop
        $sDriveLetter = ""
    Next

    If $sDriveLetter = "" Then
        ConsoleWrite("Error: Không tìm thấy ký tự ổ đĩa trống để kiểm tra phân vùng." & @CRLF)
        Return False
    EndIf

    Local $sAssignScript = $sTempDir & "\assign_letter.txt"
    $hFile = FileOpen($sAssignScript, 2)
    FileWriteLine($hFile, "select disk " & $iDiskNum)
    FileWriteLine($hFile, "select partition " & $iPartNum)
    FileWriteLine($hFile, "assign letter=" & $sDriveLetter)
    FileWriteLine($hFile, "exit")
    FileClose($hFile)
    RunWait(@ComSpec & ' /c diskpart /s "' & $sAssignScript & '"', "", @SW_HIDE)
    FileDelete($sAssignScript)
    Local $hTimer = TimerInit()
    While Not FileExists($sDriveLetter & ":\")
        If TimerDiff($hTimer) > 5000 Then ExitLoop ; Chờ tối đa 5 giây
        Sleep(250)
    WEnd
	; Kiểm tra chuyên sâu
    Local $bIsWindows = _CheckWindowsFiles($sDriveLetter)

    Local $sRemoveScript = $sTempDir & "\remove_letter.txt"
    $hFile = FileOpen($sRemoveScript, 2)
    FileWriteLine($hFile, "select disk " & $iDiskNum)
    FileWriteLine($hFile, "select partition " & $iPartNum)
    FileWriteLine($hFile, "remove letter=" & $sDriveLetter)
    FileWriteLine($hFile, "exit")
    FileClose($hFile)
    RunWait(@ComSpec & ' /c diskpart /s "' & $sRemoveScript & '"', "", @SW_HIDE)
    FileDelete($sRemoveScript)

    Return $bIsWindows
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
            ConsoleWrite("Wait for explorer.exe or setup.exe timeout, proceeding anyway..." & @CRLF)
            ExitLoop
        EndIf
        Sleep(500)
    WEnd
    ConsoleWrite("WinPE explorer.exe or setup.exe detected. Proceeding..." & @CRLF)

    ; Chờ thêm một chút để các thành phần giao diện ổn định
    Sleep(1000)
EndFunc

Func ServiceExists($sServiceName)
    Local $aServices = _Service_List()
    If Not @error Then
        For $i = 1 To $aServices[0][0]
            If $aServices[$i][0] = $sServiceName Then Return True
        Next
    EndIf
    Return False
EndFunc

; Hàm kiểm tra BitLocker qua metadata sector
Func _CheckBitLockerMetadata($iDiskNum, $iPartNum)
    Local $hDisk = _WinAPI_CreateFile("\\.\PhysicalDrive" & $iDiskNum, 2, 6, 6)
    If $hDisk = -1 Then
        ConsoleWrite("Không thể mở PhysicalDrive" & $iDiskNum & ". Thử phương pháp khác." & @CRLF)
        Return _CheckBitLockerViaDiskpart($iDiskNum, $iPartNum)
    EndIf

    Local $tBuffer = DllStructCreate("byte[512]")
    Local $iBytesRead = 0
    
    ; Đọc sector đầu tiên của partition
    _WinAPI_SetFilePointer($hDisk, 512 * _GetPartitionStartSector($iDiskNum, $iPartNum))
    Local $bSuccess = _WinAPI_ReadFile($hDisk, DllStructGetPtr($tBuffer), 512, $iBytesRead)
    _WinAPI_CloseHandle($hDisk)
    
    If Not $bSuccess Or $iBytesRead <> 512 Then
        ConsoleWrite("Đọc sector thất bại. Thử qua diskpart." & @CRLF)
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
    ConsoleWrite("Total buttons: " & $iTotalButtons & ", ScrollOffset: " & $g_iScrollOffset & @CRLF)

    For $i = 0 To $iTotalButtons - 1
        If $bHideAll Or $i < $g_iScrollOffset Or $i >= ($g_iScrollOffset + $g_iMaxButtonsVisible) Then
            GUICtrlSetState($g_aButtons_All[$i][0], $GUI_HIDE)
            ConsoleWrite("Button " & $i & " (" & $g_aButtons_All[$i][1] & ") set to HIDE" & @CRLF)
        Else
            Local $yPos = $g_iTitleHeight + (($i - $g_iScrollOffset) * $g_iButtonHeight)
            GUICtrlSetPos($g_aButtons_All[$i][0], -1, $yPos)
            GUICtrlSetState($g_aButtons_All[$i][0], $GUI_SHOW)
            ConsoleWrite("Button " & $i & " (" & $g_aButtons_All[$i][1] & ") set to SHOW at yPos: " & $yPos & @CRLF)
        EndIf
    Next

    ; Ensure scroll buttons are shown/hidden correctly
    If IsHWnd($g_hScrollUp) And IsHWnd($g_hScrollDown) And Not $bHideAll Then
        If $iTotalButtons > $g_iMaxButtonsVisible Then
            If $g_iScrollOffset > 0 Then
                GUICtrlSetState($g_hScrollUp, $GUI_SHOW)
                ConsoleWrite("ScrollUp button set to SHOW" & @CRLF)
            Else
                GUICtrlSetState($g_hScrollUp, $GUI_HIDE)
                ConsoleWrite("ScrollUp button set to HIDE" & @CRLF)
            EndIf

            If $g_iScrollOffset + $g_iMaxButtonsVisible < $iTotalButtons Then
                GUICtrlSetState($g_hScrollDown, $GUI_SHOW)
                ConsoleWrite("ScrollDown button set to SHOW" & @CRLF)
            Else
                GUICtrlSetState($g_hScrollDown, $GUI_HIDE)
                ConsoleWrite("ScrollDown button set to HIDE" & @CRLF)
            EndIf
        Else
            GUICtrlSetState($g_hScrollUp, $GUI_HIDE)
            GUICtrlSetState($g_hScrollDown, $GUI_HIDE)
            ConsoleWrite("Scroll buttons hidden (not enough buttons)" & @CRLF)
        EndIf
    Else
        ConsoleWrite("Scroll buttons not created or hidden due to bHideAll" & @CRLF)
    EndIf

    If IsHWnd($g_hFooterLabel) And Not $bHideAll Then
        If $iTotalButtons > $g_iMaxButtonsVisible Then
            GUICtrlSetState($g_hFooterLabel, $GUI_SHOW)
            ConsoleWrite("Footer label set to SHOW" & @CRLF)
        Else
            GUICtrlSetState($g_hFooterLabel, $GUI_HIDE)
            ConsoleWrite("Footer label set to HIDE" & @CRLF)
        EndIf
    EndIf
EndFunc