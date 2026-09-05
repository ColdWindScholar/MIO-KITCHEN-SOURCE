import os
import sys
import time
import warnings

import logging
from PySide6.QtCore import Qt, QTimer, QSize, QPoint, QEvent, QObject, QTranslator
from PySide6.QtGui import QIcon, QGuiApplication, QCursor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (NavigationItemPosition, SplashScreen, setTheme, Theme,
                            FluentWindow, FluentIcon as FIF)

from qt_layer.plugins import PluginPage
from qt_layer.projects import ProjectsPage
from qt_layer.settings import SettingsPage
from src.qt_layer.about import AboutPage
from src.qt_layer.home import HomePage
from utils import temp, v_code, prog_path
from src.qt_layer.settings_cfg import cfg
if sys.platform == "linux" or sys.platform == "linux2":
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

class TitleBarEventFilter(QObject):
    """Event filter for title bar dragging"""
    
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.m_drag = False
        self.m_dragPosition = QPoint()
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self.m_drag = True
                self.m_dragPosition = event.globalPos() - self.window.frameGeometry().topLeft()
                obj.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                return True
        
        elif event.type() == QEvent.MouseMove:
            if self.m_drag and event.buttons() == Qt.MouseButton.LeftButton:
                self.window.move(event.globalPos() - self.m_dragPosition)
                return True
            else:
                obj.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        
        elif event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self.m_drag = False
                obj.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                return True
        
        elif event.type() == QEvent.Leave:
            obj.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        return False


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        # Suppress window opacity warnings on Linux
        warnings.filterwarnings('ignore', message='.*opacity.*')

        # 设置主题
        setTheme(Theme.AUTO)

        self.setWindowIcon(QIcon('icon.ico'))
        
        # Create splash screen with error handling
        try:
            self.splashScreen = SplashScreen(self.windowIcon(), self)
            self.splashScreen.setIconSize(QSize(140, 140))
        except Exception as e:
            # If splash screen fails due to opacity, just continue
            print(f"Warning: SplashScreen creation skipped ({e})")
            self.splashScreen = None
        
        self.show()

        # 设置窗口标题
        self.setWindowTitle("MIO-KITCHEN")

        # 设置窗口大小
        self.resize(1000, 700)

        # 窗口居中显示
        self.center()

        # Install event filter on title bar for dragging
        self.title_bar_filter = TitleBarEventFilter(self)
        self.titleBar.installEventFilter(self.title_bar_filter)
        self.titleBar.setMouseTracking(True)
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
            QTimer.singleShot(1000, self.splashScreen.finish)

    def load_language(self):
        app = QApplication.instance()
        app.removeTranslator(self.translator)
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
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(asctime)s:%(filename)s:%(name)s:%(message)s',
                        filename=tool_log, filemode='w')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


init = lambda args: __init__qt(args)
if __name__ == '__main__':
    init(sys.argv)
