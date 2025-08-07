import sys
import os
import subprocess
import json
import requests
import psutil
import zipfile
import py7zr
import time
import shutil
import lzma
import re
import tempfile
import string
import ctypes
import shlex
from pathlib import Path
from subprocess import run
from urllib.request import urlretrieve
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QButtonGroup,
                             QHBoxLayout, QPushButton, QComboBox, QCheckBox,
                             QStackedWidget, QLabel, QFrame, QGroupBox, QLineEdit,
                             QFileDialog, QDialog, QListWidget, QRadioButton,
                             QProgressBar, QMessageBox, QMenu, QDialogButtonBox,
                             QGraphicsOpacityEffect, QListWidgetItem, QSizePolicy)
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QPalette, QActionGroup
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QTimer, QSize

if getattr(sys, 'frozen', False):
    # Khi chạy từ file .exe đã được đóng gói
    BASE_DIR = Path(sys.argv[0]).resolve().parent
else:
    # Khi chạy trực tiếp từ file script .py
    BASE_DIR = Path(__file__).resolve().parent

# --- Cấu hình và Hằng số ---
APP_VERSION = "1.0.0"

# Định nghĩa tất cả các đường dẫn dựa trên BASE_DIR
TOOLS_DIR = BASE_DIR / "Tools"
VENTOY_DIR = TOOLS_DIR / "Ventoy"
FIDO_DIR = TOOLS_DIR / "Fido"
ISOS_DIR = BASE_DIR / "ISOs"
THEMES_DIR = BASE_DIR / "Themes"
DRIVERS_DIR = BASE_DIR / "Drivers"
SCRIPTS_DIR = BASE_DIR / "Scripts"
ARIA2_DIR = TOOLS_DIR / "aria2"
WINCDEMU_DIR = TOOLS_DIR / "WinCDEmu"
TEKDTAIS_DIR = TOOLS_DIR / "TekDT_AIS"
WIMLIB_DIR = TOOLS_DIR / "wimlib"

# Đường dẫn đến các file thực thi
ARIA2_EXE = ARIA2_DIR / "aria2c.exe"
WINCDEMU_EXE = WINCDEMU_DIR / "wcdemu.exe"
WIMLIB_EXE = WIMLIB_DIR / "wimlib-imagex.exe"
TEKDTAIS_EXE = TEKDTAIS_DIR / "tekdt_ais.exe"
FIDO_SCRIPT_PATH = FIDO_DIR / "Fido.ps1"

# Các đường dẫn file cấu hình khác
ISO_ANALYSIS_CACHE = ISOS_DIR / "iso_cache.json"
SHUTDOWN_SIGNAL_TEKDTAIS = TEKDTAIS_DIR / "shutdown_signal.txt"

# Tạo các thư mục cần thiết khi khởi động
for path in [TOOLS_DIR, FIDO_DIR, ISOS_DIR, THEMES_DIR, DRIVERS_DIR, SCRIPTS_DIR, WINCDEMU_DIR, TEKDTAIS_DIR]:
    path.mkdir(parents=True, exist_ok=True)

VENTOY_API_URL = "https://api.github.com/repos/ventoy/Ventoy/releases/latest"
ARIA2_API_URL = "https://api.github.com/repos/aria2/aria2/releases/latest"
FIDO_PS1_URL = "https://github.com/pbatard/Fido/raw/refs/heads/master/Fido.ps1"
FIDO_SCRIPT_PATH = os.path.join(FIDO_DIR, "Fido.ps1")
WIMLIB_URL = "https://wimlib.net/downloads/wimlib-1.14.4-windows-x86_64-bin.zip"
WINCDEMU_API_URL = "https://api.github.com/repos/sysprogs/WinCDEmu/releases/latest"
TEKDTAIS_API_URL = "https://api.github.com/repos/tekdt/tekdtais/releases/latest"

# WINDOWS_SERVER_2016 = "https://www.microsoft.com/en-us/evalcenter/download-windows-server-2016" -> "https://go.microsoft.com/fwlink/p/?LinkID=2195174&clcid=0x409&culture=en-us&country=US"
# WINDOWS_SERVER_2022 = "https://www.microsoft.com/en-us/evalcenter/download-windows-server-2022" -> "https://go.microsoft.com/fwlink/p/?LinkID=2195280&clcid=0x409&culture=en-us&country=US"
# WINDOWS_SERVER_2025 = "https://www.microsoft.com/en-us/evalcenter/download-windows-server-2025" -> "https://go.microsoft.com/fwlink/?linkid=2293312&clcid=0x409&culture=en-us&country=us"
WINDOWS_SERVER_2016_URL = "https://go.microsoft.com/fwlink/p/?LinkID=2195174&clcid=0x409&culture=en-us&country=US"
WINDOWS_SERVER_2022_URL = "https://go.microsoft.com/fwlink/p/?LinkID=2195280&clcid=0x409&culture=en-us&country=US"
WINDOWS_SERVER_2025_URL = "https://go.microsoft.com/fwlink/?linkid=2293312&clcid=0x409&culture=en-us&country=us"

# --- Lớp Worker cho các tác vụ nền --
class Worker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    result = pyqtSignal(object)

    def __init__(self, target, *args, **kwargs):
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            res = self.target(*self.args, **self.kwargs)
            if res is not None:
                self.result.emit(res)
            self.finished.emit(True, "Tác vụ hoàn thành thành công.")
        except Exception as e:
            self.finished.emit(False, f"Lỗi trong luồng Worker:\n{str(e)}")

# --- Lớp chính của ứng dụng ---
class USBBootCreator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ais_process = None
        self.ais_hwnd = None
        self.ais_monitor_timer = QTimer(self)
        self.ais_monitor_timer.timeout.connect(self._check_ais_status)
        self.usb_monitor_timer = QTimer(self)
        self.usb_monitor_timer.timeout.connect(self._check_selected_usb_presence)
        # --- Kiểm tra quyền admin và nâng quyền nếu cần ---
        if not self.is_admin():
            print("Không có quyền admin, đang thử nâng quyền...")
            if self.elevate_privileges():
                # Không cần làm gì thêm ở đây, chỉ cần thoát tiến trình gốc.
                # Tiến trình mới sẽ tự khởi chạy.
                sys.exit(0)
            else:
                # Nếu không nâng quyền được, hiện thông báo lỗi và thoát luôn
                # vì ứng dụng cần quyền admin để hoạt động đúng.
                self.show_themed_message("Lỗi Quyền Admin", 
                         "Không thể nâng quyền quản trị viên. Ứng dụng sẽ thoát.", 
                         icon=QMessageBox.Icon.Critical)
                sys.exit(1)
        
        self.setWindowTitle(f"TekDT BMC v{APP_VERSION}")
        self.setWindowIcon(QIcon())
        self.setMinimumSize(700, 550)
        
        self.config = {
            "device": None,
            "device_name": None,
            "partition_scheme": "GPT", # Mặc định GPT
            "filesystem": "ExFAT", # Mặc định ExFAT
            "theme": None,
            "iso_list": [],
            "windows_edition": None,
            "windows_edition_index": None,
        }

        self.config["device_details"] = None
        
        self.init_ui()
        self.apply_stylesheet()
        self.install_wincdemu_driver()
        
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
            /* [MỚI] CSS cho label thông báo trạng thái */
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
            /* [MỚI] CSS cho danh sách ISO để tăng độ tương phản */
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

    def is_admin(self):
        """Kiểm tra xem ứng dụng có đang chạy với quyền admin không."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def elevate_privileges(self):
        """Thử nâng quyền của ứng dụng một cách an toàn hơn."""
        try:
            script_path = os.path.abspath(sys.argv[0])
            args = [sys.executable, script_path] + sys.argv[1:]
            # Properly quote arguments for Windows ShellExecuteW
            quoted_args = subprocess.list2cmdline(args[1:])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", args[0], quoted_args, None, 1
            )
            return True
        except Exception:
            return False
 
    def closeEvent(self, event):
        self.usb_monitor_timer.stop()
        print("Cửa sổ đang đóng, kiểm tra và dừng các tác vụ...")
        self.page2.stop_download_process()
        self.uninstall_wincdemu_driver()
        
        # Dừng TekDT AIS nếu đang chạy
        self._stop_tekdtais()
        
        event.accept()
    
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
    
    def _check_internet_connection(self):
        """Kiểm tra kết nối Internet một cách nhanh chóng."""
        try:
            # Dùng một địa chỉ IP đáng tin cậy và timeout ngắn
            requests.get("https://8.8.8.8", timeout=3)
            return True
        except requests.ConnectionError:
            return False

    def start_tekdtais(self):
        if not os.path.exists(TEKDTAIS_EXE) or self.is_tekdtais_running():
            return
            
        if os.path.exists(SHUTDOWN_SIGNAL_TEKDTAIS):
                    try:
                        os.remove(SHUTDOWN_SIGNAL_TEKDTAIS)
                        print(f"Đã xóa file tín hiệu shutdown_signal.txt cho TekDT AIS: {SHUTDOWN_SIGNAL_TEKDTAIS}")
                    except OSError as e:
                        print(f"Không thể xóa file tín hiệu shutdown_signal.txt cho TekDT AIS: {e}")

        try:
            print("Đang khởi chạy TekDT AIS ở chế độ nền...")
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0 # SW_HIDE

            self.ais_process = subprocess.Popen(
                [TEKDTAIS_EXE, "--embed-mode"], # Argument để AIS biết nó đang được nhúng
                cwd=TEKDTAIS_DIR,
                startupinfo=startupinfo
            )

            self.find_ais_window_timer = QTimer(self)
            self.find_ais_window_timer.attempts = 0
            self.find_ais_window_timer.timeout.connect(self._find_ais_window_task)
            self.find_ais_window_timer.start(250)
            self.ais_monitor_timer.start(5000)

        except Exception as e:
            self.show_themed_message("Lỗi", f"Không thể khởi chạy TekDT_AIS.exe:\n{e}", icon=QMessageBox.Icon.Warning)

    def _find_ais_window_task(self):
        self.find_ais_window_timer.attempts += 1
        # Chỉ tìm kiếm nếu chưa tìm thấy
        if not self.ais_hwnd:
            self.ais_hwnd = ctypes.windll.user32.FindWindowW(None, "TekDT AIS")

        if self.ais_hwnd:
            self.find_ais_window_timer.stop()
            print(f"Đã tìm thấy cửa sổ TekDT AIS (HWND: {self.ais_hwnd}).")

            # Ẩn cửa sổ ngay lập tức để không hiện trên taskbar
            ctypes.windll.user32.ShowWindow(self.ais_hwnd, 0) # SW_HIDE = 0

            # Nếu người dùng đang ở trang 3 thì nhúng vào luôn
            if self.stacked_widget.currentWidget() == self.page3:
                self.embed_ais_window()

        elif self.find_ais_window_timer.attempts > 40: # Thử trong 10 giây
            self.find_ais_window_timer.stop()
            print("Không thể tìm thấy cửa sổ TekDT AIS sau 10 giây.")
            self._stop_tekdtais()

    def _check_ais_status(self):
        """Định kỳ kiểm tra trạng thái của TekDT AIS và khởi động lại nếu cần."""
        # Chỉ kiểm tra nếu self.ais_process đã được khởi tạo (tức là đã từng chạy)
        # và hiện tại không còn chạy nữa.
        if self.ais_process and not self.is_tekdtais_running():
            print("Phát hiện TekDT AIS đã tắt. Đang khởi động lại...")
            # Dừng timer giám sát để tránh xung đột
            self.ais_monitor_timer.stop() 
            
            # Reset lại các biến trạng thái
            self.ais_process = None
            self.ais_hwnd = None
            
            # Gọi lại hàm khởi động. Hàm này sẽ tự động khởi chạy lại
            # tiến trình, tìm cửa sổ và cả timer giám sát.
            self.start_tekdtais()
    
    def embed_ais_window(self):
        # Kiểm tra điều kiện cơ bản
        if not self.ais_hwnd or not self.page3:
            return
        
        # Lấy container từ giao diện
        container = self.page3.embed_container
        container_id = int(container.winId())

        # Thiết lập style cho cửa sổ B
        GWL_STYLE = -16
        style = ctypes.windll.user32.GetWindowLongW(self.ais_hwnd, GWL_STYLE)
        style |= 0x40000000  # WS_CHILD: Đặt B là child window
        style &= ~0x00C00000  # Loại bỏ WS_CAPTION (thanh tiêu đề)
        style &= ~0x00040000  # Loại bỏ WS_THICKFRAME (viền resize)
        ctypes.windll.user32.SetWindowLongW(self.ais_hwnd, GWL_STYLE, style)
        
        # Đặt cửa sổ B làm con của container
        ctypes.windll.user32.SetParent(self.ais_hwnd, container_id)

        # Lấy kích thước logic của container
        container_size = container.size()
        container_width = container_size.width()
        container_height = container_size.height()

        # Lấy tỷ lệ DPI của thiết bị
        pixel_ratio = self.devicePixelRatioF()

        # Tính kích thước vật lý
        physical_width = int(container_width * pixel_ratio)
        physical_height = int(container_height * pixel_ratio)

        # Đặt kích thước và vị trí cho cửa sổ B
        SWP_FRAMECHANGED = 0x0020
        ctypes.windll.user32.SetWindowPos(
            self.ais_hwnd, 0, 0, 0, physical_width, physical_height,
            SWP_FRAMECHANGED | 0x0004  # SWP_NOZORDER
        )

        # Hiển thị cửa sổ B
        ctypes.windll.user32.ShowWindow(self.ais_hwnd, 1)  # SW_SHOW = 1
        container.setVisible(True)

        # Thêm timer để điều chỉnh kích thước sau khi hiển thị
        QTimer.singleShot(100, self.resize_ais_window)
    
    def hide_ais_window(self):
        if not self.ais_hwnd: return
        ctypes.windll.user32.ShowWindow(self.ais_hwnd, 0)
        ctypes.windll.user32.SetParent(self.ais_hwnd, 0)
        self.page3.embed_container.setVisible(False)

    def resize_ais_window(self):
        if self.ais_hwnd and self.page3.embed_container.isVisible():
            container = self.page3.embed_container
            pixel_ratio = self.devicePixelRatioF()
            width = int(container.width() * pixel_ratio)
            height = int(container.height() * pixel_ratio)

            # Đặt vị trí tại (0,0) trong container và giữ nguyên kích thước
            ctypes.windll.user32.SetWindowPos(
                self.ais_hwnd, 0, 0, 0, width, height, 
                0x0004  # Chỉ SWP_NOZORDER, bỏ SWP_NOMOVE để đặt lại vị trí
            )
    
    def is_tekdtais_running(self):
        return self.ais_process and self.ais_process.poll() is None

    def _stop_tekdtais(self):
        self.ais_monitor_timer.stop()
        if self.is_tekdtais_running():
            print(f"Đang dừng tiến trình TekDT AIS (PID: {self.ais_process.pid})...")
            with open(os.path.join(TEKDTAIS_DIR, "shutdown_signal.txt"), "w") as f:
                f.write("shutdown")
            try:
                self.ais_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("B không tự thoát, buộc dừng tất cả tiến trình liên quan...")
                # Sử dụng psutil để tìm và dừng các tiến trình liên quan
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        if "tekdt_ais.exe" in proc.info['exe'] or \
                           (proc.info['name'] == "python.exe" and proc.parent() and "tekdt_ais.exe" in proc.parent().exe()):
                            print(f"Dừng tiến trình {proc.info['name']} (PID: {proc.info['pid']})")
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            signal_file = os.path.join(TEKDTAIS_DIR, "shutdown_signal.txt")
            if os.path.exists(signal_file):
                os.remove(signal_file)
            self.ais_process = None
            self.ais_hwnd = None
    
    def on_page_changed(self, index):
        if index == 2:
            self.embed_ais_window()
        elif self.ais_hwnd:
            self.hide_ais_window()
    
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
        """Hiển thị menu cấu hình chính."""
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
            for theme_file in os.listdir(THEMES_DIR):
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

    def set_filesystem(self, fs):
        self.config["filesystem"] = fs
        print(f"Đã chọn định dạng: {fs}")

    def set_theme(self, theme_file):
        self.config["theme"] = theme_file
        print(f"Đã chọn theme: {theme_file}")

    def check_for_updates(self):
        """Kiểm tra và tải các công cụ cần thiết."""
        self.update_worker = Worker(self._update_task)
        self.update_worker.status.connect(self.init_status_label.setText)
        self.update_worker.finished.connect(self.on_updates_finished)
        self.update_worker.start()
        
    def install_wincdemu_driver(self):
        """[FIX] Cài đặt driver WinCDEmu portable khi ứng dụng khởi động."""
        if not os.path.exists(WINCDEMU_EXE):
            print("Không tìm thấy WinCDEmu.exe, bỏ qua cài đặt driver.")
            return
        try:
            print("Đang cài đặt driver WinCDEmu portable...")
            # Sử dụng CREATE_NO_WINDOW để không hiện cửa sổ console
            result = run([WINCDEMU_EXE, "/install"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            # Kiểm tra lỗi, nhưng bỏ qua lỗi "đã tồn tại"
            if result.returncode != 0 and "already exists" not in result.stderr:
                print(f"Lỗi khi cài đặt driver WinCDEmu: {result.stderr}")
            else:
                print("Driver WinCDEmu đã được cài đặt hoặc đã tồn tại.")
        except Exception as e:
            print(f"Ngoại lệ khi cài đặt driver WinCDEmu: {e}")

    def uninstall_wincdemu_driver(self):
        """[FIX] Gỡ cài đặt driver WinCDEmu portable khi ứng dụng đóng."""
        if not os.path.exists(WINCDEMU_EXE):
            print("Không tìm thấy WinCDEmu.exe, bỏ qua gỡ cài đặt driver.")
            return
        try:
            print("Đang gỡ cài đặt driver WinCDEmu portable...")
            # Sử dụng CREATE_NO_WINDOW để không hiện cửa sổ console
            run([WINCDEMU_EXE, "/uninstall"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print("Đã gỡ cài đặt driver WinCDEmu.")
        except Exception as e:
            print(f"Ngoại lệ khi gỡ cài đặt driver WinCDEmu: {e}")
        
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
        Nó sử dụng SerialNumber để đảm bảo đúng là USB đó.
        """
        selected_details = self.config.get("device_details")
        if not selected_details:
            self.usb_monitor_timer.stop()
            return

        try:
            # Lấy danh sách các ổ đĩa đang kết nối
            command = "Get-PhysicalDisk | Select-Object DeviceID, SerialNumber | ConvertTo-Json -Compress"
            process = subprocess.run(
                ['powershell', '-NoProfile', '-Command', command],
                capture_output=True, text=True, check=True,
                encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = process.stdout.strip()
            if not output.startswith('['): output = f'[{output}]'
            current_disks = json.loads(output)

            # Tìm kiếm USB trong danh sách hiện tại dựa trên SerialNumber và DeviceID
            is_present = any(
                d.get('SerialNumber') == selected_details.get('SerialNumber') and
                d.get('DeviceID') == selected_details.get('DeviceID')
                for d in current_disks
            )

            # Cập nhật trạng thái các nút bấm
            self.page1.next_button.setEnabled(is_present)
            self.page2.next_button.setEnabled(is_present and len(self.config["iso_list"]) > 0)
            self.page3.start_button.setEnabled(is_present)

            if not is_present:
                self.usb_monitor_timer.stop() # Dừng kiểm tra

                # Nếu đang trong quá trình tạo USB thì phải dừng ngay lập tức
                if hasattr(self, 'creation_worker') and self.creation_worker.isRunning():
                    print("Lỗi nghiêm trọng: USB đã bị rút ra trong quá trình tạo!")
                    self.creation_worker.terminate() # Buộc dừng luồng worker
                    # Chờ một chút để luồng thực sự dừng
                    self.creation_worker.wait(1000)
                    self.on_creation_finished(False, "USB đã bị ngắt kết nối giữa chừng. Tác vụ đã bị hủy.")
                    return

                # Nếu không phải đang tạo thì báo lỗi và quay về trang 1
                self.show_themed_message("Lỗi kết nối",
                                       "USB đã chọn đã bị ngắt kết nối. Vui lòng chọn lại.",
                                       icon=QMessageBox.Icon.Critical)
                
                # Reset cấu hình và quay về trang 1
                self.config["device"] = None
                self.config["device_name"] = None
                self.config["device_details"] = None
                self.go_to_page(0)

        except Exception as e:
            print(f"Lỗi trong quá trình giám sát USB: {e}")
            # Xử lý tương tự như không tìm thấy
            self.page1.next_button.setEnabled(False)
            self.page2.next_button.setEnabled(False)
            self.page3.start_button.setEnabled(False)
    
    def _update_task(self):
        self.update_worker.status.emit("Đang kiểm tra các công cụ...")
        has_internet = self._check_internet_connection()
        if has_internet:
            self.update_worker.status.emit("Đã kết nối Internet. Sẵn sàng kiểm tra cập nhật.")
        else:
            self.update_worker.status.emit("Không có kết nối Internet. Sẽ sử dụng các công cụ hiện có.")

        tools = [
            ("Fido", FIDO_SCRIPT_PATH, self._update_fido_script),
            ("Ventoy", os.path.join(VENTOY_DIR, "Ventoy2Disk.exe"), lambda: self._update_tool("Ventoy", VENTOY_API_URL, r"ventoy-.*-windows\.zip", self._unzip_and_move)),
            ("aria2", ARIA2_EXE, lambda: self._update_tool("aria2", ARIA2_API_URL, r"aria2-.*-win-32bit-build.*\.zip", self._unzip_and_move)),
            ("wimlib", WIMLIB_EXE, lambda: self._update_tool("wimlib", WIMLIB_URL, r"wimlib-.*-windows.*\.zip", self._unzip_and_move, ssl_verify=False)),
            ("WinCDEmu", WINCDEMU_EXE, lambda: self._update_tool("WinCDEmu", WINCDEMU_API_URL, r"PortableWinCDEmu-.*\.exe", lambda dp, dd: self._download_and_place_exe(dp, dd, "wcdemu.exe"))),
            ("TekDT_AIS", TEKDTAIS_EXE, lambda: self._update_tool("TekDT_AIS", TEKDTAIS_API_URL, r".*\.zip", self._unzip_and_move)),
        ]

        for tool_name, tool_path, update_func in tools:
            if not os.path.exists(tool_path):
                self.update_worker.status.emit(f"Công cụ {tool_name} không tồn tại.")
                if not has_internet:
                    # Lỗi nghiêm trọng: thiếu công cụ và không có mạng để tải
                    raise Exception(f"{tool_name} bị thiếu và không có kết nối Internet để tải về.")

                self.update_worker.status.emit(f"Đang tải {tool_name}...")
                try:
                    update_func() # Bắt buộc tải về lần đầu
                except Exception as e:
                    raise Exception(f"Không thể tải về công cụ bắt buộc {tool_name}: {e}")
            else:
                # Công cụ đã tồn tại
                if has_internet:
                    self.update_worker.status.emit(f"Đang kiểm tra cập nhật cho {tool_name}...")
                    try:
                        # Thử cập nhật, nhưng không báo lỗi nghiêm trọng nếu thất bại
                        update_func()
                    except Exception as e:
                        self.update_worker.status.emit(f"Lỗi khi cập nhật {tool_name}, sử dụng phiên bản hiện có. Lỗi: {e}")
                else:
                    self.update_worker.status.emit(f"{tool_name} đã có. Bỏ qua kiểm tra cập nhật.")

        self.update_worker.status.emit("Hoàn tất kiểm tra công cụ!")
        time.sleep(1)

    def _update_fido_script(self):
        """Tải trực tiếp file Fido.ps1 từ GitHub."""
        try:
            self.update_worker.status.emit("Đang tải Fido.ps1...")
            response = requests.get(FIDO_PS1_URL)
            response.raise_for_status() # Báo lỗi nếu tải thất bại
            with open(FIDO_SCRIPT_PATH, 'wb') as f:
                f.write(response.content)
            self.update_worker.status.emit("Cập nhật Fido thành công!")
        except Exception as e:
            error_message = f"Lỗi khi tải Fido.ps1: {e}"
            self.update_worker.status.emit(error_message)
            raise Exception(error_message)

    def _update_tool(self, name, api_url, asset_pattern, extract_func, ssl_verify=True):
        try:
            is_direct_url = api_url.endswith(".zip") or api_url.endswith(".7z")
            if is_direct_url:
                latest_version = os.path.basename(api_url)
            else:
                response = requests.get(api_url)
                response.raise_for_status()
                latest_release = response.json()
                latest_version = latest_release["tag_name"]
            
            tool_dest_dir = os.path.join(TOOLS_DIR, name)
            version_file = os.path.join(tool_dest_dir, "version.txt")

            current_version = ""
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    current_version = f.read().strip()
            
            if latest_version != current_version or not os.path.exists(tool_dest_dir):
                self.update_worker.status.emit(f"Tìm thấy {name} phiên bản mới. Đang tải...")
                
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

                download_path = os.path.join(TOOLS_DIR, os.path.basename(asset_url))
                
                with requests.get(asset_url, stream=True, verify=ssl_verify) as r:
                    r.raise_for_status()
                    with open(download_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                
                self.update_worker.status.emit(f"Đang xử lý {name}...")
                extract_func(download_path, tool_dest_dir)
                
                if os.path.exists(download_path):
                    try:
                        os.remove(download_path)
                        print(f"Đã xóa file tạm: {download_path}")
                    except OSError as e:
                        print(f"Không thể xóa file tạm {download_path}: {e}")

                with open(version_file, 'w') as f:
                    f.write(latest_version)
                self.update_worker.status.emit(f"Đã cập nhật {name} thành công!")
            else:
                self.update_worker.status.emit(f"{name} đã là phiên bản mới nhất.")
        except Exception as e:
            error_message = f"Lỗi trong quá trình cập nhật {name}: {e}"
            self.update_worker.status.emit(error_message)
            raise Exception(error_message)

    def _download_and_place_exe(self, downloaded_path, dest_dir, final_name):
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
    
    def _unzip_and_move(self, zip_path, dest_dir):
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
            self.creation_worker = Worker(self.create_usb_task)
            self.creation_worker.status.connect(self.page3.update_status)
            self.creation_worker.progress.connect(self.page3.update_progress)
            self.creation_worker.finished.connect(self.on_creation_finished)
            self.creation_worker.start()

    def create_usb_task(self):
        """Tác vụ tạo USB Boot chạy trong luồng nền."""
        try:
            # --- Bước 1: Tạo file cấu hình ventoy.json ---
            self.creation_worker.status.emit("Đang tạo file cấu hình ventoy.json...")
            self.creation_worker.progress.emit(20)
            ventoy_config = self._generate_ventoy_json()

            # --- Bước 2: Chạy Ventoy2Disk.exe ---
            self.creation_worker.status.emit(f"Bắt đầu tạo USB trên {self.config['device']}...")
            self.creation_worker.progress.emit(50)
            
            ventoy_exe = os.path.join(VENTOY_DIR, "Ventoy2Disk.exe")
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
                theme_zip_path = os.path.join(THEMES_DIR, self.config["theme"])
                
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
            if os.path.exists(TEKDTAIS_DIR):
                if os.path.exists(dest_ais_dir):
                    shutil.rmtree(dest_ais_dir)
                shutil.copytree(TEKDTAIS_DIR, dest_ais_dir)
                print("Đã sao chép TekDT_AIS vào USB.")

                # run_ais_script_path = os.path.join(usb_mount_point, "run_ais_setup.bat")
                # run_ais_script_content = """@echo off
# REM Search for TekDT_AIS, copy it to C drive, and execute it.
# for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    # if exist "%%D:\\TekDT_AIS\\tekdt_ais.exe" (
        # echo Found TekDT_AIS on drive %%D:
        # echo Copying TekDT_AIS to C:\\ ...
        # xcopy "%%D:\\TekDT_AIS" "C:\\TekDT_AIS\\" /E /I /Y /H /Q
        
        # echo Running installer...
        # start "" "C:\\TekDT_AIS\\tekdt_ais.exe" /install

        # goto :eof
    # )
# )
# echo TekDT_AIS not found on any drive.
# :eof
# """
                # with open(run_ais_script_path, "w") as f:
                    # f.write(run_ais_script_content)
                # print("Đã tạo run_ais_setup.bat trên USB.")
            self._process_driver_archive(usb_mount_point)

            self.creation_worker.progress.emit(100)
            self.creation_worker.status.emit("Hoàn tất! USB đã sẵn sàng.")

        except Exception as e:
            raise e

    def ask_for_product_key(self, edition_name=None):
        # Đọc danh sách key
        generic_key_path = os.path.join(BASE_DIR, "generic_keys.json")
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

    def get_generic_key(edition_name):
        generic_key_path = os.path.join(BASE_DIR, "generic_keys.json")
        if not os.path.exists(generic_key_path):
            return None
        with open(generic_key_path, "r", encoding="utf-8") as f:
            keys = json.load(f)
        return keys.get(edition_name)

    def _generate_unattend_xml(self, index, product_key=None, architecture="amd64"):
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

    def _generate_ventoy_json(self):
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
        for iso_info in self.config['iso_list']:
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
        if self.config["theme"]:
            theme_name = os.path.splitext(self.config["theme"])[0]
            config_data["theme"] = {
                "file": f"/ventoy/themes/{theme_name}/theme.txt",
                "gfxmode": "1920x1080"
            }

        return json.dumps(config_data, indent=4)

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

    def _process_driver_archive(self, usb_mount_point):
        """
        Gộp các file Drivers.7z.001 và .002 thành một file Drivers.7z duy nhất
        và sao chép trực tiếp vào thư mục ventoy trên USB.
        """
        self.creation_worker.status.emit("Đang xử lý kho driver...")
        
        # Đường dẫn tới các file driver nguồn và thư mục đích trên USB
        drivers_part1 = os.path.join(BASE_DIR, "Drivers", "Drivers.7z.001")
        drivers_part2 = os.path.join(BASE_DIR, "Drivers", "Drivers.7z.002")
        usb_ventoy_dir = os.path.join(usb_mount_point, "ventoy")
        final_archive_path = os.path.join(usb_ventoy_dir, "Drivers.7z")

        # Kiểm tra sự tồn tại của cả hai file .001, .002 và .003
        if not (os.path.exists(drivers_part1) and os.path.exists(drivers_part2)):
            self.creation_worker.status.emit("Không tìm thấy Drivers.7z.001/.002. Bỏ qua.")
            print("Không tìm thấy file driver phân mảnh, bỏ qua bước này.")
            return

        try:
            # Đảm bảo thư mục /ventoy/ trên USB đã tồn tại
            os.makedirs(usb_ventoy_dir, exist_ok=True)
            
            self.creation_worker.status.emit("Đang gộp và sao chép Drivers.7z vào USB...")
            print(f"Bắt đầu gộp file vào: {final_archive_path}")

            # Mở file đích để ghi (chế độ 'wb')
            with open(final_archive_path, "wb") as outfile:
                # Đọc và ghi nội dung từ file .001
                with open(drivers_part1, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)
                # Đọc và ghi nội dung từ file .002
                with open(drivers_part2, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)
            
            self.creation_worker.status.emit("Đã sao chép Drivers.7z vào USB thành công.")
            print("Gộp và sao chép Drivers.7z hoàn tất.")

        except Exception as e:
            error_message = f"Lỗi khi gộp và sao chép Drivers.7z: {e}"
            self.creation_worker.status.emit(error_message)
            print(error_message)
            # Nếu có lỗi, nên đưa ra ngoại lệ để dừng quá trình
            raise Exception(error_message)
    
    def on_creation_finished(self, success, message):
        """Xử lý khi quá trình tạo USB kết thúc."""
        self.page3.show_progress_ui(False)
        if success:
            self.show_themed_message("Thành Công", "Tạo USB Boot thành công!", icon=QMessageBox.Icon.Information)
        else:
            self.show_themed_message("Lỗi", f"Đã xảy ra lỗi:\n{message}", icon=QMessageBox.Icon.Critical)
        self.page3.start_button.setEnabled(True)

    def show_error(self, message):
        """Hiển thị hộp thoại lỗi."""
        self.show_themed_message("Lỗi", message, icon=QMessageBox.Icon.Critical)

# --- Các trang giao diện (QWidget) ---
class PageDeviceSelect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        self.drive_worker = None
        self.is_fetching = False
        self.init_ui()
        self.start_drive_monitor()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 20, 50, 50)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Bước 1: Chọn thiết bị USB")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        layout.addWidget(QLabel("Chọn ổ đĩa USB bạn muốn sử dụng:"))

        self.drive_combo = QComboBox()
        self.drive_combo.currentIndexChanged.connect(self.on_drive_selected)
        layout.addWidget(self.drive_combo)

        self.show_hdd_check = QCheckBox("Hiển thị tất cả các ổ đĩa (Bao gồm ổ cứng)")
        self.show_hdd_check.stateChanged.connect(self.refresh_drives)
        layout.addWidget(self.show_hdd_check)

        layout.addStretch()

        self.next_button = QPushButton("Tiếp theo →")
        self.next_button.setEnabled(False)
        layout.addWidget(self.next_button, alignment=Qt.AlignmentFlag.AlignRight)

    def start_drive_monitor(self):
        """Bắt đầu theo dõi sự thay đổi của các ổ đĩa."""
        self.refresh_drives()
        self.drive_timer = QTimer(self)
        self.drive_timer.timeout.connect(self.refresh_drives)
        self.drive_timer.start(3000)

    def refresh_drives(self):
        """
        Khởi động một luồng worker để lấy danh sách ổ đĩa mà không làm treo UI.
        """
        if self.is_fetching:
            return

        self.is_fetching = True
        self.drive_worker = Worker(self._fetch_drives_task)
        self.drive_worker.result.connect(self._update_drive_combo)
        self.drive_worker.finished.connect(self._on_fetch_finished)
        self.drive_worker.start()

    def _on_fetch_finished(self, success, message):
        """
        Slot được gọi khi luồng worker tìm ổ đĩa hoàn thành.
        Hàm này sẽ reset lại cờ is_fetching.
        """
        self.is_fetching = False
        if not success:
            print(f"Lỗi khi lấy danh sách ổ đĩa: {message}")

    def _fetch_drives_task(self):
        """
        Tác vụ chạy trong luồng nền để lấy danh sách ổ đĩa bằng PowerShell.
        """
        try:
            # Lấy thêm thuộc tính SerialNumber, VendorID, ProductID
            command = "Get-PhysicalDisk | Select-Object DeviceID, FriendlyName, Size, MediaType, BusType, SerialNumber, VendorID, ProductID | ConvertTo-Json -Compress"
            process = subprocess.run(
                ['powershell', '-NoProfile', '-Command', command],
                capture_output=True, text=True, check=True,
                encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = process.stdout.strip()
            if not output:
                return []

            # Đôi khi PowerShell chỉ trả về một object JSON, không có ngoặc vuông
            if not output.startswith('['):
                output = f'[{output}]'
            
            disks = json.loads(output)
            return disks

        except Exception as e:
            print(f"Không thể lấy danh sách ổ đĩa bằng PowerShell: {e}")
            raise e

    def _update_drive_combo(self, disks):
        """
        Cập nhật ComboBox với danh sách ổ đĩa nhận được từ luồng worker.
        """
        if disks is None: disks = []
        current_selection = self.drive_combo.currentData()
        self.drive_combo.clear()
        
        show_all = self.show_hdd_check.isChecked()
        found_drives = False

        if not disks:
            self.drive_combo.addItem("Không thể lấy danh sách ổ đĩa", None)
            self.on_drive_selected(-1)
            return

        for disk in disks:
            bus_type = disk.get('BusType', 'Unknown')
            media_type = disk.get('MediaType', 'Unspecified')
            # Phân loại USB chính xác hơn
            is_usb = (bus_type == 'USB' or media_type == 'Removable')
            
            if show_all or is_usb:
                found_drives = True
                device_id_num = disk['DeviceID']
                device_path = f"\\\\.\\PHYSICALDRIVE{device_id_num}"
                
                model = disk.get('FriendlyName', 'Unknown Disk')
                size = int(disk.get('Size', 0))
                
                gb_size = size / (1024**3)
                display_text = f"{model} ({gb_size:.2f} GB) - {bus_type}"
                self.drive_combo.addItem(display_text, disk)

        if not found_drives:
            self.drive_combo.addItem("Không tìm thấy USB nào" if not show_all else "Không tìm thấy ổ đĩa nào", None)

        index = self.drive_combo.findData(current_selection)
        if index != -1:
            self.drive_combo.setCurrentIndex(index)
        else:
            self.on_drive_selected(self.drive_combo.currentIndex())

    def on_drive_selected(self, index):
        if index == -1 or self.drive_combo.itemData(index) is None:
            self.main_app.config["device"] = None
            self.main_app.config["device_name"] = None
            self.main_app.config["device_details"] = None
            self.next_button.setEnabled(False)
            self.main_app.usb_monitor_timer.stop()
            return

        disk_details = self.drive_combo.itemData(index)
        device_path = f"\\\\.\\PHYSICALDRIVE{disk_details['DeviceID']}"
        device_name = self.drive_combo.itemText(index)

        self.main_app.config["device"] = device_path
        self.main_app.config["device_name"] = device_name
        self.main_app.config["device_details"] = disk_details
        self.next_button.setEnabled(True)

        self.main_app.usb_monitor_timer.start(2000)
class PageISOSelect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        self.aria2_process = None
        self.is_cancelling = False
        self.downloads_queue = []
        self.arch_button_group = QButtonGroup(self)
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

        # Group 2: Tải tự động
        self.download_group = QGroupBox("Tải tự động từ Microsoft")
        self.download_group_layout = QVBoxLayout(self.download_group)
        
        self.win_options = {}
        
        # Windows 10 & 11 (dùng Fido)
        fido_versions = { "Windows 11": ["x64"], "Windows 10": ["x64", "x86"] }
        for win, archs in fido_versions.items():
            cb = QCheckBox(f"{win} ({', '.join(archs)})")
            self.win_options[win] = {'checkbox': cb, 'type': 'fido', 'archs': archs}
            self.download_group_layout.addWidget(cb)
            
            # Nếu là Windows 10 thì tạo radio button chọn kiến trúc
            if win == "Windows 10":
                radios = {}
                radio_layout = QHBoxLayout()
                for arch in archs:
                    rb = QRadioButton(arch)
                    rb.setVisible(False)
                    radio_layout.addWidget(rb)
                    self.arch_button_group.addButton(rb)
                    radios[arch] = rb
                self.win_options[win]['radios'] = radios
                self.download_group_layout.addLayout(radio_layout)
                # Sự kiện hiện/ẩn radio khi tick checkbox
                cb.toggled.connect(lambda checked, win=win: self.toggle_arch_options(checked, win))

        self.download_group_layout.addWidget(QFrame(self, frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken))

        # Windows Server (dùng link trực tiếp)
        server_versions = {
            "Windows Server 2025": WINDOWS_SERVER_2025_URL,
            "Windows Server 2022": WINDOWS_SERVER_2022_URL,
            "Windows Server 2016": WINDOWS_SERVER_2016_URL
        }
        for name, url in server_versions.items():
            cb = QCheckBox(name)
            self.win_options[name] = {'checkbox': cb, 'type': 'direct', 'url': url}
            self.download_group_layout.addWidget(cb)

        self.download_button = QPushButton("Tải các mục đã chọn")
        self.download_button.clicked.connect(self.start_downloads)
        self.download_group_layout.addWidget(self.download_button)

        self.download_status_label = QLabel("")
        self.download_status_label.setObjectName("DownloadStatusLabel")
        self.download_status_label.setWordWrap(True)
        self.download_group_layout.addWidget(self.download_status_label)
        layout.addWidget(self.download_group)
        
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

        self.cancel_button.clicked.connect(self.cancel_download_clicked)

    def update_next_button_state(self):
        """Kích hoạt nút 'Tiếp theo' chỉ khi có ISO và USB vẫn được kết nối."""
        has_iso = len(self.main_app.config["iso_list"]) > 0
        is_usb_present = self.main_app.config.get("device_details") is not None
        self.next_button.setEnabled(has_iso and is_usb_present)

    def toggle_arch_options(self, checked, win_version):
        options_data = self.win_options[win_version]
        for rb in options_data['radios'].values():
            rb.setVisible(checked)
        if checked:
            # Bỏ chọn các checkbox khác
            for other_win, data in self.win_options.items():
                if other_win != win_version:
                    data['checkbox'].setChecked(False)
            # Tự động chọn radio button đầu tiên nếu chưa chọn
            if not any(rb.isChecked() for rb in options_data['radios'].values()):
                list(options_data['radios'].values())[0].setChecked(True)
        else:
            # Bỏ chọn radio nếu bỏ tick
            self.arch_button_group.setExclusive(False)
            for rb in options_data['radios'].values():
                rb.setChecked(False)
            self.arch_button_group.setExclusive(True)
    
    def browse_iso(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Chọn các file ISO", ISOS_DIR, "ISO Files (*.iso)")
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
        
        list_item = QListWidgetItem(f"{iso_info['filename']}")
        list_item.setData(Qt.ItemDataRole.UserRole, iso_path) # Lưu đường dẫn để nhận dạng
        self.iso_list_widget.addItem(list_item)
        
        self.update_next_button_state()
        self.analyze_iso(iso_info) # Phân tích để lấy thông tin phiên bản

    def remove_selected_iso(self):
        selected_items = self.iso_list_widget.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            iso_path_to_remove = item.data(Qt.ItemDataRole.UserRole)
            # Xóa khỏi config
            self.main_app.config['iso_list'] = [
                iso for iso in self.main_app.config['iso_list']
                if iso['path'] != iso_path_to_remove
            ]
            # Xóa khỏi UI
            self.iso_list_widget.takeItem(self.iso_list_widget.row(item))
        
        self.update_next_button_state()
        print("Đã cập nhật danh sách ISO:", self.main_app.config['iso_list'])

    def _get_available_drive_letter(self):
        """Tìm một ký tự ổ đĩa chưa được sử dụng."""
        used_letters = [p.mountpoint[0].upper() for p in psutil.disk_partitions()]
        for letter in string.ascii_uppercase:
            if letter not in used_letters:
                return letter
        return None
    def analyze_iso(self, iso_info_dict):
        """Phân tích file ISO bằng cách mount với WinCDEmu và đọc bằng wimlib. (Chỉ khởi tạo worker)"""
        iso_path = iso_info_dict['path']
        cache = {}
        if os.path.exists(ISO_ANALYSIS_CACHE):
            try:
                with open(ISO_ANALYSIS_CACHE, 'r') as f: cache = json.load(f)
            except (json.JSONDecodeError, IOError): pass

        size_key = str(os.path.getsize(iso_path))
        if size_key in cache:
            print(f"Đã tìm thấy thông tin ISO trong cache cho khóa: {size_key}")
            self.show_edition_selection_dialog(cache[size_key], iso_info_dict)
            return

        if not os.path.exists(WINCDEMU_EXE) or not os.path.exists(WIMLIB_EXE):
            self.main_app.show_themed_message("Lỗi", 
                                              "Không tìm thấy WinCDEmu hoặc wimlib-imagex.exe để phân tích ISO",
                                              icon=QMessageBox.Icon.Critical)
            return

        editions = {}
        drive_letter = None
        detected_arch = None
        try:
            # Bước 1: Tìm một ký tự ổ đĩa trống
            drive_letter = self._get_available_drive_letter()
            if not drive_letter:
                raise Exception("Không tìm thấy ký tự ổ đĩa trống để mount file ISO.")
            
            print(f"Sẽ mount ISO vào ổ đĩa: {drive_letter}:")

            # Bước 2: Mount ISO bằng WinCDEmu với cú pháp đúng và cờ /wait
            # Cú pháp: wcdemu.exe <image_file> <drive_letter>: /wait
            mount_cmd = [WINCDEMU_EXE, iso_path, f"{drive_letter}:", "/wait"]
            result = run(mount_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr.strip() else f"WinCDEmu trả về mã lỗi {result.returncode}."
                raise Exception(f"Không thể mount ISO: {error_msg}")

            print(f"Mount ISO thành công vào ổ {drive_letter}:")
            
            # Bước 3: Tìm file install.wim hoặc install.esd
            mounted_drive = f"{drive_letter}:"
            if os.path.exists(os.path.join(mounted_drive, "efi", "boot", "bootx64.efi")):
                detected_arch = "amd64"
                print("Phát hiện kiến trúc: 64-bit (amd64)")
            elif os.path.exists(os.path.join(mounted_drive, "efi", "boot", "bootia32.efi")):
                detected_arch = "x86"
                print("Phát hiện kiến trúc: 32-bit (x86)")
            else:
                # Nếu không có file EFI, có thể thử dựa vào các thư mục khác (dự phòng)
                if os.path.exists(os.path.join(mounted_drive, "sources", "x64")):
                     detected_arch = "amd64"
                     print("Phát hiện kiến trúc (dự phòng): 64-bit (amd64)")
                elif os.path.exists(os.path.join(mounted_drive, "sources", "x86")):
                     detected_arch = "x86"
                     print("Phát hiện kiến trúc (dự phòng): 32-bit (x86)")
                else:
                    print("Cảnh báo: Không thể tự động xác định kiến trúc. Mặc định là amd64.")
                    detected_arch = "amd64" # Mặc định

            iso_info_dict["architecture"] = detected_arch
            
            wim_path = None
            for ext in [".wim", ".esd"]:
                possible_path = os.path.join(mounted_drive, "sources", f"install{ext}")
                if os.path.exists(possible_path):
                    wim_path = possible_path
                    break
            
            if not wim_path:
                # Nếu không thấy, có thể do một số ISO chứa trong thư mục x64/x86
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

            # Bước 4: Phân tích file WIM/ESD với wimlib-imagex
            info_cmd = [WIMLIB_EXE, "info", wim_path]
            # Chạy lệnh và nhận output dưới dạng bytes thô để tránh lỗi Unicode
            result = run(info_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode != 0:
                # Giải mã stderr một cách an toàn nếu có lỗi
                error_output = result.stderr.decode(encoding='utf-8', errors='ignore')
                raise Exception(f"Không thể phân tích file WIM/ESD: {error_output}")

            current_index = ""
            # Giải mã stdout một cách an toàn, bỏ qua các ký tự không hợp lệ
            output_text = result.stdout.decode(encoding='utf-8', errors='ignore')
            for line in output_text.splitlines():
                if "Index" in line:
                    current_index = line.split(":")[-1].strip()
                elif "Name" in line and current_index:
                    name = line.split(":")[-1].strip()
                    # Một số tên có thể chứa ký tự đặc biệt không mong muốn
                    clean_name = ''.join(char for char in name if char.isprintable())
                    editions[current_index] = clean_name
                    current_index = "" # Reset để chờ index tiếp theo

            if editions:
                print(f"Các phiên bản Windows được tìm thấy: {editions}")
                cache[size_key] = editions
                with open(ISO_ANALYSIS_CACHE, 'w') as f:
                    json.dump(cache, f, indent=2)

        except Exception as e:
            self.main_app.show_error(f"Lỗi khi phân tích ISO:\n{e}")

        finally:
            # Bước 5: Luôn luôn unmount ổ đĩa ảo sau khi hoàn tất
            if drive_letter:
                print(f"Đang unmount ổ đĩa ảo {drive_letter}:")
                unmount_cmd = [WINCDEMU_EXE, "/unmount", f"{drive_letter}:"]
                run(unmount_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
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
            key = USBBootCreator.get_generic_key(selected_data[1])
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

    # def on_arch_selected(self, checked, win_version, arch):
        # if checked:
            # msg_box = QMessageBox(self)
            # msg_box.setIcon(QMessageBox.Icon.Question)
            # msg_box.setWindowTitle("Xác nhận tải xuống")
            # msg_box.setText(f"Bạn có chắc chắn muốn bắt đầu quá trình tải xuống file ISO cho\n"
                            # f"{win_version} ({arch}) không?")
            # msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            # msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            # reply = msg_box.exec()

            # if reply == QMessageBox.StandardButton.Yes:
                # self._set_ui_state(downloading=True) # Khóa UI trước khi tải
                # self.iso_path_edit.clear()
                # self.main_app.config["iso_path"] = None
                # self.next_button.setEnabled(False)
                # self.download_status_label.setText(f"Đang chuẩn bị tải {win_version} {arch}...")
                
                # self.download_worker = Worker(self._download_task, win_version, arch)
                # self.download_worker.status.connect(self.download_status_label.setText)
                # self.download_worker.finished.connect(self.on_download_finished)
                # self.download_worker.result.connect(self.on_download_result)
                # self.download_worker.start()
            # else:
                # rb_to_uncheck = self.win_options[win_version]['radios'][arch]
                # self.arch_button_group.setExclusive(False)
                # rb_to_uncheck.setChecked(False)
                # self.arch_button_group.setExclusive(True)
                # self.download_status_label.setText("")

    def start_downloads(self):
        self.downloads_queue = []
        for name, data in self.win_options.items():
            if data['checkbox'].isChecked():
                self.downloads_queue.append({'name': name, 'data': data})
        
        if not self.downloads_queue:
            self.main_app.show_themed_message("Thông báo", 
                                              "Vui lòng chọn ít nhất một phiên bản để tải.",
                                              icon=QMessageBox.Icon.Information)
            return

        self._set_ui_state(downloading=True)
        self.download_worker = Worker(self._download_task)
        self.download_worker.status.connect(self.download_status_label.setText)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.result.connect(self.on_download_result)
        self.download_worker.start()
    
    def _set_ui_state(self, downloading=False, long_task=False):
        """Cập nhật trạng thái UI cho các tác vụ tải hoặc tác vụ nền dài."""
        # Các thành phần UI liên quan đến tải file
        self.iso_list_group.setEnabled(not downloading)
        for win, data in self.win_options.items():
            data['checkbox'].setEnabled(not downloading)
            if 'radios' in data:
                for rb in data['radios'].values():
                    rb.setEnabled(not downloading)
        self.back_button.setVisible(not downloading)
        self.next_button.setVisible(not downloading)
        self.cancel_button.setVisible(downloading)
        self.download_button.setEnabled(not downloading)

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
    
    def _download_task(self):
        """Tác vụ tải file theo hàng đợi."""
        if not os.path.exists(ARIA2_EXE):
            raise FileNotFoundError("Chưa tìm thấy aria2c.exe.")

        total_downloads = len(self.downloads_queue)
        for i, item in enumerate(self.downloads_queue):
            if self.is_cancelling: break
            
            name = item['name']
            data = item['data']
            self.download_worker.status.emit(f"({i+1}/{total_downloads}) Đang chuẩn bị tải {name}...")
            
            iso_url = ""
            if data['type'] == 'fido':
                if not os.path.exists(FIDO_SCRIPT_PATH):
                    raise FileNotFoundError("Chưa tìm thấy Fido.ps1.")
                
                fido_version_map = {"Windows 11": "11", "Windows 10": "10"}
                version_arg = fido_version_map.get(name)
                # Lấy kiến trúc từ radio nếu là Win 10, còn lại mặc định x64
                if name == "Windows 10":
                    arch_arg = "x64"  # Mặc định
                    for arch, rb in data.get('radios', {}).items():
                        if rb.isChecked():
                            arch_arg = arch
                            break
                else:
                    arch_arg = "x64"

                self.download_worker.status.emit(f"({i+1}/{total_downloads}) Đang lấy link cho {name}...")
                fido_cmd = ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', FIDO_SCRIPT_PATH, '-Win', version_arg, '-Arch', arch_arg, '-Lang', 'Eng', '-GetUrl']
                process = subprocess.run(fido_cmd, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                iso_url = process.stdout.strip()
            
            elif data['type'] == 'direct':
                iso_url = self.get_final_url(data['url'])

            if not iso_url or not iso_url.startswith("http"):
                raise Exception(f"Không lấy được URL hợp lệ cho {name}.")
            iso_filename = os.path.basename(iso_url.split('?')[0])
            iso_filepath = os.path.join(ISOS_DIR, iso_filename)
            
            aria2_control_file = iso_filepath + ".aria2"
            if os.path.exists(aria2_control_file):
                self.download_worker.status.emit("Phát hiện file tải dở. Đang dọn dẹp...")
                print(f"Đang xóa file tải dở: {iso_filepath} và {aria2_control_file}")
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
                self.download_worker.result.emit(iso_filepath) # Gửi tín hiệu để thêm vào danh sách
                continue

            self.download_worker.status.emit(f"({i+1}/{total_downloads}) Đang tải {iso_filename}...")

            self.download_worker.status.emit(f"Bước 2/2: Đang tải file {iso_filename}...")
            
            aria2_cmd = [
                ARIA2_EXE,
                '--console-log-level=info',
                '--summary-interval=1',
                '-c', '-x16', '-s16',
                '-d', ISOS_DIR,
                '-o', iso_filename,
                iso_url
            ]

            self.aria2_process = subprocess.Popen(
                aria2_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW,
                bufsize=1 # Buộc ghi vào pipe sau mỗi dòng
            )
            
            for line in iter(self.aria2_process.stdout.readline, ''):
                if not self.aria2_process: break
                line = line.strip()
                print(f"[Aria2 Output]: {line}")

                # Mẫu của aria2 thường là: ... CN:1 DL:11MiB ETA:1m1s) (1%)
                match = re.search(r'\((\d{1,3})%\)', line)
                if match:
                    percent = int(match.group(1))
                    # Tạo một chuỗi trạng thái chi tiết hơn
                    speed_match = re.search(r'DL:([^\s]+)', line)
                    eta_match = re.search(r'ETA:([^\)]+)', line)
                    status_text = f"Đang tải {iso_filename}: {percent}%"
                    if speed_match:
                        status_text += f" ({speed_match.group(1)})"
                    if eta_match:
                        status_text += f" - ETA: {eta_match.group(1)}"
                    self.download_worker.status.emit(status_text)
            
            self.aria2_process.wait()
            if self.aria2_process and self.aria2_process.returncode != 0:
                if not self.is_cancelling:
                    raise Exception(f"aria2 thất bại với mã lỗi {self.aria2_process.returncode}")

            if not self.is_cancelling:
                self.download_worker.result.emit(iso_filepath)
            return None

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
            
    def _set_ui_state(self, downloading=False, long_task=False):
        """Cập nhật trạng thái UI cho các tác vụ tải hoặc tác vụ nền dài."""
        # Download-related UI
        self.iso_list_group.setEnabled(not downloading)
        for win, data in self.win_options.items():
            data['checkbox'].setEnabled(not downloading)
            if 'radios' in data:
                for rb in data['radios'].values():
                    rb.setEnabled(not downloading)
        self.back_button.setVisible(not downloading)
        self.next_button.setVisible(not downloading)
        self.cancel_button.setVisible(downloading)
        self.download_button.setEnabled(not downloading)
        # Long-running task UI (example: progress bar, disabling main window)
        if hasattr(self, "progress_bar"):
            self.progress_bar.setVisible(long_task)
        if hasattr(self, "start_button"):
            self.start_button.setEnabled(not long_task)

    def stop_download_process(self):
        """Dừng tiến trình aria2c.exe nếu nó đang chạy."""
        if self.aria2_process and self.aria2_process.poll() is None:
            print("Đang dừng tiến trình aria2c.exe...")
            self.aria2_process.terminate()
            try:
                # Chờ một chút để tiến trình kết thúc
                self.aria2_process.wait(timeout=5)
                print("Đã dừng tiến trình aria2c.exe.")
            except subprocess.TimeoutExpired:
                print("Không thể dừng aria2c.exe một cách nhẹ nhàng, buộc phải kill.")
                self.aria2_process.kill()
        self.aria2_process = None

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

class PageFinalize(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        self.ais_process = None
        self.ais_hwnd = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 20, 50, 50)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Bước 3: Hoàn tất")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        self.summary_group = QGroupBox("Lựa chọn phần mềm được cài đặt tự động sau khi cài Windows")
        summary_layout = QVBoxLayout(self.summary_group)

        self.embed_container = QFrame()
        self.embed_container.setMinimumSize(400, 300)
        self.embed_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.embed_container.setFrameShadow(QFrame.Shadow.Sunken)
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.embed_container.setSizePolicy(size_policy)
        self.embed_container.setVisible(False) # Sẽ được quản lý bởi main_app
        summary_layout.addWidget(self.embed_container, 1)
        layout.addWidget(self.summary_group, 1)

        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        nav_layout = QHBoxLayout()
        self.back_button = QPushButton("← Quay lại")
        self.start_button = QPushButton("Bắt đầu tạo")
        nav_layout.addWidget(self.back_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.start_button)
        layout.addLayout(nav_layout)
    
    def hideEvent(self, event):
        """Dừng TekDT AIS khi giao diện bị ẩn."""
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)

    def find_and_embed_window(self):
        self.find_window_timer.attempts += 1
        self.ais_hwnd = ctypes.windll.user32.FindWindowW(None, "TekDT AIS")

        if self.ais_hwnd:
            self.find_window_timer.stop()
            container_id = int(self.embed_container.winId())

            GWL_STYLE = -16
            style = ctypes.windll.user32.GetWindowLongW(self.ais_hwnd, GWL_STYLE)
            remove_styles = 0x00C00000 | 0x00080000 | 0x00040000  # WS_CAPTION | WS_SYSMENU | WS_THICKFRAME
            new_style = style & ~remove_styles
            new_style |= 0x40000000  # WS_CHILD
            ctypes.windll.user32.SetWindowLongW(self.ais_hwnd, GWL_STYLE, new_style)
            
            ctypes.windll.user32.SetParent(self.ais_hwnd, container_id)
            
            # Đặt vị trí và kích thước bằng SetWindowPos
            width = self.embed_container.width()
            height = self.embed_container.height()
            ctypes.windll.user32.SetWindowPos(
                self.ais_hwnd, 0, 0, 0, width, height, 
                0x0004 | 0x0010  # SWP_NOZORDER | SWP_NOMOVE
            )
            
            ctypes.windll.user32.ShowWindow(self.ais_hwnd, 1)
            self.embed_container.setVisible(True)
            print(f"Đã nhúng cửa sổ TekDT AIS với kích thước: {width}x{height}")
        elif self.find_window_timer.attempts > 40:
            self.find_window_timer.stop()
            self.main_app.show_error("Không thể tìm thấy cửa sổ TekDT AIS để nhúng.")

    def resizeEvent(self, event):
        """Kích hoạt việc thay đổi kích thước cửa sổ nhúng khi container thay đổi."""
        super().resizeEvent(event)
        # Gọi hàm resize của cửa sổ chính để nó xử lý
        self.main_app.resize_ais_window()
  
    def show_progress_ui(self, show):
        self.progress_bar.setVisible(show)
        self.status_label.setVisible(show)
        self.start_button.setEnabled(not show)
        self.back_button.setEnabled(not show)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, text):
        self.status_label.setText(text)

def main():
    # Bật nhận biết DPI cho ứng dụng để scaling hoạt động chính xác
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    window = USBBootCreator()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()