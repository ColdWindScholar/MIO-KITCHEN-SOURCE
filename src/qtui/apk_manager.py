import logging
import os

from PySide6.QtCore import QCoreApplication, QThread, Qt, QSize, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from androguard.core.apk import APK
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    InfoBar,
    ListWidget,
    MessageBox,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    themeColor,
)

from src.qtui.settings_cfg import cfg


def read_apk(path):
    filename = os.path.basename(path)
    record = {
        "path": path,
        "filename": filename,
        "name": os.path.splitext(filename)[0],
        "author": "",
        "package": "",
        "version": "",
        "version_code": "",
        "min_sdk": "",
        "target_sdk": "",
        "permissions": [],
        "icon_data": b"",
        "size": 0,
        "error": "",
    }
    try:
        record["size"] = os.path.getsize(path)
        apk = APK(path)
        record["name"] = apk.get_app_name() or record["name"]
        record["package"] = apk.get_package() or ""
        record["version"] = apk.get_androidversion_name() or ""
        record["version_code"] = apk.get_androidversion_code() or ""
        record["min_sdk"] = apk.get_min_sdk_version() or ""
        record["target_sdk"] = apk.get_target_sdk_version() or ""
        record["permissions"] = apk.get_permissions() or []

        manifest = apk.get_android_manifest_xml()
        if manifest is not None:
            android_ns = "{http://schemas.android.com/apk/res/android}"
            for metadata in manifest.iter("meta-data"):
                name = metadata.get(android_ns + "name", "").casefold()
                if name in {"author", "developer", "android:author"}:
                    record["author"] = metadata.get(android_ns + "value", "")
                    if record["author"]:
                        break

        if not record["author"]:
            certificates = apk.get_certificates()
            if certificates:
                subject = certificates[0].subject.native
                if isinstance(subject, dict):
                    author = subject.get("common_name") or subject.get("organization_name") or ""
                    record["author"] = ", ".join(author) if isinstance(author, list) else str(author)
                else:
                    record["author"] = str(subject)

        icon_path = apk.get_app_icon(max_dpi=480)
        if icon_path:
            record["icon_data"] = apk.get_file(icon_path) or b""
    except Exception as error:
        record["error"] = str(error)
        logging.exception("Unable to read APK metadata from %s", path)
    return record


class ApkScanThread(QThread):
    apk_loaded = Signal(int, dict)
    progress_changed = Signal(int, int)
    scan_finished = Signal(int, int, str)

    def __init__(self, project_path, generation, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.generation = generation

    def run(self):
        total = 0
        try:
            for root, directories, filenames in os.walk(self.project_path):
                if self.isInterruptionRequested():
                    break
                directories[:] = [directory for directory in directories if not directory.startswith(".")]
                for filename in filenames:
                    if self.isInterruptionRequested():
                        break
                    if not filename.lower().endswith(".apk"):
                        continue
                    path = os.path.join(root, filename)
                    self.apk_loaded.emit(self.generation, read_apk(path))
                    total += 1
                    self.progress_changed.emit(self.generation, total)
        except OSError as error:
            self.scan_finished.emit(self.generation, total, str(error))
            return
        self.scan_finished.emit(self.generation, total, "")


class ApkCard(CardWidget):
    selected = Signal(str)

    def __init__(self, path, record, parent=None):
        super().__init__(parent)
        self.path = path
        self.setObjectName("ApkCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.setMinimumHeight(78)

        self.checkbox = CheckBox(self)
        layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignVCenter)

        icon_label = BodyLabel(self)
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if record["icon_data"]:
            image = QImage.fromData(record["icon_data"])
            if not image.isNull():
                pixmap = QPixmap.fromImage(image).scaled(
                    QSize(48, 48),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        labels = QVBoxLayout()
        labels.setSpacing(3)
        name_label = StrongBodyLabel(record["name"], self)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        name_label.setToolTip(record["name"])
        name_label.setWordWrap(False)
        name_label.setMinimumWidth(0)
        labels.addWidget(name_label)
        package_label = CaptionLabel(record["package"] or self.tr("Unknown package"), self)
        package_label.setMinimumWidth(0)
        package_label.setToolTip(record["package"])
        labels.addWidget(package_label)
        size_sdk = self.tr("{} • SDK {}").format(
            self._format_size(record["size"]), record["target_sdk"] or "?"
        )
        size_label = CaptionLabel(size_sdk, self)
        labels.addWidget(size_label)
        layout.addLayout(labels, 1)

    @staticmethod
    def _format_size(size):
        units = ("B", "KB", "MB", "GB")
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} GB"

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.property("selected"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(themeColor()), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 6, 6)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.path)
        super().mousePressEvent(event)


class ApkManagerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ApkManagerPage")
        self.apk_records = {}
        self.card_widgets = {}
        self._workers = set()
        self._generation = 0
        self._selected_path = None
        self._project_path = ""
        self._scan_path = ""
        self.setup_ui()
        cfg.currentProjectName.valueChanged.connect(self.refresh_apks)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_workers)
        self.refresh_apks()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        toolbar = QHBoxLayout()
        self.status_label = BodyLabel(self)
        toolbar.addWidget(self.status_label)
        toolbar.addStretch(1)
        self.scan_directory_button = PushButton(self.tr("Scan a dir"), self)
        self.scan_directory_button.clicked.connect(self.choose_scan_directory)
        toolbar.addWidget(self.scan_directory_button)
        self.import_debloat_button = PushButton(self.tr("Import debloat list"), self)
        self.import_debloat_button.clicked.connect(self.import_debloat_list)
        toolbar.addWidget(self.import_debloat_button)
        self.remove_selected_button = PushButton(self.tr("Remove Selected"), self)
        self.remove_selected_button.clicked.connect(self.remove_selected)
        self.remove_selected_button.hide()
        toolbar.addWidget(self.remove_selected_button)
        main_layout.addLayout(toolbar)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        self.list_area = ScrollArea(self)
        self.list_area.setWidgetResizable(True)
        self.list_area.setStyleSheet("background: transparent; border: none;")
        self.list_area.viewport().setStyleSheet("background: transparent;")
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QGridLayout(self.list_container)
        self.list_layout.setContentsMargins(4, 4, 4, 4)
        self.list_layout.setHorizontalSpacing(12)
        self.list_layout.setVerticalSpacing(12)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_area.setWidget(self.list_container)
        content_layout.addWidget(self.list_area, 3)

        self.details_panel = CardWidget(self)
        self.details_panel.setObjectName("ApkDetailsPanel")
        self.details_panel.setMinimumWidth(300)
        self.details_panel.setMaximumWidth(360)
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(22, 20, 22, 20)
        details_layout.setSpacing(12)
        self.detail_icon = BodyLabel(self.details_panel)
        self.detail_icon.setFixedSize(80, 80)
        self.detail_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self.detail_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        self.detail_name = SubtitleLabel(self.tr("Select an APK"), self.details_panel)
        self.detail_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_name.setWordWrap(True)
        details_layout.addWidget(self.detail_name)
        self.detail_package = BodyLabel("", self.details_panel)
        self.detail_package.setWordWrap(True)
        self.detail_package.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(self.detail_package)
        self.detail_version = CaptionLabel("", self.details_panel)
        details_layout.addWidget(self.detail_version)
        self.detail_min_sdk = CaptionLabel("", self.details_panel)
        details_layout.addWidget(self.detail_min_sdk)
        self.detail_target_sdk = CaptionLabel("", self.details_panel)
        details_layout.addWidget(self.detail_target_sdk)
        details_layout.addWidget(StrongBodyLabel(self.tr("Permissions"), self.details_panel))
        self.permissions_list = ListWidget(self.details_panel)
        details_layout.addWidget(self.permissions_list, 1)
        content_layout.addWidget(self.details_panel, 2)
        main_layout.addLayout(content_layout, 1)


    def showEvent(self, event):
        super().showEvent(event)
        if not self.apk_records and not any(worker.isRunning() for worker in self._workers):
            self.refresh_apks()

    def refresh_apks(self, *_):
        self._generation += 1
        generation = self._generation
        for worker in tuple(self._workers):
            worker.requestInterruption()

        self.apk_records.clear()
        self._selected_path = None
        self.details_panel.hide()
        self._clear_cards()

        project_name = cfg.currentProjectName.value
        self._project_path = (
            os.path.join(cfg.workingFolder.value, project_name) if project_name else ""
        )
        if not project_name or not os.path.isdir(self._project_path):
            self._scan_path = ""
            self.status_label.setText(self.tr("Select a project to list its APK files."))
            return

        self._scan_path = self._project_path
        self._start_scan(self._scan_path, generation)

    def _start_scan(self, directory, generation=None):
        if generation is None:
            self._generation += 1
            generation = self._generation
            for worker in tuple(self._workers):
                worker.requestInterruption()
            self.apk_records.clear()
            self._selected_path = None
            self.details_panel.hide()
            self._clear_cards()

        self.status_label.setText(self.tr("Loading APK files..."))
        worker = ApkScanThread(directory, generation)
        self._workers.add(worker)
        worker.apk_loaded.connect(self._on_apk_loaded)
        worker.progress_changed.connect(self._on_scan_progress)
        worker.scan_finished.connect(self._on_scan_finished)
        worker.finished.connect(lambda current=worker: self._workers.discard(current))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_apk_loaded(self, generation, record):
        if generation != self._generation:
            return
        self.apk_records[record["path"]] = record
        self._add_card(record["path"], record)
        if self._selected_path is None and record["path"] in self.card_widgets:
            self.show_details(record["path"])

    def _on_scan_progress(self, generation, count=None):
        if count is None:
            count = generation
            generation = self._generation
        if generation == self._generation:
            self.status_label.setText(self.tr("Loading APKs... {} found").format(count))

    def _on_scan_finished(self, generation, count, error):
        if generation != self._generation:
            return
        self._update_status()
        if error:
            self.status_label.setText(self.tr("APK scan failed: {}").format(error))

    def _update_status(self):
        self.status_label.setText(
            self.tr("Loaded {} APK(s) completely.").format(len(self.apk_records))
        )

    def _clear_cards(self):
        self.card_widgets.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._update_remove_selected_button()

    def _add_card(self, path, record):
        card = ApkCard(path, record, self.list_container)
        card.selected.connect(self.show_details)
        card.checkbox.toggled.connect(self._update_remove_selected_button)
        self.card_widgets[path] = card
        card.setObjectName("ApkCard")
        self._style_card(card, selected=path == self._selected_path)
        self._relayout_cards()

    def _relayout_cards(self):
        columns = min(3, max(1, self.list_area.viewport().width() // 260))
        for index, card in enumerate(self.card_widgets.values()):
            self.list_layout.addWidget(card, index // columns, index % columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_cards()

    @staticmethod
    def _style_card(card, selected):
        card.setProperty("selected", selected)
        card.update()

    def _update_remove_selected_button(self, *_):
        selected = any(card.checkbox.isChecked() for card in self.card_widgets.values())
        self.remove_selected_button.setVisible(selected)

    def remove_selected(self):
        selected_paths = [
            path for path, card in self.card_widgets.items() if card.checkbox.isChecked()
        ]
        if not selected_paths:
            return
        dialog = MessageBox(
            self.tr("Remove APKs"),
            self.tr("Permanently delete {} selected APK(s)?").format(len(selected_paths)),
            self,
        )
        if dialog.exec() != 1:
            return
        errors = []
        for path in selected_paths:
            try:
                os.remove(path)
            except OSError as error:
                errors.append(f"{path}: {error}")
        if errors:
            InfoBar.error(self.tr("Remove APKs"), "\n".join(errors), parent=self)
        if self._selected_path in selected_paths:
            self._selected_path = None
            self.details_panel.hide()
        if self._scan_path and os.path.isdir(self._scan_path):
            self._start_scan(self._scan_path)
        else:
            self.refresh_apks()

    def show_details(self, path):
        record = self.apk_records.get(path)
        if not record:
            return
        self._selected_path = path
        for card_path, card in self.card_widgets.items():
            self._style_card(card, selected=card_path == path)
        self.details_panel.show()
        self.detail_name.setText(record["name"])
        self.detail_package.setText(record["package"] or self.tr("Unknown package"))
        self.detail_version.setText(self.tr("Version: {}").format(record["version"] or "?"))
        self.detail_min_sdk.setText(self.tr("Min. SDK Version: {}").format(record["min_sdk"] or "?"))
        self.detail_target_sdk.setText(
            self.tr("Target SDK Version: {}").format(record["target_sdk"] or "?")
        )
        self.detail_name.setToolTip(record["error"])
        self.permissions_list.clear()
        self.permissions_list.addItems(record["permissions"])
        if record["icon_data"]:
            image = QImage.fromData(record["icon_data"])
            if not image.isNull():
                self.detail_icon.setPixmap(
                    QPixmap.fromImage(image).scaled(
                        QSize(80, 80),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self.detail_icon.clear()

    def choose_scan_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, self.tr("Scan a directory"), self._scan_path or self._project_path or os.getcwd()
        )
        if directory:
            self._scan_path = directory
            self._start_scan(directory)

    def import_debloat_list(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import debloat list"),
            self._scan_path or self._project_path or os.getcwd(),
            self.tr("Text files (*.txt *.list);;All files (*)"),
        )
        if not filename:
            return
        try:
            with open(filename, "r", encoding="utf-8-sig") as file:
                entries = {
                    line.strip().casefold()
                    for line in file
                    if line.strip() and not line.lstrip().startswith(("#", "//"))
                }
        except (OSError, UnicodeError) as error:
            InfoBar.error(
                self.tr("Import debloat list"),
                self.tr("Could not read debloat list: {}").format(error),
                parent=self,
            )
            return

        matched = 0
        for record in self.apk_records.values():
            keys = {
                record["package"].casefold(),
                record["filename"].casefold(),
                os.path.splitext(record["filename"])[0].casefold(),
            }
            if keys & entries:
                card = self.card_widgets.get(record["path"])
                if card:
                    card.checkbox.setChecked(True)
                matched += 1
        if not matched:
            InfoBar.warning(
                self.tr("Import debloat list"),
                self.tr("No APKs matched the imported list."),
                parent=self,
            )

    def closeEvent(self, event):
        self._stop_workers()
        super().closeEvent(event)

    def _stop_workers(self):
        for worker in tuple(self._workers):
            worker.requestInterruption()
            worker.wait()
