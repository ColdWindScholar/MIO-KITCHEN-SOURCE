# Copyright (C) 2022-2026 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
import platform
import sys
import time

from PySide6.QtCore import Qt, QSize, QTranslator
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (NavigationItemPosition, SplashScreen, FluentIcon as FIF, SplitFluentWindow ,FluentWindow)

from src.core.utils import temp, v_code, prog_path
from src.qtui.about import AboutPage
from src.qtui.home import HomePage
from src.qtui.plugins import PluginPage
from src.qtui.projects import ProjectsPage
from src.qtui.settings import SettingsPage
from src.qtui.settings_cfg import cfg
pyi_splash_available = False
if platform.system() != 'Darwin':
    try:
        import pyi_splash

        pyi_splash.update_text('Loading ...')
        pyi_splash_available = True
    except ModuleNotFoundError:
        ...
if sys.platform == "linux" or sys.platform == "linux2":
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ["QT_QPA_PLATFORM"] = "xcb"



class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('icon.ico'))
        self.setWindowTitle('MIO-KITCHEN')


        # Create splash screen with error handling
        try:
            self.splashScreen = SplashScreen(self.windowIcon(), self)
            self.splashScreen.setIconSize(QSize(140, 140))
        except Exception as e:
            # If splash screen fails due to opacity, just continue
            print(f"Warning: SplashScreen creation skipped ({e})")
            self.splashScreen = None
        
        self.show()


        # 设置窗口大小
        self.resize(1000, 700)

        # 窗口居中显示
        self.center()

        # Install event filter on title bar for dragging
        self.translator = QTranslator()
        # 创建页面
        self.home_page = HomePage()
        self.project_page = ProjectsPage()
        self.plugin_page = PluginPage()
        self.about_page = AboutPage()
        self.settings_page = SettingsPage()

        # 初始化导航
        self.initNavigation()
        cfg.language.valueChanged.connect(self.load_language)

        # Finish splash screen if it was created
        if self.splashScreen:
            self.splashScreen.finish()

    def load_language(self):
        app = QApplication.instance()
        if self.translator.load(cfg.language.value, os.path.join(prog_path, 'bin', 'languages')):
            if not app:
                return
            app.installTranslator(self.translator)


    def center(self):
        desktop = QGuiApplication.primaryScreen().availableGeometry()
        screen_width = desktop.width()
        screen_height = desktop.height()
        x = (screen_width - self.width()) // 2
        y = (screen_height - self.height()) // 2
        self.move(x, y)

    def initNavigation(self):
        # 添加导航项
        self.addSubInterface(self.home_page, FIF.HOME, self.tr('Home'))
        self.addSubInterface(self.project_page, FIF.DOCUMENT, self.tr('Project'))
        self.addSubInterface(self.plugin_page, FIF.APPLICATION, self.tr('Plugins'))
        self.addSubInterface(self.about_page, FIF.INFO, self.tr('About'), NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.settings_page, FIF.SETTING, self.tr("Settings"), NavigationItemPosition.BOTTOM)

        # 默认显示主页
        self.switchTo(self.home_page)


def __init__qt(args):
    tool_log = f'{temp}/{time.strftime("%Y%m%d_%H-%M-%S", time.localtime())}_{v_code()}.log'
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(args)
    translator = QTranslator()
    if translator.load(cfg.language.value, os.path.join(prog_path, 'bin', 'languages')):
        app.installTranslator(translator)
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(asctime)s:%(filename)s:%(name)s:%(message)s',
                        filename=tool_log, filemode='w')
    window = MainWindow()
    window.load_language()
    window.show()
    if pyi_splash_available:
        pyi_splash.close()
    sys.exit(app.exec())


init = __init__qt
if __name__ == '__main__':
    init(sys.argv)
