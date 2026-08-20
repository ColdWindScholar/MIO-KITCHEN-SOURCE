import sys

from PySide6.QtCore import Qt, QTimer, QSize, QPoint, QEvent
from PySide6.QtGui import QIcon, QGuiApplication, QCursor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import NavigationItemPosition, SplashScreen, setTheme, Theme, FluentWindow, FluentIcon as FIF

from .about import AboutPage
from .home import HomePage
from .plugin import PluginPage
from .project import ProjectPage
from .settings import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        # 设置主题
        setTheme(Theme.DARK)

        self.setWindowIcon(QIcon('icon.ico'))
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(140, 140))
        self.show()

        # 设置窗口标题
        self.setWindowTitle("MIO-KITCHEN")

        # 设置窗口大小
        self.resize(900, 700)

        # 窗口居中显示
        self.center()

        # Window dragging support
        self.drag_position = QPoint()
        self.is_dragging = False
        self.title_bar_height = 40
        self.normal_cursor = QCursor(Qt.CursorShape.ArrowCursor)

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
        self.addSubInterface(self.about_page, FIF.INFO, '关于', NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.settings_page, FIF.SETTING, '设置', NavigationItemPosition.BOTTOM)

        # 默认显示主页
        self.switchTo(self.home_page)

    def eventFilter(self, obj, event):
        """Global event filter to handle window dragging"""
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                # Check if click is on title bar area (40px from top)
                global_pos = QGuiApplication.primaryScreen().geometry().topLeft()
                if event.globalPos().y() - self.frameGeometry().top() < self.title_bar_height:
                    self.is_dragging = True
                    self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                    self.setCursor(self.normal_cursor)
                    return False
        
        elif event.type() == QEvent.MouseMove:
            if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
                self.move(event.globalPos() - self.drag_position)
                return False
            # Reset cursor when not on title bar
            if not self.is_dragging:
                local_y = event.globalPos().y() - self.frameGeometry().top()
                if local_y < self.title_bar_height:
                    self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
                else:
                    self.setCursor(self.normal_cursor)
        
        elif event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self.is_dragging = False
                self.setCursor(self.normal_cursor)
                return False

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """Handle mouse press for window dragging from title bar"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is on the title bar area (upper region)
            if event.position().y() < self.title_bar_height:
                self.is_dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging"""
        if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPos() - self.drag_position)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Update cursor when moving over title bar"""
        if self.is_dragging:
            self.move(event.globalPos() - self.drag_position)
        else:
            # Show open hand cursor over title bar
            if event.position().y() < self.title_bar_height:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.setCursor(self.normal_cursor)
        super().mouseMoveEvent(event)


def __init__qt(args):
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(args)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


init = lambda args: __init__qt(args)
if __name__ == '__main__':
    init(sys.argv)
