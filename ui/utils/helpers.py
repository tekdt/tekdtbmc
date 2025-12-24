import json, os, shutil, time, subprocess, ctypes, zipfile, config, tempfile, re, hashlib, traceback, sqlite3
from ctypes import wintypes
from pathlib import Path
from ui.utils import secret_key, tool_manager

def _copy_with_progress(worker, src, dst, total_copy_size, copied_so_far, base_progress, progress_range):
    """
    Sao chép một file và cập nhật tiến trình dựa trên tổng dung lượng cần sao chép.
    
    Args:
        worker: Worker thread instance để emit tín hiệu.
        src (str): Đường dẫn file nguồn.
        dst (str): Đường dẫn file đích.
        total_copy_size (int): Tổng dung lượng của tất cả các file sẽ được sao chép.
        copied_so_far (int): Dung lượng đã được sao chép từ các bước trước.
        base_progress (int): Tiến trình cơ bản khi bắt đầu giai đoạn sao chép (vd: 15).
        progress_range (int): Phạm vi tiến trình dành cho việc sao chép (vd: 65).

    Returns:
        int: Tổng dung lượng đã sao chép sau khi hoàn thành (copied_so_far + file_size).
    """
    try:
        file_size = os.path.getsize(src)
        filename = os.path.basename(src)
        # Chỉ cập nhật status cho các file lớn để tránh làm lag UI
        if file_size > 10 * 1024 * 1024: # Lớn hơn 10MB
            worker.status.emit(f"Đang sao chép: {filename}...")

        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            # Sử dụng buffer lớn để tăng tốc độ I/O
            buffer_size = 1024 * 1024 * 16 # 16MB buffer
            while True:
                buf = fsrc.read(buffer_size)
                if not buf:
                    break
                fdst.write(buf)
                copied_so_far += len(buf)
                
                # Tính toán và gửi tín hiệu tiến trình
                if total_copy_size > 0:
                    copy_percentage = copied_so_far / total_copy_size
                    current_progress = int(base_progress + (copy_percentage * progress_range))
                    worker.progress.emit(current_progress)
        
        return copied_so_far
    except Exception as e:
        raise IOError(f"Lỗi khi sao chép file '{src}' tới '{dst}': {e}")

def _process_driver_archive(main_app, usb_mount_point):
    """
    Xử lý kho driver (Monolithic hoặc Modular) và công cụ TekDT_PE.
    """
    main_app.creation_worker.status.emit("Đang xử lý kho driver và công cụ TekDT_PE...")
    drivers_dir = config.DRIVERS_DIR
    tekdt_pe = drivers_dir / "TekDT_PE.7z"
    usb_ventoy_dir = Path(usb_mount_point) / "ventoy"
    
    # Path cố định cho file DB
    final_db_path = usb_ventoy_dir / "db.sqlite"

    if not drivers_dir.exists():
        msg = "Thư mục Drivers không tồn tại. Bỏ qua."
        main_app.creation_worker.status.emit(msg)
        print(msg)
        return

    os.makedirs(usb_ventoy_dir, exist_ok=True)

    # --- PHẦN 1: XỬ LÝ DRIVERS (HỖ TRỢ CẢ MONOLITHIC VÀ MODULAR) ---
    try:
        drivers_subdir = drivers_dir / "Drivers"
        if not drivers_subdir.exists():
            msg = "Thư mục Drivers/Drivers không tồn tại. Bỏ qua driver packs."
            main_app.creation_worker.status.emit(msg)
            print(msg)
        else:
            # 1. Tìm tất cả các ứng viên file .7z và .7z.001
            # Chúng ta sẽ dùng Dictionary để nhóm các phần split lại với nhau
            # Key: Tên file đích trên USB (ví dụ: Drivers.7z hoặc DP_Video.7z)
            # Value: List các file nguồn [(index, path), ...]
            archive_groups = {}

            all_files = list(drivers_subdir.glob("*.7z*"))
            
            for p in all_files:
                name = p.name
                # Kiểm tra dạng file thường: Name.7z
                if name.lower().endswith(".7z"):
                    target_name = name
                    if target_name not in archive_groups: archive_groups[target_name] = []
                    archive_groups[target_name].append((0, p)) # Index 0 cho file đơn
                
                # Kiểm tra dạng split: Name.7z.001
                # Regex tìm .7z.số (vd: Drivers.7z.001 hoặc DP_VGA.7z.001)
                m = re.match(r"^(.*\.7z)\.(\d+)$", name, re.IGNORECASE)
                if m:
                    base_name = m.group(1) # Drivers.7z
                    idx = int(m.group(2))  # 001 -> 1
                    if base_name not in archive_groups: archive_groups[base_name] = []
                    archive_groups[base_name].append((idx, p))

            # 2. Xử lý copy/gộp
            if not archive_groups:
                 main_app.creation_worker.status.emit("Không tìm thấy gói driver (.7z) nào.")
            else:
                for target_name, parts in archive_groups.items():
                    final_path = usb_ventoy_dir / target_name
                    
                    # Sắp xếp các phần: (0, path) hoặc (1, path), (2, path)...
                    parts.sort(key=lambda x: x[0])
                    source_files = [x[1] for x in parts]

                    main_app.creation_worker.status.emit(f"Đang xử lý gói: {target_name}...")
                    print(f"Processing package {target_name} with {len(source_files)} parts.")

                    # Nếu chỉ có 1 file và không phải là split part (hoặc split part nhưng chỉ có 1 file .001 lẻ loi)
                    # Tuy nhiên logic ở đây là: Nếu file gốc là .7z -> Copy. 
                    # Nếu file gốc là .7z.001 -> Merge vào .7z đích (để AutoIt dễ xử lý hơn, hoặc giữ nguyên).
                    # Để tương thích tốt nhất với logic AutoIt (ưu tiên tìm .7z), ta sẽ MERGE các file .001 thành .7z
                    
                    if len(source_files) == 1 and parts[0][0] == 0:
                        # Đây là file .7z chuẩn, copy thẳng
                        shutil.copy(source_files[0], final_path)
                    else:
                        # Đây là file split (.001...), hoặc logic gộp nhiều file
                        # Gộp tất cả vào file đích .7z (loại bỏ đuôi .001 trên USB)
                        with open(final_path, "wb") as outfile:
                            for part in source_files:
                                with open(part, "rb") as infile:
                                    shutil.copyfileobj(infile, outfile)
                    
                main_app.creation_worker.status.emit("Đã hoàn tất sao chép các gói Driver.")

    except Exception as e:
        msg = f"Lỗi khi xử lý Drivers: {e}"
        main_app.creation_worker.status.emit(msg)
        print(msg)
        raise

    # --- PHẦN 2: XỬ LÝ DB.SQLITE ---
    try:
        db_subdir = drivers_dir / "DB"
        if not db_subdir.exists():
            msg = "Thư mục Drivers/DB không tồn tại. Bỏ qua db.sqlite."
            main_app.creation_worker.status.emit(msg)
            print(msg)
        else:
            # Logic tìm db.sqlite hoặc db.sqlite.001
            parts_with_index = []
            direct_db = db_subdir / "db.sqlite"
            
            if direct_db.exists():
                parts_with_index.append((0, direct_db))
            else:
                candidates = [p for p in db_subdir.glob("db.sqlite.*") if p.is_file()]
                pattern = re.compile(r"^db\.sqlite\.(\d+)$")
                for p in candidates:
                    m = pattern.match(p.name)
                    if m:
                        idx = int(m.group(1))
                        parts_with_index.append((idx, p))
            
            if parts_with_index:
                parts_with_index.sort(key=lambda t: t[0])
                parts = [p for _, p in parts_with_index]
                
                main_app.creation_worker.status.emit("Đang sao chép Database driver...")
                with open(final_db_path, "wb") as outfile:
                    for part in parts:
                        with open(part, "rb") as infile:
                            shutil.copyfileobj(infile, outfile)
                print("Sao chép db.sqlite hoàn tất.")

    except Exception as e:
        msg = f"Lỗi khi xử lý db.sqlite: {e}"
        main_app.creation_worker.status.emit(msg)
        print(msg)
        raise

    # --- PHẦN 3: XỬ LÝ TEKDT_PE.7Z ---
    try:
        tekdt_pe_archive_path = usb_ventoy_dir / "TekDT_PE.7z"
        if tekdt_pe.exists():
            main_app.creation_worker.status.emit("Đang sao chép TekDT_PE.7z...")
            shutil.copy(tekdt_pe, tekdt_pe_archive_path)
            print("Sao chép TekDT_PE.7z hoàn tất.")
        else:
            print("Không tìm thấy TekDT_PE.7z.")
    except Exception as e:
        msg = f"Lỗi khi sao chép TekDT_PE.7z: {e}"
        main_app.creation_worker.status.emit(msg)
        print(msg)
        raise

def _generate_ventoy_json(main_app):
    """
    Tạo nội dung file JSON cấu hình cho Ventoy.
    Hàm này được giữ nguyên logic từ file gốc của bạn.
    """
    config_data = {
        "control": [
            {
                "VTOY_SECONDARY_TIMEOUT": "3",
                "VTOY_MAX_SEARCH_LEVEL": "0",
                "VTOY_WIN11_BYPASS_CHECK": "1",
                "VTOY_WIN11_BYPASS_NRO": "1"
            }
        ],
        "auto_install": [],
        "injection": [],
        "menu_alias": []
    }

    for iso_info in main_app.config['iso_list']:
        iso_filename_with_path = f"/{iso_info['filename']}"
        if iso_info.get("unattend_file"):
            config_data["auto_install"].append({
                "image": iso_filename_with_path,
                "template": f"/ventoy/{iso_info['unattend_file']}",
                "autosel": 1
            })
        if iso_info.get("alias"):
            config_data["menu_alias"].append({
                "image": iso_filename_with_path,
                "alias": iso_info["alias"]
            })
    
    # Chỉ thêm injection nếu có file Drivers
    tekdtpe_archive = config.DRIVERS_DIR / "TekDT_PE.7z"
    if tekdtpe_archive.exists():
        config_data["injection"].append({
            "parent": "/",
            "archive": "/ventoy/TekDT_PE.7z"
        })

    if not config_data["auto_install"]: del config_data["auto_install"]
    if not config_data["injection"]: del config_data["injection"]
    if not config_data["menu_alias"]: del config_data["menu_alias"]
    
    if main_app.config["theme"]:
        theme_name = os.path.splitext(main_app.config["theme"])[0]
        config_data["theme"] = {
            "file": f"/ventoy/themes/{theme_name}/theme.txt",
            "gfxmode": "1920x1080"
        }
    return config_data # Trả về dict thay vì string

def _generate_unattend_xml(main_app, index, product_key=None, architecture="amd64", language="en-US"):
    """Tạo file unattend.xml với các thông tin chi tiết về phiên bản, kiến trúc và ngôn ngữ."""
    # Nếu đang ở chế độ lược bỏ ISO, index luôn là 1 vì file WIM mới chỉ có một phiên bản.
    final_index = 1 if main_app.config.get("prune_iso", True) else index
    
    # Nếu vẫn không có key, để trống (cài đặt sẽ hỏi lại)
    if product_key:
        product_key_xml = f"""<ProductKey>
                <Key>{product_key}</Key>
                <WillShowUI>OnError</WillShowUI>
            </ProductKey>
        """
    else:
        product_key_xml = r"<ProductKey />"

    return f"""<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">

<settings pass="windowsPE">
    <component name="Microsoft-Windows-International-Core-WinPE" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <SetupUILanguage>
            <UILanguage>{language}</UILanguage>
        </SetupUILanguage>
        <UILanguageFallback>{language}</UILanguageFallback>
        <InputLocale>{language}</InputLocale>
        <SystemLocale>{language}</SystemLocale>
        <UILanguage>{language}</UILanguage>
        <UserLocale>{language}</UserLocale>
    </component>

    <component name="Microsoft-Windows-Setup" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <ImageInstall>
            <OSImage>
                <InstallFrom>
                    <MetaData wcm:action="add">
                        <Key>/IMAGE/INDEX</Key>
                        <Value>{index}</Value>
                    </MetaData>
                </InstallFrom>
            </OSImage>
        </ImageInstall>

        <UserData>
            {product_key_xml}
            <AcceptEula>true</AcceptEula>
            <FullName>Admin</FullName>
            <Organization>TekDT BMC</Organization>
        </UserData>
    </component>
</settings>

<settings pass="offlineServicing">
    <component name="Microsoft-Windows-PnpCustomizationsNonWinPE" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <DriverPaths>
            <PathAndCredentials wcm:action="add" wcm:keyValue="1">
                <Path>X:\\Drivers</Path>
            </PathAndCredentials>
        </DriverPaths>
    </component>
    <component name="Microsoft-Windows-Foundation-Package" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <WindowsOptionalFeature>
            <Name>NetFx3</Name>
            <State>Enabled</State>
        </WindowsOptionalFeature>
    </component>
</settings>

<settings pass="specialize">    
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <ComputerName>*</ComputerName>
        <TimeZone>SE Asia Standard Time</TimeZone>
    </component>
</settings>

<settings pass="oobeSystem">
    <component name="Microsoft-Windows-International-Core" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <InputLocale>{language}</InputLocale>
        <SystemLocale>{language}</SystemLocale>
        <UILanguage>{language}</UILanguage>
        <UserLocale>{language}</UserLocale>
    </component>
    
    <component name="Microsoft-Windows-SecureStartup-FilterDriver" processorArchitecture="{architecture}" language="neutral" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" publicKeyToken="31bf3856ad364e35" versionScope="nonSxS">
        <PreventDeviceEncryption>true</PreventDeviceEncryption>
    </component>
    
    <component name="Microsoft-Windows-EnhancedStorage-Adm" processorArchitecture="{architecture}" language="neutral" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" publicKeyToken="31bf3856ad364e35" versionScope="nonSxS">
        <TCGSecurityActivationDisabled>1</TCGSecurityActivationDisabled>
    </component>

    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <AutoLogon>
            <Enabled>true</Enabled>
            <Username>Administrator</Username>
            <LogonCount>1</LogonCount>
            <Password>
                <Value/>
                <PlainText>true</PlainText>
            </Password>
        </AutoLogon>
        <UserAccounts>
            <LocalAccounts>
                <LocalAccount wcm:action="add">
                    <Password>
                        <Value/>
                        <PlainText>true</PlainText>
                    </Password>
                    <Group>Administrators</Group>
                    <Name>Administrator</Name>
                    <DisplayName/>
                </LocalAccount>
            </LocalAccounts>
        </UserAccounts>
        <OOBE>
            <ProtectYourPC>3</ProtectYourPC>
            <HideEULAPage>true</HideEULAPage>
            <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
            <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
        </OOBE>
        <FirstLogonCommands>
            <SynchronousCommand wcm:action="add">
                <CommandLine>powershell -Command "Get-Volume | Where-Object {{ $_.DriveType -eq 'Removable' -and (Test-Path ($_.DriveLetter + ':\\TekDT_AIS\\tekdt_ais.exe')) }} | ForEach-Object {{ Start-Process ($_.DriveLetter + ':\\TekDT_AIS\\tekdt_ais.exe') -ArgumentList '/install' }}"</CommandLine>
                <Description>Find and run TekDT AIS Installer</Description>
                <Order>1</Order>
            </SynchronousCommand>
        </FirstLogonCommands>
    </component>
</settings>

</unattend>
"""

def _copy_tekdtais_selectively(main_app, source_dir, dest_dir, total_copy_size, copied_so_far, base_progress, progress_range):
    """
    Sao chép thư mục TekDT AIS có chọn lọc và cập nhật tiến trình.
    """
    worker = main_app.creation_worker
    worker.status.emit("Đang sao chép TekDT AIS (chọn lọc)...")
    
    config_path = source_dir / "app_config.json"
    source_apps_dir = source_dir / "Apps"
    apps_to_copy = []

    if not config_path.exists():
        print(f"Cảnh báo: Không tìm thấy {config_path}. Sẽ sao chép toàn bộ.")
        if os.path.exists(dest_dir): shutil.rmtree(dest_dir)
        shutil.copytree(source_dir, dest_dir)
        # Ước tính dung lượng đã sao chép
        dir_size = sum(p.stat().st_size for p in Path(source_dir).rglob('*'))
        return copied_so_far + dir_size

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            app_config = json.load(f)
        apps_to_copy = [name for name, settings in app_config.get("app_items", {}).items() if settings.get("auto_install")]
        print(f"Các ứng dụng TekDT AIS sẽ được sao chép: {apps_to_copy}")
    except Exception as e:
        print(f"Lỗi đọc app_config.json: {e}. Sẽ sao chép toàn bộ.")
        if os.path.exists(dest_dir): shutil.rmtree(dest_dir)
        shutil.copytree(source_dir, dest_dir)
        dir_size = sum(p.stat().st_size for p in Path(source_dir).rglob('*'))
        return copied_so_far + dir_size

    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    # Sao chép có chọn lọc và theo dõi tiến trình
    for dirpath, dirnames, filenames in os.walk(source_dir, topdown=True):
        relative_path = os.path.relpath(dirpath, source_dir)
        dest_path = os.path.join(dest_dir, relative_path)
        
        if Path(dirpath).resolve() == source_apps_dir.resolve():
            dirnames[:] = [d for d in dirnames if d in apps_to_copy]

        os.makedirs(dest_path, exist_ok=True)
        
        for file in filenames:
            src_file = os.path.join(dirpath, file)
            dst_file = os.path.join(dest_path, file)
            copied_so_far = _copy_with_progress(worker, src_file, dst_file, total_copy_size, copied_so_far, base_progress, progress_range)
    
    print("Đã sao chép TekDT AIS (chọn lọc) vào USB.")
    return copied_so_far


def _create_fill_file(main_app, file_path, size_in_bytes, total_fill_target, space_filled_so_far):
    """
    Tạo một tệp có kích thước cụ thể và cập nhật tiến trình trong giai đoạn lấp đầy.
    """
    worker = main_app.creation_worker
    worker.status.emit(f"Đang tạo file lấp đầy: {os.path.basename(file_path)}")

    CHUNK_SIZE = 16 * 1024 * 1024
    zeros = b'\x00' * CHUNK_SIZE
    FILE_ATTRIBUTE_HIDDEN = 0x02
    FILE_ATTRIBUTE_SYSTEM = 0x04

    bytes_written = 0
    try:
        with open(file_path, "wb") as f:
            while bytes_written < size_in_bytes:
                write_size = min(CHUNK_SIZE, size_in_bytes - bytes_written)
                f.write(zeros if write_size == CHUNK_SIZE else b'\x00' * write_size)
                bytes_written += write_size
                
                current_total_filled = space_filled_so_far + bytes_written
                if total_fill_target > 0:
                    # Giai đoạn lấp đầy từ 80% -> 100%
                    fill_percentage = current_total_filled / total_fill_target
                    current_progress = int(80 + (fill_percentage * 20)) # 20 là phạm vi của giai đoạn này
                    worker.progress.emit(current_progress)
                    worker.status.emit(
                        f"Đang lấp đầy: {current_total_filled / (1024**3):.2f} / {total_fill_target / (1024**3):.2f} GB"
                    )
        
        ctypes.windll.kernel32.SetFileAttributesW(file_path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
        return bytes_written

    except Exception as e:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except OSError: pass
        raise IOError(f"Không thể ghi vào file '{file_path}'. Đĩa có thể đã đầy. Lỗi: {e}")

def _process_and_copy_iso(worker, main_app, iso_info, usb_mount_point, total_copy_size, copied_so_far, base_progress, progress_range):
    """
    Xử lý và sao chép một file ISO.
    Nếu prune_iso=True, sẽ tối ưu hóa ISO trước khi sao chép.
    Ngược lại, chỉ sao chép file gốc.
    """
    dest_iso_path = os.path.join(usb_mount_point, iso_info['filename'])

    should_prune = main_app.config.get("prune_iso", True) and iso_info.get("windows_edition_index")

    if not should_prune:
        return _copy_with_progress(worker, iso_info['path'], dest_iso_path, total_copy_size, copied_so_far, base_progress, progress_range)

    worker.status.emit(f"Đang tối ưu hóa ISO: {iso_info['filename']}...")
    print(f"Bắt đầu quá trình tối ưu hóa cho {iso_info['filename']}")
    
    mounted_drive = None
    temp_iso_content_dir = tempfile.mkdtemp(prefix="iso_content_")

    def _remove_readonly_attribute(path):
        # Đi bộ qua tất cả các file và thư mục để gỡ bỏ thuộc tính read-only
        for root, dirs, files in os.walk(path):
            for name in files:
                filepath = os.path.join(root, name)
                os.chmod(filepath, 0o777)  # stat.S_IWRITE
            for name in dirs:
                dirpath = os.path.join(root, name)
                os.chmod(dirpath, 0o777)

    def get_short_path(long_path):
        """Trả về đường dẫn dạng 8.3 để tránh lỗi oscdimg."""
        buffer = ctypes.create_unicode_buffer(260)
        get_short_path_name = ctypes.windll.kernel32.GetShortPathNameW
        if get_short_path_name(long_path, buffer, 260) > 0:
            return buffer.value
        return long_path  # Nếu fail, giữ nguyên nhưng log
        print(f"Cảnh báo: Không thể lấy short path cho {long_path}")

    try:
        worker.status.emit(f"Mounting {iso_info['filename']}...")
        mount_cmd = ['powershell', '-NoProfile', '-Command', f'Mount-DiskImage -ImagePath "{iso_info["path"]}" -PassThru | Get-Volume | Select-Object -ExpandProperty DriveLetter']
        proc = subprocess.run(mount_cmd, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        drive_letter = proc.stdout.strip()
        if not drive_letter: raise Exception("Không thể lấy ký tự ổ đĩa sau khi mount.")
        mounted_drive = f"{drive_letter}:\\"
        print(f"ISO được mount tới: {mounted_drive}")

        worker.status.emit("Sao chép nội dung ISO gốc...")
        shutil.copytree(mounted_drive, temp_iso_content_dir, dirs_exist_ok=True)
        
        # Gỡ bỏ thuộc tính read-only sau khi sao chép
        worker.status.emit("Cập nhật quyền truy cập file tạm...")
        _remove_readonly_attribute(temp_iso_content_dir)
        print(f"Đã gỡ bỏ thuộc tính read-only cho các file trong: {temp_iso_content_dir}")
        
        # Unmount ISO ngay sau khi đã sao chép xong để giải phóng tài nguyên
        unmount_cmd = ['powershell', '-NoProfile', '-Command', f'Dismount-DiskImage -ImagePath "{iso_info["path"]}"']
        subprocess.run(unmount_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        mounted_drive = None  # Đánh dấu là đã unmount
        print("Đã unmount ISO gốc để tiếp tục xử lý.")

        wim_path_original = None
        wim_path_temp = None
        for ext in [".wim", ".esd"]:
            p = Path(temp_iso_content_dir) / "sources" / f"install{ext}"
            if p.exists():
                wim_path_original = str(p)
                wim_path_temp = str(Path(tempfile.gettempdir()) / f"slim_install_{iso_info['filename']}{ext}")  # Unique để tránh overwrite
                break
        
        if not wim_path_original: raise Exception("Không tìm thấy install.wim/esd trong ISO.")
        
        original_ext = Path(wim_path_original).suffix.lower()
        compression_method = "--compress=LZX" if original_ext == ".wim" else "--compress=LZMS"
        worker.status.emit(f"Trích xuất phiên bản: {iso_info['windows_edition_name']}...")
        export_cmd = [
            str(config.WIMLIB_EXE),
            "export",
            wim_path_original,
            iso_info["windows_edition_index"],  # Index nguồn
            wim_path_temp,
            compression_method,  # Dùng kiểu nén phù hợp
            "--check"            # Thêm cờ kiểm tra tính toàn vẹn
            # KHÔNG DÙNG "--boot" ở đây
        ]
        print(f"Đang chạy lệnh wimlib: {' '.join(export_cmd)}")
        proc = subprocess.run(export_cmd, capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if proc.returncode != 0:
            print(f"Lỗi wimlib: {proc.stderr}")

        os.remove(wim_path_original)
        shutil.move(wim_path_temp, wim_path_original)
        print("Đã thay thế file WIM/ESD thành công.")
        
        ei_cfg = Path(temp_iso_content_dir) / "sources" / "ei.cfg"
        if ei_cfg.exists():
            try:
                os.remove(ei_cfg)
                print("Đã xoá ei.cfg để tránh xung đột edition (sử dụng autounattend.xml với key tự động).")
            except Exception as e:
                print(f"⚠️ Không thể xoá ei.cfg: {e}. Có thể bỏ qua nếu autounattend override.")

        worker.status.emit(f"Đang tạo lại file ISO tối ưu...")
        if not config.OSCDIMG_EXE.exists():
            raise FileNotFoundError(f"Không tìm thấy công cụ tạo ISO tại: {config.OSCDIMG_EXE}")
        
        temp_new_iso_path = os.path.join(tempfile.gettempdir(), iso_info['filename'])
        
        # Lấy short path cho tất cả
        short_temp_iso_content_dir = get_short_path(temp_iso_content_dir)
        short_temp_new_iso_path = get_short_path(temp_new_iso_path)
        bootloader_path = get_short_path(os.path.join(temp_iso_content_dir, "boot", "etfsboot.com"))
        efi_boot_path = get_short_path(os.path.join(temp_iso_content_dir, "efi", "microsoft", "boot", "efisys.bin"))
        
        if not os.path.exists(bootloader_path):
            raise FileNotFoundError(f"Không tìm thấy bootloader tại: {bootloader_path}")
        if not os.path.exists(efi_boot_path):
            raise FileNotFoundError(f"Không tìm thấy EFI boot file tại: {efi_boot_path}")
        
        # Cải thiện volume label: replace space/special bằng _, upper case, giới hạn 32
        volume_label = Path(iso_info["filename"]).stem.replace(" ", "_").replace("-", "_")[:32].upper()
        
        rebuild_cmd = [
            str(config.OSCDIMG_EXE),
            "-m", "-o", "-u2", "-udfver102",
            f"-bootdata:2#p0,e,b{bootloader_path}#pEF,e,b{efi_boot_path}",
            f"-l{volume_label}",
            short_temp_iso_content_dir,
            short_temp_new_iso_path
        ]
        print(f"Đang chạy lệnh oscdimg: {' '.join(rebuild_cmd)}")
        try:
            proc = subprocess.run(rebuild_cmd, capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.CalledProcessError as e:
            print(f"Lỗi oscdimg: Return code {e.returncode}\nStdout: {e.stdout}\nStderr: {e.stderr}")
            raise
        
        worker.status.emit(f"Sao chép ISO đã tối ưu vào USB...")
        copied_bytes = _copy_with_progress(worker, temp_new_iso_path, dest_iso_path, total_copy_size, copied_so_far, base_progress, progress_range)

        os.remove(temp_new_iso_path)
        
        return copied_bytes

    finally:
        if mounted_drive:  # Chỉ chạy nếu việc unmount ở trên thất bại
            unmount_cmd = ['powershell', '-NoProfile', '-Command', f'Dismount-DiskImage -ImagePath "{iso_info["path"]}"']
            subprocess.run(unmount_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if os.path.exists(temp_iso_content_dir):
            shutil.rmtree(temp_iso_content_dir, ignore_errors=True)
        print("Đã hoàn tất dọn dẹp cho quá trình tối ưu ISO.")

def create_usb_task(main_app):
    """Tác vụ tạo USB Boot chạy trong luồng nền với tiến trình được thiết kế lại."""
    worker = main_app.creation_worker
    try:
        worker.progress.emit(0)
        
        # --- GIAI ĐOẠN 1: ĐỊNH DẠNG USB VỚI VENTOY (0% -> 15%) ---
        install_mode = main_app.config.get("install_mode", "DESTRUCTIVE")
        worker.status.emit(f"Đang cài đặt Ventoy lên {main_app.config['device']}...")
        ventoy_exe = config.VENTOY_DIR / "Ventoy2Disk.exe"
        if not ventoy_exe.exists():
            raise FileNotFoundError("Không tìm thấy Ventoy2Disk.exe.")

        phy_drive_num = main_app.config["device"].replace("\\\\.\\PHYSICALDRIVE", "")
        
        # Luôn thêm /R:16 để tạo phân vùng MSR 16MB cho việc ghi chữ ký an toàn
        common_args = [str(ventoy_exe), "VTOYCLI", "/I", f"/PhyDrive:{phy_drive_num}", "/R:16"]

        if install_mode == "NON_DESTRUCTIVE":
            worker.status.emit("Chế độ không phá hủy: Cài đặt vào vùng dung lượng trống...")
            cmd = common_args + ["/NonDest"]
        else: # DESTRUCTIVE (Default)
            worker.status.emit("Chế độ phá hủy: Định dạng lại toàn bộ ổ đĩa...")
            cmd = common_args
            if main_app.config["partition_scheme"] == "GPT": cmd.append("/GPT")
            cmd.append(f"/FS:{main_app.config['filesystem'].upper()}")

        print(f"Executing Ventoy command: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in iter(process.stdout.readline, ''): print(line.strip())
        process.wait()

        if process.returncode != 0:
            raise Exception(f"Ventoy2Disk.exe thất bại với mã lỗi {process.returncode}")

        # --- GIAI ĐOẠN 2: GHI DẤU BẢN QUYỀN (ANTI-CLONING) NGAY LẬP TỨC ---
        # Đây là bước kiểm tra quan trọng, nếu thất bại sẽ dừng toàn bộ quá trình.
        worker.progress.emit(10)
        worker.status.emit("Đang ghi dấu bản quyền (chữ ký số) lên USB...")
        try:
            # Lấy partition_scheme từ config
            partition_scheme = main_app.config["partition_scheme"]
            _write_usb_signature(main_app.config['device_details'], phy_drive_num, partition_scheme)
            worker.status.emit("Ghi dấu bản quyền thành công.")
            print("Đã tạo phân vùng ẩn và ghi chữ ký thành công.")
        except Exception as sig_error:
            # Nếu ghi chữ ký thất bại, ném ra một ngoại lệ để dừng toàn bộ tác vụ.
            # Người dùng sẽ nhận được thông báo lỗi này trên UI.
            error_message = f"LỖI QUAN TRỌNG: Không thể ghi dấu bản quyền vào USB. Lý do: {sig_error}. Tác vụ đã bị hủy."
            print(error_message)
            raise Exception(error_message)

        worker.progress.emit(15)
        worker.status.emit("Cài đặt Ventoy thành công. Bắt đầu sao chép file...")
        
        # --- GIAI ĐOẠN 3: SAO CHÉP TẤT CẢ CÁC FILE (15% -> 80%) ---
        time.sleep(5)
        usb_mount_point = _get_drive_mount_point(main_app, main_app.config["device"])
        if not usb_mount_point:
            raise Exception("Không thể tìm thấy điểm mount của USB sau khi tạo.")

        usb_ventoy_dir = os.path.join(usb_mount_point, "ventoy")
        os.makedirs(usb_ventoy_dir, exist_ok=True)
        
        # Tạo các file unattend trước
        for i, iso_info in enumerate(main_app.config['iso_list']):
            if iso_info.get("windows_edition_index"):
                # Lấy kiến trúc và ngôn ngữ từ iso_info, có giá trị dự phòng để tránh lỗi
                edition_arch = iso_info.get("windows_edition_arch", "amd64")
                edition_lang = iso_info.get("windows_edition_lang", "en-US")
                
                unattend_content = _generate_unattend_xml(
                    main_app, 
                    iso_info["windows_edition_index"], 
                    iso_info.get("product_key"), 
                    architecture=edition_arch,
                    language=edition_lang
                )
                unattend_filename = f"unattend_{i}_{Path(iso_info['filename']).stem}.xml"
                iso_info['unattend_file'] = unattend_filename
                with open(os.path.join(usb_ventoy_dir, unattend_filename), "w", encoding='utf-8') as f:
                    f.write(unattend_content)
        
        # Lấy lại cấu hình ventoy.json sau khi đã có tên file unattend
        base_config = _generate_ventoy_json(main_app)
        
        # Gộp cấu hình theme (giữ nguyên logic gốc)
        if main_app.config["theme"]:
            worker.status.emit("Đang cài đặt theme và gộp cấu hình...")
            theme_zip_path = config.THEMES_DIR / main_app.config["theme"]
            with zipfile.ZipFile(theme_zip_path, 'r') as theme_zip:
                theme_json_content = None
                for json_path in ['ventoy/ventoy.json', 'ventoy.json']:
                    if json_path in theme_zip.namelist():
                        try:
                            with theme_zip.open(json_path) as json_file:
                                theme_json_content = json.load(json_file)
                            break
                        except Exception as e: print(f"Lỗi đọc {json_path} từ theme: {e}")
                
                members = [m for m in theme_zip.infolist() if 'ventoy.json' not in m.filename]
                theme_zip.extractall(usb_mount_point, members=members)

                if theme_json_content and 'theme' in theme_json_content:
                    base_config['theme'] = theme_json_content['theme']
                    print("Đã gộp cấu hình 'theme' từ file zip.")

        # Ghi file ventoy.json cuối cùng
        with open(os.path.join(usb_ventoy_dir, "ventoy.json"), "w", encoding='utf-8') as f:
            json.dump(base_config, f, indent=4, ensure_ascii=False)

        # Tính tổng dung lượng cần sao chép để theo dõi tiến trình
        # Sử dụng lại hàm tính size của main_app để đồng bộ
        total_copy_size = main_app._get_dir_size(config.TEKDTAIS_DIR) if config.TEKDTAIS_DIR.exists() else 0
        total_copy_size += sum(os.path.getsize(iso['path']) for iso in main_app.config['iso_list'])
        if (config.DRIVERS_DIR / "Drivers.7z.001").exists():
             total_copy_size += os.path.getsize(config.DRIVERS_DIR / "Drivers.7z.001")
             total_copy_size += os.path.getsize(config.DRIVERS_DIR / "Drivers.7z.002")
        
        copied_so_far = 0
        base_progress = 15
        progress_range = 65

        # Sao chép ISOs
        print("Đang sao chép file ISO...")
        for iso_info in main_app.config['iso_list']:
            copied_so_far = _process_and_copy_iso(worker, main_app, iso_info, usb_mount_point, total_copy_size, copied_so_far, base_progress, progress_range)

        # Sao chép TekDT AIS
        dest_ais_dir = os.path.join(usb_mount_point, "TekDT_AIS")
        if config.TEKDTAIS_DIR.exists():
            if main_app.config.get("copy_ais_selection_only", True):
                copied_so_far = _copy_tekdtais_selectively(main_app, config.TEKDTAIS_DIR, dest_ais_dir, total_copy_size, copied_so_far, base_progress, progress_range)
            else:
                worker.status.emit("Đang sao chép toàn bộ TekDT AIS...")
                if os.path.exists(dest_ais_dir): shutil.rmtree(dest_ais_dir)
                shutil.copytree(config.TEKDTAIS_DIR, dest_ais_dir)
                # Cập nhật tiến trình ước tính
                copied_so_far += sum(p.stat().st_size for p in Path(config.TEKDTAIS_DIR).rglob('*'))
                copy_percentage = copied_so_far / total_copy_size if total_copy_size > 0 else 1
                worker.progress.emit(int(base_progress + (copy_percentage * progress_range)))

        # Gộp và chép Drivers.7z và TekDT_PE.7z
        _process_driver_archive(main_app, usb_mount_point)
        
        worker.progress.emit(80) # Hoàn tất sao chép file
        
        # ====== Giai đoạn tạo file khởi động lại vào BIOS ======
        bios_tool_path = os.path.join(usb_mount_point, "Access_BIOS.bat")

        batch_content = r"""@echo off
title CONG CU TRUY CAP BIOS/UEFI
:: Kiem tra quyen Admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Vui long chay file nay bang quyen Administrator!
    pause
    exit
)

:: 1. Kiem tra che do UEFI bang cach tim kiem path winload.efi trong bcdedit
bcdedit | findstr /i "winload.efi" >nul
if %errorlevel% neq 0 (
    echo He thong dang chay o che do Legacy (BIOS). 
    echo Lenh shutdown /fw chi ho tro che do UEFI.
    pause
    exit
)

:: 2. Bat WinRE de tranh loi 203 (The system could not find the environment option...)
echo Dang kiem tra va kich hoat WinRE...
reagentc /enable >nul

:: 3. Thuc thi lenh khoi dong vao BIOS
echo May tinh se khoi dong lai vao BIOS trong giay lat...
shutdown /r /fw /t 3
"""

        try:
            with open(bios_tool_path, "w", encoding="cp850") as f:
                f.write(batch_content)
        except Exception as e:
            print(f"Lỗi tạo file BIOS tool: {e}")
        
        # --- GIAI ĐOẠN 4: LẤP ĐẦY DUNG LƯỢNG TRỐNG (80% -> 95%) ---
        if main_app.config.get("fill_space", True):
            worker.status.emit("Đang tính toán dung lượng trống...")
            time.sleep(2)

            try:
                # Lấy kích thước cluster để dự trữ không gian tối thiểu cho metadata
                try:
                    sectors_per_cluster = wintypes.DWORD()
                    bytes_per_sector = wintypes.DWORD()
                    ctypes.windll.kernel32.GetDiskFreeSpaceW(
                        ctypes.c_wchar_p(usb_mount_point),
                        ctypes.byref(sectors_per_cluster),
                        ctypes.byref(bytes_per_sector),
                        None, None
                    )
                    cluster_size = sectors_per_cluster.value * bytes_per_sector.value
                    RESERVE_SPACE = cluster_size if cluster_size > 0 else 64 * 1024
                except Exception as e:
                    print(f"Không thể lấy kích thước cluster, sử dụng giá trị dự phòng 64KB. Lỗi: {e}")
                    RESERVE_SPACE = 64 * 1024 # Giá trị dự phòng

                usage = shutil.disk_usage(usb_mount_point)
                total_free_space = usage.free
                fill_space_target = total_free_space - RESERVE_SPACE
                
                if fill_space_target <= 0:
                    print("Không đủ dung lượng trống để thực hiện lấp đầy.")
                else:
                    fs_type = main_app.config["filesystem"].upper()
                    print(f"Dung lượng trống: {total_free_space / (1024**3):.2f} GB. Sẽ lấp đầy: {fill_space_target / (1024**3):.2f} GB. Định dạng: {fs_type}")

                    fill_file_dir = os.path.join(usb_mount_point, "TekDT_Fill")
                    os.makedirs(fill_file_dir, exist_ok=True)
                    
                    space_to_fill = fill_space_target
                    space_filled_so_far = 0

                    if fs_type == "FAT32":
                        max_chunk_size = 2 * 1024 * 1024 * 1024
                        file_index = 1
                        while space_to_fill > 0:
                            file_size = min(space_to_fill, max_chunk_size)
                            file_path = os.path.join(fill_file_dir, f"fill_{file_index:03d}.dat")
                            
                            written = _create_fill_file(main_app, file_path, file_size, fill_space_target, space_filled_so_far)
                            space_filled_so_far += written
                            space_to_fill -= written
                            if written < file_size:
                                print("Cảnh báo: Không thể ghi thêm dữ liệu. Đĩa có thể đã đầy.")
                                break
                            file_index += 1
                    else:
                        if space_to_fill > 0:
                            final_fill_path = os.path.join(fill_file_dir, "fill_final.dat")
                            _create_fill_file(main_app, final_fill_path, space_to_fill, fill_space_target, space_filled_so_far)
                    
                    worker.status.emit("Đã lấp đầy dung lượng trống.")
                    print("Hoàn tất việc lấp đầy dung lượng trống.")

            except Exception as fill_error:
                print(f"Lỗi trong quá trình lấp đầy dung lượng: {fill_error}")
                worker.status.emit(f"Cảnh báo: Không thể lấp đầy dung lượng trống. Lỗi: {fill_error}")

        # --- GIAI ĐOẠN 5: ĐỔI TÊN Ổ ĐĨA VÀ XÁC THỰC LẠI CHỮ KÝ (95% -> 100%) ---
        worker.status.emit("Đang đổi tên ổ đĩa...")
        try:
            worker.status.emit("Đang xác thực lại ổ đĩa...")
            time.sleep(3) # Cho Windows thời gian để gắn lại ổ đĩa
            usb_mount_point = _get_drive_mount_point(main_app, main_app.config["device"])
            if not usb_mount_point:
                raise IOError("Không thể tìm thấy ổ đĩa sau khi ghi chữ ký.")
            
            drive_letter = usb_mount_point[0]  # Lấy ký tự ổ đĩa, ví dụ 'E' từ 'E:\\'
            root_path = f"{drive_letter}:\\"  # ví dụ "E:\\"
            
            # Lấy thông tin filesystem
            fs_name_buffer = ctypes.create_unicode_buffer(32)
            success = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root_path),
                None,
                0,
                None,
                None,
                None,
                fs_name_buffer,
                ctypes.sizeof(fs_name_buffer)
            )
            if not success:
                raise OSError(f"Không thể lấy thông tin volume. Mã lỗi: {ctypes.windll.kernel32.GetLastError()}")

            fs_type_detected = fs_name_buffer.value.upper()
            print(f"Filesystem detected: {fs_type_detected}")

            # Chọn nhãn gốc theo filesystem
            if "FAT" in fs_type_detected:  # FAT, FAT32, FAT16
                candidate_label = "TEKDT_BOOT"
                max_len = 11
            elif "EXFAT" in fs_type_detected:
                candidate_label = "TEKDT BMC BOOT"
                # exFAT/NTFS thường cho tới 32; nhưng có môi trường/công cụ hạn chế -> thử 32, nếu fail sẽ fallback ngắn hơn
                max_len = 32
            elif "NTFS" in fs_type_detected:
                candidate_label = "TekDT BMC BOOT DEVICE"
                max_len = 32
            else:
                candidate_label = "TekDT BMC BOOT"
                max_len = 32

            # Loại bỏ ký tự cấm (đặc biệt cần cho FAT)
            forbidden_chars = set('*?/\\|,;:+=<>[]"')  # danh sách ký tự không hợp lệ cho volume label
            cleaned = ''.join(ch for ch in candidate_label if ch not in forbidden_chars)
            # Trim khoảng trắng/dấu chấm đầu/cuối (an toàn cho volume label)
            cleaned = cleaned.strip(" .")
            if "FAT" in fs_type_detected:
                # FAT lưu nhãn ở uppercase; chuẩn hóa
                cleaned = cleaned.upper()

            # Áp giới hạn độ dài ban đầu
            if len(cleaned) > max_len:
                cleaned = cleaned[:max_len]

            # Thử gọi SetVolumeLabelW; nếu lỗi 154 (label too long) thì lặp rút ngắn dần và thử lại
            attempt_label = cleaned
            set_success = False
            last_error = None
            min_len = 3  # không rút ngắn quá ngắn
            attempts = 0
            while len(attempt_label) >= min_len and attempts < 32:
                # Gọi API
                res = ctypes.windll.kernel32.SetVolumeLabelW(ctypes.c_wchar_p(root_path), ctypes.c_wchar_p(attempt_label))
                if res:
                    set_success = True
                    print(f"Đã đổi tên ổ đĩa thành '{attempt_label}'.")
                    worker.status.emit(f"Đã đổi tên ổ đĩa thành '{attempt_label}'.")
                    break
                else:
                    err = ctypes.windll.kernel32.GetLastError()
                    last_error = err
                    print(f"SetVolumeLabelW thất bại với mã lỗi: {err} khi thử nhãn '{attempt_label}'")
                    # Nếu là label quá dài (154), rút ngắn tên và thử lại
                    if err == 154:  # ERROR_LABEL_TOO_LONG
                        # rút ngắn 1 ký tự và thử lại
                        attempt_label = attempt_label[:-1]
                        attempts += 1
                        continue
                    else:
                        # nếu lỗi khác (ví dụ quyền), thì không thử rút ngắn; thoát để báo lỗi cho người dùng
                        break

            if not set_success:
                raise OSError(f"Không thể đổi tên ổ đĩa. Mã lỗi cuối: {last_error}")
        except Exception as label_error:
            print(f"Cảnh báo: Không thể đổi tên ổ đĩa. Lỗi: {label_error}")
            worker.status.emit(f"Cảnh báo: Không thể đổi tên ổ đĩa. Lỗi: {label_error}")
            time.sleep(2)
        
        worker.status.emit("Đang xác thực lại dấu bản quyền...")
        try:
            _verify_usb_signature(main_app.config['device_details'], phy_drive_num)
        except Exception as verify_error:
            # Nếu xác thực cuối cùng thất bại, cũng báo lỗi nghiêm trọng.
            error_message = f"LỖI CUỐI CÙNG: Dấu bản quyền đã bị hỏng hoặc không tồn tại sau khi hoàn tất. Lý do: {verify_error}"
            print(error_message)
            raise Exception(error_message)

        worker.progress.emit(100)
        worker.status.emit("Hoàn tất! USB đã sẵn sàng.")

    except Exception as e:
        traceback.print_exc()
        raise e

def _get_drive_mount_point(main_app, device_path):
    """
    Lấy ký tự ổ đĩa (mount point) từ physical drive path.
    Giữ nguyên logic từ file gốc của bạn.
    """
    try:
        drive_number = int(device_path.replace("\\\\.\\PHYSICALDRIVE", ""))
    except (ValueError, TypeError): return None

    for _ in range(10):
        try:
            command = f"Get-Partition -DiskNumber {drive_number} | Where-Object {{($_.DriveLetter) -and ($_.Type -ne 'Recovery')}} | Select-Object -ExpandProperty DriveLetter"
            proc = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True, check=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            drive_letter = proc.stdout.strip()
            if drive_letter and len(drive_letter) == 1:
                return f"{drive_letter}:\\"
        except Exception:
            pass
        time.sleep(1)
    return None

def get_generic_key(edition_name):
    """
    Lấy key Windows generic từ file JSON.
    Giữ nguyên logic từ file gốc của bạn.
    """
    generic_key_path = config.BASE_DIR / "generic_keys.json"
    if not generic_key_path.exists():
        return None
    with open(generic_key_path, "r", encoding="utf-8") as f:
        keys = json.load(f)
    return keys.get(edition_name)

def _get_disk_id_with_diskpart(phy_drive_num):
    """
    Sử dụng diskpart để lấy Disk ID (cho MBR) hoặc Disk GUID (cho GPT).
    """
    script_content = f"select disk {phy_drive_num}\ndetail disk\nexit"
    
    # Chạy diskpart và lấy output
    proc = subprocess.run(
        'diskpart',
        input=script_content,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    
    if proc.returncode != 0:
        raise IOError(f"Diskpart thất bại khi lấy chi tiết ổ đĩa {phy_drive_num}.")

    output = proc.stdout
    # Thử tìm Disk GUID trước (cho GPT)
    guid_match = re.search(r"Disk ID\s*:\s*\{([A-F0-9-]+)\}", output, re.IGNORECASE)
    if guid_match:
        disk_id = guid_match.group(1)
        print(f"Tìm thấy Disk GUID (GPT): {disk_id}")
        return disk_id

    # Nếu không, tìm Disk ID (cho MBR)
    id_match = re.search(r"Disk ID\s*:\s*([A-F0-9]+)", output, re.IGNORECASE)
    if id_match:
        disk_id = id_match.group(1)
        print(f"Tìm thấy Disk ID (MBR): {disk_id}")
        return disk_id

    raise ValueError(f"Không thể tìm thấy Disk ID hoặc GUID cho ổ đĩa {phy_drive_num}.")

def _get_reserved_partition_offset(phy_drive_num):
    """
    Sử dụng PowerShell để lấy offset (vị trí bắt đầu) của phân vùng 16MB
    được Ventoy chừa lại.
    Hàm này hoạt động trên cả MBR và GPT bằng cách tìm phân vùng cuối cùng
    có kích thước trong khoảng 15-17MiB và không có ký tự ổ đĩa.
    """
    try:
        # Kích thước phân vùng có thể không chính xác là 16MiB do căn chỉnh sector.
        # Vì vậy, chúng ta tìm kiếm trong một phạm vi hợp lý (ví dụ: 15MB đến 17MB).
        LOWER_BOUND_BYTES = 15 * 1024 * 1024
        UPPER_BOUND_BYTES = 17 * 1024 * 1024

        # Lệnh PowerShell để:
        # 1. Lấy tất cả phân vùng của đĩa.
        # 2. Sắp xếp chúng theo vị trí bắt đầu (offset) giảm dần, để phân vùng cuối cùng lên đầu.
        # 3. Chọn phân vùng đầu tiên trong danh sách (tức là phân vùng cuối cùng trên đĩa).
        # 4. Kiểm tra xem nó có kích thước trong khoảng 15-17MiB và không có ký tự ổ đĩa không.
        # 5. Nếu đúng, trả về giá trị Offset của nó.
        cmd = (
            f"Get-Partition -DiskNumber {phy_drive_num} | "
            f"Sort-Object -Property Offset -Descending | "
            f"Select-Object -First 1 | "
            f"Where-Object {{ ($_.Size -ge {LOWER_BOUND_BYTES}) -and ($_.Size -le {UPPER_BOUND_BYTES}) -and !$_.DriveLetter }} | "
            f"Select-Object -ExpandProperty Offset"
        )
        proc = subprocess.run(
            ['powershell', '-NoProfile', '-Command', cmd],
            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        offset_str = proc.stdout.strip()
        
        if not offset_str:
            raise IOError("Không tìm thấy phân vùng 16MB dành riêng. Hãy đảm bảo bạn đã dùng tham số /R:16 khi tạo Ventoy và quá trình tạo phân vùng ẩn đã thành công.")
        
        print(f"Tìm thấy phân vùng 16MB dành riêng tại offset: {offset_str}")
        return int(offset_str)
        
    except subprocess.CalledProcessError as e:
        raise IOError(f"Lỗi khi tìm kiếm phân vùng 16MB dành riêng: {e.stderr}")
    except ValueError:
        raise IOError(f"Không thể chuyển đổi offset thành số nguyên: '{proc.stdout.strip()}'")
    except Exception as e:
        raise IOError(f"Một lỗi không xác định đã xảy ra khi lấy thông tin phân vùng: {e}")

def _write_usb_signature(device_details, phy_drive_num, partition_scheme):
    """
    Tạo một phân vùng ẩn 16MB, sau đó ghi chữ ký vào đó.
    Đây là phương pháp an toàn và bền vững nhất.
    """
    # Bước 1: Tạo và ẩn phân vùng bằng diskpart
    _create_and_hide_signature_partition(phy_drive_num, partition_scheme)
    
    # Đợi một chút để hệ điều hành nhận diện phân vùng mới
    time.sleep(3)

    # Bước 2: Lấy offset của phân vùng vừa tạo
    target_offset = _get_reserved_partition_offset(phy_drive_num)

    # Bước 3: Ghi dữ liệu vào offset đó
    disk_identifier = _get_disk_id_with_diskpart(phy_drive_num)
    string_to_hash = disk_identifier + secret_key.SECRET_KEY
    hashed_signature = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
    padded_data = hashed_signature.encode('ascii').ljust(512, b'\0')
    drive_path = f"\\\\.\\PHYSICALDRIVE{phy_drive_num}"
    
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2
    OPEN_EXISTING = 3
    handle = -1
    try:
        handle = ctypes.windll.kernel32.CreateFileW(
            drive_path, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
        if handle == -1: raise PermissionError(f"Không thể mở ổ đĩa {drive_path}. Mã lỗi: {ctypes.windll.kernel32.GetLastError()}")
        
        low_part = ctypes.c_ulong(target_offset & 0xFFFFFFFF)
        high_part = ctypes.c_long(target_offset >> 32)
        ctypes.windll.kernel32.SetFilePointer(handle, low_part, ctypes.byref(high_part), 0)
        
        bytes_written = ctypes.c_ulong(0)
        success = ctypes.windll.kernel32.WriteFile(handle, padded_data, len(padded_data), ctypes.byref(bytes_written), None)
        if not success or bytes_written.value != len(padded_data): raise IOError(f"Lỗi WriteFile. Mã lỗi: {ctypes.windll.kernel32.GetLastError()}")
        
        ctypes.windll.kernel32.FlushFileBuffers(handle)
        print(f"Đã ghi thành công chữ ký vào phân vùng ẩn tại offset {target_offset}.")
    finally:
        if handle != -1: ctypes.windll.kernel32.CloseHandle(handle)

def _verify_usb_signature(device_details, phy_drive_num):
    """
    Xác thực chữ ký bằng cách tìm offset của phân vùng ẩn và đọc dữ liệu.
    """
    print("Bắt đầu quá trình xác thực lại chữ ký...")
    
    # Bước 1: Lấy offset của phân vùng ẩn
    target_offset = _get_reserved_partition_offset(phy_drive_num)

    # Bước 2: Đọc và so sánh
    disk_identifier = _get_disk_id_with_diskpart(phy_drive_num)
    string_to_hash = disk_identifier + secret_key.SECRET_KEY
    expected_signature = hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
    drive_path = f"\\\\.\\PHYSICALDRIVE{phy_drive_num}"

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2
    OPEN_EXISTING = 3
    handle = -1
    try:
        handle = ctypes.windll.kernel32.CreateFileW(
            drive_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
        if handle == -1: raise PermissionError(f"Không thể mở ổ đĩa {drive_path}. Mã lỗi: {ctypes.windll.kernel32.GetLastError()}")

        low_part = ctypes.c_ulong(target_offset & 0xFFFFFFFF)
        high_part = ctypes.c_long(target_offset >> 32)
        ctypes.windll.kernel32.SetFilePointer(handle, low_part, ctypes.byref(high_part), 0)

        buffer = ctypes.create_string_buffer(512)
        bytes_read = ctypes.c_ulong(0)
        ctypes.windll.kernel32.ReadFile(handle, buffer, 512, ctypes.byref(bytes_read), None)

        read_signature = buffer.value[:len(expected_signature)].decode('ascii')
        if read_signature != expected_signature:
            raise ValueError("Xác thực chữ ký thất bại! Chữ ký không khớp.")
        
        print("Xác thực chữ ký thành công.")
        return True
    finally:
        if handle != -1: ctypes.windll.kernel32.CloseHandle(handle)

def _create_and_hide_signature_partition(phy_drive_num, partition_scheme):
    """
    Sử dụng diskpart để tạo một phân vùng trong không gian trống 16MB
    và thiết lập ID của nó để Windows bỏ qua, không mount.
    """
    print(f"Bắt đầu tạo và ẩn phân vùng chữ ký trên Disk {phy_drive_num} với scheme {partition_scheme}...")
    
    script_content = f"select disk {phy_drive_num}\n"
    # Lệnh 'create partition primary' sẽ tự động sử dụng không gian unallocated có sẵn.
    # Vì Ventoy với /R:16 để lại đúng 1 khoảng trống ở cuối, lệnh này sẽ tạo đúng phân vùng 16MB.
    script_content += "create partition primary\n"

    if partition_scheme.upper() == "GPT":
        # GUID '0FC63DAF-8483-4772-8E79-3D69D8477DE4' là của 'Linux filesystem data'.
        # Windows sẽ nhận dạng đây là phân vùng hợp lệ nhưng không tự động mount hay định dạng nó.
        # Đây là một cách an toàn để "ẩn" phân vùng.
        script_content += 'set id="0FC63DAF-8483-4772-8E79-3D69D8477DE4"\n'
        print("Đang thiết lập GPT Type ID thành 'Linux filesystem data'.")
    else: # MBR
        # ID '27' tương ứng với 'Hidden NTFS WinRE'.
        # Lệnh 'override' là bắt buộc để diskpart cho phép thay đổi ID thành loại không chuẩn.
        script_content += "set id=27 override\n"
        print("Đang thiết lập MBR System ID thành '0x27' (Hidden).")
    
    script_content += "rescan\n"
    script_content += "exit\n"

    try:
        proc = subprocess.run(
            'diskpart',
            input=script_content,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        print("Diskpart thực thi thành công:\n" + proc.stdout)
    except subprocess.CalledProcessError as e:
        error_message = f"Diskpart thất bại khi tạo phân vùng chữ ký. Lỗi:\n{e.stdout}\n{e.stderr}"
        raise IOError(error_message)

def parse_torrent_files(torrent_path):
    """Parse output của `aria2c --show-files` dòng-thứ-dòng, trả về list dict {idx,name,size}."""
    aria2_path = tool_manager.get_tool_path("aria2c")
    if not aria2_path or not os.path.exists(torrent_path):
        return []

    try:
        result = subprocess.run(
            [aria2_path, "--show-files", str(torrent_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        lines = result.stdout.splitlines()
        files_list = []

        # Duyệt từng dòng, tìm dòng "idx|path" rồi lấy size từ dòng kế tiếp nếu có
        for i, ln in enumerate(lines):
            m = re.match(r'^\s*(\d+)\|\s*(.+)$', ln)
            if not m:
                continue
            idx = m.group(1).strip()
            full_path = m.group(2).strip()
            filename = os.path.basename(full_path)

            # Lấy dung lượng từ dòng kế tiếp (nếu có)
            size = "?"
            if i + 1 < len(lines):
                sm = re.search(r'\|\s*([\d\.,]+\s*[KMG]?i?B)', lines[i+1])
                if sm:
                    size = sm.group(1).strip()

            # Lọc theo tiền tố DriverPack/DP_
            if filename.startswith(("DP_", "DriverPack_")):
                files_list.append({
                    "idx": idx,
                    "name": filename,
                    "size": size
                })

        files_list.sort(key=lambda x: x['name'])
        print(f"Hệ thống tìm thấy: {len(files_list)} gói Driver phù hợp.")
        return files_list

    except Exception as e:
        print(f"Lỗi phân tích torrent: {e}")
        return []


def extract_db_from_driverpack(archive_path, dest_db_file):
    """Giải nén duy nhất file db.sqlite từ DriverPack_*.7z"""
    seven_zip_path = tool_manager.get_tool_path("7z")
    dest_dir = os.path.dirname(dest_db_file)
    os.makedirs(dest_dir, exist_ok=True)
    try:
        # e: extract, -o: output, -y: overwrite, db.sqlite: file cần lấy, -r: tìm đệ quy
        cmd = [seven_zip_path, "e", str(archive_path), f"-o{dest_dir}", "db.sqlite", "-r", "-y"]
        subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return os.path.exists(dest_db_file)
    except:
        return False

def process_downloaded_drivers(temp_dir, selected_names=None):
    FINAL_DRIVER_DIR = os.path.join(config.BASE_DIR, "Drivers", "Drivers")
    DB_DIR = os.path.join(config.BASE_DIR, "Drivers", "DB")
    os.makedirs(FINAL_DRIVER_DIR, exist_ok=True)
    os.makedirs(DB_DIR, exist_ok=True)

    moved = []

    for root, _, files in os.walk(temp_dir):
        for fname in files:
            src = os.path.join(root, fname)

            # ===== CASE 1: FILE DB ĐẶC BIỆT =====
            if fname.startswith("DriverPack_") and fname.endswith(".7z"):
                # Giải nén db.sqlite
                try:
                    subprocess.run([
                        tool_manager.get_tool_path("7z"),
                        "e",
                        src,
                        "index/db.sqlite",
                        f"-o{DB_DIR}",
                        "-y"
                    ], creationflags=subprocess.CREATE_NO_WINDOW)

                    print(f"[DB] extracted db.sqlite from {fname}")
                except Exception as e:
                    print(f"[DB] extract failed: {e}")
                continue

            # ===== CASE 2: DRIVER THƯỜNG =====
            if selected_names and fname not in selected_names:
                continue

            if fname.startswith("DP_") and fname.endswith(".7z"):
                dst = os.path.join(FINAL_DRIVER_DIR, fname)
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
                moved.append(fname)

    print(f"[process_downloaded_drivers] moved: {moved}")

    # ✅ XÓA TEMP
    shutil.rmtree(temp_dir, ignore_errors=True)
    return moved

def get_aria2_download_cmd(torrent_path, download_dir, select_indices):
    """Tạo lệnh aria2c và sửa lỗi treo 99%"""
    aria2_path = tool_manager.get_tool_path("aria2c")
    return [
        aria2_path,
        f"--dir={download_dir}",
        f"--select-file={select_indices}",
        "--seed-time=0",
        "--bt-stop-timeout=60",        # Thoát nếu sau 60s không có data mới
        "--file-allocation=none",
        "--allow-overwrite=true",
        "--bt-seed-unverified=true",
        "--bt-save-metadata=false",
        str(torrent_path)
    ]

def validate_drivers_with_db(db_path, drivers_dir):
    """Kiểm tra các file DP_ hiện có trong Drivers/Drivers có khớp với bảng Drivers trong db.sqlite không."""
    if not os.path.exists(db_path):
        return False, "Thiếu file cơ sở dữ liệu db.sqlite."
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Lấy danh sách file .7z hiện có (bỏ đuôi .7z để so sánh với trường 'pack')
        local_files = [f for f in os.listdir(drivers_dir) if f.startswith("DP_") and f.endswith(".7z")]
        
        for f in local_files:
            pack_name = f[:-3] # Xóa .7z
            cursor.execute("SELECT 1 FROM Drivers WHERE pack = ?", (pack_name,))
            if not cursor.fetchone():
                conn.close()
                return False, f"Gói driver '{f}' không hợp lệ hoặc không có trong cơ sở dữ liệu."
        
        conn.close()
        return True, ""
    except Exception as e:
        return False, f"Lỗi truy vấn DB: {e}"

def is_internet_available():
    """Kiểm tra kết nối internet nhanh."""
    try:
        requests.get("https://8.8.8.8", timeout=3)
        return True
    except:
        return False