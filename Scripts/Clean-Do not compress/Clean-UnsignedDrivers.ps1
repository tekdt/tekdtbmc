param(
    [Parameter(Mandatory=$true)]
    [string]$rootPath
)

# Kiểm tra đường dẫn tồn tại
if (-not (Test-Path -Path $rootPath)) {
    Write-Host "Thu muc khong ton tai!" -ForegroundColor Red
    exit
}

# Bước 1: Xóa các file TXT, DLL, EXE, MSI
Get-ChildItem -Path $rootPath -Recurse -Include @('*.png', '*.jpg', '*.jpeg', '*.txt', '*.wmv', '*.wav', '*.chm', '*.xml', '*.htm', '*.html', '*.avi', '*.rtf', '*.tx_', '*.bmp', '*.mpg', '*.js', '*.7z', '*.bin', '*.exe', '*.dll', '*.ico') -File | ForEach-Object {
    try {
        Remove-Item -Path $_.FullName -Force
        Write-Host "Da xoa: $($_.FullName)" -ForegroundColor Yellow
    }
    catch {
        Write-Host "Loi khi xoa $($_.FullName): $_" -ForegroundColor Red
    }
}

# Bước 2: Kiểm tra và xóa driver chưa ký số
$unsignedDrivers = Get-ChildItem -Path $rootPath -Recurse -Filter *.sys -File | Where-Object {
    try {
        $sig = Get-AuthenticodeSignature -FilePath $_.FullName
        return ($sig.Status -ne 'Valid')
    }
    catch {
        return $true
    }
}

if ($unsignedDrivers) {
    $unsignedDrivers | ForEach-Object {
        try {
            Remove-Item -Path $_.FullName -Force
            Write-Host "Da xoa driver chua ky so: $($_.FullName)" -ForegroundColor Cyan
        }
        catch {
            Write-Host "Loi khi xoa driver $($_.FullName): $_" -ForegroundColor Red
        }
    }
}
else {
    Write-Host "Khong tim thay driver nao chua ky so!" -ForegroundColor Green
}



# param(
    # [Parameter(Mandatory=$true)]
    # [string]$rootPath
# )

# # Danh sách phần mở rộng được giữ lại (cần cho nạp driver)
# $keepExtensions = @('.inf', '.sys', '.cat')

# # Kiểm tra đường dẫn tồn tại
# if (-not (Test-Path -Path $rootPath)) {
    # Write-Host "Dir is empty!" -ForegroundColor Red
    # exit
# }

# # Bước 1: Xóa tất cả file KHÔNG có phần mở rộng trong danh sách giữ lại
# Get-ChildItem -Path $rootPath -Recurse -File | Where-Object {
    # $_.Extension -notin $keepExtensions
# } | ForEach-Object {
    # try {
        # Remove-Item -Path $_.FullName -Force
        # Write-Host "Deleted: $($_.FullName)" -ForegroundColor Yellow
    # }
    # catch {
        # Write-Host "Error while deleting driver $($_.FullName): $_" -ForegroundColor Red
    # }
# }

# # Bước 2: Kiểm tra và xóa driver chưa ký số (chỉ kiểm tra file .sys)
# $unsignedDrivers = Get-ChildItem -Path $rootPath -Recurse -Filter *.sys -File | Where-Object {
    # try {
        # $sig = Get-AuthenticodeSignature -FilePath $_.FullName
        # return ($sig.Status -ne 'Valid')
    # }
    # catch {
        # return $true
    # }
# }

# if ($unsignedDrivers) {
    # $unsignedDrivers | ForEach-Object {
        # try {
            # Remove-Item -Path $_.FullName -Force
            # Write-Host "Deleted unsigned digital driver: $($_.FullName)" -ForegroundColor Cyan
        # }
        # catch {
            # Write-Host "Error while deleting driver $($_.FullName): $_" -ForegroundColor Red
        # }
    # }
# }
# else {
    # Write-Host "Not found any unsigned digital drivers!" -ForegroundColor Green
# }

# Bước 3: Xóa các thư mục rỗng (tùy chọn)
Get-ChildItem -Path $rootPath -Recurse -Directory | Where-Object {
    $_.GetFiles().Count -eq 0 -and $_.GetDirectories().Count -eq 0
} | ForEach-Object {
    try {
        Remove-Item -Path $_.FullName -Force
        Write-Host "Deleted empty folder: $($_.FullName)" -ForegroundColor DarkGray
    }
    catch {
        Write-Host "Error while deleting folder $($_.FullName): $_" -ForegroundColor Red
    }
}