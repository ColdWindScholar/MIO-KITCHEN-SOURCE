import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QFrame, QFileDialog
from qfluentwidgets import (
    TitleLabel, SwitchSettingCard, FluentIcon, OptionsSettingCard, ComboBoxSettingCard,
    PushSettingCard, PrimaryPushSettingCard, setTheme
)

from src.core.utils import temp, re_folder, hum_convert
from src.qtui.settings_cfg import *


class SettingsPage(QScrollArea):
    """ 设置页面 """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self.initUI()
        

    def initUI(self):
        """ 初始化UI """
        self.scrollWidget = QWidget()
        self.scrollWidget.setObjectName("scrollWidgetSettings")
        self.scrollWidget.setStyleSheet("QWidget{background: transparent}")
        self.scrollLayout = QVBoxLayout(self.scrollWidget)
        self.scrollLayout.setContentsMargins(40, 40, 40, 40)
        self.scrollLayout.setSpacing(20)
        self.scrollLayout.setAlignment(Qt.AlignTop)
        
        title = TitleLabel(self.tr("Settings"), self.scrollWidget)
        self.scrollLayout.addWidget(title)
        # theme
        self.theme_card = OptionsSettingCard(
            qconfig.themeMode,
            FluentIcon.BRUSH,
            self.tr("Theme"),
            self.tr("Set Theme"),
            texts=[self.tr("Light"), self.tr("Dark"), self.tr("Follow System Settings")]
        )
        self.scrollLayout.addWidget(self.theme_card)
        #languages
        self.languageCard = ComboBoxSettingCard(
            configItem=cfg.language,
            icon=FluentIcon.LANGUAGE,
            title=self.tr("Language"),
            content=self.tr("Choose your Language"),
            texts=cfg.allLanguagesHum
        )
        self.scrollLayout.addWidget(self.languageCard)
        #
        self.workingCard = PushSettingCard(text=self.tr("Choose"),
                                           icon=FluentIcon.DOWNLOAD,
                                           title=self.tr("Working Folder"),
                                           content=cfg.workingFolder.value)
        self.workingCard.clicked.connect(self.change_working_folder)
        self.scrollLayout.addWidget(self.workingCard)

        #
        self.projectStructureCard = OptionsSettingCard(
            cfg.projectStructure,
            FluentIcon.CONSTRACT,
            self.tr("Project Structure"),
            self.tr("Adjust project Structure"),
            texts=cfg.projectStructure.options
        )
        self.scrollLayout.addWidget(self.projectStructureCard)
        self.cpioImplCard = OptionsSettingCard(
            cfg.cpioImpl,
            FluentIcon.UNIT,
            self.tr("Cpio Implement"),
            self.tr("Native's binary, another's built-in func."),
            texts=cfg.cpioImpl.options
        )
        # clean
        self.cleanCacheCard = PrimaryPushSettingCard(
            text=self.tr("Clean"),
            icon=FluentIcon.DOWNLOAD,
            title=self.tr("Cache Size"),
            content=hum_convert(self.get_cache_size())
        )
        self.cleanCacheCard.clicked.connect(self.clean_cache)
        self.scrollLayout.addWidget(self.cleanCacheCard)
        self.scrollLayout.addWidget(self.cpioImplCard)
        #ai
        self.aiEngine = SwitchSettingCard(
            FluentIcon.SAVE,
            self.tr("Ai Engine"),
            self.tr("An smart assistance for you"),
            cfg.aiEngine,
            parent=self.scrollWidget
        )
        self.scrollLayout.addWidget(self.aiEngine)
        #
        self.selinuxPatch = SwitchSettingCard(
            FluentIcon.SAVE,
            self.tr("Context Patch"),
            self.tr("Patch selinux context before repacking."),
            cfg.selinuxPatch,
            parent=self.scrollWidget
        )
        self.scrollLayout.addWidget(self.selinuxPatch)
        self.autoUnpack = SwitchSettingCard(
            FluentIcon.SAVE,
            self.tr("Auto Unpack"),
            self.tr("Unpack images directly."),
            cfg.autoUnpack,
            parent=self.scrollWidget
        )
        self.scrollLayout.addWidget(self.autoUnpack)
        self.checkUpdate = SwitchSettingCard(
            FluentIcon.SAVE,
            self.tr("Check Update"),
            self.tr("Check Update"),
            cfg.checkUpdate,
            parent=self.scrollWidget
        )
        self.scrollLayout.addWidget(self.checkUpdate)


        self.scrollLayout.addStretch()
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.viewport().setStyleSheet("background: transparent")
        cfg.themeChanged.connect(self.onThemeChanged)

    def onThemeChanged(self, theme):
        setTheme(theme)

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
