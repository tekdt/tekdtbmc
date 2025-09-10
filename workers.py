from PySide6.QtCore import QThread, Signal

class Worker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str)
    result = Signal(object)
    about_to_finish = Signal(QThread)

    def __init__(self, name, target, *args, **kwargs):
        super().__init__()
        self.name = name
        self.target = target
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """
        Chạy target trong thread, luôn phát result (cả khi là None)
        và đảm bảo phát finished/about_to_finish đúng.
        """
        res = None
        try:
            res = self.target(*self.args, **self.kwargs)
            try:
                self.result.emit(res)
            except Exception as e:
                print(f"Lỗi khi emit result trong Worker '{self.name}': {e}")
            self.finished.emit(True, "Tác vụ hoàn thành thành công.")
        except Exception as e:
            if not isinstance(e, SystemExit):
                print(f"Lỗi trong luồng Worker '{self.name}': {e}")
                try:
                    self.result.emit(None)
                except Exception:
                    pass
                self.finished.emit(False, f"Lỗi trong luồng Worker '{self.name}':\n{str(e)}")
        finally:
            try:
                self.about_to_finish.emit(self)
            except Exception:
                pass