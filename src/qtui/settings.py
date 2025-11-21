import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QFrame
from qfluentwidgets import (
    HyperlinkCard, TitleLabel, SwitchSettingCard, FluentIcon
)
from qfluentwidgets.common.config import ConfigItem, BoolValidator, QConfig


class Config(QConfig):
    """ 应用配置类 """
    autoSaveProjects = ConfigItem("Projects", "AutoSave", True, BoolValidator())
    enableNotifications = ConfigItem("General", "EnableNotifications", True, BoolValidator())

def load_config():
    """ 加载配置文件 """
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.json"))
    cfg = Config()
    
    if not os.path.exists(config_file) or os.path.getsize(config_file) == 0:
        save_config(cfg)
        return cfg

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "Projects/AutoSave" in data:
            cfg.autoSaveProjects.value = data["Projects/AutoSave"]
        if "General/EnableNotifications" in data:
            cfg.enableNotifications.value = data["General/EnableNotifications"]
        return cfg
    except:
        os.remove(config_file) if os.path.exists(config_file) else None
        save_config(cfg)
        return cfg

def save_config(cfg):
    """ 保存配置文件 """
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.json"))
    try:
        data = {
            "Projects/AutoSave": cfg.autoSaveProjects.value,
            "General/EnableNotifications": cfg.enableNotifications.value
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except:
        pass

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
        self.autoSaveCard.checkedChanged.connect(self.on_auto_save_changed)
        self.scrollLayout.addWidget(self.autoSaveCard)

        self.notificationCard = SwitchSettingCard(
            FluentIcon.RINGER,
            "启用通知",
            "在操作完成时显示通知提醒",
            cfg.enableNotifications,
            parent=self.scrollWidget
        )
        self.notificationCard.setChecked(cfg.enableNotifications.value)
        self.notificationCard.checkedChanged.connect(self.on_notification_changed)
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

    def on_auto_save_changed(self, checked):
        cfg.autoSaveProjects.value = checked
        save_config(cfg)

    def on_notification_changed(self, checked):
        cfg.enableNotifications.value = checked
        save_config(cfg)