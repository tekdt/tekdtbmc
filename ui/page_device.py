import subprocess
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton)
from PySide6.QtCore import Qt, QTimer

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
        self.drive_fetch_worker = self.main_app._create_and_start_worker(
            name="DriveFetcher",
            target=self._fetch_drives_task,
            on_result=self._update_drive_combo,
            on_finished=self._on_fetch_finished
        )

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