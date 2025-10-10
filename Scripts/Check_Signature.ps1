# ============================================================================
# Script: Check USB Signature (100% synced with Python implementation)
# Purpose: Verify USB authenticity by checking SHA256 hash signature
# ============================================================================

param(
    [int]$PhyDriveNum = -1  # -1 = check all drives
)

# Import secret key (adjust path as needed)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SecretKeyFile = Join-Path $ScriptDir "secret_key.ps1"

if (Test-Path $SecretKeyFile) {
    . $SecretKeyFile
    Write-Host "Secret key loaded" -ForegroundColor Green
} else {
    Write-Host "ERROR: secret_key.ps1 not found!" -ForegroundColor Red
    exit 1
}

# ============================================================================
# Function: Get-DiskIDViaDiskpart
# Get Disk ID/GUID using diskpart (same as Python)
# ============================================================================
function Get-DiskIDViaDiskpart {
    param([int]$DiskNum)
    
    $ScriptFile = [System.IO.Path]::GetTempFileName()
    $OutputFile = [System.IO.Path]::GetTempFileName()
    
    @"
select disk $DiskNum
detail disk
exit
"@ | Out-File -FilePath $ScriptFile -Encoding ASCII
    
    $null = diskpart /s $ScriptFile > $OutputFile 2>&1
    $Output = Get-Content $OutputFile -Raw
    
    Remove-Item $ScriptFile, $OutputFile -Force -ErrorAction SilentlyContinue
    
    # Try to find GUID first (GPT)
    if ($Output -match "Disk ID\s*:\s*\{([A-F0-9-]+)\}") {
        return $Matches[1]
    }
    
    # Try to find Disk ID (MBR)
    if ($Output -match "Disk ID\s*:\s*([A-F0-9]{8})") {
        return $Matches[1]
    }
    
    return $null
}

# ============================================================================
# Function: Get-DiskSizeViaDiskpart
# Get exact disk size using diskpart (synced with Python WMI method)
# ============================================================================
function Get-DiskSizeViaDiskpart {
    param([int]$DiskNum)
    
    try {
        # Method 1: WMI (same as Python)
        $Disk = Get-WmiObject -Class Win32_DiskDrive -Filter "Index = $DiskNum"
        if ($Disk -and $Disk.Size) {
            Write-Host "  → Disk size from WMI: $($Disk.Size) bytes" -ForegroundColor Cyan
            return [int64]$Disk.Size
        }
    } catch {
        Write-Host "  → WMI failed, trying diskpart..." -ForegroundColor Yellow
    }
    
    # Method 2: Parse diskpart detail disk
    $ScriptFile = [System.IO.Path]::GetTempFileName()
    $OutputFile = [System.IO.Path]::GetTempFileName()
    
    @"
select disk $DiskNum
detail disk
exit
"@ | Out-File -FilePath $ScriptFile -Encoding ASCII
    
    $null = diskpart /s $ScriptFile > $OutputFile 2>&1
    $Output = Get-Content $OutputFile -Raw
    
    Remove-Item $ScriptFile, $OutputFile -Force -ErrorAction SilentlyContinue
    
    # Parse: "Disk ID: ... Type: ... Status: ... Capacity: XXX GB"
    if ($Output -match "Capacity\s*:\s*([\d.]+)\s*(GB|MB|TB)") {
        $Value = [double]$Matches[1]
        $Unit = $Matches[2]
        
        $SizeBytes = switch ($Unit) {
            "TB" { $Value * 1024 * 1024 * 1024 * 1024 }
            "GB" { $Value * 1024 * 1024 * 1024 }
            "MB" { $Value * 1024 * 1024 }
            default { $Value }
        }
        
        Write-Host "  → Disk size from diskpart: $([int64]$SizeBytes) bytes" -ForegroundColor Cyan
        return [int64]$SizeBytes
    }
    
    return 0
}

# ============================================================================
# Function: Read-SectorData
# Read data from specific offset (synced with Python)
# ============================================================================
function Read-SectorData {
    param(
        [string]$DevicePath,
        [int64]$Offset,
        [int]$BytesToRead
    )
    
    try {
        # Open device with read access
        $FileStream = New-Object System.IO.FileStream(
            $DevicePath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        
        # Seek to offset
        $null = $FileStream.Seek($Offset, [System.IO.SeekOrigin]::Begin)
        
        # Read data
        $Buffer = New-Object byte[] $BytesToRead
        $BytesRead = $FileStream.Read($Buffer, 0, $BytesToRead)
        
        $FileStream.Close()
        $FileStream.Dispose()
        
        if ($BytesRead -eq 0) {
            Write-Host "  → ERROR: 0 bytes read from offset" -ForegroundColor Red
            return ""
        }
        
        Write-Host "  → Successfully read $BytesRead bytes from offset $Offset" -ForegroundColor Green
        
        # Convert to ASCII string (same as Python: decode as ASCII)
        $Result = [System.Text.Encoding]::ASCII.GetString($Buffer)
        
        # Trim null characters
        return $Result.TrimEnd([char]0)
        
    } catch {
        Write-Host "  → ERROR reading sector: $_" -ForegroundColor Red
        return ""
    }
}

# ============================================================================
# Function: Verify-USBSignature
# Main verification function (100% synced with Python)
# ============================================================================
function Verify-USBSignature {
    param([int]$DiskNum)
    
    Write-Host "`n=== Checking PhysicalDrive$DiskNum ===" -ForegroundColor Cyan
    
    # STEP 1: Get Disk ID/GUID
    $DiskID = Get-DiskIDViaDiskpart -DiskNum $DiskNum
    if (-not $DiskID) {
        Write-Host "  → ERROR: Cannot get Disk ID. Skipping." -ForegroundColor Red
        return $false
    }
    Write-Host "  Disk ID/GUID: $DiskID" -ForegroundColor White
    
    # STEP 2: Get Disk Size
    $DiskSize = Get-DiskSizeViaDiskpart -DiskNum $DiskNum
    if ($DiskSize -le 0) {
        Write-Host "  → ERROR: Cannot get disk size. Skipping." -ForegroundColor Red
        return $false
    }
    Write-Host "  Disk Size: $DiskSize bytes ($([math]::Round($DiskSize/1GB, 2)) GB)" -ForegroundColor White
    
    # STEP 3: Calculate target offset (EXACTLY as Python does)
    $SECTOR_SIZE = 512
    $NUM_SECTORS = 10
    $RequiredSpace = $NUM_SECTORS * $SECTOR_SIZE
    $TargetOffset = $DiskSize - $RequiredSpace
    
    Write-Host "  Target Offset: $TargetOffset bytes (Disk Size - $RequiredSpace)" -ForegroundColor White
    
    if ($TargetOffset -lt 0) {
        Write-Host "  → ERROR: Negative offset. Skipping." -ForegroundColor Red
        return $false
    }
    
    # STEP 4: Generate expected hash (same as Python: SHA256(disk_id + secret_key))
    $StringToHash = $DiskID + $SECRET_KEY
    $SHA256 = [System.Security.Cryptography.SHA256]::Create()
    $HashBytes = $SHA256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($StringToHash))
    $ExpectedHash = ($HashBytes | ForEach-Object { $_.ToString("x2") }) -join ""
    $SHA256.Dispose()
    
    Write-Host "  Expected Hash: $ExpectedHash" -ForegroundColor Yellow
    
    # STEP 5: Read stored data from sector
    $DevicePath = "\\.\PhysicalDrive$DiskNum"
    $StoredData = Read-SectorData -DevicePath $DevicePath -Offset $TargetOffset -BytesToRead $SECTOR_SIZE
    
    if (-not $StoredData) {
        Write-Host "  → ERROR: Cannot read data from offset." -ForegroundColor Red
        return $false
    }
    
    # STEP 6: Extract stored hash (first 64 hex characters)
    $StoredHash = $StoredData.Substring(0, [Math]::Min(64, $StoredData.Length)).ToLower()
    $StoredHash = $StoredHash -replace '[^0-9a-f]', ''  # Remove non-hex chars
    
    Write-Host "  Stored Hash:   $StoredHash" -ForegroundColor Yellow
    
    # STEP 7: Compare
    if ($ExpectedHash -eq $StoredHash -and $StoredHash.Length -eq 64) {
        Write-Host "`n✅ VERIFICATION SUCCESS on PhysicalDrive$DiskNum ✅`n" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  → Hash mismatch! USB may be cloned." -ForegroundColor Red
        if ($StoredHash.Length -ne 64) {
            Write-Host "    (Stored hash length: $($StoredHash.Length), expected: 64)" -ForegroundColor Red
        }
        return $false
    }
}

# ============================================================================
# Main Execution
# ============================================================================
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "USB Signature Verification Tool (Synced)" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

if ($PhyDriveNum -ge 0) {
    # Check specific drive
    $Result = Verify-USBSignature -DiskNum $PhyDriveNum
    exit $(if ($Result) { 0 } else { 1 })
} else {
    # Check all drives
    $Found = $false
    for ($i = 0; $i -le 15; $i++) {
        $DevPath = "\\.\PhysicalDrive$i"
        
        # Quick check if drive exists
        try {
            $fs = New-Object System.IO.FileStream($DevPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $fs.Close()
            $fs.Dispose()
            
            if (Verify-USBSignature -DiskNum $i) {
                $Found = $true
                break
            }
        } catch {
            # Drive doesn't exist, skip silently
            continue
        }
    }
    
    if (-not $Found) {
        Write-Host "`n❌ VERIFICATION FAILED on all drives ❌`n" -ForegroundColor Red
        exit 1
    }
    exit 0
}