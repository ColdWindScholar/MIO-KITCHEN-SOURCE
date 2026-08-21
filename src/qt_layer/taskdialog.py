import sys

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout
from qfluentwidgets import SubtitleLabel, IndeterminateProgressRing, PushButton, PlainTextEdit


# =========================================================================
# 📡 1. Stream Interceptor (Redirects sys.stdout safely to Qt Signals)
# =========================================================================
class StreamToSignal(QObject):
    text_written = Signal(str)

    def __init__(self, original_stream):
        super().__init__()
        self.original_stream = original_stream

    def write(self, text):
        # Always output to native console terminal as a reliable backup
        self.original_stream.write(text)
        if text.strip():  # Skip empty newline clutter lines
            self.text_written.emit(text)

    def flush(self):
        self.original_stream.flush()



class GenericTaskWorker(QThread):

    task_finished = Signal(bool) # Emits True on success, False on exception

    def __init__(self, target_func, *args, **kwargs):
        super().__init__()
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # Execute your normal Python function with all passed parameters
            self.target_func(*self.args, **self.kwargs)
            self.task_finished.emit(True)
        except Exception as e:
            # Print the error so sys.stderr / the dialog catches and displays the stacktrace
            print(f"\n[ERROR] Thread execution collapsed with exception:\n{str(e)}")
            self.task_finished.emit(False)

class TaskWorker(QThread):
    """Executes long-running file operations safely off the GUI main thread."""
    task_finished = Signal(bool)

    def run(self):
        try:
            # 💡 Standard print commands will be automatically captured by the dialog!
            print("[INFO] Starting pipeline execution suite...")

            print("[INFO] Loading source image vectors into allocation maps...")

            print("[WARNING] Sparse layout detected inside block metadata.")

            print("[SUCCESS] Image decompression sequence concluded successfully.")
            self.task_finished.emit(True)
        except Exception as e:
            print(f"[ERROR] Task encountered structural crash failure: {str(e)}")
            self.task_finished.emit(False)


class StreamLogDialog(QDialog):
    def __init__(self, title_text="正在处理核心流水线", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.resize(580, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr

        self.initUI(title_text)

    def initUI(self, title_text):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        self.title_label = SubtitleLabel(title_text, self)

        # High-tech loader indicator asset tracking state configurations
        self.progress_ring = IndeterminateProgressRing(self)
        self.progress_ring.setFixedSize(22, 22)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.progress_ring)
        main_layout.addLayout(header_layout)

        # Consolas Monospace Cyberpunk Log Text Window Framework Frame
        self.console_view = PlainTextEdit(self)
        self.console_view.setReadOnly(True)
        self.console_view.setUndoRedoEnabled(False)

        main_layout.addWidget(self.console_view)

        # Bottom Confirmation Layout Space Drawer
        footer_layout = QHBoxLayout()
        footer_layout.addStretch(1)
        self.close_btn = PushButton("确定", self)
        self.close_btn.setFixedWidth(100)
        self.close_btn.setEnabled(False)  # Locked tight until task completion signature registers
        self.close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.close_btn)
        main_layout.addLayout(footer_layout)

    def start_redirected_task(self, worker_thread: QThread):
        """Hijacks standard I/O streams and runs the worker thread smoothly."""
        self.worker = worker_thread

        # 🔗 Route stdout and stderr targets straight into stream interceptor logic
        self.stdout_redirector = StreamToSignal(sys.stdout)
        self.stderr_redirector = StreamToSignal(sys.stderr)

        self.stdout_redirector.text_written.connect(self._append_redirected_text)
        self.stderr_redirector.text_written.connect(self._append_redirected_text)

        sys.stdout = self.stdout_redirector
        sys.stderr = self.stderr_redirector

        # Listen for task thread resolution markers
        self.worker.task_finished.connect(self._on_task_completed)

        # Fire up animation loops and asynchronous execution processing layers
        self.progress_ring.start()
        self.worker.start()

    def _append_redirected_text(self, text):
        self.console_view.moveCursor(self.console_view.textCursor().MoveOperation.End)
        self.console_view.insertPlainText(text)
        self.console_view.ensureCursorVisible()

    def _on_task_completed(self, success):
        """Gracefully tears down the stream hijack loops when background works finish."""
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

        self.progress_ring.stop()
        self.progress_ring.hide()
        self.close_btn.setEnabled(True)

        if success:
            self.title_label.setText("任务执行成功")
            self._append_redirected_text("[TASK] Done!")
        else:
            self.title_label.setText("任务执行中断")
            self._append_redirected_text("[ERROR] Failed!")

    def closeEvent(self, event):
        """Safety check to ensure streams are restored even if user forces window closed."""
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        super().closeEvent(event)
