import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QFrame
from qfluentwidgets import (
    HyperlinkCard, TitleLabel, SwitchSettingCard, FluentIcon, qconfig
)
from qfluentwidgets.common.config import ConfigItem, BoolValidator, QConfig, OptionsConfigItem, OptionsValidator
from src.core.utils import prog_path

config_file = os.path.abspath(os.path.join(prog_path, 'bin', "settings.json"))


class Config(QConfig):
    """ 应用配置类 """
    #themeMode = OptionsConfigItem("Settings", 'theme', 'auto', OptionsValidator(['auto', 'dark', 'light']), restart=True)
    autoSaveProjects = ConfigItem("Projects", "AutoSave", True, BoolValidator())
    enableNotifications = ConfigItem("General", "EnableNotifications", True, BoolValidator())

def load_config():
    """ 加载配置文件 """
    config = Config()
    qconfig.load(config_file, cfg)
    return config



# 初始化配置
cfg = load_config()

class SettingsPage(QScrollArea):
    """ 设置页面 """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self.initUI()
        
        self.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#scrollWidget {
                background: transparent;
            }
        """)

    def initUI(self):
        """ 初始化UI """
        self.scrollWidget = QWidget()
        self.scrollWidget.setObjectName("scrollWidget")
        self.scrollLayout = QVBoxLayout(self.scrollWidget)
        self.scrollLayout.setContentsMargins(40, 40, 40, 40)
        self.scrollLayout.setSpacing(20)
        self.scrollLayout.setAlignment(Qt.AlignTop)
        
        title = TitleLabel("设置", self.scrollWidget)
        self.scrollLayout.addWidget(title)

        self.autoSaveCard = SwitchSettingCard(
            FluentIcon.SAVE,
            "自动保存项目",
            "在关闭项目时自动保存项目数据",
            cfg.autoSaveProjects,
            parent=self.scrollWidget
        )
        self.autoSaveCard.setChecked(cfg.autoSaveProjects.value)
        self.scrollLayout.addWidget(self.autoSaveCard)

        self.notificationCard = SwitchSettingCard(
            FluentIcon.RINGER,
            "启用通知",
            "在操作完成时显示通知提醒",
            cfg.enableNotifications,
            parent=self.scrollWidget
        )
        self.notificationCard.setChecked(cfg.enableNotifications.value)
        self.scrollLayout.addWidget(self.notificationCard)

        self.helpCard = HyperlinkCard(
            "#",
            "打开帮助页面",
            FluentIcon.HELP,
            "帮助",
            "发现 ROM Tools 的神奇用法",
            self.scrollWidget
        )
        self.scrollLayout.addWidget(self.helpCard)

        self.scrollLayout.addStretch()
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
