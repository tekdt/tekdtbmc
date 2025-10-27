; Debug_CheckDB.au3
#Include <SQLite.au3>

Local $sDb = "E:\ventoy\db.sqlite" ; sửa đường dẫn nếu cần
If @AutoItX64 = 1 Then
	_SQLite_Startup('sqlite3_x64.dll', False, 1)
Else
	_SQLite_Startup('sqlite3.dll', False, 1)
EndIf

If Not FileExists($sDb) Then
    MsgBox(16, "DEBUG", "File DB không tồn tại: " & $sDb)
    _SQLite_Shutdown()
    Exit
EndIf

Local $hDb = _SQLite_Open($sDb)
If @error Then
    MsgBox(16, "DEBUG", "Mở DB thất bại: " & _SQLite_ErrMsg($hDb))
    _SQLite_Shutdown()
    Exit
EndIf

Local $aRes, $iRows = 0, $iCols = 0
Local $iRet = _SQLite_GetTable($hDb, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;", $aRes, $iRows, $iCols)

If $iRet <> $SQLITE_OK Or $iRows = 0 Then
    MsgBox(48, "DEBUG", "Không tìm thấy table nào hoặc truy vấn lỗi. Lỗi: " & _SQLite_ErrMsg($hDb))
Else
    ; aRes là mảng 1D: header ở các chỉ số 0..(iCols-1), dữ liệu bắt đầu từ index = iCols
    Local $sOut = ""
    For $r = 1 To $iRows
        For $c = 0 To $iCols - 1
            Local $idx = $iCols + (($r - 1) * $iCols) + $c
            $sOut &= $aRes[$idx] & @CRLF
        Next
    Next
    MsgBox(64, "Tables found (" & $iRows & ")", $sOut)
EndIf

_SQLite_Close($hDb)
_SQLite_Shutdown()
