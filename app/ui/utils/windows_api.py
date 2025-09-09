import ctypes
import os
import sys
import subprocess
import config
import psutil
from ctypes import wintypes

def is_admin():
    """Kiểm tra xem ứng dụng có đang chạy với quyền admin không."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def elevate_privileges():
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

def install_wincdemu_driver():
    """[FIX] Cài đặt driver WinCDEmu portable khi ứng dụng khởi động."""
    if not os.path.exists(config.WINCDEMU_EXE):
        print("Không tìm thấy WinCDEmu.exe, bỏ qua cài đặt driver.")
        return
    try:
        print("Đang cài đặt driver WinCDEmu portable...")
        # Sử dụng CREATE_NO_WINDOW để không hiện cửa sổ console
        result = run([config.WINCDEMU_EXE, "/install"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        # Kiểm tra lỗi, nhưng bỏ qua lỗi "đã tồn tại"
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"Lỗi khi cài đặt driver WinCDEmu: {result.stderr}")
        else:
            print("Driver WinCDEmu đã được cài đặt hoặc đã tồn tại.")
    except Exception as e:
        print(f"Ngoại lệ khi cài đặt driver WinCDEmu: {e}")

def uninstall_wincdemu_driver():
    """[FIX] Gỡ cài đặt driver WinCDEmu portable khi ứng dụng đóng."""
    if not os.path.exists(config.WINCDEMU_EXE):
        print("Không tìm thấy WinCDEmu.exe, bỏ qua gỡ cài đặt driver.")
        return
    try:
        print("Đang gỡ cài đặt driver WinCDEmu portable...")
        # Sử dụng CREATE_NO_WINDOW để không hiện cửa sổ console
        run([config.WINCDEMU_EXE, "/uninstall"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        print("Đã gỡ cài đặt driver WinCDEmu.")
    except Exception as e:
        print(f"Ngoại lệ khi gỡ cài đặt driver WinCDEmu: {e}")

def _get_windows_for_pid(pid):
    """Enumerate hwnd cho PID, nhưng chỉ thêm nếu title == 'TekDT AIS'."""
    hwnds = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @EnumWindowsProc
    def _enum(hwnd, lParam):
        pid_dw = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_dw))
        if pid_dw.value == pid:
            title = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, title, 256)
            if title.value == "TekDT AIS":  # Chỉ thêm nếu title khớp
                hwnds.append(hwnd)
                print(f"HWND {hwnd} thuộc PID {pid}, title: {title.value} (đã thêm)")
            else:
                print(f"HWND {hwnd} thuộc PID {pid}, title: {title.value} (bỏ qua vì không khớp title)")
        return True

    ctypes.windll.user32.EnumWindows(_enum, 0)
    return hwnds

def _find_ais_window_task(main_window):
    """
    Tìm mọi cửa sổ thuộc tiến trình TekDT AIS (dựa trên PID chính, các tiến trình con, và title).
    Nếu tìm thấy, chuyển về TOOLWINDOW, ẩn ngay lập tức, rồi nhúng nếu ở page3.
    """
    main_window.find_ais_window_timer.attempts += 1

    # Nếu đã có danh sách hwnds thì không cần tìm lại
    if getattr(main_window, "ais_hwnds", None):
        return

    # Lấy PID từ main_window.ais_process
    pid = None
    if getattr(main_window, "ais_process", None):
        try:
            pid = main_window.ais_process.pid
        except Exception:
            pid = None

    # Tìm tất cả hwnd từ PID chính và các tiến trình con (đã lọc theo title trong _get_windows_for_pid)
    hwnds = []
    if pid:
        related_pids = _get_all_related_pids(pid)
        print(f"Các PID liên quan của TekDT AIS: {related_pids}")
        for related_pid in related_pids:
            hwnds.extend(_get_windows_for_pid(related_pid))

    # Tìm thêm theo title "TekDT AIS" (bổ sung, nếu không gắn với PID)
    h = ctypes.windll.user32.FindWindowW(None, "TekDT AIS")
    if h and h not in hwnds:
        hwnds.append(h)
        print(f"Tìm thấy cửa sổ theo title 'TekDT AIS': {h}")

    if hwnds:
        main_window.ais_hwnds = hwnds
        main_window.find_ais_window_timer.stop()
        print(f"Đã tìm thấy {len(hwnds)} cửa sổ TekDT AIS hợp lệ: {hwnds}")

        # Thay đổi style và ẩn ngay lập tức
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        for hwnd in hwnds:
            try:
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ex_style = (ex_style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE (ẩn trước khi nhúng)
            except Exception as e:
                print(f"Lỗi khi chỉnh style cho HWND {hwnd}: {e}")

        # Nếu ở page3, nhúng ngay
        if main_window.stacked_widget.currentWidget() == main_window.page3:
            main_window.embed_ais_window()

    elif main_window.find_ais_window_timer.attempts > 120:  # 30 giây
        main_window.find_ais_window_timer.stop()
        print("Không thể tìm thấy cửa sổ TekDT AIS sau 30 giây. Tiếp tục chạy ẩn, không cleanup.")

def _get_all_related_pids(parent_pid):
    """
    Lấy danh sách tất cả PID liên quan, bao gồm PID chính và các tiến trình con.
    """
    pids = [parent_pid]
    try:
        parent = psutil.Process(parent_pid)
        for child in parent.children(recursive=True):
            pids.append(child.pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return pids

def embed_ais_window(main_window):
    """Nhúng các cửa sổ TekDT AIS vào container trên page3."""
    hwnds = getattr(main_window, "ais_hwnds", None)
    if not hwnds or not main_window.page3:
        print("Không nhúng được: Không có hwnd hoặc page3 không tồn tại.")
        return

    container = main_window.page3.embed_container
    container_id = int(container.winId())

    GWL_STYLE = -16
    SWP_FRAMECHANGED = 0x0020
    SWP_NOZORDER = 0x0004
    SWP_SHOWWINDOW = 0x0040

    pixel_ratio = main_window.devicePixelRatioF()
    container_size = container.size()
    physical_width = int(container_size.width() * pixel_ratio)
    physical_height = int(container_size.height() * pixel_ratio)

    for hwnd in hwnds:
        try:
            # Thiết lập style: WS_CHILD, xóa caption/thickframe
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            style |= 0x40000000  # WS_CHILD
            style &= ~0x00C00000  # Xóa WS_CAPTION
            style &= ~0x00040000  # Xóa WS_THICKFRAME
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            # Set parent để nhúng
            ctypes.windll.user32.SetParent(hwnd, container_id)

            # Đặt kích thước và vị trí
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, physical_width, physical_height,
                SWP_FRAMECHANGED | SWP_NOZORDER | SWP_SHOWWINDOW
            )

            # Hiển thị cửa sổ nhúng (force show sau nhúng)
            ctypes.windll.user32.ShowWindow(hwnd, 1)  # SW_SHOW
            ctypes.windll.user32.UpdateWindow(hwnd)  # Force redraw
            ctypes.windll.user32.BringWindowToTop(hwnd)  # Đưa lên trên để tránh bị đè
        except Exception as e:
            print(f"Lỗi khi nhúng HWND {hwnd}: {e}")

    container.setVisible(True)
    print(f"Đã nhúng {len(hwnds)} cửa sổ TekDT AIS vào container.")

    # Đặt lại kích thước sau 100ms
    QTimer.singleShot(100, main_window.resize_ais_window)

def resize_ais_window(main_window):
    """Thay đổi kích thước cửa sổ TekDT AIS nhúng để khớp với container."""
    if not hasattr(main_window, "ais_hwnds") or not main_window.ais_hwnds:
        print("Không có cửa sổ TekDT AIS để thay đổi kích thước.")
        return

    container = main_window.page3.embed_container
    if not container.isVisible():
        print("Container không hiển thị, bỏ qua thay đổi kích thước.")
        return

    pixel_ratio = main_window.devicePixelRatioF()  # Lấy tỷ lệ DPI
    container_size = container.size()
    physical_width = int(container_size.width() * pixel_ratio)
    physical_height = int(container_size.height() * pixel_ratio)

    # Định nghĩa các cờ SetWindowPos (nếu chưa có ở nơi khác)
    SWP_FRAMECHANGED = 0x0020
    SWP_NOZORDER = 0x0004
    SWP_SHOWWINDOW = 0x0040

    for hwnd in main_window.ais_hwnds:
        try:
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, physical_width, physical_height,
                SWP_FRAMECHANGED | SWP_NOZORDER | SWP_SHOWWINDOW
            )
            print(f"Đã thay đổi kích thước HWND {hwnd} thành {physical_width}x{physical_height}")
        except Exception as e:
            print(f"Lỗi khi thay đổi kích thước HWND {hwnd}: {e}")

def hide_ais_window(main_window):
    """Ẩn tất cả cửa sổ TekDT AIS khi không ở page3."""
    hwnds = getattr(main_window, "ais_hwnds", None)
    if not hwnds:
        return
    for hwnd in hwnds:
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            ctypes.windll.user32.SetParent(hwnd, 0)  # Tháo parent nếu cần
        except Exception as e:
            print(f"Lỗi khi ẩn HWND {hwnd}: {e}")