from PySide6.QtCore import Slot
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import PushButton, TextEdit

class LogMessageBoxBase(QWidget):
    """
    一个通用的日志弹窗基础类
    支持展示不同颜色的日志（Info, Warning, Error）
    """

    def __init__(self, title="日志详情", parent=None):
        # 确保 parent 和当前窗口在同一个线程（通常是主线程）
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(500, 350)

        # 初始化布局
        self.layout = QVBoxLayout(self)

        # 文本显示区域（只读）
        self.text_edit = TextEdit(self)
        self.text_edit.setReadOnly(True)
        self.layout.addWidget(self.text_edit)

        # 底部按钮布局
        self.button_layout = QHBoxLayout()
        self.clear_btn = PushButton("清空", self)

        self.button_layout.addStretch()
        self.button_layout.addWidget(self.clear_btn)
        self.layout.addLayout(self.button_layout)

        # 绑定按钮事件
        self.clear_btn.clicked.connect(self.text_edit.clear)

        # 预设不同日志级别的颜色格式
        self._formats = {
            "INFO": self._create_format(QColor("#2ECC71")),  # 绿色
            "WARN": self._create_format(QColor("#F1C40F")),  # 黄色
            "ERROR": self._create_format(QColor("#E74C3C")),  # 红色
            "DEBUG": self._create_format(QColor("#95A5A6")),  # 灰色
        }

    def _create_format(self, color: QColor) -> QTextCharFormat:
        """创建特定颜色的文本格式"""
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        return fmt

    @Slot(str, str)
    def append_log(self, level: str, message: str):
        """
        核心方法：追加一条带颜色的日志
        使用 @Slot 装饰器，确保它可以安全地接收来自外部（甚至子线程）的信号
        """
        level = level.upper()
        fmt = self._formats.get(level, self._formats["INFO"])

        # 移动光标到末尾，防止用户点击导致插入位置错乱
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

        # 插入带颜色的日志级别前缀，形如 [INFO]
        self.text_edit.setCurrentCharFormat(fmt)
        self.text_edit.insertPlainText(f"[{level}] ")

        # 插入正文（恢复默认颜色）
        default_fmt = QTextCharFormat()
        self.text_edit.setCurrentCharFormat(default_fmt)
        self.text_edit.insertPlainText(f"{message}\n")

        # 自动滚动到最下方
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
