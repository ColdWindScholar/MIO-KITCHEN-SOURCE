import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtWidgets import QApplication
from qfluentwidgets import NavigationItemPosition, SplashScreen, setTheme, Theme, FluentWindow, FluentIcon as FIF
from qframelesswindow.windows import QSize

from about import AboutPage
from home import HomePage
from plugin import PluginPage
from project import ProjectPage
from settings import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        # 设置主题
        setTheme(Theme.DARK)

        self.setWindowIcon(QIcon('resource/logo.png'))
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(140, 140))
        self.show()

        # 设置窗口标题
        self.setWindowTitle("SY ROM Tools - 一款普通的ROM工具")

        # 设置窗口大小
        self.resize(900, 700)

        # 窗口居中显示
        self.center()

        # 创建页面
        self.home_page = HomePage()
        self.project_page = ProjectPage()
        self.plugin_page = PluginPage()
        self.about_page = AboutPage()
        self.settings_page = SettingsPage()

        # 初始化导航
        self.initNavigation()

        QTimer.singleShot(1000, self.splashScreen.finish)

    def center(self):
        desktop = QGuiApplication.primaryScreen().availableGeometry()
        screen_width = desktop.width()
        screen_height = desktop.height()
        x = (screen_width - self.width()) // 2
        y = (screen_height - self.height()) // 2
        self.move(x, y)

    def initNavigation(self):
        # 添加导航项
        self.addSubInterface(self.home_page, FIF.HOME, '主页')
        self.addSubInterface(self.project_page, FIF.DOCUMENT, '项目')
        self.addSubInterface(self.plugin_page, FIF.APPLICATION, '插件')
        self.addSubInterface(self.about_page, FIF.INFO, '关于' , NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.settings_page, FIF.SETTING, '设置', NavigationItemPosition.BOTTOM)

        # 默认显示主页
        self.switchTo(self.home_page)

if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())