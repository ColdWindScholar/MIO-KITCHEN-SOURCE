import sys

from PySide6.QtCore import Qt, QObject, Signal, QThread, QElapsedTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFrame
from qfluentwidgets import SubtitleLabel, BodyLabel, IndeterminateProgressRing, PushButton


class StreamToSignal(QObject):
    text_written = Signal(str)

    def __init__(self, original_stream):
        super().__init__()
        self.original_stream = original_stream

    def write(self, text):
        self.original_stream.write(text)
        cleaned = text.strip()
        if cleaned:
            # 优雅清洗进度条和换行符干扰
            cleaned = cleaned.replace('\r', '\n').split('\n')[-1].strip()
            if cleaned:
                self.text_written.emit(cleaned)

    def flush(self):
        self.original_stream.flush()


# =========================================================================
# ⚙️ 2. 泛用性高并发后台线程 (Production Generic Worker)
# =========================================================================
class GenericTaskWorker(QThread):
    task_finished = Signal(bool)

    def __init__(self, target_func, *args, **kwargs):
        super().__init__()
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.target_func(*self.args, **self.kwargs)
            self.task_finished.emit(True)
        except Exception as e:
            print(f"\n[ERROR] Core collapse: {str(e)}")
            self.task_finished.emit(False)


# =========================================================================
# 🎨 3. 终极版极致静音通用提示窗 (Premium Minimalist Dialog)
# =========================================================================
class StreamLogDialog(QDialog):
    def __init__(self, title_text="处理中...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.setFixedSize(400, 240)  # 紧凑无赘肉
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        self.elapsed_timer = QElapsedTimer()
        self.worker = None

        self.initUI(title_text)

    def initUI(self, title_text):
        self.setStyleSheet("""
            QDialog {
                background-color: #1c1c1e; 
            }
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 20)
        main_layout.setSpacing(0)

        # 1. 顶层状态轨
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.title_label = SubtitleLabel(title_text, self)
        self.title_label.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 500; font-family: system-ui;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)

        # 精致微型小圆环
        self.progress_ring = IndeterminateProgressRing(self)
        self.progress_ring.setFixedSize(18, 18)
        self.progress_ring.setStrokeWidth(2.2)
        header_layout.addWidget(self.progress_ring)
        main_layout.addLayout(header_layout)

        main_layout.addSpacing(12)

        # 2. 状态标签（全中性色）
        self.status_label = BodyLabel("连接到内核...", self)
        self.status_label.setStyleSheet("color: #8e8e93; font-size: 13px; font-family: system-ui;")
        main_layout.addWidget(self.status_label)

        main_layout.addSpacing(20)

        # 3. 生产级单线横向卡片仪表盘
        self.dashboard_panel = QFrame(self)
        self.dashboard_panel.hide()

        dash_layout = QHBoxLayout(self.dashboard_panel)
        dash_layout.setContentsMargins(12, 8, 12, 8)
        dash_layout.setSpacing(10)


        dash_layout.addSpacing(12)


        dash_layout.addStretch(1)

        self.val_func = BodyLabel("kernel")
        self.val_func.setStyleSheet("color: #48484a; font-size: 17px; font-weight: bold;")
        dash_layout.addWidget(self.val_func)

        main_layout.addWidget(self.dashboard_panel)
        main_layout.addStretch(1)

        # 4. 底部确定控制栏
        footer_layout = QHBoxLayout()
        footer_layout.addStretch(1)
        self.close_btn = PushButton("确定", self)
        self.close_btn.setFixedWidth(72)
        self.close_btn.setEnabled(False)

        # 💡 核心修复：连接到自定义的显式关闭函数，不再使用容易失效的隐式 self.accept
        self.close_btn.clicked.connect(self._on_close_clicked)

        footer_layout.addWidget(self.close_btn)
        main_layout.addLayout(footer_layout)
    def start_redirected_task(self, worker_thread: GenericTaskWorker):
        self.worker = worker_thread

        self.stdout_redirector = StreamToSignal(sys.stdout)
        self.stderr_redirector = StreamToSignal(sys.stderr)

        self.stdout_redirector.text_written.connect(self._clean_and_render_text)
        self.stderr_redirector.text_written.connect(self._clean_and_render_text)

        sys.stdout = self.stdout_redirector
        sys.stderr = self.stderr_redirector
        self.worker.task_finished.connect(self._on_task_completed)

        self.elapsed_timer.start()
        self.progress_ring.start()
        self.worker.start()

    def _clean_and_render_text(self, text):
        display_text = text
        for prefix in ["[INFO]", "[WARNING]", "[ERROR]", "[SUCCESS]", ">>"]:
            if prefix in text:
                display_text = text.replace(prefix, "").strip()
                break

        if len(display_text) > 36:
            display_text = display_text[:34] + "..."

        self.status_label.setText(display_text)

    def _on_task_completed(self, success):
        seconds_spent = self.elapsed_timer.elapsed() / 1000.0

        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

        self.progress_ring.stop()
        self.progress_ring.hide()

        self.close_btn.setEnabled(True)
        self.close_btn.setFocus()  # 回车盲操聚焦



        if self.worker and hasattr(self.worker, 'target_func'):
            func_name = getattr(self.worker.target_func, '__name__', 'anonymous')
            self.val_func.setText(f"{func_name} finished in {seconds_spent} seconds")


        if success:
            self.title_label.setText("任务已完成")
            self.status_label.setText("操作已成功结束。")
        else:
            self.title_label.setText("发生异常")
            self.title_label.setStyleSheet("color: #ff453a; font-size: 15px; font-weight: 500;")
            self.status_label.setText("执行中遭遇中断，请查看终端报错。")

        self.dashboard_panel.show()

    def _on_close_clicked(self):
        """💡 核心修复：显式关闭当前的模态框，规避 Fluent 组件的底层摩擦阻断"""
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        self.done(1)  # 通知事件流结束，1秒瞬间闭合

    def closeEvent(self, event):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        super().closeEvent(event)
