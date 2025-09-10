import ui.utils.windows_api as windows_api
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox, 
                             QHBoxLayout, QProgressBar, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QTimer

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
        # Kiểm tra xem phương thức tồn tại trước khi gọi
        windows_api.resize_ais_window(self.main_app)
        # Force update container để tránh lỗi hiển thị
        if hasattr(self, 'embed_container'):
            self.embed_container.update()
  
    def show_progress_ui(self, show):
        self.progress_bar.setVisible(show)
        self.status_label.setVisible(show)
        self.start_button.setEnabled(not show)
        self.back_button.setEnabled(not show)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, text):
        self.status_label.setText(text)
