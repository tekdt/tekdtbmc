#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Kiểm tra chữ ký USB đã được ghi bởi Python script (Đồng bộ hoàn toàn)

.PARAMETER PhysicalDriveNumber
    Số hiệu ổ đĩa cần kiểm tra (mặc định: 1)

.PARAMETER SecretKey
    Secret key dùng để tạo hash (phải khớp với Python)
#>

param(
    [int]$PhysicalDriveNumber = 1,
    [string]$SecretKey = "_TekDT@BMC391152"  # Thay bằng secret key thực tế
)

# ==================== CẤU HÌNH ====================
$SECTOR_SIZE = 512
$NUM_SECTORS = 10
$REQUIRED_SPACE = $NUM_SECTORS * $SECTOR_SIZE

# ==================== HÀM CHÍNH ====================

function Get-DiskIdentifier {
    param([int]$DiskNum)
    
    $scriptFile = "$env:TEMP\get_disk_id_$DiskNum.txt"
    $outputFile = "$env:TEMP\disk_id_out_$DiskNum.txt"
    
    # Tạo script diskpart
    @"
select disk $DiskNum
detail disk
list partition
exit
"@ | Out-File -FilePath $scriptFile -Encoding ASCII
    
    # Chạy diskpart
    diskpart /s $scriptFile | Out-File -FilePath $outputFile -Encoding UTF8
    $output = Get-Content -Path $outputFile -Raw
    
    # Dọn dẹp
    Remove-Item $scriptFile, $outputFile -ErrorAction SilentlyContinue
    
    # Parse Disk ID (GPT GUID hoặc MBR hex)
    if ($output -match 'Disk ID\s*:\s*\{([A-F0-9-]+)\}') {
        $diskID = $matches[1]
        Write-Host "Disk ID (GPT GUID): $diskID" -ForegroundColor Cyan
    }
    elseif ($output -match 'Disk ID\s*:\s*([A-F0-9]+)') {
        $diskID = $matches[1]
        Write-Host "Disk ID (MBR): $diskID" -ForegroundColor Cyan
    }
    else {
        throw "Không tìm thấy Disk ID trong output của diskpart"
    }
    
    return $diskID, $output
}

function Get-EndOfLastPartition {
    param([string]$DiskpartOutput, [int]$DiskNum)
    
    $maxEnd = 0
    
    # Parse từng partition
    $partitionMatches = [regex]::Matches($DiskpartOutput, 'Partition\s+(\d+).*?Offset:\s+(\d+)\s+KB.*?Size:\s+([\d.]+)\s+(MB|GB|TB|KB)')
    
    foreach ($match in $partitionMatches) {
        $partNum = $match.Groups[1].Value
        $offsetKB = [long]$match.Groups[2].Value
        $size = [double]$match.Groups[3].Value
        $unit = $match.Groups[4].Value
        
        # Quy đổi Size về KB
        switch ($unit) {
            'TB' { $sizeKB = $size * 1024 * 1024 * 1024 }
            'GB' { $sizeKB = $size * 1024 * 1024 }
            'MB' { $sizeKB = $size * 1024 }
            'KB' { $sizeKB = $size }
        }
        
        # Tính end (bytes)
        $offsetBytes = $offsetKB * 1024
        $sizeBytes = $sizeKB * 1024
        $end = $offsetBytes + $sizeBytes
        
        if ($end -gt $maxEnd) {
            $maxEnd = $end
        }
        
        Write-Host "  Partition $partNum : Offset=$offsetBytes, Size=$sizeBytes, End=$end" -ForegroundColor Gray
    }
    
    if ($maxEnd -eq 0) {
        throw "Không tìm thấy partition nào hoặc không parse được"
    }
    
    Write-Host "End of last partition: $maxEnd bytes" -ForegroundColor Cyan
    return $maxEnd
}

function Get-DiskSizeViaWMI {
    param([int]$DiskNum)
    
    $disk = Get-WmiObject -Class Win32_DiskDrive | Where-Object { $_.Index -eq $DiskNum }
    if (-not $disk) {
        throw "Không tìm thấy PhysicalDrive $DiskNum trong WMI"
    }
    
    $diskSize = [long]$disk.Size
    Write-Host "Disk Size (WMI): $diskSize bytes" -ForegroundColor Cyan
    return $diskSize
}

function Read-SectorData {
    param(
        [string]$DevicePath,
        [long]$Offset,
        [int]$BytesToRead
    )
    
    try {
        $buffer = New-Object byte[] $BytesToRead
        $fileStream = New-Object System.IO.FileStream(
            $DevicePath, 
            [System.IO.FileMode]::Open, 
            [System.IO.FileAccess]::Read, 
            [System.IO.FileShare]::ReadWrite
        )
        
        $fileStream.Seek($Offset, [System.IO.SeekOrigin]::Begin) | Out-Null
        $bytesRead = $fileStream.Read($buffer, 0, $BytesToRead)
        $fileStream.Close()
        
        if ($bytesRead -eq 0) {
            throw "Đọc được 0 bytes"
        }
        
        Write-Host "Đã đọc $bytesRead bytes từ offset $Offset" -ForegroundColor Green
        return $buffer
    }
    catch {
        Write-Host "Lỗi khi đọc sector: $_" -ForegroundColor Red
        return $null
    }
}

function Get-SHA256Hash {
    param([string]$InputString)
    
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($InputString)
    $hashBytes = $sha256.ComputeHash($bytes)
    $hash = [System.BitConverter]::ToString($hashBytes) -replace '-', ''
    
    return $hash.ToLower()
}

# ==================== CHƯƠNG TRÌNH CHÍNH ====================

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  USB Signature Checker (Python Synced)" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

try {
    # Bước 1: Lấy Disk ID
    Write-Host "[1/5] Lấy Disk Identifier..." -ForegroundColor Cyan
    $diskID, $diskpartOutput = Get-DiskIdentifier -DiskNum $PhysicalDriveNumber
    
    # Bước 2: Tính End of Last Partition
    Write-Host "`n[2/5] Tính End of Last Partition..." -ForegroundColor Cyan
    $endLastPart = Get-EndOfLastPartition -DiskpartOutput $diskpartOutput -DiskNum $PhysicalDriveNumber
    
    # Bước 3: Lấy Disk Size
    Write-Host "`n[3/5] Lấy Disk Size..." -ForegroundColor Cyan
    $diskSize = Get-DiskSizeViaWMI -DiskNum $PhysicalDriveNumber
    
    # Kiểm tra unallocated space
    $unallocatedEnd = $diskSize - $endLastPart
    Write-Host "Unallocated at end: $unallocatedEnd bytes" -ForegroundColor Cyan
    
    if ($unallocatedEnd -lt $REQUIRED_SPACE) {
        Write-Host "CẢNH BÁO: Unallocated tại cuối không đủ ($unallocatedEnd < $REQUIRED_SPACE bytes)" -ForegroundColor Yellow
    }
    
    # Tính target offset (GIỐNG PYTHON)
    $targetOffset = $diskSize - $REQUIRED_SPACE
    Write-Host "Target Offset: $targetOffset bytes (Hex: 0x$($targetOffset.ToString('X')))" -ForegroundColor Cyan
    
    # Bước 4: Tạo Expected Hash
    Write-Host "`n[4/5] Tạo Expected Hash..." -ForegroundColor Cyan
    $stringToHash = $diskID + $SecretKey
    $expectedHash = Get-SHA256Hash -InputString $stringToHash
    Write-Host "Expected Hash: $expectedHash" -ForegroundColor Green
    
    # Bước 5: Đọc và kiểm tra
    Write-Host "`n[5/5] Đọc Stored Hash từ USB..." -ForegroundColor Cyan
    $drivePath = "\\.\PHYSICALDRIVE$PhysicalDriveNumber"
    $buffer = Read-SectorData -DevicePath $drivePath -Offset $targetOffset -BytesToRead $SECTOR_SIZE
    
    if ($null -eq $buffer) {
        throw "Không đọc được dữ liệu từ ổ đĩa"
    }
    
    # Trích xuất hash (64 ký tự hex đầu tiên)
    $storedHashBytes = $buffer[0..63]
    $storedHash = [System.Text.Encoding]::ASCII.GetString($storedHashBytes).ToLower()
    
    # Kiểm tra format hex hợp lệ
    if ($storedHash -notmatch '^[a-f0-9]{64}$') {
        Write-Host "CẢNH BÁO: Stored hash không đúng format hex (có thể chưa ghi hoặc bị lỗi)" -ForegroundColor Yellow
        Write-Host "Stored Hash (raw): $storedHash" -ForegroundColor Gray
    }
    else {
        Write-Host "Stored Hash: $storedHash" -ForegroundColor Green
    }
    
    # So sánh
    Write-Host "`n========================================" -ForegroundColor Yellow
    if ($expectedHash -eq $storedHash) {
        Write-Host "✓ KIỂM TRA THÀNH CÔNG!" -ForegroundColor Green
        Write-Host "USB này là bản gốc hợp lệ." -ForegroundColor Green
    }
    else {
        Write-Host "✗ KIỂM TRA THẤT BẠI!" -ForegroundColor Red
        Write-Host "USB này không hợp lệ hoặc đã bị sao chép." -ForegroundColor Red
        Write-Host "`nChi tiết:" -ForegroundColor Yellow
        Write-Host "  Expected: $expectedHash" -ForegroundColor Gray
        Write-Host "  Stored  : $storedHash" -ForegroundColor Gray
    }
    Write-Host "========================================" -ForegroundColor Yellow
    
    # Hiển thị dữ liệu raw (để debug)
    Write-Host "`n[DEBUG] Dữ liệu raw (512 bytes đầu):" -ForegroundColor DarkGray
    $hexString = [System.BitConverter]::ToString($buffer) -replace '-', ' '
    Write-Host $hexString.Substring(0, [Math]::Min(200, $hexString.Length)) -ForegroundColor DarkGray
    Write-Host "..." -ForegroundColor DarkGray
}
catch {
    Write-Host "`n✗ LỖI: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
    exit 1
}

Write-Host "`nHoàn tất." -ForegroundColor Cyan