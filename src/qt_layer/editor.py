import sys
import os
from PySide6.QtCore import Qt, QDir
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QFileSystemModel
from qfluentwidgets import (
    TreeView,
    TextEdit,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    InfoBar,
    InfoBarPosition,
    setTheme,
    Theme
)


class EditorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.current_filepath = None
        self._is_changing_encoding = False

        self.init_ui()
        self.apply_bulletproof_dark_theme()

        # Load the current working directory by default
        self.update_workspace_dir(os.getcwd())

    def init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        # ----------------------------------------------------
        # 1. Left Sidebar: Local File Explorer (Tree Area)
        # ----------------------------------------------------
        self.sidebar_layout = QVBoxLayout()

        # Open Folder Workspace Button
        self.open_dir_btn = PushButton("Open Folder", self)
        self.open_dir_btn.clicked.connect(self.on_open_directory_clicked)
        self.sidebar_layout.addWidget(self.open_dir_btn)

        # Setup File System Data Pipeline
        self.file_model = QFileSystemModel()
        self.file_model.setFilter(QDir.Files | QDir.NoDotAndDotDot)  # Show files only

        # Fluent Styled Tree View for structural navigation
        self.file_tree_widget = TreeView(self)
        self.file_tree_widget.setModel(self.file_model)
        self.file_tree_widget.setFixedWidth(260)

        # Hide unnecessary metadata headers (Size, Type, Date Modified)
        for i in range(1, self.file_model.columnCount()):
            self.file_tree_widget.setColumnHidden(i, True)
        self.file_tree_widget.setHeaderHidden(True)

        # Listen for directory tree item mouse selection clicks
        self.file_tree_widget.clicked.connect(self.on_file_tree_item_clicked)
        self.sidebar_layout.addWidget(self.file_tree_widget)

        self.main_layout.addLayout(self.sidebar_layout)

        # ----------------------------------------------------
        # 2. Right Side: Code Editor Workspace
        # ----------------------------------------------------
        self.editor_container = QVBoxLayout()
        self.editor_container.setSpacing(10)

        self.control_bar = QHBoxLayout()
        self.control_bar.addStretch(1)

        # Hot-swappable document encoding combobox profiles
        self.encoding_box = ComboBox(self)
        self.encoding_options = ["UTF-8", "GBK", "UTF-16", "ISO-8859-1"]
        self.encoding_box.addItems(self.encoding_options)
        self.encoding_box.setCurrentIndex(0)
        self.encoding_box.setFixedWidth(120)
        self.encoding_box.currentTextChanged.connect(self.on_encoding_changed)
        self.control_bar.addWidget(self.encoding_box)

        self.save_btn = PrimaryPushButton("Save File", self)
        self.save_btn.clicked.connect(self.save_current_file)
        self.control_bar.addWidget(self.save_btn)

        self.editor_container.addLayout(self.control_bar)

        self.code_edit = TextEdit(self)
        self.code_edit.setPlaceholderText("Select a file from the workspace explorer list...")

        font = self.code_edit.font()
        font.setFamily("Consolas")
        font.setPointSize(11)
        self.code_edit.setFont(font)

        self.editor_container.addWidget(self.code_edit)
        self.main_layout.addLayout(self.editor_container, stretch=1)

    def apply_bulletproof_dark_theme(self):
        """Forces custom dark stylesheet rules to correct platform rendering problems."""
        self.setStyleSheet("""
            EditorPage { background-color: #202020; }
            QWidget { background-color: #202020; color: #FFFFFF; }
            QTreeView {
                background-color: #2d2d2d;
                border: 1px solid #3f3f3f;
                border-radius: 6px;
                color: #E3E3E3;
                padding: 5px;
            }
            QTreeView::item { padding: 6px; border-radius: 4px; }
            QTreeView::item:hover { background-color: #383838; }
            QTreeView::item:selected { background-color: #0078d4; color: #FFFFFF; }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #3f3f3f;
                border-radius: 6px;
                color: #F5F5F5;
                padding: 8px;
            }
            QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #3f3f3f;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 4px;
            }
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #3f3f3f;
                color: #FFFFFF;
                padding: 5px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #383838; }
        """)

    def update_workspace_dir(self, target_directory):
        """Binds a fresh root OS path array to the model structure visualization."""
        self.file_model.setRootPath(target_directory)
        self.file_tree_widget.setRootIndex(self.file_model.index(target_directory))

    def on_open_directory_clicked(self):
        """Allows mounting external local directories to the project tree wrapper."""
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Workspace Directory", os.getcwd())
        if selected_dir:
            self.update_workspace_dir(selected_dir)

    def on_file_tree_item_clicked(self, index):
        """Resolves target item index coordinates to real absolute file handles on disk."""
        if not self.file_model.isDir(index):
            self.current_filepath = self.file_model.filePath(index)
            chosen_encoding = self.encoding_box.currentText()
            self.read_file_contents(self.current_filepath, chosen_encoding)

    def read_file_contents(self, filepath, encoding):
        if not filepath or not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
            self._is_changing_encoding = True
            self.code_edit.setPlainText(content)
            self._is_changing_encoding = False
        except UnicodeDecodeError:
            self.show_toast_message("Decoding Failure", f"Cannot decode layout using {encoding}.", is_error=True)
            self.code_edit.clear()
        except Exception as e:
            self.show_toast_message("Error", f"Failed to fetch content: {str(e)}", is_error=True)

    def on_encoding_changed(self, new_encoding):
        if self._is_changing_encoding or not self.current_filepath:
            return
        self.read_file_contents(self.current_filepath, new_encoding)

    def save_current_file(self):
        if not self.current_filepath:
            self.show_toast_message("Action Prohibited", "No active target file selected.", is_error=True)
            return
        target_encoding = self.encoding_box.currentText()
        text_payload = self.code_edit.toPlainText()
        try:
            with open(self.current_filepath, "w", encoding=target_encoding) as f:
                f.write(text_payload)
            self.show_toast_message("Success", f"Changes flushed cleanly using {target_encoding}!", is_error=False)
        except Exception as e:
            self.show_toast_message("Write Crash", f"File output stream error: {str(e)}", is_error=True)

    def show_toast_message(self, title, content, is_error=False):
        if is_error:
            InfoBar.error(title=title, content=content, orient=Qt.Horizontal,
                          isClosable=True, position=InfoBarPosition.TOP, duration=3500, parent=self)
        else:
            InfoBar.success(title=title, content=content, orient=Qt.Horizontal,
                            isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    setTheme(Theme.DARK)

    window = EditorPage()
    window.resize(1000, 650)
    window.setWindowTitle("Fluent Local Document Editor")
    window.show()

    sys.exit(app.exec())
