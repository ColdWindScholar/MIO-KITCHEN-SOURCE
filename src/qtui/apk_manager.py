from PySide6.QtWidgets import QWidget
from androguard.core.apk import APK
from loguru import logger
logger.remove()

class ApkManagerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ApkManagerPage")
