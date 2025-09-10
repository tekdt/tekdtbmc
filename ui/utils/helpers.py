import json, os, shutil, time, subprocess, ctypes, zipfile, config
from ctypes import wintypes
from pathlib import Path

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
    Gộp các file Drivers.7z.001 và .002, sao chép vào thư mục ventoy trên USB.
    Hàm này được giữ nguyên logic từ file gốc của bạn.
    """
    main_app.creation_worker.status.emit("Đang xử lý kho driver...")
    
    drivers_part1 = config.DRIVERS_DIR / "Drivers.7z.001"
    drivers_part2 = config.DRIVERS_DIR / "Drivers.7z.002"
    usb_ventoy_dir = os.path.join(usb_mount_point, "ventoy")
    final_archive_path = os.path.join(usb_ventoy_dir, "Drivers.7z")
    
    if not config.DRIVERS_DIR.exists():
        main_app.creation_worker.status.emit("Thư mục Drivers không tồn tại. Bỏ qua.")
        print("Thư mục Drivers không tồn tại cạnh ứng dụng.")
        return

    if not (os.path.exists(drivers_part1) and os.path.exists(drivers_part2)):
        main_app.creation_worker.status.emit("Không tìm thấy Drivers.7z.001/.002. Bỏ qua.")
        print("Không tìm thấy file driver phân mảnh, bỏ qua bước này.")
        return

    try:
        os.makedirs(usb_ventoy_dir, exist_ok=True)
        main_app.creation_worker.status.emit("Đang gộp và sao chép Drivers.7z vào USB...")
        print(f"Bắt đầu gộp file vào: {final_archive_path}")

        with open(final_archive_path, "wb") as outfile:
            with open(drivers_part1, "rb") as infile:
                shutil.copyfileobj(infile, outfile)
            with open(drivers_part2, "rb") as infile:
                shutil.copyfileobj(infile, outfile)
        
        main_app.creation_worker.status.emit("Đã sao chép Drivers.7z vào USB thành công.")
        print("Gộp và sao chép Drivers.7z hoàn tất.")
    except Exception as e:
        error_message = f"Lỗi khi gộp và sao chép Drivers.7z: {e}"
        main_app.creation_worker.status.emit(error_message)
        print(error_message)
        raise Exception(error_message)


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
    drivers_archive = config.DRIVERS_DIR / "Drivers.7z.001"
    if drivers_archive.exists():
        config_data["injection"].append({
            "parent": "/",
            "archive": "/ventoy/Drivers.7z"
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


def _generate_unattend_xml(main_app, index, product_key=None, architecture="amd64"):
    """
    Tạo file unattend.xml với một product key đã được cung cấp.
    Hàm này được giữ nguyên logic từ file gốc của bạn.
    """
    if product_key:
        product_key_xml = f"""<ProductKey>
                <Key>{product_key}</Key>
                <WillShowUI>OnError</WillShowUI>
            </ProductKey>"""
    else:
        product_key_xml = r"<ProductKey />"

    return f"""<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
<settings pass="windowsPE">
    <component name="Microsoft-Windows-International-Core-WinPE" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
        <SetupUILanguage><UILanguage>en-US</UILanguage></SetupUILanguage>
        <InputLocale>en-US</InputLocale><SystemLocale>en-US</SystemLocale><UILanguage>en-US</UILanguage><UserLocale>en-US</UserLocale>
    </component>
    <component name="Microsoft-Windows-Setup" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
        <ImageInstall><OSImage><InstallFrom><MetaData wcm:action="add"><Key>/IMAGE/INDEX</Key><Value>{index}</Value></MetaData></InstallFrom></OSImage></ImageInstall>
        <UserData>{product_key_xml}<AcceptEula>true</AcceptEula><FullName>Admin</FullName><Organization>TekDT BMC</Organization></UserData>
    </component>
</settings>
<settings pass="offlineServicing">
    <component name="Microsoft-Windows-PnpCustomizationsNonWinPE" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
        <DriverPaths><PathAndCredentials wcm:action="add" wcm:keyValue="1"><Path>X:\\Drivers</Path></PathAndCredentials></DriverPaths>
    </component>
</settings>
<settings pass="specialize">    
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
        <ComputerName>*</ComputerName><TimeZone>SE Asia Standard Time</TimeZone>
    </component>
</settings>
<settings pass="oobeSystem">
    <component name="Microsoft-Windows-International-Core" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
        <InputLocale>en-US</InputLocale><SystemLocale>en-US</SystemLocale><UILanguage>en-US</UILanguage><UserLocale>en-US</UserLocale>
    </component>
    <component name="Microsoft-Windows-SecureStartup-FilterDriver" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" versionScope="nonSxS"><PreventDeviceEncryption>true</PreventDeviceEncryption></component>
    <component name="Microsoft-Windows-EnhancedStorage-Adm" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" versionScope="nonSxS"><TCGSecurityActivationDisabled>1</TCGSecurityActivationDisabled></component>
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="{architecture}" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
        <AutoLogon><Enabled>true</Enabled><Username>Administrator</Username><LogonCount>1</LogonCount><Password><Value/><PlainText>true</PlainText></Password></AutoLogon>
        <UserAccounts><LocalAccounts><LocalAccount wcm:action="add"><Password><Value/><PlainText>true</PlainText></Password><Group>Administrators</Group><Name>Administrator</Name></LocalAccount></LocalAccounts></UserAccounts>
        <OOBE><ProtectYourPC>3</ProtectYourPC><HideEULAPage>true</HideEULAPage><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE><HideOnlineAccountScreens>true</HideOnlineAccountScreens></OOBE>
        <FirstLogonCommands>
            <SynchronousCommand wcm:action="add">
                <CommandLine>powershell -Command "Get-Volume | Where-Object {{ ($_.DriveType -eq 'Removable') -and (Test-Path ($_.DriveLetter + ':\\TekDT_AIS\\tekdt_ais.exe')) }} | ForEach-Object {{ Start-Process ($_.DriveLetter + ':\\TekDT_AIS\\tekdt_ais.exe') -ArgumentList '/install' }}"</CommandLine>
                <Description>Find and run TekDT AIS Installer</Description><Order>1</Order>
            </SynchronousCommand>
        </FirstLogonCommands>
    </component>
</settings>
</unattend>"""


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
        apps_to_copy = [name for name, settings in app_config.items() if settings.get("auto_install")]
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


def create_usb_task(main_app):
    """Tác vụ tạo USB Boot chạy trong luồng nền với tiến trình được thiết kế lại."""
    worker = main_app.creation_worker
    try:
        worker.progress.emit(0)
        
        # --- GIAI ĐOẠN 1: ĐỊNH DẠNG USB VỚI VENTOY (0% -> 15%) ---
        worker.status.emit(f"Đang định dạng USB {main_app.config['device']} với Ventoy...")
        ventoy_exe = config.VENTOY_DIR / "Ventoy2Disk.exe"
        if not ventoy_exe.exists():
            raise FileNotFoundError("Không tìm thấy Ventoy2Disk.exe.")

        phy_drive_num = main_app.config["device"].replace("\\\\.\\PHYSICALDRIVE", "")
        cmd = [str(ventoy_exe), "VTOYCLI", "/I", f"/PhyDrive:{phy_drive_num}"]
        if main_app.config["partition_scheme"] == "GPT": cmd.append("/GPT")
        cmd.append(f"/FS:{main_app.config['filesystem'].upper()}")

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in iter(process.stdout.readline, ''): print(line.strip())
        process.wait()

        if process.returncode != 0:
            raise Exception(f"Ventoy2Disk.exe thất bại với mã lỗi {process.returncode}")

        worker.progress.emit(15)
        worker.status.emit("Định dạng USB thành công. Bắt đầu sao chép file...")
        
        # --- GIAI ĐOẠN 2: SAO CHÉP TẤT CẢ CÁC FILE (15% -> 80%) ---
        time.sleep(5)
        usb_mount_point = _get_drive_mount_point(main_app, main_app.config["device"])
        if not usb_mount_point:
            raise Exception("Không thể tìm thấy điểm mount của USB sau khi tạo.")

        usb_ventoy_dir = os.path.join(usb_mount_point, "ventoy")
        os.makedirs(usb_ventoy_dir, exist_ok=True)
        
        # Tạo các file unattend trước
        for i, iso_info in enumerate(main_app.config['iso_list']):
            if iso_info.get("windows_edition_index"):
                unattend_content = _generate_unattend_xml(main_app, iso_info["windows_edition_index"], iso_info.get("product_key"), iso_info.get("architecture", "amd64"))
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
        progress_range = 65 # (80 - 15)

        # Sao chép ISOs
        for iso_info in main_app.config['iso_list']:
            dest_iso_path = os.path.join(usb_mount_point, iso_info['filename'])
            copied_so_far = _copy_with_progress(worker, iso_info['path'], dest_iso_path, total_copy_size, copied_so_far, base_progress, progress_range)

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

        # Gộp và chép Drivers.7z
        _process_driver_archive(main_app, usb_mount_point)
        
        worker.progress.emit(80) # Hoàn tất sao chép file
        
        # --- GIAI ĐOẠN 3: LẤP ĐẦY DUNG LƯỢNG TRỐNG (80% -> 100%) ---
        if main_app.config.get("fill_space", True):
            worker.status.emit("Đang tính toán dung lượng trống...")
            time.sleep(2)
            try:
                usage = shutil.disk_usage(usb_mount_point)
                total_free_space = usage.free
                RESERVE_SPACE = 64 * 1024 * 1024 # 64MB
                fill_space_target = total_free_space - RESERVE_SPACE

                if fill_space_target <= 0:
                    print("Không đủ dung lượng trống để lấp đầy.")
                else:
                    fill_file_dir = os.path.join(usb_mount_point, "TekDT_Fill")
                    os.makedirs(fill_file_dir, exist_ok=True)
                    if main_app.config["filesystem"].upper() == "FAT32":
                        max_chunk = 2 * 1024 * 1024 * 1024
                        filled = 0
                        idx = 1
                        while filled < fill_space_target:
                            size = min(max_chunk, fill_space_target - filled)
                            path = os.path.join(fill_file_dir, f"fill_{idx:03d}.dat")
                            written = _create_fill_file(main_app, path, size, fill_space_target, filled)
                            filled += written
                            if written < size: break
                            idx += 1
                    else:
                        path = os.path.join(fill_file_dir, "fill_final.dat")
                        _create_fill_file(main_app, path, fill_space_target, fill_space_target, 0)
            except Exception as e:
                worker.status.emit(f"Cảnh báo: Không thể lấp đầy dung lượng. Lỗi: {e}")

        worker.progress.emit(100)
        worker.status.emit("Hoàn tất! USB đã sẵn sàng.")

    except Exception as e:
        import traceback
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