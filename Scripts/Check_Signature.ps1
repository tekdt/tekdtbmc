# Chạy với quyền Administrator
$phyDriveNum = 1 # Thay đổi số hiệu ổ đĩa cần kiểm tra

$disk = Get-WmiObject -Class Win32_DiskDrive | Where-Object { $_.Index -eq $phyDriveNum }
if (-not $disk) { throw "Không tìm thấy PhysicalDrive $phyDriveNum." }

$diskSize = $disk.Size
$drivePath = "\\.\PHYSICALDRIVE$phyDriveNum"
$targetOffset = $diskSize - (10 * 512)

Write-Host "Đang kiểm tra: $($disk.Model)"
Write-Host "Kích thước chính xác: $diskSize bytes" -ForegroundColor Cyan
Write-Host "Offset cần kiểm tra: $targetOffset (Decimal)" -ForegroundColor Cyan

$buffer = New-Object byte[] 512
$fileStream = New-Object System.IO.FileStream($drivePath, 'Open', 'Read', 'ReadWrite')
$fileStream.Seek($targetOffset, 'Begin') | Out-Null
$bytesRead = $fileStream.Read($buffer, 0, 512)
$fileStream.Close()

Write-Host "Bytes đã đọc: $bytesRead"
Write-Host "-------------------------------------------"
Write-Host "Dữ liệu dạng HEX (giống HxD):" -ForegroundColor Green
# --- THAY ĐỔI Ở ĐÂY ---
# Chuyển đổi buffer byte thành chuỗi Hex và hiển thị
$hexString = [System.BitConverter]::ToString($buffer)
Write-Host $hexString -ForegroundColor White

Write-Host "-------------------------------------------"
Write-Host "Dữ liệu dạng Text (đã lọc):" -ForegroundColor Green
# Giữ lại cách hiển thị cũ để đối chiếu
$sectorString = [System.Text.Encoding]::UTF8.GetString($buffer).TrimEnd([char]0)
Write-Host $sectorString
Write-Host "-------------------------------------------"