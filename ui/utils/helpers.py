import json
import os
import shutil
import time
import subprocess
import ctypes
import zipfile
from ctypes import wintypes
from pathlib import Path
import config

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
        worker.status.emit(f"Đang sao chép: {filename}...")

        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            # Sử dụng buffer lớn hơn để tăng tốc độ I/O
            buffer_size = 1024 * 1024 * 4 # 4MB buffer
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
    Gộp các file Drivers.7z.001 và .002 thành một file Drivers.7z duy nhất
    và sao chép trực tiếp vào thư mục ventoy trên USB.
    """
    main_app.creation_worker.status.emit("Đang xử lý kho driver...")
    
    # Đường dẫn tới các file driver nguồn và thư mục đích trên USB
    drivers_part1 = config.DRIVERS_DIR / "Drivers.7z.001"
    drivers_part2 = config.DRIVERS_DIR / "Drivers.7z.002"
    usb_ventoy_dir = os.path.join(usb_mount_point, "ventoy")
    final_archive_path = os.path.join(usb_ventoy_dir, "Drivers.7z")
    
    if not config.DRIVERS_DIR.exists():
        main_app.creation_worker.status.emit("Thư mục Drivers không tồn tại. Bỏ qua.")
        print("Thư mục Drivers không tồn tại cạnh ứng dụng.")
        return 0

    # Kiểm tra sự tồn tại của cả hai file .001, .002 và .003
    if not (os.path.exists(drivers_part1) and os.path.exists(drivers_part2)):
        main_app.creation_worker.status.emit("Không tìm thấy Drivers.7z.001/.002. Bỏ qua.")
        print("Không tìm thấy file driver phân mảnh, bỏ qua bước này.")
        return

    try:
        # Đảm bảo thư mục /ventoy/ trên USB đã tồn tại
        os.makedirs(usb_ventoy_dir, exist_ok=True)
        
        main_app.creation_worker.status.emit("Đang gộp và sao chép Drivers.7z vào USB...")
        print(f"Bắt đầu gộp file vào: {final_archive_path}")

        # Mở file đích để ghi (chế độ 'wb')
        with open(final_archive_path, "wb") as outfile:
            # Đọc và ghi nội dung từ file .001
            with open(drivers_part1, "rb") as infile:
                shutil.copyfileobj(infile, outfile)
            # Đọc và ghi nội dung từ file .002
            with open(drivers_part2, "rb") as infile:
                shutil.copyfileobj(infile, outfile)
        
        main_app.creation_worker.status.emit("Đã sao chép Drivers.7z vào USB thành công.")
        print("Gộp và sao chép Drivers.7z hoàn tất.")

    except Exception as e:
        error_message = f"Lỗi khi gộp và sao chép Drivers.7z: {e}"
        main_app.creation_worker.status.emit(error_message)
        print(error_message)
        # Nếu có lỗi, nên đưa ra ngoại lệ để dừng quá trình
        raise Exception(error_message)

def _generate_ventoy_json(main_app):
    """Tạo nội dung file JSON cấu hình cho Ventoy."""
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
        "injection": [], # Khởi tạo danh sách injection rỗng
        "menu_alias": []   # Khởi tạo danh sách menu_alias rỗng
    }

    # Duyệt qua danh sách ISO một lần để tạo tất cả cấu hình cần thiết
    for iso_info in main_app.config['iso_list']:
        iso_filename_with_path = f"/{iso_info['filename']}"

        # 1. Thêm cấu hình auto_install (nếu có)
        if iso_info.get("unattend_file"):
            config_data["auto_install"].append({
                "image": iso_filename_with_path,
                "template": f"/ventoy/{iso_info['unattend_file']}",
                "autosel": 1
            })

        # 2. Thêm cấu hình menu_alias (nếu có)
        if iso_info.get("alias"):
            config_data["menu_alias"].append({
                "image": iso_filename_with_path,
                "alias": iso_info["alias"]
            })
        
    # Thêm cấu hình injection cho tất cả ISO
    config_data["injection"].append({
        "parent": "/",
        "archive": "/ventoy/Drivers.7z"
    })

    # Xóa các khóa rỗng nếu không có cấu hình nào được thêm
    if not config_data["auto_install"]:
        del config_data["auto_install"]
    if not config_data["injection"]:
        del config_data["injection"]
    if not config_data["menu_alias"]:
        del config_data["menu_alias"]
    
    # Cấu hình theme (giữ nguyên)
    if main_app.config["theme"]:
        theme_name = os.path.splitext(main_app.config["theme"])[0]
        config_data["theme"] = {
            "file": f"/ventoy/themes/{theme_name}/theme.txt",
            "gfxmode": "1920x1080"
        }

    return json.dumps(config_data, indent=4)

def _generate_unattend_xml(main_app, index, product_key=None, architecture="amd64"):
    """Tạo file unattend.xml với một product key đã được cung cấp."""
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
            <UILanguage>en-US</UILanguage>
        </SetupUILanguage>
        <UILanguageFallback>en-US</UILanguageFallback>
        <InputLocale>en-US</InputLocale>
        <SystemLocale>en-US</SystemLocale>
        <UILanguage>en-US</UILanguage>
        <UserLocale>en-US</UserLocale>
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
</settings>

<settings pass="specialize">    
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <ComputerName>*</ComputerName>
        <TimeZone>SE Asia Standard Time</TimeZone>
    </component>
</settings>

<settings pass="oobeSystem">
    <component name="Microsoft-Windows-International-Core" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <InputLocale>en-US</InputLocale>
        <SystemLocale>en-US</SystemLocale>
        <UILanguage>en-US</UILanguage>
        <UserLocale>en-US</UserLocale>
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

def _copy_tekdtais_selectively(main_app, source_dir, dest_dir):
    """
    Sao chép thư mục TekDT AIS có chọn lọc và cập nhật tiến trình.
    Chỉ những ứng dụng trong thư mục 'Apps' có 'auto_install' = True trong
    app_config.json mới được sao chép.
    
    Args:
        source_dir (Path): Đường dẫn thư mục nguồn (ví dụ: config.TEKDTAIS_DIR).
        dest_dir (str): Đường dẫn thư mục đích trên USB.
    """
    main_app.creation_worker.status.emit("Đang sao chép TekDT AIS (chọn lọc)...")
    
    config_path = source_dir / "app_config.json"
    source_apps_dir = source_dir / "Apps"
    
    apps_to_copy = []
    if not config_path.exists():
        print(f"Cảnh báo: Không tìm thấy {config_path}. Sẽ sao chép toàn bộ TekDT AIS.")
        if os.path.exists(dest_dir): shutil.rmtree(dest_dir)
        shutil.copytree(source_dir, dest_dir)
        return copied_so_far + main_app._get_dir_size(source_dir)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            app_config = json.load(f)
        
        apps_to_copy = [name for name, settings in app_config.items() if settings.get("auto_install")]
        
        print(f"Các ứng dụng TekDT AIS sẽ được sao chép: {apps_to_copy}")

    except (json.JSONDecodeError, IOError) as e:
        print(f"Lỗi đọc app_config.json: {e}. Sẽ sao chép toàn bộ TekDT AIS.")
        if os.path.exists(dest_dir): shutil.rmtree(dest_dir)
        shutil.copytree(source_dir, dest_dir)
        return copied_so_far + main_app._get_dir_size(source_dir)

    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    # Sao chép có chọn lọc và theo dõi tiến trình
    for dirpath, dirnames, filenames in os.walk(source_dir):
        # Xác định thư mục đích tương ứng
        relative_path = os.path.relpath(dirpath, source_dir)
        dest_path = os.path.join(dest_dir, relative_path)
        
        # Lọc thư mục con trong 'Apps'
        if Path(dirpath).resolve() == source_apps_dir.resolve():
            dirnames[:] = [d for d in dirnames if d in apps_to_copy]

        # Tạo các thư mục con cần thiết
        os.makedirs(dest_path, exist_ok=True)
        
        for file in filenames:
            src_file = os.path.join(dirpath, file)
            dst_file = os.path.join(dest_path, file)
            copied_so_far = _copy_with_progress(main_app.creation_worker, src_file, dst_file, total_copy_size, copied_so_far, base_progress, progress_range)
    
    print("Đã sao chép TekDT AIS (chọn lọc) vào USB.")
    return copied_so_far

def _create_fill_file(self, file_path, size_in_bytes, total_fill_target, space_filled_so_far):
    """
    Tạo một tệp có kích thước cụ thể bằng cách ghi các khối zero.
    Cung cấp các cập nhật tiến trình chi tiết cho giao diện người dùng.
    """
    worker = main_app.creation_worker
    worker.status.emit(f"Đang tạo file lấp đầy: {os.path.basename(file_path)}")

    # Định nghĩa các hằng số
    CHUNK_SIZE = 16 * 1024 * 1024  # Ghi mỗi lần 16 MB để tối ưu hiệu suất
    zeros = b'\x00' * CHUNK_SIZE
    FILE_ATTRIBUTE_HIDDEN = 0x02
    FILE_ATTRIBUTE_SYSTEM = 0x04

    bytes_written = 0
    try:
        with open(file_path, "wb") as f:
            while bytes_written < size_in_bytes:
                # Xác định kích thước khối cho lần ghi này
                write_size = min(CHUNK_SIZE, size_in_bytes - bytes_written)
                
                # Ghi khối dữ liệu
                f.write(zeros if write_size == CHUNK_SIZE else b'\x00' * write_size)
                
                bytes_written += write_size
                
                # Cập nhật tiến trình tổng thể
                current_total_filled = space_filled_so_far + bytes_written
                # Chỉ cập nhật UI nếu có dung lượng cần lấp đầy
                if total_fill_target > 0:
                    # Giai đoạn lấp đầy từ 80% -> 100%
                    fill_percentage = current_total_filled / total_fill_target
                    current_progress = int(80 + (fill_percentage * 20)) # 20 là phạm vi của giai đoạn này
                    worker.progress.emit(current_progress)
                    worker.status.emit(
                        f"Đang lấp đầy: {current_total_filled / (1024**3):.2f} / {total_fill_target / (1024**3):.2f} GB"
                    )
        
        # Đặt thuộc tính file thành Ẩn + Hệ thống sau khi tạo xong
        ctypes.windll.kernel32.SetFileAttributesW(file_path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
        return bytes_written  # Trả về số byte đã thực sự được ghi

    except Exception as e:
        # Dọn dẹp nếu có sự cố
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        # Báo lỗi với ngữ cảnh rõ ràng hơn
        raise IOError(f"Không thể ghi vào file '{file_path}'. Lỗi: {e}")

def create_usb_task(self):
    """Tác vụ tạo USB Boot chạy trong luồng nền."""
    worker = main_app.creation_worker
    try:
        # --- Bước 1: Tạo file cấu hình ventoy.json ---
        self.creation_worker.status.emit("Đang tạo file cấu hình ventoy.json...")
        self.creation_worker.progress.emit(20)
        ventoy_config = self._generate_ventoy_json()

        # --- Bước 2: Chạy Ventoy2Disk.exe ---
        self.creation_worker.status.emit(f"Bắt đầu tạo USB trên {self.config['device']}...")
        self.creation_worker.progress.emit(50)
        
        ventoy_exe = os.path.join(config.VENTOY_DIR, "Ventoy2Disk.exe")
        if not os.path.exists(ventoy_exe):
            raise FileNotFoundError("Không tìm thấy Ventoy2Disk.exe. Vui lòng kiểm tra lại thư mục Tools.")

        # Lấy số ổ vật lý từ device path
        device_path = self.config["device"]  # Ví dụ: \\.\PHYSICALDRIVE2
        phy_drive_num = device_path.replace("\\\\.\\PHYSICALDRIVE", "")

        cmd = [
            ventoy_exe,
            "VTOYCLI",
            "/I",  # Hoặc "/U" nếu update
            f"/PhyDrive:{phy_drive_num}",
        ]

        if self.config["partition_scheme"] == "GPT":
            cmd.append("/GPT")
        
        # Thêm định dạng hệ thống file
        cmd.append(f"/FS:{self.config['filesystem'].upper()}")  # EXFAT/NTFS/FAT32

        # Chạy và theo dõi output
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip()) # In ra console để debug
                # Có thể phân tích output ở đây để cập nhật tiến trình chi tiết hơn
        
        if process.returncode != 0:
            raise Exception(f"Ventoy2Disk.exe thất bại với mã lỗi {process.returncode}")

        self.creation_worker.progress.emit(70)

        # --- Bước 3: Chép file cấu hình và ISO vào USB ---
        self.creation_worker.status.emit("Đang chép file vào USB...")
        
        # Chờ USB được mount lại
        time.sleep(5)
        usb_mount_point = self._get_drive_mount_point(self.config["device"])
        if not usb_mount_point:
            raise Exception("Không thể tìm thấy điểm mount của USB sau khi tạo.")

        # Tạo thư mục ventoy trên USB
        usb_ventoy_dir = os.path.join(usb_mount_point, "ventoy")
        os.makedirs(usb_ventoy_dir, exist_ok=True)
        
        # Tạo các file unattend.xml riêng cho mỗi ISO cần
        for i, iso_info in enumerate(self.config['iso_list']):
            if iso_info.get("windows_edition_index"):
                self.creation_worker.status.emit(f"Đang tạo unattend cho {iso_info['filename']}...")
                product_key = iso_info.get("product_key")
                architecture = iso_info.get("architecture", "amd64")
                unattend_content = self._generate_unattend_xml(iso_info["windows_edition_index"], product_key, architecture)
                unattend_filename = f"unattend_{i}_{os.path.basename(iso_info['filename'])}.xml"
                iso_info['unattend_file'] = unattend_filename
                with open(os.path.join(usb_ventoy_dir, unattend_filename), "w", encoding='utf-8') as f:
                    f.write(unattend_content)

        # 1. Tạo cấu hình cơ bản từ ứng dụng
        # Dùng json.loads để có một dictionary, không phải string
        base_config = json.loads(self._generate_ventoy_json())

        # 2. Xử lý theme và gộp cấu hình
        if self.config["theme"]:
            self.creation_worker.status.emit("Đang cài đặt theme và gộp cấu hình...")
            theme_zip_path = os.path.join(config.THEMES_DIR, self.config["theme"])
            
            with zipfile.ZipFile(theme_zip_path, 'r') as theme_zip:
                # Đọc ventoy.json từ trong file zip nếu có
                # Một số theme có thể đặt file này ở 'ventoy/ventoy.json' hoặc 'ventoy.json'
                theme_json_content = None
                for json_path_in_zip in ['ventoy/ventoy.json', 'ventoy.json']:
                    if json_path_in_zip in theme_zip.namelist():
                        try:
                            with theme_zip.open(json_path_in_zip) as json_file:
                                theme_json_content = json.load(json_file)
                            break # Tìm thấy thì thoát vòng lặp
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            print(f"Lỗi khi đọc {json_path_in_zip} từ theme: {e}")

                # Giải nén toàn bộ theme vào thư mục /ventoy/themes/
                members_to_extract = [member for member in theme_zip.infolist() if 'ventoy.json' not in member.filename]
                theme_zip.extractall(usb_mount_point, members=members_to_extract)

                # Gộp cấu hình: Ưu tiên khối "theme" từ file zip
                if theme_json_content and 'theme' in theme_json_content:
                    base_config['theme'] = theme_json_content['theme']
                    print("Đã gộp cấu hình 'theme' từ file zip.")
        
        # 3. Ghi file ventoy.json cuối cùng ra USB
        ventoy_json_path = os.path.join(usb_ventoy_dir, "ventoy.json")
        self.creation_worker.status.emit("Đang ghi file cấu hình ventoy.json...")
        with open(ventoy_json_path, "w", encoding='utf-8') as f:
            # Dùng json.dump để ghi dictionary ra file, indent=4 để dễ đọc
            json.dump(base_config, f, indent=4, ensure_ascii=False)

        self.creation_worker.progress.emit(85)
        self.creation_worker.status.emit("Đang sao chép file ISO...")

        # Chép tất cả các file ISO
        total_isos = len(self.config['iso_list'])
        for i, iso_info in enumerate(self.config['iso_list']):
            progress_start = 70
            progress_per_iso = 30 / total_isos
            self.creation_worker.status.emit(f"({i+1}/{total_isos}) Đang sao chép {iso_info['filename']}...")
            
            shutil.copy(iso_info["path"], usb_mount_point)
            self.creation_worker.progress.emit(int(progress_start + (i + 1) * progress_per_iso))
        
        self.creation_worker.status.emit("Đang sao chép TekDT AIS vào USB...")
        dest_ais_dir = os.path.join(usb_mount_point, "TekDT_AIS")
        if os.path.exists(config.TEKDTAIS_DIR):
            # Kiểm tra cấu hình để quyết định cách sao chép
            if self.config.get("copy_ais_selection_only", True):
                # Gọi hàm sao chép có chọn lọc
                self._copy_tekdtais_selectively(config.TEKDTAIS_DIR, dest_ais_dir)
            else:
                # Sao chép toàn bộ như cũ
                self.creation_worker.status.emit("Đang sao chép toàn bộ TekDT AIS vào USB...")
                if os.path.exists(dest_ais_dir):
                    shutil.rmtree(dest_ais_dir)
                shutil.copytree(config.TEKDTAIS_DIR, dest_ais_dir)
                print("Đã sao chép toàn bộ TekDT_AIS vào USB.")

        self._process_driver_archive(usb_mount_point)

        if self.config.get("fill_space", True):
            self.creation_worker.status.emit("Đang tính toán dung lượng trống...")
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
                    fs_type = self.config["filesystem"].upper()
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
                            
                            written = self._create_fill_file(file_path, file_size, fill_space_target, space_filled_so_far)
                            space_filled_so_far += written
                            space_to_fill -= written
                            if written < file_size:
                                print("Cảnh báo: Không thể ghi thêm dữ liệu. Đĩa có thể đã đầy.")
                                break
                            file_index += 1
                    else:
                        if space_to_fill > 0:
                            final_fill_path = os.path.join(fill_file_dir, "fill_final.dat")
                            self._create_fill_file(final_fill_path, space_to_fill, fill_space_target, space_filled_so_far)
                    
                    self.creation_worker.status.emit("Đã lấp đầy dung lượng trống.")
                    print("Hoàn tất việc lấp đầy dung lượng trống.")

            except Exception as fill_error:
                print(f"Lỗi trong quá trình lấp đầy dung lượng: {fill_error}")
                self.creation_worker.status.emit(f"Cảnh báo: Không thể lấp đầy dung lượng trống. Lỗi: {fill_error}")
        
        self.creation_worker.progress.emit(100)
        self.creation_worker.status.emit("Hoàn tất! USB đã sẵn sàng.")

    except Exception as e:
        raise e

def _get_drive_mount_point(self, device_path):
    """Lấy ký tự ổ đĩa (mount point) từ physical drive path bằng PowerShell."""
    try:
        drive_number_str = device_path.replace("\\\\.\\PHYSICALDRIVE", "")
        drive_number = int(drive_number_str)
    except (ValueError, TypeError):
        print(f"Định dạng device_path không hợp lệ: {device_path}")
        return None

    # Thử lại vài lần vì Windows có thể cần vài giây để gán ký tự ổ đĩa
    for i in range(10):  # Thử trong 10 giây
        try:
            # Lệnh PowerShell để lấy ký tự ổ đĩa từ số thứ tự của ổ cứng
            command = f"Get-Partition -DiskNumber {drive_number} | Where-Object {{($_.DriveLetter) -and ($_.Type -ne 'Recovery')}} | Select-Object -ExpandProperty DriveLetter"
            
            proc = subprocess.run(
                ['powershell', '-NoProfile', '-Command', command],
                capture_output=True, text=True, check=True,
                encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            drive_letter = proc.stdout.strip()
            
            if drive_letter and len(drive_letter) == 1:
                mount_point = f"{drive_letter}:\\"
                print(f"Đã tìm thấy mount point cho Disk {drive_number}: {mount_point}")
                return mount_point
                
        except subprocess.CalledProcessError as e:
            # Lỗi này có thể xảy ra nếu lệnh không trả về gì, cứ thử lại
            print(f"Lỗi khi chạy PowerShell (lần thử {i+1}): {e.stderr}")
        except Exception as e:
            print(f"Ngoại lệ khi tìm mount point (lần thử {i+1}): {e}")

        time.sleep(1) # Chờ 1 giây trước khi thử lại

    print(f"Không thể tìm thấy mount point cho {device_path} sau nhiều lần thử.")
    return None

def get_generic_key(edition_name):
    generic_key_path = os.path.join(config.BASE_DIR, "generic_keys.json")
    if not os.path.exists(generic_key_path):
        return None
    with open(generic_key_path, "r", encoding="utf-8") as f:
        keys = json.load(f)
    return keys.get(edition_name)