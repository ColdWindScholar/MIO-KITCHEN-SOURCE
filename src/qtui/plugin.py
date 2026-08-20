from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    TitleLabel,
    PushButton,
    FluentIcon as FIF,
    CardWidget,
    BodyLabel,
    CaptionLabel,
)


class PluginItemCard(CardWidget):
    """Plugin item card within a section"""

    def __init__(self, name, version, description, icon, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Icon
        icon_label = BodyLabel()
        icon_pixmap = icon.icon().pixmap(48, 48)  # Convert FluentIcon to QPixmap
        icon_label.setPixmap(icon_pixmap)
        layout.addWidget(icon_label)

        # Content area
        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Top row: name and version
        top_layout = QHBoxLayout()
        name_label = BodyLabel(name)
        name_label.setStyleSheet("font-weight: bold;")
        version_label = CaptionLabel(f"v{version}")
        version_label.setStyleSheet("color: #999999;")
        top_layout.addWidget(name_label)
        top_layout.addStretch()
        top_layout.addWidget(version_label)

        # Description
        desc_label = CaptionLabel(description)
        desc_label.setStyleSheet("color: #CCCCCC;")
        desc_label.setWordWrap(True)

        content_layout.addLayout(top_layout)
        content_layout.addWidget(desc_label)

        layout.addLayout(content_layout)
        layout.addStretch()
        self.setLayout(layout)


class PluginSectionCard(CardWidget):
    """Plugin section card (Built-in or Third-party)"""

    def __init__(self, title, icon, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Section header
        header_layout = QHBoxLayout()
        title_label = TitleLabel(title)
        title_label.setStyleSheet("font-size: 16px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Plugin items container
        self.plugins_layout = QVBoxLayout()
        self.plugins_layout.setSpacing(10)
        self.plugins_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.addLayout(self.plugins_layout)
        main_layout.addStretch()

        self.setLayout(main_layout)

    def add_plugin(self, name, version, description, icon):
        """Add a plugin item to this section"""
        plugin_card = PluginItemCard(name, version, description, icon)
        self.plugins_layout.addWidget(plugin_card)


class PluginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PluginPage")
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(24)

        # Page title
        title = TitleLabel("插件管理")
        title.setStyleSheet("font-size: 28px; color: #FFFFFF; font-weight: bold;")
        main_layout.addWidget(title)

        # Built-in plugins section
        builtin_card = PluginSectionCard("内置插件", FIF.DEVELOPER_TOOLS)
        builtin_card.add_plugin("日志插件", "1.0.0", "内置日志管理和查询功能", FIF.DOCUMENT)
        main_layout.addWidget(builtin_card)

        # Third-party plugins section
        thirdparty_card = PluginSectionCard("第三方插件", FIF.DOWN)
        thirdparty_card.add_plugin("Redis缓存", "2.1.0", "Redis 数据库连接和操作插件", FIF.CLOUD)
        thirdparty_card.add_plugin("ElasticSearch", "1.5.2", "ElasticSearch 搜索引擎集成", FIF.SEARCH)
        main_layout.addWidget(thirdparty_card)

        # Install button
        button_layout = QHBoxLayout()
        install_btn = PushButton("安装新插件", self, FIF.DOWNLOAD)
        install_btn.setMaximumWidth(160)
        install_btn.clicked.connect(self.install_plugin)
        button_layout.addStretch()
        button_layout.addWidget(install_btn)
        main_layout.addLayout(button_layout)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def install_plugin(self):
        print("打开插件安装对话框")
        # TODO: Implement plugin installation dialog