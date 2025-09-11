from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, QFileDialog, QDialog,
                             QCheckBox, QPushButton, QListWidget, QGroupBox, QListWidgetItem,
                             QHBoxLayout, QDialogButtonBox, QRadioButton, QButtonGroup, QGridLayout)
from PySide6.QtCore import Qt, QTimer
import config, os, shutil, psutil, subprocess, string, json, requests, time, threading, re, tempfile
from ui.utils import helpers
from urllib.parse import urlparse
from queue import Queue, Empty
from pathlib import Path

class PageISOSelect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        self.aria2_process = None
        self.is_cancelling = False
        self.downloads_queue = []
        self.arch_button_group = QButtonGroup(self)
        self.source_button_group = QButtonGroup(self)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 20, 50, 50)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Bước 2: Chọn hoặc tải các file ISO")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        # Group 1: Danh sách các file ISO đã chọn
        self.iso_list_group = QGroupBox("Danh sách ISO sẽ được thêm vào USB")
        group1_layout = QVBoxLayout(self.iso_list_group)

        self.iso_list_widget = QListWidget()
        self.iso_list_widget.setAlternatingRowColors(True)
        group1_layout.addWidget(self.iso_list_widget)

        iso_buttons_layout = QHBoxLayout()
        add_iso_button = QPushButton("Thêm ISO từ máy...")
        add_iso_button.clicked.connect(self.browse_iso)
        remove_iso_button = QPushButton("Xóa ISO đã chọn")
        remove_iso_button.clicked.connect(self.remove_selected_iso)
        iso_buttons_layout.addWidget(add_iso_button)
        iso_buttons_layout.addWidget(remove_iso_button)
        group1_layout.addLayout(iso_buttons_layout)
        layout.addWidget(self.iso_list_group)
        
        self.source_group = QGroupBox("Lấy link trực tiếp từ")
        source_layout = QHBoxLayout(self.source_group)
        source_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.microsoft_radio = QRadioButton("Fido Script")
        self.microsoft_radio.setChecked(True)
        self.gravesoft_radio = QRadioButton("MSDL.GraveSoft.Dev")

        self.source_button_group.addButton(self.microsoft_radio)
        self.source_button_group.addButton(self.gravesoft_radio)
        self.source_button_group.buttonToggled.connect(self._on_source_changed)

        source_layout.addWidget(self.microsoft_radio)
        source_layout.addWidget(self.gravesoft_radio)
        layout.addWidget(self.source_group)

        # Group 2: Tải tự động
        self.microsoft_download_group = QGroupBox("Tải tự động từ Microsoft")
        self.microsoft_download_group_layout = QVBoxLayout(self.microsoft_download_group)
        
        self.win_options = {}
        
        # Windows 10 & 11 (dùng Fido)
        microsoft_options_layout = QGridLayout()
        microsoft_options_layout.setColumnStretch(0, 1)
        microsoft_options_layout.setColumnStretch(1, 1)

        # --- CỘT 1 ---
        # Windows 11
        win11_cb = QCheckBox("Windows 11 (x64)")
        self.win_options["Windows 11"] = {'checkbox': win11_cb, 'type': 'fido', 'archs': ["x64"]}
        microsoft_options_layout.addWidget(win11_cb, 0, 0) # Hàng 0, Cột 0

        # Windows 10 (gồm Checkbox và Radio Buttons)
        win10_container = QWidget()
        win10_layout = QVBoxLayout(win10_container)
        win10_layout.setContentsMargins(0, 0, 0, 0)
        
        win10_cb = QCheckBox("Windows 10 (x64, x86)")
        self.win_options["Windows 10"] = {'checkbox': win10_cb, 'type': 'fido', 'archs': ["x64", "x86"]}
        win10_layout.addWidget(win10_cb)
        
        win10_radios = {}
        win10_radio_layout = QHBoxLayout()
        for arch in ["x64", "x86"]:
            rb = QRadioButton(arch)
            rb.setVisible(False)
            win10_radio_layout.addWidget(rb)
            self.arch_button_group.addButton(rb)
            win10_radios[arch] = rb
        self.win_options["Windows 10"]['radios'] = win10_radios
        win10_layout.addLayout(win10_radio_layout)
        win10_cb.toggled.connect(lambda checked, win="Windows 10": self.toggle_arch_options(checked, win))
        
        microsoft_options_layout.addWidget(win10_container, 1, 0) # Hàng 1, Cột 0

        # --- CỘT 2 ---
        server_versions = {
            "Windows Server 2025": config.WINDOWS_SERVER_2025_URL,
            "Windows Server 2022": config.WINDOWS_SERVER_2022_URL,
            "Windows Server 2016": config.WINDOWS_SERVER_2016_URL
        }
        
        row_index = 0
        for name, url in server_versions.items():
            cb = QCheckBox(name)
            self.win_options[name] = {'checkbox': cb, 'type': 'direct', 'url': url}
            microsoft_options_layout.addWidget(cb, row_index, 1)
            row_index += 1
            
        self.microsoft_download_group_layout.addLayout(microsoft_options_layout)

        self.download_button = QPushButton("Tải các mục đã chọn")
        self.download_button.clicked.connect(self.start_downloads)
        self.microsoft_download_group_layout.addWidget(self.download_button)

        layout.addWidget(self.microsoft_download_group)
        
        self.gravesoft_download_group = QGroupBox("Tải tự động từ MSDL.GraveSoft.Dev")
        gravesoft_main_layout = QVBoxLayout(self.gravesoft_download_group)
        
        # (Giữ nguyên phần code thêm các combobox và nút tải cho GraveSoft)
        gravesoft_main_layout.addWidget(QLabel("1. Chọn phiên bản Windows:"))
        self.gravesoft_product_combo = QComboBox()
        self.gravesoft_product_combo.addItem("Vui lòng chọn nguồn tải...", None)
        gravesoft_main_layout.addWidget(self.gravesoft_product_combo)
        self.gravesoft_sku_label = QLabel("2. Chọn ngôn ngữ và kiến trúc:")
        self.gravesoft_sku_combo = QComboBox()
        self.gravesoft_sku_label.setVisible(False)
        self.gravesoft_sku_combo.setVisible(False)
        gravesoft_main_layout.addWidget(self.gravesoft_sku_label)
        gravesoft_main_layout.addWidget(self.gravesoft_sku_combo)
        gravesoft_main_layout.addStretch() 
        self.gravesoft_download_button = QPushButton("Tải mục đã chọn")
        self.gravesoft_download_button.setVisible(False)
        self.gravesoft_download_button.clicked.connect(self.start_downloads)
        gravesoft_main_layout.addWidget(self.gravesoft_download_button)

        self.gravesoft_download_group.setVisible(False)
        layout.addWidget(self.gravesoft_download_group)
        
        # Thêm label trạng thái vào layout chính, ngay trên các nút điều hướng
        self.download_status_label = QLabel("")
        self.download_status_label.setObjectName("DownloadStatusLabel") # Giữ lại style
        self.download_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Căn giữa
        self.download_status_label.setWordWrap(True)
        layout.addWidget(self.download_status_label)

        layout.addStretch()

        # Nút điều hướng
        nav_layout = QHBoxLayout()
        self.back_button = QPushButton("← Quay lại")
        self.cancel_button = QPushButton("Hủy Tải")
        self.cancel_button.setVisible(False)
        self.cancel_button.setStyleSheet("background-color: #BF616A;")
        self.next_button = QPushButton("Tiếp theo →")
        self.update_next_button_state()

        nav_layout.addWidget(self.back_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.cancel_button)
        nav_layout.addWidget(self.next_button)
        layout.addLayout(nav_layout)

        self.sync_ui_with_config()
        
        self.cancel_button.clicked.connect(self.cancel_download_clicked)
        self.gravesoft_product_combo.currentIndexChanged.connect(self._on_product_selected)
        self.gravesoft_sku_combo.currentIndexChanged.connect(self._on_sku_selected)

    def update_next_button_state(self):
        """Kích hoạt nút 'Tiếp theo' chỉ khi có ISO và USB vẫn được kết nối."""
        has_iso = len(self.main_app.config["iso_list"]) > 0
        is_usb_present = self.main_app.config.get("device_details") is not None
        self.next_button.setEnabled(has_iso and is_usb_present)
    
    def _on_source_changed(self, button, checked):
        """Xử lý khi người dùng thay đổi nguồn tải."""
        if not checked:
            return

        is_microsoft = (button == self.microsoft_radio)
        self.microsoft_download_group.setVisible(is_microsoft)
        self.gravesoft_download_group.setVisible(not is_microsoft)

        # Nếu chuyển sang MassGrave và chưa có dữ liệu, hãy tải nó
        if not is_microsoft and self.gravesoft_product_combo.count() <= 1:
            self._fetch_products()

    def _fetch_products(self):
        """Bắt đầu một luồng để tải danh sách sản phẩm."""
        self.gravesoft_product_combo.clear()
        self.gravesoft_product_combo.addItem("Đang tải danh sách sản phẩm...", None)
        self.product_fetch_worker = self.main_app._create_and_start_worker(
            name="ProductFetcher",
            target=self._fetch_products_task,
            on_result=self._populate_product_combo,
            on_finished=lambda s, m: print(f"Product fetch finished: {s}, {m}")
        )

    def _fetch_products_task(self):
        """Tác vụ nền: Lấy JSON danh sách sản phẩm."""
        url = "https://github.com/gravesoft/msdl/raw/refs/heads/main/data/products.json"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Lỗi khi tải products.json: {e}")
            return None

    def _populate_product_combo(self, products_data):
        """Điền dữ liệu sản phẩm vào combobox đầu tiên."""
        self.gravesoft_product_combo.clear()
        if not products_data:
            self.gravesoft_product_combo.addItem("Lỗi tải dữ liệu", None)
            return

        self.gravesoft_product_combo.addItem("Vui lòng chọn phiên bản Windows...", None)
        # Sắp xếp các sản phẩm theo tên để dễ tìm
        sorted_products = sorted(products_data.items(), key=lambda item: item[1])
        for product_id, product_name in sorted_products:
            self.gravesoft_product_combo.addItem(product_name, product_id)

    def _on_product_selected(self, index):
        """Kích hoạt khi người dùng chọn một sản phẩm."""
        # Ẩn và xóa các lựa chọn cũ
        self.gravesoft_sku_label.setVisible(False)
        self.gravesoft_sku_combo.setVisible(False)
        self.gravesoft_download_button.setVisible(False)
        self.gravesoft_sku_combo.clear()

        product_id = self.gravesoft_product_combo.itemData(index)
        if not product_id:
            return

        # Hiển thị trạng thái đang tải và bắt đầu worker
        self.gravesoft_sku_label.setVisible(True)
        self.gravesoft_sku_combo.setVisible(True)
        self.gravesoft_sku_combo.addItem("Đang tải ngôn ngữ/phiên bản...", None)

        self.sku_fetch_worker = self.main_app._create_and_start_worker(
            name="SkuFetcher",
            target=self._fetch_skus_task,
            on_result=self._populate_sku_combo,
            args=[product_id] # Truyền product_id vào worker
        )

    def _fetch_skus_task(self, product_id):
        """Tác vụ nền: Lấy thông tin SKU cho một sản phẩm."""
        url = f"https://api.gravesoft.dev/msdl/skuinfo?product_id={product_id}"
        try:
            # API của MassGrave yêu cầu User-Agent để hoạt động
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            # đảm bảo trả về list (một số API trả object)
            data = response.json()
            if data is None:
                return []
            return data
        except ValueError:
            print("Phản hồi không phải JSON:", getattr(response, 'text', '')[:200])
            return []
        except Exception as e:
            print(f"Lỗi khi tải SKU info: {e}")
            return []

    def _guess_arch_from_filename(self, filename):
        """Thử đoán arch từ tên file (ví dụ contains '_x64' hoặc '_x32')"""
        if not filename:
            return "unknown"
        fn = filename.lower()
        if "_x64" in fn or "x64" in fn:
            return "x64"
        if "_x86" in fn or "_x32" in fn or "x32" in fn:
            return "x32"
        # fallback kiểm tra '64' hay '32' ở cuối token
        m = re.search(r'[_\-](x?64|x?86|x?32)\b', fn)
        if m:
            return m.group(1)
        return "unknown"

    def _populate_sku_combo(self, skus_data):
        """
        Điền dữ liệu cho combobox ngôn ngữ/phiên bản (combobox thứ 2).
        Hỗ trợ cả 2 trường hợp: skus_data là dict có 'Skus' hoặc là list.
        Mỗi item trong combobox sẽ tương ứng 1 FriendlyFileNames (ví dụ x32/x64).
        """
        # reset
        try:
            self.gravesoft_sku_combo.blockSignals(True)
        except Exception:
            pass
        self.gravesoft_sku_combo.clear()

        # Lấy list thực tế
        if not skus_data:
            self.gravesoft_sku_combo.addItem("Không có phiên bản (dữ liệu rỗng)", None)
            try:
                self.gravesoft_sku_combo.blockSignals(False)
            except Exception:
                pass
            return

        if isinstance(skus_data, dict) and 'Skus' in skus_data:
            skus_list = skus_data.get('Skus') or []
        elif isinstance(skus_data, list):
            skus_list = skus_data
        else:
            # dữ liệu lạ
            self.gravesoft_sku_combo.addItem("Dữ liệu không đúng định dạng", None)
            try:
                self.gravesoft_sku_combo.blockSignals(False)
            except Exception:
                pass
            return

        if not skus_list:
            self.gravesoft_sku_combo.addItem("Không có phiên bản", None)
            try:
                self.gravesoft_sku_combo.blockSignals(False)
            except Exception:
                pass
            return

        # Thêm placeholder
        self.gravesoft_sku_combo.addItem("Chọn ngôn ngữ / phiên bản...", None)

        # Duyệt từng sku (mỗi sku là dict trong JSON bạn đưa)
        for sku in skus_list:
            if not isinstance(sku, dict):
                # phòng hờ: nếu không phải dict -> hiển thị chuỗi đơn giản
                display = str(sku)
                self.gravesoft_sku_combo.addItem(display, {"sku_id": None, "language": display, "filename": None, "arch": None})
                continue

            sku_id = sku.get("Id") or sku.get("id") or sku.get("SkuId") or None
            language = sku.get("Language") or sku.get("LocalizedLanguage") or sku.get("ProductDisplayName") or "Unknown language"

            friendly_files = sku.get("FriendlyFileNames") or sku.get("FriendlyFiles") or []
            # Nếu API không trả FriendlyFileNames, fallback tạo từ Description hoặc Id
            if not friendly_files:
                # tạo một mục đại diện
                display = f"{language} - {sku_id or 'n/a'}"
                self.gravesoft_sku_combo.addItem(display, {"sku_id": sku_id, "language": language, "filename": None, "arch": None})
                continue

            # Thêm một item cho mỗi filename (thường có 2: x32 và x64)
            for fname in friendly_files:
                arch = self._guess_arch_from_filename(fname)
                display = f"{language} — {arch} ({fname})"
                userdata = {"sku_id": sku_id, "language": language, "filename": fname, "arch": arch}
                self.gravesoft_sku_combo.addItem(display, userdata)

        try:
            self.gravesoft_sku_combo.blockSignals(False)
        except Exception:
            pass

    def _on_sku_selected(self, index):
        """Kích hoạt khi người dùng chọn SKU, hiển thị nút tải."""
        sku_data = self.gravesoft_sku_combo.itemData(index)  # Đây là dict với "sku_id", "language", "filename", "arch"
        self.gravesoft_download_button.setVisible(bool(sku_data and sku_data.get("sku_id")))
    
    def sync_ui_with_config(self):
        """Đọc danh sách ISO từ config và hiển thị lên UI."""
        self.iso_list_widget.clear() # Xóa list cũ trên UI để tránh trùng lặp
        
        # Lấy danh sách iso_list từ config, nếu không có thì dùng list rỗng
        iso_list_data = self.main_app.config.get('iso_list', [])
        
        for iso_info in iso_list_data:
            # Xác định văn bản hiển thị dựa trên việc đã chọn edition hay chưa
            display_text = iso_info['filename']
            if iso_info.get("windows_edition_name"):
                display_text += f" (Tự động cài đặt: {iso_info['windows_edition_name']})"
            else:
                display_text += " (Cài đặt thủ công)"

            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.ItemDataRole.UserRole, iso_info['path']) # Lưu đường dẫn
            self.iso_list_widget.addItem(list_item)
            
        self.update_next_button_state()
    
    def browse_iso(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Chọn các file ISO", str(config.ISOS_DIR), "ISO Files (*.iso)")
        for file_path in file_paths:
            self.add_iso_to_list(file_path)

    def add_iso_to_list(self, iso_path, edition_info=None):
        """Thêm một ISO vào danh sách và UI, sau đó phân tích nó."""
        # Kiểm tra xem ISO đã tồn tại trong danh sách chưa
        if any(iso['path'] == iso_path for iso in self.main_app.config['iso_list']):
            print(f"ISO {iso_path} đã có trong danh sách.")
            return

        iso_info = {
            "path": iso_path,
            "filename": os.path.basename(iso_path),
            "edition_index": None,
            "edition_name": None
        }
        self.main_app.config['iso_list'].append(iso_info)
        self.main_app.save_config()
        
        list_item = QListWidgetItem(f"{iso_info['filename']}")
        list_item.setData(Qt.ItemDataRole.UserRole, iso_path) # Lưu đường dẫn để nhận dạng
        self.iso_list_widget.addItem(list_item)
        
        self.update_next_button_state()
        self.analyze_iso(iso_info) # Phân tích để lấy thông tin phiên bản

    def remove_selected_iso(self):
        selected_items = self.iso_list_widget.selectedItems()
        if not selected_items:
            return

        items_were_removed = False
        for item in selected_items:
            # Lấy đường dẫn từ item dữ liệu, đảm bảo xử lý cả / và \
            iso_path_to_remove = os.path.normpath(item.data(Qt.ItemDataRole.UserRole))

            # Xóa khỏi config, so sánh đường dẫn đã được chuẩn hóa
            initial_count = len(self.main_app.config['iso_list'])
            self.main_app.config['iso_list'] = [
                iso for iso in self.main_app.config['iso_list']
                if os.path.normpath(iso['path']) != iso_path_to_remove
            ]
            
            # Nếu có sự thay đổi về số lượng, tức là đã xóa thành công
            if len(self.main_app.config['iso_list']) < initial_count:
                items_were_removed = True
            
            # Xóa khỏi UI
            self.iso_list_widget.takeItem(self.iso_list_widget.row(item))
        
        # Chỉ lưu lại file nếu thực sự có ISO bị xóa
        if items_were_removed:
            print("Đã cập nhật danh sách ISO, đang lưu vào file...")
            # Gọi hàm lưu cấu hình của ứng dụng chính
            if hasattr(self.main_app, 'save_config'):
                self.main_app.save_config()
            else:
                print("Cảnh báo: self.main_app không có phương thức save_config().")
        
        self.update_next_button_state()

    def _get_available_drive_letter(self):
        """Tìm một ký tự ổ đĩa chưa được sử dụng."""
        used_letters = [p.mountpoint[0].upper() for p in psutil.disk_partitions()]
        for letter in string.ascii_uppercase:
            if letter not in used_letters:
                return letter
        return None
    
    def analyze_iso(self, iso_info_dict):
        """Phân tích file ISO bằng cách ưu tiên mount với PowerShell, fallback sang WinCDEmu nếu thất bại."""
        iso_path = iso_info_dict['path']
        cache = {}
        editions = {} # Khởi tạo editions ở đây

        if os.path.exists(config.ISO_ANALYSIS_CACHE):
            try:
                with open(config.ISO_ANALYSIS_CACHE, 'r') as f: cache = json.load(f)
            except (json.JSONDecodeError, IOError): pass

        size_key = str(os.path.getsize(iso_path))
        
        # Logic xử lý cache được sửa lại
        is_cached = size_key in cache
        if is_cached:
            print(f"Đã tìm thấy thông tin ISO trong cache cho khóa: {size_key}")
            editions = cache[size_key] # Chỉ lấy dữ liệu từ cache và để code chạy tiếp
        
        # Toàn bộ khối phân tích gốc chỉ chạy nếu không có cache
        if not is_cached:
            if not os.path.exists(config.WIMLIB_EXE):
                self.main_app.show_themed_message("Lỗi", 
                                                  "Không tìm thấy wimlib-imagex.exe để phân tích ISO",
                                                  icon=QMessageBox.Icon.Critical)
                return

            mounted_drive = None
            detected_arch = None
            mount_method = None  # Track cách mount: 'powershell' hoặc 'wincdemu'
            try:
                # Bước 0: Kiểm tra PowerShell tồn tại
                powershell_path = shutil.which('powershell')
                if powershell_path:
                    print("PowerShell tồn tại, thử mount bằng PowerShell.")
                    try:
                        # Bước 1: Mount bằng PowerShell
                        mount_cmd = [
                            'powershell', '-NoProfile', '-Command',
                            f'Mount-DiskImage -ImagePath "{iso_path}" -StorageType ISO'
                        ]
                        result = subprocess.run(mount_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        if result.returncode != 0:
                            error_msg = result.stderr.strip() or f"PowerShell trả về mã lỗi {result.returncode}."
                            raise Exception(f"Không thể mount ISO bằng PowerShell: {error_msg}")

                        # Lấy drive letter
                        query_cmd = [
                            'powershell', '-NoProfile', '-Command',
                            f'(Get-DiskImage -ImagePath "{iso_path}" | Get-Volume).DriveLetter'
                        ]
                        result = subprocess.run(query_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        if result.returncode != 0:
                            raise Exception(f"Không thể lấy drive letter từ PowerShell: {result.stderr.strip()}")
                        
                        drive_letter = result.stdout.strip()
                        if not drive_letter:
                            raise Exception("Không tìm thấy drive letter sau khi mount bằng PowerShell.")
                        
                        mounted_drive = f"{drive_letter}:"
                        mount_method = 'powershell'
                        print(f"Mount ISO thành công bằng PowerShell vào ổ {mounted_drive}")
                    except Exception as ps_err:
                        print(f"Lỗi mount bằng PowerShell: {ps_err}. Fallback sang WinCDEmu.")
                        # Tiếp tục fallback dưới
                else:
                    print("PowerShell không tồn tại, fallback sang WinCDEmu.")

                # Nếu PowerShell thất bại hoặc không tồn tại, fallback sang WinCDEmu
                if not mounted_drive:
                    if not os.path.exists(config.WINCDEMU_EXE):
                        raise Exception("Không tìm thấy WinCDEmu.exe để fallback mount ISO.")

                    # Mount bằng WinCDEmu
                    drive_letter = self._get_available_drive_letter()
                    if not drive_letter:
                        raise Exception("Không tìm thấy ký tự ổ đĩa trống để mount bằng WinCDEmu.")
                    
                    print(f"Sẽ mount ISO bằng WinCDEmu vào ổ đĩa: {drive_letter}:")
                    mount_cmd = [config.WINCDEMU_EXE, iso_path, f"{drive_letter}:", "/wait"]
                    result = subprocess.run(mount_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    
                    if result.returncode != 0:
                        error_msg = result.stderr.strip() if result.stderr.strip() else f"WinCDEmu trả về mã lỗi {result.returncode}."
                        raise Exception(f"Không thể mount ISO bằng WinCDEmu: {error_msg}")

                    mounted_drive = f"{drive_letter}:"
                    mount_method = 'wincdemu'
                    print(f"Mount ISO thành công bằng WinCDEmu vào ổ {mounted_drive}")

                # Bước tiếp: Phát hiện kiến trúc và phân tích WIM/ESD (giữ nguyên logic cũ)
                if os.path.exists(os.path.join(mounted_drive, "efi", "boot", "bootx64.efi")):
                    detected_arch = "amd64"
                    print("Phát hiện kiến trúc: 64-bit (amd64)")
                elif os.path.exists(os.path.join(mounted_drive, "efi", "boot", "bootia32.efi")):
                    detected_arch = "x86"
                    print("Phát hiện kiến trúc: 32-bit (x86)")
                else:
                    if os.path.exists(os.path.join(mounted_drive, "sources", "x64")):
                        detected_arch = "amd64"
                        print("Phát hiện kiến trúc (dự phòng): 64-bit (amd64)")
                    elif os.path.exists(os.path.join(mounted_drive, "sources", "x86")):
                        detected_arch = "x86"
                        print("Phát hiện kiến trúc (dự phòng): 32-bit (x86)")
                    else:
                        print("Cảnh báo: Không thể tự động xác định kiến trúc. Mặc định là amd64.")
                        detected_arch = "amd64"

                iso_info_dict["architecture"] = detected_arch
                
                wim_path = None
                for ext in [".wim", ".esd"]:
                    possible_path = os.path.join(mounted_drive, "sources", f"install{ext}")
                    if os.path.exists(possible_path):
                        wim_path = possible_path
                        break
                
                if not wim_path:
                    for arch_folder in ["x64", "x86"]:
                        for ext in [".wim", ".esd"]:
                            possible_path = os.path.join(mounted_drive, "sources", arch_folder, f"install{ext}")
                            if os.path.exists(possible_path):
                                wim_path = possible_path
                                break
                        if wim_path: break
                
                if not wim_path:
                    raise Exception("Không tìm thấy file install.wim hoặc install.esd trong ISO.")
                
                print(f"Đã tìm thấy file image tại: {wim_path}")

                info_cmd = [config.WIMLIB_EXE, "info", wim_path]
                result = subprocess.run(info_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                if result.returncode != 0:
                    error_output = result.stderr.decode(encoding='utf-8', errors='ignore')
                    raise Exception(f"Không thể phân tích file WIM/ESD: {error_output}")

                current_index = ""
                output_text = result.stdout.decode(encoding='utf-8', errors='ignore')
                for line in output_text.splitlines():
                    if "Index" in line:
                        current_index = line.split(":")[-1].strip()
                    elif "Name" in line and current_index:
                        name = line.split(":")[-1].strip()
                        clean_name = ''.join(char for char in name if char.isprintable())
                        editions[current_index] = clean_name
                        current_index = ""

                if editions:
                    print(f"Các phiên bản Windows được tìm thấy: {editions}")
                    cache[size_key] = editions
                    with open(config.ISO_ANALYSIS_CACHE, 'w') as f:
                        json.dump(cache, f, indent=2)

            except Exception as e:
                self.main_app.show_error(f"Lỗi khi phân tích ISO:\n{e}")

            finally:
                # Unmount dựa trên mount_method
                if mounted_drive and iso_path:
                    if mount_method == 'powershell':
                        print(f"Đang unmount ISO bằng PowerShell: {iso_path}")
                        unmount_cmd = [
                            'powershell', '-NoProfile', '-Command',
                            f'Dismount-DiskImage -ImagePath "{iso_path}"'
                        ]
                        subprocess.run(unmount_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    elif mount_method == 'wincdemu':
                        drive_letter = mounted_drive[0]  # Ví dụ 'Z:'
                        print(f"Đang unmount ổ đĩa ảo {drive_letter}: bằng WinCDEmu")
                        unmount_cmd = [config.WINCDEMU_EXE, "/unmount", f"{drive_letter}:"]
                        subprocess.run(unmount_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Lệnh gọi này giờ đây sẽ chạy cho cả 2 trường hợp (có cache và không có cache)
        self.show_edition_selection_dialog(editions, iso_info_dict)

    def show_edition_selection_dialog(self, editions, iso_info_dict):
        """Hiển thị dialog chọn phiên bản và cập nhật dict của ISO."""
        if not editions:
            # Cập nhật UI để hiển thị không có tùy chọn auto-install
            for i in range(self.iso_list_widget.count()):
                item = self.iso_list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == iso_info_dict['path']:
                    item.setText(f"{iso_info_dict['filename']} (Cài đặt thủ công)")
                    break
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Chọn phiên bản cho {iso_info_dict['filename']}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Tùy chọn: Chọn một phiên bản để tự động cài đặt."))
        list_widget = QListWidget()
        pro_index = None
        # Sắp xếp các phiên bản theo index để đảm bảo thứ tự
        sorted_editions = sorted(editions.items(), key=lambda item: int(item[0]))

        for index, name in sorted_editions:
            list_widget.addItem(f"{name} (Index: {index})")
            list_widget.item(list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, (index, name))
            if "Pro" in name and pro_index is None:
                pro_index = list_widget.count() - 1

        if pro_index is not None:
            list_widget.setCurrentRow(pro_index)
        else:
            list_widget.setCurrentRow(0)

        layout.addWidget(list_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted and list_widget.currentItem():
            selected_data = list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
            iso_info_dict["windows_edition_index"] = selected_data[0]
            iso_info_dict["windows_edition_name"] = selected_data[1]
            iso_info_dict["alias"] = f"{iso_info_dict['windows_edition_name']} ({iso_info_dict['filename']})"
            print(f"Đã chọn cho {iso_info_dict['filename']}: {selected_data[1]} (Index: {selected_data[0]})")
            
            # --- LOGIC HỎI KEY ĐƯỢC DI CHUYỂN VÀO ĐÂY ---
            key = helpers.get_generic_key(selected_data[1])
            if not key:
                key = self.main_app.ask_for_product_key(selected_data[1])
            iso_info_dict["product_key"] = key # Lưu key vào dict
            print(f"Đã lấy Product Key: {'Có' if key else 'Không'}")
            
        else:
            iso_info_dict["windows_edition_index"] = None
            iso_info_dict["windows_edition_name"] = None
            iso_info_dict["alias"] = None
            iso_info_dict["product_key"] = None
            print(f"Không chọn tự động cài đặt cho {iso_info_dict['filename']}.")
        
        # Cập nhật lại Text trên List Widget
        for i in range(self.iso_list_widget.count()):
            item = self.iso_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == iso_info_dict['path']:
                if iso_info_dict.get("windows_edition_name"):
                    item.setText(f"{iso_info_dict['filename']} (Tự động cài đặt: {iso_info_dict['windows_edition_name']})")
                else:
                    item.setText(f"{iso_info_dict['filename']} (Cài đặt thủ công)")
                break

    def toggle_arch_options(self, checked, win_version):
        options_data = self.win_options[win_version]
        for rb in options_data['radios'].values():
            rb.setVisible(checked)
        if checked:
            # Bỏ chọn các checkbox khác
            for other_win, data in self.win_options.items():
                if other_win != win_version:
                    data['checkbox'].setChecked(False)
            # Tự động chọn radio button đầu tiên nếu chỉ có 1 lựa chọn
            if len(options_data['radios']) == 1:
                list(options_data['radios'].values())[0].setChecked(True)
        else:
            is_any_rb_checked = any(rb.isChecked() for rb in options_data['radios'].values())
            if is_any_rb_checked:
                self.arch_button_group.setExclusive(False)
                for rb in options_data['radios'].values():
                    rb.setChecked(False)
                self.arch_button_group.setExclusive(True)

    def start_downloads(self):
        self.downloads_queue.clear()

        if self.microsoft_radio.isChecked():
            # Logic cho nguồn Microsoft giữ nguyên
            for name, data in self.win_options.items():
                if data['checkbox'].isChecked():
                    self.downloads_queue.append({'name': name, 'data': data})
        else:
            # LOGIC CHO NGUỒN MASSGRAVE
            product_id = self.gravesoft_product_combo.currentData()
            sku_data = self.gravesoft_sku_combo.currentData()  # Lấy userdata dict từ combobox thứ hai
            product_name = self.gravesoft_product_combo.currentText()
            sku_name = self.gravesoft_sku_combo.currentText()

            if product_id and sku_data and sku_data.get("sku_id"):
                self.downloads_queue.append({
                    'name': f"{product_name} ({sku_name})",
                    'product_id': product_id,
                    'sku_id': sku_data["sku_id"],  # Lấy sku_id từ userdata
                    'selected_filename': sku_data.get("filename"),  # Lưu filename đã chọn để so khớp sau
                    'is_gravesoft': True 
                })

        if not self.downloads_queue:
            self.main_app.show_themed_message("Thông báo",
                                              "Vui lòng chọn ít nhất một phiên bản để tải.",
                                              icon=QMessageBox.Icon.Information)
            return

        self._set_ui_state(downloading=True)
        self.download_worker = self.main_app._create_and_start_worker(
            name="Downloader",
            target=self._download_task,
            on_status=self.download_status_label.setText,
            on_finished=self.on_download_finished,
            on_result=self.on_download_result
        )
    
    def _set_ui_state(self, downloading=False, long_task=False):
        """Cập nhật trạng thái UI cho các tác vụ tải hoặc tác vụ nền dài."""
        # Trạng thái bật/tắt của các control (True = bật, False = tắt)
        is_enabled = not downloading

        # Vô hiệu hóa toàn bộ các group thay vì từng control lẻ
        self.iso_list_group.setEnabled(is_enabled)
        self.source_group.setEnabled(is_enabled)
        self.microsoft_download_group.setEnabled(is_enabled)
        self.gravesoft_download_group.setEnabled(is_enabled)
        
        # Ẩn/hiện các nút điều hướng
        self.back_button.setVisible(is_enabled)
        self.next_button.setVisible(is_enabled)
        self.cancel_button.setVisible(downloading)

        # Các thành phần UI cho tác vụ chạy nền dài (ví dụ: thanh tiến trình)
        if hasattr(self, "progress_bar"):
            self.progress_bar.setVisible(long_task)
        if hasattr(self, "start_button"):
            self.start_button.setEnabled(not long_task)
    
    def get_final_url(self, url):
        try:
            resp = requests.head(url, allow_redirects=True)
            return resp.url
        except Exception as e:
            print(f"Lỗi lấy link cuối cùng: {e}")
            return url

    def _run_aria2_stream(self, aria2_cmd, iso_filename, download_worker=None, poll_interval=0.5):
        """
        Chạy aria2c bằng subprocess, đọc stdout trong một luồng riêng, đưa dòng đọc được vào Queue.
        Bắt mọi ngoại lệ trong thread đọc để tránh crash ứng dụng khi pipe bị đóng đột ngột.
        Trả về returncode của tiến trình (int) hoặc None nếu không khởi chạy được.
        """
        try:
            self.aria2_process = subprocess.Popen(
                aria2_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW,
                bufsize=1
            )
        except Exception as e:
            # Không thể khởi chạy aria2
            print(f"[_run_aria2_stream] Lỗi khởi chạy aria2c: {e}")
            self.aria2_process = None
            return None

        output_queue = Queue()

        def _reader(proc, q):
            """Luồng đọc: phải bắt mọi exception để không làm rớt tiến trình chính."""
            try:
                # Dùng readline lặp cho tới EOF. Nếu pipe đột ngột đóng, có thể raise -> catch bên ngoài.
                while True:
                    try:
                        line = proc.stdout.readline()
                    except Exception as e:
                        print(f"[_reader] Lỗi khi đọc stdout aria2: {e}")
                        break
                    if line == '':
                        # EOF
                        break
                    q.put(line)
            except Exception as e:
                print(f"[_reader] Ngoại lệ bất ngờ: {e}")
            finally:
                # Đảm bảo luôn gửi sentinel hoàn tất
                try:
                    q.put(None)
                except Exception:
                    pass

        reader_thread = threading.Thread(target=_reader, args=(self.aria2_process, output_queue), daemon=True)
        reader_thread.start()

        try:
            # Vòng lặp chính: lấy dòng từ queue và xử lý; cho phép kiểm tra is_cancelling định kỳ
            while True:
                if getattr(self, "is_cancelling", False):
                    # Nếu user yêu cầu dừng, break ra để dọn dẹp
                    print("[_run_aria2_stream] is_cancelling được bật, sẽ dừng aria2.")
                    break

                # Nếu process đã kết thúc và queue rỗng -> thoát
                if self.aria2_process.poll() is not None and output_queue.empty():
                    break

                try:
                    line = output_queue.get(timeout=poll_interval)
                except Empty:
                    # timeout -> quay lại vòng để check is_cancelling hoặc poll
                    continue

                # sentinel: None nghĩa luồng đọc đã xong
                if line is None:
                    break

                line = line.strip()
                if not line:
                    continue

                # Debug/log
                print(f"[Aria2] {line}")

                # Cập nhật UI nếu có download_worker (giữ logic cũ của bạn)
                try:
                    m = re.search(r'\((\d{1,3})%\)', line)
                    if m and download_worker:
                        percent = int(m.group(1))
                        speed_match = re.search(r'DL:([^\s]+)', line)
                        eta_match = re.search(r'ETA:([^)]+)', line)
                        status_text = f"Đang tải {iso_filename}: {percent}%"
                        if speed_match:
                            status_text += f" ({speed_match.group(1)})"
                        if eta_match:
                            status_text += f" - ETA: {eta_match.group(1)}"
                        try:
                            download_worker.status.emit(status_text)
                        except Exception:
                            # Nếu emit lỗi thì bỏ qua, không làm crash
                            pass
                except Exception as e:
                    print(f"[_run_aria2_stream] Lỗi khi phân tích dòng: {e}")

            # Kết thúc vòng đọc: chờ process kết thúc (với timeout ngắn)
            try:
                if self.aria2_process and self.aria2_process.poll() is None:
                    self.aria2_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Nếu không tự exit, kill để dọn dẹp
                try:
                    self.aria2_process.kill()
                except Exception as e:
                    print(f"[_run_aria2_stream] Lỗi kill aria2: {e}")

        finally:

            try:
                output_queue.put(None)
            except Exception:
                pass

            # Join luồng đọc với timeout ngắn
            reader_thread.join(timeout=3)
            if reader_thread.is_alive():
                print("[_run_aria2_stream] Cảnh báo: reader_thread vẫn alive sau 3s; thread là daemon nên sẽ kết thúc khi app thoát.")

        return getattr(self.aria2_process, "returncode", None)
    
    def _download_task(self):
        """Tác vụ tải file theo hàng đợi, sử dụng _run_aria2_stream để chạy aria2 an toàn."""
        if not os.path.exists(config.ARIA2_EXE):
            raise FileNotFoundError("Chưa tìm thấy aria2c.exe.")

        total_downloads = len(self.downloads_queue)
        for i, item in enumerate(self.downloads_queue):
            if getattr(self, "is_cancelling", False):
                break

            name = item['name']
            self.download_worker.status.emit(f"({i+1}/{total_downloads}) Đang chuẩn bị tải {name}...")

            iso_url = ""
            header_list = []
            cookie_file = None
            selected_filename = item.get('selected_filename', None)

            # -- xác định iso_url (giữ nguyên logic cũ) --
            try:
                if item.get('is_gravesoft'):
                    self.download_worker.status.emit(f"Bước 1/2: Lấy link tải cho {name}...")
                    product_id = item['product_id']
                    sku_id = item['sku_id']
                    proxy_url = f"https://api.gravesoft.dev/msdl/proxy?product_id={product_id}&sku_id={sku_id}"

                    headers_api = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                    }
                    response = requests.get(proxy_url, headers=headers_api, timeout=20)
                    response.raise_for_status()
                    link_data = response.json()
                    options = link_data.get("ProductDownloadOptions", [])
                    if not options:
                        raise Exception("API không trả về ProductDownloadOptions.")
                    found = False
                    for opt in options:
                        uri = opt.get("Uri")
                        if not uri: continue
                        parsed_uri = urlparse(uri)
                        filename_from_uri = os.path.basename(parsed_uri.path)
                        if filename_from_uri == selected_filename:
                            iso_url = uri
                            found = True
                            break
                    if not found:
                        raise Exception(f"Không tìm thấy Uri khớp với filename: {selected_filename}")
                else:
                    data = item['data']
                    if data['type'] == 'fido':
                        if not os.path.exists(config.FIDO_SCRIPT_PATH):
                            raise FileNotFoundError("Chưa tìm thấy Fido.ps1.")
                        fido_version_map = {"Windows 11": "11", "Windows 10": "10"}
                        version_arg = fido_version_map.get(name)
                        arch_arg = "x64"
                        if name == "Windows 10":
                            for arch, rb in data.get('radios', {}).items():
                                if rb.isChecked():
                                    arch_arg = arch
                                    break
                        self.download_worker.status.emit(f"({i+1}/{total_downloads}) Đang lấy link cho {name}...")
                        fido_cmd = ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', config.FIDO_SCRIPT_PATH, '-Win', version_arg, '-Arch', arch_arg, '-Lang', 'Eng', '-GetUrl']
                        process = subprocess.run(fido_cmd, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        iso_url = process.stdout.strip()
                    elif data['type'] == 'direct':
                        iso_url = self.get_final_url(data['url'])
            except Exception as e:
                raise Exception(f"Không thể lấy URL cho {name}: {e}")

            if not iso_url or not iso_url.startswith("http"):
                raise Exception(f"Không lấy được URL hợp lệ cho {name}.")

            iso_filename = selected_filename if item.get('is_gravesoft') else os.path.basename(iso_url.split('?')[0])
            iso_filepath = os.path.join(config.ISOS_DIR, iso_filename)

            # Nếu có file .aria2 (dang dở) -> xóa
            aria2_control_file = iso_filepath + ".aria2"
            if os.path.exists(aria2_control_file):
                self.download_worker.status.emit("Phát hiện file tải dở. Đang dọn dẹp...")
                try:
                    os.remove(aria2_control_file)
                    if os.path.exists(iso_filepath):
                        os.remove(iso_filepath)
                    self.download_worker.status.emit("Đã dọn dẹp xong. Bắt đầu tải lại...")
                    time.sleep(1)
                except OSError as e:
                    raise Exception(f"Lỗi khi dọn dẹp file tải dở: {e}")

            if os.path.exists(iso_filepath):
                self.download_worker.status.emit(f"({i+1}/{total_downloads}) File {iso_filename} đã tồn tại. Bỏ qua.")
                self.download_worker.result.emit(iso_filepath)
                continue

            # Chuẩn bị command aria2
            self.download_worker.status.emit(f"({i+1}/{total_downloads}) Đang tải {iso_filename}...")
            aria2_cmd = [str(config.ARIA2_EXE), '--console-log-level=warn', '--summary-interval=1', '-c', '-x16', '-s16', '-d', str(config.ISOS_DIR), '-o', iso_filename]
            for header in header_list:
                aria2_cmd.extend(['--header', header])
            if cookie_file:
                aria2_cmd.extend(['--load-cookies', cookie_file])
            aria2_cmd.append(iso_url)

            # GỌI helper an toàn để chạy aria2 và đọc output
            try:
                rc = self._run_aria2_stream(aria2_cmd, iso_filename, download_worker=self.download_worker)
            except Exception as e:
                # Nếu helper raise lỗi, bọc và ném tiếp để on_download_finished xử lý
                raise Exception(f"Lỗi khi chạy aria2c: {e}")

            # Dọn cookie tạm (nếu có)
            if cookie_file and os.path.exists(cookie_file):
                try: os.remove(cookie_file)
                except OSError: pass

            if getattr(self, "is_cancelling", False):
                # Nếu user đã hủy trong quá trình tải
                break

            # Kiểm tra mã trả về
            if rc is None:
                raise Exception("Không thể khởi chạy aria2 (rc=None).")
            if rc != 0:
                raise Exception(f"aria2 thất bại với mã lỗi {rc}")

            # Thành công
            self.download_worker.result.emit(iso_filepath)

    def on_download_result(self, iso_path):
        """Xử lý khi có kết quả từ luồng tải về."""
        if iso_path and not self.is_cancelling:
            self.main_app.config["iso_path"] = iso_path
            self.add_iso_to_list(iso_path)
            self.download_status_label.setText(f"Tải thành công!\n{os.path.basename(iso_path)}")

    def on_download_finished(self, success, message):
        was_cancelled = self.is_cancelling
        self.is_cancelling = False
        self._set_ui_state(downloading=False)
        if was_cancelled:
            self.download_status_label.setText("Đã hủy tải xuống.")
            self._reset_arch_radio_buttons()
            return
        if not success:
            self.main_app.show_error(message)
            self.download_status_label.setText(f"Lỗi: {message.splitlines()[-1]}")

    def _reset_arch_radio_buttons(self):
            # Bỏ chọn radio button
            for win_data in self.win_options.values():
                if 'radios' in win_data:
                    for radio_button in win_data['radios'].values():
                        if radio_button.isChecked():
                            self.arch_button_group.setExclusive(False)
                            radio_button.setChecked(False)
                            self.arch_button_group.setExclusive(True)
                            break

    def stop_download_process(self):
        """Dừng tiến trình aria2c.exe VÀ luồng QThread quản lý nó một cách an toàn."""
        # Đánh cờ is_cancelling để helper/luồng biết cần dừng
        self.is_cancelling = True

        # Nếu tiến trình aria2 đang chạy, cố terminate/kills
        try:
            if getattr(self, "aria2_process", None) and self.aria2_process.poll() is None:
                print("[stop_download_process] Đang terminate aria2...")
                try:
                    self.aria2_process.terminate()
                    try:
                        self.aria2_process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        self.aria2_process.kill()
                except Exception as e:
                    print(f"[stop_download_process] Lỗi khi terminate/kill aria2: {e}")
        except Exception as e:
            print(f"[stop_download_process] Lỗi kiểm tra aria2_process: {e}")

        # Đóng stdout nếu còn mở
        try:
            if getattr(self, "aria2_process", None) and getattr(self.aria2_process, "stdout", None):
                try:
                    self.aria2_process.stdout.close()
                except Exception:
                    pass
        except Exception:
            pass

        # Reset object
        self.aria2_process = None

        # Dừng QThread download_worker (nếu có)
        if hasattr(self, 'download_worker') and self.download_worker.isRunning():
            print("[stop_download_process] Đã yêu cầu dừng download_worker (luồng sẽ tự kết thúc).")
        
        # Reset object
        self.aria2_process = None

        # Xóa cookie tạm
        try:
            temp_dir = tempfile.gettempdir()
            for file in os.listdir(temp_dir):
                if file.startswith("cookies_") and file.endswith(".txt"):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except OSError:
                        pass
        except Exception:
            pass

    def cancel_download_clicked(self):
        """Xử lý khi người dùng bấm nút Hủy Tải."""
        reply = self.main_app.show_themed_message("Hủy Tải",
                                    "Bạn có chắc muốn dừng quá trình tải xuống không?",
                                    icon=QMessageBox.Icon.Question,
                                    buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    defaultButton=QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.is_cancelling = True
            self.stop_download_process()
            self.download_status_label.setText("Đang hủy tải...")
            # Việc reset UI sẽ được thực hiện trong on_download_finished