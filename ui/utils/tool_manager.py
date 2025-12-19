import requests, os, re, time, shutil, zipfile, subprocess, config
from pathlib import Path

def _check_internet_connection():
    """Kiểm tra kết nối Internet một cách nhanh chóng."""
    try:
        # Dùng một địa chỉ IP đáng tin cậy và timeout ngắn
        requests.get("https://8.8.8.8", timeout=3)
        return True
    except requests.ConnectionError:
        return False

def _check_self_update(main_window):
    """Kiểm tra phiên bản của chính chương trình trên GitHub và lấy đúng link tải file ZIP."""
    API_URL = config.SELF_UPDATE_API_URL 
    try:
        response = requests.get(API_URL, timeout=5)
        response.raise_for_status()
        latest_release = response.json()
        
        remote_version_tag = latest_release.get("tag_name", "").lstrip('v')
        local_version = config.APP_VERSION

        if remote_version_tag > local_version:
            # SỬA: Tìm đúng URL tải về trong 'assets'
            download_url = None
            for asset in latest_release.get("assets", []):
                # Giả định file phát hành là file .zip
                if asset.get("name", "").endswith(".zip"):
                    download_url = asset.get("browser_download_url")
                    break
            
            if download_url:
                # Gửi tín hiệu về luồng chính với URL tải về chính xác
                main_window.new_version_found.emit(remote_version_tag, download_url)
            else:
                print("Cảnh báo: Tìm thấy phiên bản mới nhưng không tìm thấy file .zip trong assets.")

    except requests.exceptions.RequestException as e:
        print(f"Không thể kiểm tra phiên bản mới: {e}")
    except Exception as e:
        print(f"Lỗi không xác định khi kiểm tra phiên bản: {e}")

def _update_task(main_window):
    if not config.TOOLS_DIR.exists():
        config.TOOLS_DIR.mkdir()

    has_internet = _check_internet_connection()
    if has_internet:
        main_window.update_worker.status.emit("Đang kiểm tra phiên bản chương trình...")
        _check_self_update(main_window) # Gọi hàm kiểm tra phiên bản mới
        main_window.update_worker.status.emit("Đã kết nối Internet. Sẵn sàng kiểm tra cập nhật công cụ.")
    else:
        main_window.update_worker.status.emit("Không có kết nối Internet. Sẽ sử dụng các công cụ hiện có.")

    main_window.update_worker.status.emit("Đang kiểm tra các công cụ...")

    tools = [
        ("Fido", config.FIDO_SCRIPT_PATH, _update_fido_script(main_window)),
        ("oscdimg", config.OSCDIMG_EXE, _update_oscdimg_exe(main_window)),
        ("Ventoy", os.path.join(config.VENTOY_DIR, "Ventoy2Disk.exe"), lambda: _update_tool(main_window, "Ventoy", config.VENTOY_API_URL, r"ventoy-.*-windows\.zip", lambda zip_path, dest_dir: _unzip_and_move(main_window, zip_path, dest_dir))),
        ("aria2", config.ARIA2_EXE, lambda: _update_tool(main_window, "aria2", config.ARIA2_API_URL, r"aria2-.*-win-32bit-build.*\.zip", lambda zip_path, dest_dir: _unzip_and_move(main_window, zip_path, dest_dir))),
        ("wimlib", config.WIMLIB_EXE, lambda: _update_tool(main_window, "wimlib", config.WIMLIB_URL, r"wimlib-.*-windows.*\.zip", lambda zip_path, dest_dir: _unzip_and_move(main_window, zip_path, dest_dir), ssl_verify=False)),
        ("WinCDEmu", config.WINCDEMU_EXE, lambda: _update_tool(main_window, "WinCDEmu", config.WINCDEMU_API_URL, r"PortableWinCDEmu-.*\.exe", lambda dp, dd: _download_and_place_exe(dp, dd, "wcdemu.exe"))),
        ("TekDT_AIS", config.TEKDTAIS_EXE, lambda: _update_tool(main_window, "TekDT_AIS", config.TEKDTAIS_API_URL, r".*\.zip", lambda zip_path, dest_dir: _unzip_and_move(main_window, zip_path, dest_dir))),
    ]

    for tool_name, tool_path, update_func in tools:
        if not os.path.exists(tool_path):
            main_window.update_worker.status.emit(f"Công cụ {tool_name} không tồn tại.")
            if not has_internet:
                # Lỗi nghiêm trọng: thiếu công cụ và không có mạng để tải
                raise Exception(f"{tool_name} bị thiếu và không có kết nối Internet để tải về.")

            main_window.update_worker.status.emit(f"Đang tải {tool_name}...")
            try:
                update_func() # Bắt buộc tải về lần đầu
            except Exception as e:
                raise Exception(f"Không thể tải về công cụ bắt buộc {tool_name}: {e}")
        else:
            # Công cụ đã tồn tại
            if has_internet:
                main_window.update_worker.status.emit(f"Đang kiểm tra cập nhật cho {tool_name}...")
                try:
                    # Thử cập nhật, nhưng không báo lỗi nghiêm trọng nếu thất bại
                    update_func()
                except Exception as e:
                    main_window.update_worker.status.emit(f"Lỗi khi cập nhật {tool_name}, sử dụng phiên bản hiện có. Lỗi: {e}")
            else:
                main_window.update_worker.status.emit(f"{tool_name} đã có. Bỏ qua kiểm tra cập nhật.")

    main_window.update_worker.status.emit("Hoàn tất kiểm tra công cụ!")
    time.sleep(1)

def _update_fido_script(main_window):
    """Tải trực tiếp file Fido.ps1 từ GitHub."""
    try:
        main_window.update_worker.status.emit("Đang tải Fido.ps1...")
        response = requests.get(config.FIDO_PS1_URL)
        response.raise_for_status() # Báo lỗi nếu tải thất bại
        with open(config.FIDO_SCRIPT_PATH, 'wb') as f:
            f.write(response.content)
        main_window.update_worker.status.emit("Cập nhật Fido thành công!")
    except Exception as e:
        error_message = f"Lỗi khi tải Fido.ps1: {e}"
        main_window.update_worker.status.emit(error_message)
        raise Exception(error_message)
        
def _update_oscdimg_exe(main_window):
    """Tải trực tiếp file OSCDIMG từ Microsoft."""
    try:
        main_window.update_worker.status.emit("Đang tải OSCDIMG...")
        response = requests.get(config.OSCDIMG_EXE_URL)
        response.raise_for_status() # Báo lỗi nếu tải thất bại
        with open(config.OSCDIMG_EXE, 'wb') as f:
            f.write(response.content)
        main_window.update_worker.status.emit("Cập nhật OSCDIMG thành công!")
    except Exception as e:
        error_message = f"Lỗi khi tải OSCDIMG: {e}"
        main_window.update_worker.status.emit(error_message)
        raise Exception(error_message)

def _update_tool(main_window, name, api_url, asset_pattern, extract_func, ssl_verify=True):
    try:
        is_direct_url = api_url.endswith(".zip") or api_url.endswith(".7z")
        if is_direct_url:
            latest_version = os.path.basename(api_url)
        else:
            response = requests.get(api_url)
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release["tag_name"]
        
        tool_dest_dir = os.path.join(config.TOOLS_DIR, name)
        version_file = os.path.join(tool_dest_dir, "version.txt")

        current_version = ""
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                current_version = f.read().strip()
        
        if latest_version != current_version or not os.path.exists(tool_dest_dir):
            main_window.update_worker.status.emit(f"Tìm thấy {name} phiên bản mới. Đang tải...")
            
            if is_direct_url:
                asset_url = api_url
            else:
                asset_url = ""
                for asset in latest_release["assets"]:
                    if re.match(asset_pattern, asset["name"]):
                        asset_url = asset["browser_download_url"]
                        break
                if not asset_url:
                    raise Exception(f"Không tìm thấy file tải về cho {name} với pattern: {asset_pattern}")

            download_path = os.path.join(config.TOOLS_DIR, os.path.basename(asset_url))
            
            with requests.get(asset_url, stream=True, verify=ssl_verify) as r:
                r.raise_for_status()
                with open(download_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            main_window.update_worker.status.emit(f"Đang xử lý {name}...")
            extract_func(download_path, tool_dest_dir)
            
            if os.path.exists(download_path):
                try:
                    os.remove(download_path)
                    print(f"Đã xóa file tạm: {download_path}")
                except OSError as e:
                    print(f"Không thể xóa file tạm {download_path}: {e}")

            with open(version_file, 'w') as f:
                f.write(latest_version)
            main_window.update_worker.status.emit(f"Đã cập nhật {name} thành công!")
        else:
            main_window.update_worker.status.emit(f"{name} đã là phiên bản mới nhất.")
    except Exception as e:
        error_message = f"Lỗi trong quá trình cập nhật {name}: {e}"
        main_window.update_worker.status.emit(error_message)
        raise Exception(error_message)

def _download_and_place_exe(downloaded_path, dest_dir, final_name):
    """
    Di chuyển file đã tải về vào thư mục đích và đổi tên.
    Hàm này dùng cho các công cụ là file .exe độc lập.
    """
    # Tạo thư mục đích nếu chưa có
    os.makedirs(dest_dir, exist_ok=True)
    
    # Xóa file cũ nếu có để đảm bảo cập nhật
    final_path = os.path.join(dest_dir, final_name)
    if os.path.exists(final_path):
        os.remove(final_path)
        
    # Di chuyển file vừa tải về vào vị trí cuối cùng
    shutil.move(downloaded_path, final_path)

def _unzip_and_move(main_window, zip_path, dest_dir):
    """
    Giải nén file .zip một cách linh hoạt và di chuyển nội dung.
    Hàm này xử lý cả hai trường hợp:
    1. File zip chứa một thư mục gốc duy nhất (như Ventoy, aria2).
    2. File zip chứa nhiều file/thư mục ở cấp cao nhất (như wimlib).
    """
    # Tạo một thư mục tạm để giải nén, tránh xung đột tên.
    # Thư mục này sau đó sẽ được đổi tên thành dest_dir hoặc nội dung của nó sẽ được di chuyển.
    temp_extract_dir = dest_dir + "_temp"

    # Dọn dẹp các thư mục cũ từ lần chạy trước nếu có
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir)

    # Giải nén vào thư mục tạm
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.namelist():
            member_path = os.path.join(temp_extract_dir, member)
            abs_member_path = os.path.abspath(member_path)
            abs_extract_dir = os.path.abspath(temp_extract_dir)
            if not abs_member_path.startswith(abs_extract_dir + os.sep):
                raise Exception(f"Unsafe ZIP entry detected: {member}")
        zip_ref.extractall(temp_extract_dir)

    # Lấy danh sách các mục đã được giải nén trong thư mục tạm
    extracted_items = os.listdir(temp_extract_dir)
    if not extracted_items:
        shutil.rmtree(temp_extract_dir)
        raise Exception(f"File zip {os.path.basename(zip_path)} trống.")

    # Trường hợp 1: File zip có một thư mục gốc duy nhất.
    if len(extracted_items) == 1:
        inner_path = os.path.join(temp_extract_dir, extracted_items[0])
        if os.path.isdir(inner_path):
            # Di chuyển thư mục con đó ra ngoài và đổi tên thành dest_dir
            shutil.move(inner_path, dest_dir)
            # Dọn dẹp thư mục tạm (giờ đã trống)
            os.rmdir(temp_extract_dir)
            return

    # Trường hợp 2: File zip có cấu trúc phẳng (nhiều file/thư mục).
    # Chỉ cần đổi tên thư mục tạm thành thư mục đích.
    shutil.move(temp_extract_dir, dest_dir)

def get_tool_path(name):
    """
    Trả về đường dẫn tuyệt đối của các công cụ hỗ trợ hoặc các thư mục/file dữ liệu driver.
    Hàm này giúp quản lý tập trung các đường dẫn trong dự án.
    """
    base_dir = config.BASE_DIR
    
    # 1. Nhóm các công cụ thực thi (Executables)
    if name == "aria2c":
        # Mặc định aria2c nằm trong thư mục Tools/aria2c
        path = os.path.join(base_dir, "Tools", "aria2", "aria2c.exe")
        return path if os.path.exists(path) else None
    
    if name == "7z":
        # Mặc định 7z nằm trong thư mục Tools/7z, nếu không thấy sẽ trả về '7z.exe' để gọi từ PATH hệ thống
        path = os.path.join(base_dir, "Tools", "7z", "7z.exe")
        return path if os.path.exists(path) else "7z.exe"

    # 2. Nhóm các đường dẫn dữ liệu Driver và Database
    if name == "db_file":
        # File SQLite chứa bản đồ Driver
        return os.path.join(base_dir, "Drivers", "DB", "db.sqlite")
    
    if name == "drivers_dir":
        # Thư mục chứa các file nén DP_*.7z
        return os.path.join(base_dir, "Drivers", "Drivers")
        
    if name == "torrent_file":
        # File torrent gốc để phân tích danh sách driver
        return os.path.join(base_dir, "Drivers", "DriverPack-Offline.torrent")
    
    if name == "version_json":
        # File lưu vết phiên bản driver đã tải
        return os.path.join(base_dir, "Drivers", "driver_versions.json")

    return None