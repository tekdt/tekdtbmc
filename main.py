import config
import os
import sys
import subprocess
import json
import psutil
import webbrowser
from workers import Worker
from ui.page_device import PageDeviceSelect
from ui.page_iso import PageISOSelect
from ui.page_finalize import PageFinalize
from ui.utils import windows_api, tool_manager, helpers

# --- Import thư viện PySide6 ---
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QDialog, QComboBox, QDialogButtonBox,
                             QStackedWidget, QLabel, QMessageBox, QMenu, QGraphicsOpacityEffect, QPushButton, QLineEdit)
from PySide6.QtGui import QIcon, QAction, QActionGroup
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, Signal, QTimer, qInstallMessageHandler, QFileSystemWatcher

def qt_message_handler(mode, context, message):
    """
    Hàm tùy chỉnh để lọc các thông điệp cảnh báo không mong muốn từ Qt.
    """
    # Các chuỗi trong thông điệp cần bỏ qua
    suppress_list = ["QPainter::", "Paint device returned engine == 0"]
    
    # Nếu bất kỳ chuỗi nào trong danh sách xuất hiện trong thông điệp, bỏ qua nó
    if any(text in message for text in suppress_list):
        return
    
    # In các thông điệp khác ra stderr như mặc định
    # Điều này giúp giữ lại các thông báo lỗi quan trọng khác.
    original_handler = sys.stderr.write
    original_handler(f"{message}\n")

# --- Lớp chính của ứng dụng ---
class USBBootCreator(QMainWindow):
    new_version_found = Signal(str, str)
    
    def __init__(self):
        """
        Hàm khởi tạo của cửa sổ chính.
        Thiết lập các biến, worker, timer, kiểm tra quyền admin,
        và khởi tạo giao diện người dùng (UI).
        """
        super().__init__()
        self.active_workers = []
        self.ais_process = None
        self.ais_hwnd = None
        self.ais_monitor_timer = QTimer(self)
        self.ais_monitor_timer.timeout.connect(self._check_ais_status)
        self.usb_monitor_timer = QTimer(self)
        self.usb_monitor_timer.timeout.connect(self._check_selected_usb_presence)
        self.is_checking_usb = False
        
        # Khởi tạo File System Watcher để theo dõi app_config.json
        self.ais_config_path = str(config.TEKDTAIS_DIR / "app_config.json")
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self._on_ais_config_changed)
        
        # --- Kiểm tra quyền admin và nâng quyền nếu cần ---
        if not windows_api.is_admin():
            print("Không có quyền admin, đang thử nâng quyền...")
            if self.elevate_privileges():
                sys.exit(0)
            else:
                self.show_themed_message("Lỗi Quyền Admin", 
                         "Không thể nâng quyền quản trị viên. Ứng dụng sẽ thoát.", 
                         icon=QMessageBox.Icon.Critical)
                sys.exit(1)
        
        self.setWindowTitle(f"TekDT BMC v{config.APP_VERSION}")
        if config.ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(config.ICON_PATH)))
        else:
            print(f"Cảnh báo: Không tìm thấy file icon tại '{config.ICON_PATH}'")
            self.setWindowIcon(QIcon())
        
        # Tính toán và thiết lập kích thước cửa sổ dựa trên màn hình
        # Lấy thông tin màn hình chính
        screen = QApplication.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            desired_width = int(available_geometry.width() * 0.6)
            desired_height = int(available_geometry.height() * 0.9)
            
            # Thiết lập kích thước ban đầu cho cửa sổ
            self.resize(desired_width, desired_height)
            
            # Cập nhật kích thước tối thiểu để không bị co quá nhỏ
            self.setMinimumSize(int(desired_width * 0.7), int(desired_height * 0.7))
        else:
            # Fallback về kích thước cố định nếu không lấy được thông tin màn hình
            self.setMinimumSize(800, 600)
            self.resize(960, 720)
        
        self.config = {
            "device": None,
            "device_name": None,
            "partition_scheme": "GPT",
            "filesystem": "ExFAT",
            "theme": None,
            "fill_space": True,
            "iso_list": [],
            "windows_edition": None,
            "windows_edition_index": None,
            "copy_ais_selection_only": True, 
        }

        self.config["device_details"] = None
        self.load_config()
        
        self.init_ui()
        self.apply_stylesheet()
        self.new_version_found.connect(self.prompt_for_update)
        windows_api.install_wincdemu_driver()
        
        self.lock_ui_for_updates()
        self.check_for_updates()

    def init_ui(self):
        # --- Widget chính và layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Nút Menu (Hamburger) ---
        self.menu_button = QPushButton("☰")
        self.menu_button.setObjectName("MenuButton")
        self.menu_button.setFixedSize(40, 40)
        self.menu_button.clicked.connect(self.show_main_menu)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.menu_button, alignment=Qt.AlignmentFlag.AlignLeft)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # --- Stacked Widget cho các bước ---
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        self.page1 = PageDeviceSelect(self)
        self.page2 = PageISOSelect(self)
        self.page3 = PageFinalize(self)

        self.stacked_widget.addWidget(self.page1)
        self.stacked_widget.addWidget(self.page2)
        self.stacked_widget.addWidget(self.page3)
        
        self.stacked_widget.currentChanged.connect(self.on_page_changed)

        self.init_status_label = QLabel("Đang khởi tạo...")
        self.init_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.init_status_label.setStyleSheet("font-size: 11pt; color: #ECEFF4;")
        main_layout.addWidget(self.init_status_label)
        
        self.page1.next_button.clicked.connect(lambda: self.go_to_page(1))
        self.page2.next_button.clicked.connect(lambda: self.go_to_page(2))
        self.page2.back_button.clicked.connect(lambda: self.go_to_page(0))
        self.page3.back_button.clicked.connect(lambda: self.go_to_page(1))
        self.page3.start_button.clicked.connect(self.confirm_and_start)

    def apply_stylesheet(self):
        """Áp dụng màu sắc và style cho ứng dụng."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2E3440;
            }
            QWidget {
                color: #D8DEE9;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            #MenuButton {
                font-size: 18pt;
                font-weight: bold;
                border: none;
                background-color: transparent;
            }
            #MenuButton:hover {
                background-color: #4C566A;
            }
            QStackedWidget {
                background-color: transparent;
            }
            QLabel {
                font-size: 12pt;
            }
            QLabel#TitleLabel {
                font-size: 20pt;
                font-weight: bold;
                color: #88C0D0;
                padding-bottom: 10px;
            }
            /* CSS cho label thông báo trạng thái */
            QLabel#DownloadStatusLabel {
                color: #A3BE8C; /* Màu xanh lá cây sáng, dễ đọc */
                font-weight: bold;
                padding-top: 5px;
            }
            QPushButton {
                background-color: #5E81AC;
                border-radius: 5px;
                padding: 10px;
                font-size: 12pt;
                font-weight: bold;
                border: 1px solid #4C566A;
            }
            QPushButton:hover {
                background-color: #81A1C1;
            }
            QPushButton:pressed {
                background-color: #88C0D0;
            }
            QPushButton:disabled {
                background-color: #4C566A;
                color: #6a7180;
            }
            QComboBox {
                padding: 8px;
                border: 1px solid #4C566A;
                border-radius: 5px;
                background-color: #3B4252;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #3B4252;
                border: 1px solid #4C566A;
                selection-background-color: #5E81AC;
            }
            QCheckBox {
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #4C566A;
                border-radius: 5px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #4C566A;
                border-radius: 5px;
                background-color: #3B4252;
            }
            /* CSS cho danh sách ISO để tăng độ tương phản */
            QListWidget {
                background-color: #3B4252;
                border-radius: 5px;
                border: 1px solid #4C566A;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px; /* Bo góc nhẹ cho mỗi item */
            }
            QListWidget::item:hover {
                background-color: #4C566A;
            }
            QListWidget::item:selected {
                background-color: #5E81AC; /* Màu xanh đậm hơn khi chọn */
                color: #ECEFF4; /* Màu chữ trắng sáng khi chọn */
            }
            QProgressBar {
                border: 1px solid #4C566A;
                border-radius: 5px;
                text-align: center;
                color: #ECEFF4;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #A3BE8C;
                border-radius: 5px;
            }
            QMenu {
                background-color: #3B4252;
                border: 1px solid #434C5E;
            }
            QMenu::item:selected {
                background-color: #5E81AC;
            }
        """)

    def prompt_for_update(self, new_version, download_url):
        """Hiển thị hộp thoại hỏi người dùng có muốn cập nhật không."""
        message = (f"Đã có phiên bản mới <b>{new_version}</b>!\n"
                   f"Phiên bản hiện tại của bạn là {APP_VERSION}.\n\n"
                   "Bạn có muốn truy cập trang tải về không?")
        
        reply = self.show_themed_message("Có phiên bản mới!", message,
                                       icon=QMessageBox.Icon.Information,
                                       buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       defaultButton=QMessageBox.StandardButton.Yes)
        
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(download_url)

 
    def closeEvent(self, event):
        """Sự kiện đóng ứng dụng, hiển thị xác nhận và đảm bảo dừng tất cả các tác vụ nền."""
        
        # Thêm hộp thoại xác nhận trước khi thoát
        reply = self.show_themed_message(
            "Xác nhận thoát",
            "Bạn có chắc chắn muốn thoát chương trình không?",
            icon=QMessageBox.Icon.Question,
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            defaultButton=QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            event.ignore()  # Hủy sự kiện đóng cửa sổ
            return

        # Nếu người dùng chọn "Yes", tiếp tục với quy trình dọn dẹp hiện có
        print("Cửa sổ đang đóng, bắt đầu quy trình dọn dẹp...")

        # Dừng các tiến trình và timer không phải QThread trước
        self.usb_monitor_timer.stop()
        self.page2.is_cancelling = True 
        if self.page2.aria2_process:
             self.page2.aria2_process.kill()
        self._stop_tekdtais()
        windows_api.uninstall_wincdemu_driver()

        # Dừng tất cả các luồng worker đang chạy
        for worker in list(self.active_workers):
            if worker.isRunning():
                print(f"Đang yêu cầu dừng luồng '{worker.name}'...")
                worker.terminate()
                if not worker.wait(5000):
                    print(f"CẢNH BÁO: Luồng '{worker.name}' không phản hồi sau 5 giây.")

        print("Quy trình dọn dẹp hoàn tất. Ứng dụng sẽ đóng.")
        event.accept() # Chấp nhận sự kiện đóng cửa sổ
    
    def show_themed_message(self, title, text, icon=QMessageBox.Icon.NoIcon, 
                            buttons=QMessageBox.StandardButton.Ok, 
                            defaultButton=QMessageBox.StandardButton.NoButton):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon)
        msg_box.setStandardButtons(buttons)
        if defaultButton != QMessageBox.StandardButton.NoButton:
            msg_box.setDefaultButton(defaultButton)
        
        # Áp dụng stylesheet tùy chỉnh
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #3B4252;
                color: #D8DEE9;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            QMessageBox QLabel {
                color: #D8DEE9;
            }
            QMessageBox QPushButton {
                background-color: #5E81AC;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 11pt;
                font-weight: bold;
                border: 1px solid #4C566A;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #81A1C1;
            }
            QMessageBox QPushButton:pressed {
                background-color: #88C0D0;
            }
        """)
        return msg_box.exec()

    def start_tekdtais(self):
        if not os.path.exists(config.TEKDTAIS_EXE) or self.is_tekdtais_running():
            return

        if os.path.exists(config.SHUTDOWN_SIGNAL_TEKDTAIS):
            try:
                os.remove(config.SHUTDOWN_SIGNAL_TEKDTAIS)
                print(f"Đã xóa file tín hiệu shutdown_signal.txt cho TekDT AIS: {config.SHUTDOWN_SIGNAL_TEKDTAIS}")
            except OSError as e:
                print(f"Không thể xóa file tín hiệu shutdown_signal.txt cho TekDT AIS: {e}")

        try:
            print("Đang khởi chạy TekDT AIS ở chế độ nền (ẩn hoàn toàn)...")
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

            self.ais_process = subprocess.Popen(
                [config.TEKDTAIS_EXE, "--embed-mode"],
                cwd=config.TEKDTAIS_DIR,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )

            # Reset trạng thái
            self.ais_hwnds = None
            self.ais_hwnd = None

            # Khởi động timer tìm cửa sổ
            self.find_ais_window_timer = QTimer(self)
            self.find_ais_window_timer.attempts = 0
            self.find_ais_window_timer.timeout.connect(
                lambda: windows_api._find_ais_window_task(self)
            )
            self.find_ais_window_timer.start(250)
            self.ais_monitor_timer.start(5000)

        except Exception as e:
            self.show_themed_message("Lỗi", f"Không thể khởi chạy TekDT_AIS.exe:\n{e}", icon=QMessageBox.Icon.Warning)

    def save_config(self):
        """Lưu cấu hình hiện tại vào file JSON."""
        try:
            with open(config.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Không thể lưu cấu hình vào {config.CONFIG_FILE}: {e}")

    def load_config(self):
        """Tải cấu hình từ file JSON nếu tồn tại, nếu không thì tạo mới."""
        if config.CONFIG_FILE.exists():
            try:
                with open(config.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Cập nhật config hiện tại với các giá trị đã tải
                    # Điều này giúp giữ lại các khóa mới nếu phiên bản mới có thêm tùy chọn
                    self.config.update(loaded_config)
                    print("Đã tải cấu hình từ tekdt_bmc.json")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Lỗi khi đọc file cấu hình, sử dụng mặc định: {e}")
                # Nếu file bị lỗi, lưu lại cấu hình mặc định
                self.save_config()
        else:
            # Nếu file không tồn tại, tạo nó với các giá trị mặc định
            print("Không tìm thấy file cấu hình, đang tạo file mới với giá trị mặc định.")
            self.save_config()
    
    def _create_and_start_worker(self, name, target, on_result=None, on_finished=None, on_status=None, on_progress=None, *args, **kwargs):
        """
        Tạo Worker, hỗ trợ 2 kiểu truyền tham số cho target:
          - truyền positional trực tiếp: _create_and_start_worker(..., product_id)
          - hoặc truyền bằng keyword 'args' (danh sách/tuple) như code cũ: _create_and_start_worker(..., args=[product_id])
        """
        # Nếu caller dùng args=[...], lấy ra
        forwarded_args = []
        if 'args' in kwargs and isinstance(kwargs['args'], (list, tuple)):
            forwarded_args = list(kwargs.pop('args'))

        # Nếu caller dùng worker_kwargs= {...} để truyền kwargs cho target
        forwarded_kwargs = {}
        if 'worker_kwargs' in kwargs and isinstance(kwargs['worker_kwargs'], dict):
            forwarded_kwargs = kwargs.pop('worker_kwargs')

        # Bất kỳ kwargs còn lại (không phải on_result/on_finished...) sẽ coi là worker kwargs
        # (nếu bạn không muốn như vậy, có thể thay đổi)
        # Gộp forwarded_kwargs với bất kỳ kwargs còn lại
        for k in list(kwargs.keys()):
            # tránh ghi đè 'on_result','on_finished','on_status','on_progress' (đã là tham số)
            if k not in ('on_result','on_finished','on_status','on_progress'):
                forwarded_kwargs[k] = kwargs.pop(k)

        # Kết hợp positional args (truyền cả forwarded_args và *args)
        combined_args = forwarded_args + list(args)

        worker = Worker(name, target, *combined_args, **forwarded_kwargs)

        # Kết nối các tín hiệu nếu có hàm xử lý tương ứng
        if on_result: worker.result.connect(on_result)
        if on_finished: worker.finished.connect(on_finished)
        if on_status: worker.status.connect(on_status)
        if on_progress: worker.progress.connect(on_progress)

        # Kết nối tín hiệu tự hủy theo dõi
        worker.about_to_finish.connect(self._on_worker_finished)

        # Thêm vào danh sách theo dõi và khởi chạy
        self.active_workers.append(worker)
        worker.start()
        return worker

    def _on_worker_finished(self, worker_thread):
        """Xóa worker khỏi danh sách theo dõi khi nó kết thúc."""
        if worker_thread in self.active_workers:
            self.active_workers.remove(worker_thread)
    
    def _check_ais_status(self):
        """Định kỳ kiểm tra trạng thái của TekDT AIS và chỉ khởi động lại nếu ở page3."""
        if self.stacked_widget.currentWidget() != self.page3:
            print("Không ở page3, không kiểm tra trạng thái TekDT AIS.")
            self.ais_monitor_timer.stop()  # Dừng timer nếu không ở page3
            return

        if self.ais_process and not self.is_tekdtais_running():
            print("Phát hiện TekDT AIS đã tắt. Đang khởi động lại...")
            self.ais_monitor_timer.stop()
            self.ais_process = None
            self.ais_hwnds = None
            self.start_tekdtais()
    
    def is_tekdtais_running(self):
        return self.ais_process and self.ais_process.poll() is None

    def _stop_tekdtais(self):
        self.ais_monitor_timer.stop()
        if self.is_tekdtais_running():
            print(f"Đang dừng tiến trình TekDT AIS (PID: {self.ais_process.pid})...")
            with open(os.path.join(config.TEKDTAIS_DIR, "shutdown_signal.txt"), "w") as f:
                f.write("shutdown")
            try:
                self.ais_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("TekDT AIS không tự thoát, buộc dừng tất cả tiến trình liên quan...")
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        exe_path = proc.info.get('exe')
                        name = proc.info.get('name')
                        if (exe_path and "tekdt_ais.exe" in exe_path) or \
                           (name == "python.exe" and proc.parent() and proc.parent().exe() and "tekdt_ais.exe" in proc.parent().exe()):
                            print(f"Dừng tiến trình {proc.info['name']} (PID: {proc.info['pid']})")
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            signal_file = os.path.join(config.TEKDTAIS_DIR, "shutdown_signal.txt")
            if os.path.exists(signal_file):
                try:
                    os.remove(signal_file)
                except OSError as e:
                    print(f"Không thể xóa file tín hiệu: {e}")
            self.ais_process = None
            self.ais_hwnds = None
    
    def _cleanup_ais_process_task(self):
        """
        Tác vụ này chỉ chạy trong worker thread để dọn dẹp tiến trình TekDT AIS.
        Nó không tương tác với bất kỳ QTimer nào.
        """
        if self.is_tekdtais_running():
            print(f"Đang dừng tiến trình TekDT AIS (PID: {self.ais_process.pid})...")
            # Phần code xử lý tiến trình được giữ nguyên từ hàm _stop_tekdtais
            with open(os.path.join(config.TEKDTAIS_DIR, "shutdown_signal.txt"), "w") as f:
                f.write("shutdown")
            try:
                self.ais_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("TekDT AIS không tự thoát, buộc dừng tất cả tiến trình liên quan...")
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        exe_path = proc.info.get('exe')
                        name = proc.info.get('name')
                        if (exe_path and "tekdt_ais.exe" in exe_path) or (name == "python.exe" and proc.parent() and proc.parent().exe() and "tekdt_ais.exe" in proc.parent().exe()):
                            print(f"Dừng tiến trình {proc.info['name']} (PID: {proc.info['pid']})")
                            proc.kill()
                            pass
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            signal_file = os.path.join(config.TEKDTAIS_DIR, "shutdown_signal.txt")
            if os.path.exists(signal_file):
                os.remove(signal_file)
        
        # Reset các biến trạng thái
        self.ais_process = None
        self.ais_hwnd = None
    
    def on_page_changed(self, index):
        # Quản lý việc theo dõi file config của AIS
        # Dừng theo dõi khi rời khỏi trang 3
        if self.file_watcher.files():
            self.file_watcher.removePaths(self.file_watcher.files())
            print(f"Đã dừng theo dõi file: {self.ais_config_path}")

        if index == 2: # Khi chuyển đến trang Finalize
            windows_api.embed_ais_window(self)
            self.ais_monitor_timer.start(5000)
            self._update_capacity_check()
            # Bắt đầu theo dõi file khi vào trang 3
            if os.path.exists(self.ais_config_path):
                self.file_watcher.addPath(self.ais_config_path)
                print(f"Đang theo dõi thay đổi trên file: {self.ais_config_path}")
        elif self.ais_hwnd:
            windows_api.hide_ais_window(self)
    
    # Hàm xử lý khi file app_config.json thay đổi
    def _on_ais_config_changed(self, path):
        print(f"Phát hiện thay đổi trong '{path}'. Đang tính toán lại dung lượng...")
        # Một số trình soạn thảo xóa và tạo lại file, vì vậy chúng ta cần thêm lại đường dẫn
        # để đảm bảo tiếp tục theo dõi.
        QTimer.singleShot(100, lambda: self.file_watcher.addPath(path))
        self._update_capacity_check()

    def _get_dir_size(self, start_path, ignore_func=None):
        """Tính tổng dung lượng của một thư mục, có hỗ trợ hàm ignore."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(start_path):
            if ignore_func:
                # Lọc danh sách thư mục con để không duyệt vào
                ignored_dirs = ignore_func(dirpath, dirnames)
                dirnames[:] = [d for d in dirnames if d not in ignored_dirs]
                
                # Lọc danh sách file
                ignored_files = ignore_func(dirpath, filenames)
                filenames[:] = [f for f in filenames if f not in ignored_files]

            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size

    def _update_capacity_check(self):
        """Tính toán tổng dung lượng cần thiết và cập nhật UI."""
        label = self.page3.capacity_status_label
        start_button = self.page3.start_button
        
        label.setText("Đang tính toán dung lượng yêu cầu...")
        label.setStyleSheet("font-weight: bold; padding: 10px; color: #D8DEE9;")
        label.setVisible(True)
        QApplication.processEvents() # Force update UI

        # --- Bắt đầu tính toán ---
        total_required_size = 0

        # 1. Dung lượng ISOs
        for iso in self.config.get('iso_list', []):
            try:
                total_required_size += os.path.getsize(iso['path'])
            except FileNotFoundError:
                self.show_error(f"Không tìm thấy file ISO: {iso['path']}. Vui lòng xóa khỏi danh sách.")
                return

        # 2. Dung lượng Drivers
        drivers_part1 = config.DRIVERS_DIR / "Drivers.7z.001"
        drivers_part2 = config.DRIVERS_DIR / "Drivers.7z.002"
        if drivers_part1.exists() and drivers_part2.exists():
            total_required_size += os.path.getsize(drivers_part1)
            total_required_size += os.path.getsize(drivers_part2)

        # 3. Dung lượng Theme
        if self.config.get('theme'):
            theme_path = config.THEMES_DIR / self.config['theme']
            if theme_path.exists():
                total_required_size += os.path.getsize(theme_path)

        # 4. Dung lượng TekDT AIS (phức tạp hơn)
        if config.TEKDTAIS_DIR.exists():
            if not self.config.get("copy_ais_selection_only", True):
                # Sao chép toàn bộ
                total_required_size += self._get_dir_size(config.TEKDTAIS_DIR)
            else:
                # Sao chép chọn lọc
                config_path = config.TEKDTAIS_DIR / "app_config.json"
                source_apps_dir = config.TEKDTAIS_DIR / "Apps"
                apps_to_copy = []
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            app_config = json.load(f)
                        apps_to_copy = [name for name, settings in app_config.items() if settings.get("auto_install")]
                    except Exception as e:
                        print(f"Lỗi đọc app_config.json, sẽ tính toàn bộ size: {e}")
                        total_required_size += self._get_dir_size(config.TEKDTAIS_DIR)
                
                def ignore_apps(directory, contents):
                    if config.Path(directory).resolve() == source_apps_dir.resolve():
                        return [item for item in contents if item not in apps_to_copy]
                    return []
                total_required_size += self._get_dir_size(config.TEKDTAIS_DIR, ignore_func=ignore_apps)

        # 5. Dung lượng dự phòng (Ventoy, file config, metadata...) - ~500MB
        overhead = 500 * 1024 * 1024
        total_required_size += overhead

        # --- So sánh và cập nhật UI ---
        device_details = self.config.get('device_details')
        if not device_details:
            label.setText("Vui lòng chọn một USB ở Bước 1.")
            label.setStyleSheet("font-weight: bold; padding: 10px; color: #EBCB8B;") # Vàng
            start_button.setEnabled(False)
            return

        usb_size = device_details.get('Size', 0)
        
        # Chuyển đổi sang GB để hiển thị
        required_gb = total_required_size / (1024**3)
        usb_gb = usb_size / (1024**3)

        if total_required_size > usb_size:
            message = (f"DUNG LƯỢNG KHÔNG ĐỦ!<br>"
                       f"Yêu cầu: <b>{required_gb:.2f} GB</b> / Sẵn có: <b>{usb_gb:.2f} GB</b>")
            label.setText(message)
            label.setStyleSheet("font-weight: bold; padding: 10px; color: #BF616A;") # Đỏ
            start_button.setEnabled(False)
        else:
            message = (f"Đủ dung lượng<br>"
                       f"Yêu cầu: <b>{required_gb:.2f} GB</b> / Sẵn có: <b>{usb_gb:.2f} GB</b>")
            label.setText(message)
            label.setStyleSheet("font-weight: bold; padding: 10px; color: #A3BE8C;") # Xanh
            start_button.setEnabled(True)

    def lock_ui_for_updates(self):
        """Vô hiệu hóa các thành phần UI chính trong khi kiểm tra cập nhật."""
        self.stacked_widget.setEnabled(False)
        self.menu_button.setEnabled(False)
        self.init_status_label.setText("Đang khởi tạo và kiểm tra các công cụ...")
        self.init_status_label.setVisible(True)
    
    def go_to_page(self, index):
        if index == 0:
            self.usb_monitor_timer.stop()
            self.config["device_details"] = None
        """Chuyển trang với hiệu ứng mờ dần (fade) ổn định."""
        current_widget = self.stacked_widget.currentWidget()
        if not current_widget:
            self.stacked_widget.setCurrentIndex(index)
            return

        # Tạo hiệu ứng mờ (fade out) cho widget hiện tại
        effect_out = QGraphicsOpacityEffect(current_widget)
        current_widget.setGraphicsEffect(effect_out)
        self.anim_out = QPropertyAnimation(effect_out, b"opacity")
        self.anim_out.setDuration(200)
        self.anim_out.setStartValue(1.0)
        self.anim_out.setEndValue(0.0)
        self.anim_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        # Khi fade out xong, chuyển trang và fade in
        self.anim_out.finished.connect(lambda: self.switch_and_fade_in(index))
        QApplication.processEvents()

    def switch_and_fade_in(self, index):
        """Hàm phụ trợ: Chuyển index và thực hiện fade in."""
        self.stacked_widget.setCurrentIndex(index)
        new_widget = self.stacked_widget.currentWidget()

        # Tạo hiệu ứng hiện (fade in) cho widget mới
        effect_in = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(effect_in)
        self.anim_in = QPropertyAnimation(effect_in, b"opacity")
        self.anim_in.setDuration(200)
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(1.0)
        self.anim_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim_in.finished.connect(lambda: self.finalize_page_after_animation(new_widget))
        self.anim_in.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def finalize_page_after_animation(self, widget):
        """Xử lý sau khi hiệu ứng hoàn tất - đặc biệt cho trang 3"""
        widget.update()
        widget.repaint()
        QApplication.processEvents()
    
    def show_main_menu(self):
        """
        Hiển thị menu cấu hình chính (menu hamburger).
        Menu này cho phép người dùng thay đổi các tùy chọn như
        Partition Scheme, Filesystem, Theme, và các cài đặt khác.
        """
        menu = QMenu(self)
        
        # --- Partition Scheme ---
        scheme_menu = menu.addMenu("Cấu trúc ổ đĩa (Partition Scheme)")
        gpt_action = QAction("GPT (UEFI)", self, checkable=True)
        gpt_action.setChecked(self.config["partition_scheme"] == "GPT")
        gpt_action.triggered.connect(lambda: self.set_partition_scheme("GPT"))
        mbr_action = QAction("MBR (Legacy BIOS)", self, checkable=True)
        mbr_action.setChecked(self.config["partition_scheme"] == "MBR")
        mbr_action.triggered.connect(lambda: self.set_partition_scheme("MBR"))
        scheme_group = QActionGroup(self)
        scheme_group.addAction(gpt_action)
        scheme_group.addAction(mbr_action)
        scheme_menu.addAction(gpt_action)
        scheme_menu.addAction(mbr_action)

        # --- Filesystem ---
        fs_menu = menu.addMenu("Định dạng (Filesystem)")
        exfat_action = QAction("ExFAT", self, checkable=True)
        exfat_action.setChecked(self.config["filesystem"] == "ExFAT")
        exfat_action.triggered.connect(lambda: self.set_filesystem("ExFAT"))
        ntfs_action = QAction("NTFS", self, checkable=True)
        ntfs_action.setChecked(self.config["filesystem"] == "NTFS")
        ntfs_action.triggered.connect(lambda: self.set_filesystem("NTFS"))
        fat32_action = QAction("FAT32", self, checkable=True)
        fat32_action.setChecked(self.config["filesystem"] == "FAT32")
        fat32_action.triggered.connect(lambda: self.set_filesystem("FAT32"))
        fs_group = QActionGroup(self)
        fs_group.addAction(exfat_action)
        fs_group.addAction(ntfs_action)
        fs_group.addAction(fat32_action)
        fs_menu.addAction(exfat_action)
        fs_menu.addAction(ntfs_action)
        fs_menu.addAction(fat32_action)
        
        # --- Fill Remaining Space ---
        fill_menu = menu.addMenu("Lấp đầy dung lượng")
        yes_action = QAction("Có", self, checkable=True)
        yes_action.setChecked(self.config.get("fill_space", True))
        yes_action.triggered.connect(lambda: self.set_fill_space(True))
        
        no_action = QAction("Không", self, checkable=True)
        no_action.setChecked(not self.config.get("fill_space", True))
        no_action.triggered.connect(lambda: self.set_fill_space(False))

        fill_group = QActionGroup(self)
        fill_group.addAction(yes_action)
        fill_group.addAction(no_action)
        fill_menu.addAction(yes_action)
        fill_menu.addAction(no_action)
        
        # Tùy chọn sao chép TekDT AIS
        menu.addSeparator()
        ais_copy_menu = menu.addMenu("Lọc và chỉ lấy những phần mềm được Thêm")
        
        yes_ais_action = QAction("Yes", self, checkable=True)
        # Mặc định là True nếu chưa có trong config
        yes_ais_action.setChecked(self.config.get("copy_ais_selection_only", True))
        yes_ais_action.triggered.connect(lambda: self.set_copy_ais_selection(True))

        no_ais_action = QAction("No", self, checkable=True)
        no_ais_action.setChecked(not self.config.get("copy_ais_selection_only", True))
        no_ais_action.triggered.connect(lambda: self.set_copy_ais_selection(False))

        ais_copy_group = QActionGroup(self)
        ais_copy_group.addAction(yes_ais_action)
        ais_copy_group.addAction(no_ais_action)
        ais_copy_menu.addAction(yes_ais_action)
        ais_copy_menu.addAction(no_ais_action)
        
        menu.addSeparator()

        # --- Themes ---
        theme_menu = menu.addMenu("Giao diện (Ventoy Theme)")
        no_theme_action = QAction("Mặc định (Không có)", self, checkable=True)
        no_theme_action.setChecked(self.config["theme"] is None)
        no_theme_action.triggered.connect(lambda: self.set_theme(None))
        theme_menu.addAction(no_theme_action)
        theme_group = QActionGroup(self)
        theme_group.addAction(no_theme_action)
        
        try:
            if not config.THEMES_DIR.exists():
                print("Thư mục Themes không tồn tại, bỏ qua việc tải theme.")
            else:
                for theme_file in os.listdir(config.THEMES_DIR):
                    if theme_file.endswith(".zip"):
                        theme_name = os.path.splitext(theme_file)[0]
                        action = QAction(theme_name, self, checkable=True)
                        action.setChecked(self.config["theme"] == theme_file)
                        action.triggered.connect(lambda checked, t=theme_file: self.set_theme(t))
                        theme_group.addAction(action)
                        theme_menu.addAction(action)
        except FileNotFoundError:
            pass

        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def set_partition_scheme(self, scheme):
        self.config["partition_scheme"] = scheme
        print(f"Đã chọn cấu trúc: {scheme}")
        self.save_config()
        self._update_capacity_check()

    def set_filesystem(self, fs):
        self.config["filesystem"] = fs
        print(f"Đã chọn định dạng: {fs}")
        self.save_config()
        self._update_capacity_check()

    def set_theme(self, theme_file):
        self.config["theme"] = theme_file
        print(f"Đã chọn theme: {theme_file}")
        self.save_config()
        self._update_capacity_check()

    def set_fill_space(self, fill):
        self.config["fill_space"] = fill
        print(f"Đã chọn Lấp đầy dung lượng: {'Có' if fill else 'Không'}")
        self.save_config()
        self._update_capacity_check()

    def check_for_updates(self):
        self.update_worker = self._create_and_start_worker(
            name="ToolUpdater",
            target=lambda: tool_manager._update_task(self),
            on_status=self.init_status_label.setText,
            on_finished=self.on_updates_finished
        )
 
    def on_updates_finished(self, success, message):
        """Kích hoạt lại UI sau khi cập nhật công cụ hoàn tất."""
        if success:
            self.init_status_label.setText("Các công cụ đã sẵn sàng!")
            QTimer.singleShot(1500, lambda: self.init_status_label.setVisible(False))
            self.stacked_widget.setEnabled(True)
            self.menu_button.setEnabled(True)
            self.start_tekdtais()
        else:
            self.init_status_label.setText("Lỗi khởi tạo nghiêm trọng!")
            self.show_themed_message("Lỗi nghiêm trọng",
                               f"Không thể tải các công cụ cần thiết. Ứng dụng sẽ thoát.\n\nChi tiết: {message}",
                               icon=QMessageBox.Icon.Critical)
            sys.exit(1)
    
    def _check_selected_usb_presence(self):
        """
        Khởi tạo một luồng Worker để kiểm tra sự tồn tại của USB mà không làm treo UI.
        """
        if self.is_checking_usb: # Nếu đang kiểm tra thì bỏ qua
            return

        selected_details = self.config.get("device_details")
        if not selected_details:
            self.usb_monitor_timer.stop()
            return
            
        self.is_checking_usb = True
        self.usb_presence_worker = self._create_and_start_worker(
            name="USBPresenceCheck",
            target=self._check_usb_presence_task,
            on_result=self._handle_usb_presence_result,
            args=[selected_details] # Quan trọng: Truyền tham số qua args
        )
    
    def _check_usb_presence_task(self, selected_details):
        """Tác vụ chạy trong luồng nền để kiểm tra sự tồn tại của USB."""
        try:
            command = "Get-PhysicalDisk | Select-Object DeviceID, SerialNumber | ConvertTo-Json -Compress"
            process = subprocess.run(
                ['powershell', '-NoProfile', '-Command', command],
                capture_output=True, text=True, check=True,
                encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = process.stdout.strip()
            if not output.startswith('['): output = f'[{output}]'
            current_disks = json.loads(output)
            
            is_present = any(
                d.get('SerialNumber') == selected_details.get('SerialNumber') and
                d.get('DeviceID') == selected_details.get('DeviceID')
                for d in current_disks
            )
            return is_present
        except Exception as e:
            print(f"Lỗi trong luồng kiểm tra USB: {e}")
            return False
    
    def _handle_usb_presence_result(self, is_present):
        """Xử lý kết quả từ luồng kiểm tra USB và cập nhật UI."""
        self.is_checking_usb = False # Reset cờ

        # Cập nhật trạng thái các nút bấm
        self.page1.next_button.setEnabled(is_present)
        self.page2.next_button.setEnabled(is_present and len(self.config["iso_list"]) > 0)

        # Cập nhật lại trạng thái nút Start ở trang 3
        if self.stacked_widget.currentWidget() == self.page3:
            self._update_capacity_check()
        else:
            self.page3.start_button.setEnabled(is_present)

        if not is_present:
            self.usb_monitor_timer.stop() # Dừng kiểm tra

            if hasattr(self, 'creation_worker') and self.creation_worker.isRunning():
                print("Lỗi nghiêm trọng: USB đã bị rút ra trong quá trình tạo!")
                self.creation_worker.terminate()
                self.creation_worker.wait(1000)
                self.on_creation_finished(False, "USB đã bị ngắt kết nối giữa chừng. Tác vụ đã bị hủy.")
                return

            self.show_themed_message("Lỗi kết nối",
                                   "USB đã chọn đã bị ngắt kết nối. Vui lòng chọn lại.",
                                   icon=QMessageBox.Icon.Critical)
            
            self.config["device"] = None
            self.config["device_name"] = None
            self.config["device_details"] = None
            self.go_to_page(0)

    def confirm_and_start(self):
        """Hiển thị cảnh báo và bắt đầu quá trình tạo USB."""
        if not self.config.get("device"):
            self.show_themed_message("Lỗi", "Vui lòng chọn một ổ đĩa USB!", icon=QMessageBox.Icon.Warning)
            return

        if not self.config.get("iso_list"):
            self.show_themed_message("Lỗi", "Vui lòng chọn hoặc tải ít nhất một file ISO!", icon=QMessageBox.Icon.Warning)
            return

        confirm_text = (f"<b>CẢNH BÁO!</b><br><br>"
                        f"Tất cả dữ liệu trên ổ đĩa <b>{self.config['device_name']}</b> "
                        f"(<b>{self.config['device']}</b>) sẽ bị <b>XÓA SẠCH</b>.<br><br>"
                        "Bạn có chắc chắn muốn tiếp tục không?")

        reply = self.show_themed_message("XÁC NHẬN XÓA DỮ LIỆU", confirm_text, 
                                       icon=QMessageBox.Icon.Warning, 
                                       buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       defaultButton=QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.page3.show_progress_ui(True)
            self.creation_worker = self._create_and_start_worker(
                name="USBCreator",
                target=helpers.create_usb_task,
                on_status=self.page3.update_status,
                on_progress=self.page3.update_progress,
                on_finished=self.on_creation_finished,
                args=[self]
            )

    def set_copy_ais_selection(self, copy_only_selected):
        """
        Thiết lập tùy chọn có chỉ sao chép các phần mềm được chọn của TekDT AIS hay không.
        
        Args:
            copy_only_selected (bool): True nếu chỉ sao chép phần mềm có auto_install=True,
                                       False nếu sao chép toàn bộ.
        """
        self.config["copy_ais_selection_only"] = copy_only_selected
        print(f"Đã chọn Chỉ tạo cùng phần mềm được thêm: {'Yes' if copy_only_selected else 'No'}")
        self.save_config()
        self._update_capacity_check()

    def ask_for_product_key(self, edition_name=None):
        # Đọc danh sách key
        generic_key_path = os.path.join(config.BASE_DIR, "generic_keys.json")
        keys = {}
        if os.path.exists(generic_key_path):
            with open(generic_key_path, "r", encoding="utf-8") as f:
                keys = json.load(f)
        # Tạo dialog chọn key
        dialog = QDialog(self)
        dialog.setWindowTitle("Chọn hoặc nhập Product Key")
        layout = QVBoxLayout(dialog)
        label = QLabel("Không tìm thấy Product Key phù hợp.\nVui lòng chọn hoặc nhập key:")
        layout.addWidget(label)
        combo = QComboBox()
        combo.addItem("Nhập key thủ công...", "")
        for name, key in keys.items():
            combo.addItem(f"{name}: {key}", key)
        layout.addWidget(combo)
        key_edit = QLineEdit()
        key_edit.setPlaceholderText("Nhập Product Key tại đây nếu muốn")
        layout.addWidget(key_edit)
        def on_combo_changed(idx):
            key = combo.itemData(idx)
            key_edit.setText(key)
        combo.currentIndexChanged.connect(on_combo_changed)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return key_edit.text().strip()
        return ""

    def on_creation_finished(self, success, message):
        """Xử lý khi quá trình tạo USB kết thúc."""
        self.page3.show_progress_ui(False)
        if success:
            self.show_themed_message("Thành Công", "Tạo USB Boot thành công!", icon=QMessageBox.Icon.Information)
        else:
            self.show_themed_message("Lỗi", f"Đã xảy ra lỗi:\n{message}", icon=QMessageBox.Icon.Critical)
        # Sau khi hoàn tất, cập nhật lại trạng thái nút bấm
        self._update_capacity_check()

    def show_error(self, message):
        """Hiển thị hộp thoại lỗi."""
        self.show_themed_message("Lỗi", message, icon=QMessageBox.Icon.Critical)

def main():
    # Cài đặt bộ lọc thông điệp để ẩn các cảnh báo QPainter không cần thiết
    qInstallMessageHandler(qt_message_handler)
    
    # Bật nhận biết DPI cho ứng dụng để scaling hoạt động chính xác
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    window = USBBootCreator()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()