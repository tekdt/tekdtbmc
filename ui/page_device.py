import subprocess
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton)
from PySide6.QtCore import Qt, QTimer

MIN_UNALLOCATED_SPACE_BYTES = 1 * 1024 * 1024 * 1024 

class PageDeviceSelect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        self.drive_worker = None
        self.is_fetching = False
        self.eligibility_worker = None
        self.init_ui()
        self.start_drive_monitor()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 20, 50, 50)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Bước 1: Chọn thiết bị")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        layout.addWidget(QLabel("Chọn ổ đĩa bạn muốn sử dụng:"))

        self.drive_combo = QComboBox()
        self.drive_combo.currentIndexChanged.connect(self.on_drive_selected)
        layout.addWidget(self.drive_combo)
        
        self.eligibility_status_label = QLabel("")
        self.eligibility_status_label.setStyleSheet("font-style: italic; color: #EBCB8B;")
        self.eligibility_status_label.setWordWrap(True)
        layout.addWidget(self.eligibility_status_label)

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
        
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        
        show_all = self.show_hdd_check.isChecked()
        found_drives = False
        new_index_to_select = -1

        if not disks:
            self.drive_combo.addItem("Không thể lấy danh sách ổ đĩa", None)
        else:
            for disk in disks:
                bus_type = disk.get('BusType', 'Unknown')
                media_type = disk.get('MediaType', 'Unspecified')
                is_usb = (bus_type == 'USB' or media_type == 'Removable')
                
                if show_all or is_usb:
                    found_drives = True
                    model = disk.get('FriendlyName', 'Unknown Disk')
                    size = int(disk.get('Size', 0))
                    
                    gb_size = size / (1024**3)
                    display_text = f"{model} ({gb_size:.2f} GB) - {bus_type}"
                    self.drive_combo.addItem(display_text, disk)

                    # Kiểm tra xem mục này có phải là mục đã chọn trước đó không
                    if current_selection and disk.get('DeviceID') == current_selection.get('DeviceID'):
                        new_index_to_select = self.drive_combo.count() - 1

            if not found_drives:
                self.drive_combo.addItem("Không tìm thấy USB nào" if not show_all else "Không tìm thấy ổ đĩa nào", None)

        # Chọn lại mục đã chọn trước đó nếu nó vẫn tồn tại
        if new_index_to_select != -1:
            self.drive_combo.setCurrentIndex(new_index_to_select)
        elif self.drive_combo.count() > 0:
            self.drive_combo.setCurrentIndex(0)

        #! Mở lại tín hiệu
        self.drive_combo.blockSignals(False)
        
        # Vì đã chặn tín hiệu, chúng ta cần kiểm tra xem lựa chọn hiện tại có khác với lựa chọn trong config không
        # Nếu khác (ví dụ: USB bị rút ra), hãy kích hoạt on_drive_selected để cập nhật trạng thái
        current_data = self.drive_combo.currentData()
        config_data = self.main_app.config.get("device_details")
        
        current_id = current_data.get('DeviceID') if current_data else None
        config_id = config_data.get('DeviceID') if config_data else None

        if current_id != config_id:
            self.on_drive_selected(self.drive_combo.currentIndex())

    def on_drive_selected(self, index):
        #! Hủy bỏ worker kiểm tra cũ nếu nó đang chạy để tránh xung đột
        if self.eligibility_worker and self.eligibility_worker.isRunning():
            self.eligibility_worker.terminate()
            self.eligibility_worker.wait() # Đợi worker dừng hẳn

        self.eligibility_status_label.setText("") # Clear previous status
        if index == -1 or self.drive_combo.itemData(index) is None:
            self.main_app.config["device"] = None
            self.main_app.config["device_name"] = None
            self.main_app.config["device_details"] = None
            self.main_app.config["install_mode"] = "DESTRUCTIVE"
            self.next_button.setEnabled(False)
            self.main_app.usb_monitor_timer.stop()
            return

        disk_details = self.drive_combo.itemData(index)
        device_path = f"\\\\.\\PHYSICALDRIVE{disk_details['DeviceID']}"
        device_name = self.drive_combo.itemText(index)

        self.main_app.config["device"] = device_path
        self.main_app.config["device_name"] = device_name
        self.main_app.config["device_details"] = disk_details
        
        bus_type = disk_details.get('BusType', 'Unknown')
        media_type = disk_details.get('MediaType', 'Unspecified')
        is_usb = (bus_type == 'USB' or media_type == 'Removable')

        # If it's a USB or removable drive, proceed as normal (destructive mode)
        if is_usb:
            self.main_app.config["install_mode"] = "DESTRUCTIVE"
            self.eligibility_status_label.setText("Chế độ: Xóa toàn bộ dữ liệu trên USB và cài mới.")
            self.eligibility_status_label.setStyleSheet("font-style: italic; color: #D8DEE9;")
            self.next_button.setEnabled(True)
            self.main_app.usb_monitor_timer.start(2000)
        else:
            # If it's a regular HDD/SSD, check for non-destructive eligibility
            self.main_app.usb_monitor_timer.stop() # Stop USB check for HDD
            self.next_button.setEnabled(False) # Disable until check is complete
            self.eligibility_status_label.setText("Đang kiểm tra ổ cứng để cài đặt không phá hủy...")
            self.eligibility_status_label.setStyleSheet("font-style: italic; color: #EBCB8B;")
            
            self.eligibility_worker = self.main_app._create_and_start_worker(
                name="HddEligibilityCheck",
                target=self._check_hdd_eligibility_task,
                on_result=self._handle_hdd_eligibility_result,
                args=[disk_details['DeviceID']]
            )

    def _check_hdd_eligibility_task(self, disk_id):
        """
        Checks a disk for sufficient unallocated space for non-destructive install.
        Returns a tuple: (is_eligible, message)
        """
        try:
            # 1. Get total disk size
            cmd_disk_size = f"(Get-Disk -Number {disk_id}).Size"
            proc_disk_size = subprocess.run(['powershell', '-Command', cmd_disk_size], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            total_size = int(proc_disk_size.stdout.strip())

            # 2. Get sum of all partitions' sizes
            cmd_partitions_size = f"Get-Partition -DiskNumber {disk_id} | Measure-Object -Property Size -Sum | Select-Object -ExpandProperty Sum"
            proc_partitions_size = subprocess.run(['powershell', '-Command', cmd_partitions_size], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Xử lý trường hợp không có phân vùng nào
            partitions_output = proc_partitions_size.stdout.strip()
            partitions_total_size = int(partitions_output) if partitions_output else 0
            
            unallocated_space = total_size - partitions_total_size
            
            if unallocated_space >= MIN_UNALLOCATED_SPACE_BYTES:
                gb_space = unallocated_space / (1024**3)
                return (True, f"Phát hiện {gb_space:.2f} GB dung lượng trống. Sẵn sàng cho cài đặt không phá hủy.")
            else:
                gb_required = MIN_UNALLOCATED_SPACE_BYTES / (1024**3)
                return (False, f"Không đủ dung lượng chưa phân bổ ở cuối ổ đĩa. Yêu cầu ít nhất {gb_required:.2f} GB.")

        except Exception as e:
            print(f"Error checking HDD eligibility: {e}")
            return (False, "Lỗi khi kiểm tra ổ đĩa. Không thể tiếp tục.")

    def _handle_hdd_eligibility_result(self, result):
        is_eligible, message = result
        if is_eligible:
            self.main_app.config["install_mode"] = "NON_DESTRUCTIVE"
            self.eligibility_status_label.setText(f"✅ {message}")
            self.eligibility_status_label.setStyleSheet("font-style: italic; color: #A3BE8C;") # Green
            self.next_button.setEnabled(True)
        else:
            self.main_app.config["install_mode"] = "DESTRUCTIVE" # Fallback
            self.eligibility_status_label.setText(f"❌ {message}")
            self.eligibility_status_label.setStyleSheet("font-style: italic; color: #BF616A;") # Red
            self.next_button.setEnabled(False)