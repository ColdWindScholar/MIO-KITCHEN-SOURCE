import logging
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QFrame, QFileDialog
from qfluentwidgets import (
    HyperlinkCard, TitleLabel, SwitchSettingCard, FluentIcon, qconfig, OptionsSettingCard, ComboBoxSettingCard,
    PushSettingCard, PrimaryPushSettingCard
)
from qfluentwidgets.common.config import ConfigItem, BoolValidator, QConfig, OptionsConfigItem, OptionsValidator
from src.core.utils import prog_path, temp, re_folder
from utils import hum_convert

config_file = os.path.abspath(os.path.join(prog_path, 'bin', "settings.json"))


class Config(QConfig):
    """ 应用配置类 """
    allLanguages = [i[:-5] for i in os.listdir(os.path.join(prog_path, 'bin', 'languages'))]
    workingFolder = ConfigItem("Tool", "WorkingFolder", prog_path)
    language = OptionsConfigItem(
        "Tool", "Language", "English", OptionsValidator(allLanguages), restart=True)
    aiEngine = ConfigItem("Tool", 'AiEngine', False, BoolValidator())
    projectStructure = OptionsConfigItem("Tool", "ProjectStructure", "Single", OptionsValidator(['Single', "Split"]))
    cpioImpl = OptionsConfigItem("Tool", "CpioImpl", "Native", OptionsValidator(['Native', "Python"]))
    autoSaveProjects = ConfigItem("Projects", "AutoSave", True, BoolValidator())
    enableNotifications = ConfigItem("General", "EnableNotifications", True, BoolValidator())

def load_config():
    """ 加载配置文件 """
    config = Config()
    qconfig.load(config_file, config)
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
        # theme
        self.theme_card = OptionsSettingCard(
            qconfig.themeMode,
            FluentIcon.BRUSH,
            "应用主题",
            "调整你的应用外观",
            texts=["浅色", "深色", "跟随系统设置"]
        )
        self.scrollLayout.addWidget(self.theme_card)
        #languages
        self.languageCard = ComboBoxSettingCard(
            configItem=cfg.language,
            icon=FluentIcon.LANGUAGE,
            title="语言",
            content="调整语言",
            texts=cfg.allLanguages
        )
        self.scrollLayout.addWidget(self.languageCard)
        #
        self.workingCard = PushSettingCard(text="选择文件夹",
                                           icon=FluentIcon.DOWNLOAD,
                                           title="下载目录",
                                           content=cfg.workingFolder.value)
        self.workingCard.clicked.connect(self.change_working_folder)
        self.scrollLayout.addWidget(self.workingCard)

        #
        self.projectStructureCard = OptionsSettingCard(
            cfg.projectStructure,
            FluentIcon.PROJECTOR,
            "projectStructureCard",
            "projectStructureCard",
            texts=cfg.projectStructure.options
        )
        self.scrollLayout.addWidget(self.projectStructureCard)
        self.cpioImplCard = OptionsSettingCard(
            cfg.cpioImpl,
            FluentIcon.UNIT,
            "cpioImpl",
            "cpioImpl",
            texts=cfg.cpioImpl.options
        )
        # clean
        self.cleanCacheCard = PrimaryPushSettingCard(
            text="Clean",
            icon=FluentIcon.DOWNLOAD,
            title="CacheSize",
            content=hum_convert(self.get_cache_size())
        )
        self.cleanCacheCard.clicked.connect(self.clean_cache)
        self.scrollLayout.addWidget(self.cleanCacheCard)

        self.scrollLayout.addWidget(self.cpioImplCard)
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

    def change_working_folder(self):
        if not (folder := QFileDialog.getExistingDirectory()):
            return
        cfg.set(cfg.workingFolder, folder)
        self.workingCard.setContent(cfg.workingFolder.value)

    def get_cache_size(self):
        size = 0
        for root, _, files in os.walk(temp):
            try:
                size += sum([os.path.getsize(os.path.join(root, name)) for name in files if
                             not os.path.islink(os.path.join(root, name))])
            except:
                logging.exception("Bugs")
        return size

    def clean_cache(self):
        try:
            re_folder(temp)
        except:
            logging.exception("Bugs")
        self.cleanCacheCard.setContent(hum_convert(self.get_cache_size()))
