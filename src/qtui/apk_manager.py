import logging
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.getLogger("androguard").setLevel(logging.CRITICAL)

from PySide6.QtCore import QCoreApplication, QThread, Qt, QSize, Signal
from PySide6.QtGui import QImage, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from androguard.core.axml import ARSCParser, AXMLPrinter
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    FluentIcon as FIF,
    InfoBar,
    LineEdit,
    ListWidget,
    MessageBox,
    PushButton,
    SearchLineEdit,
    SegmentedWidget,
    StrongBodyLabel,
    TableWidget,
    TabWidget,
)

from src.qtui.settings_cfg import cfg


def read_apk(path):
    filename = os.path.basename(path)
    record = {
        "path": path,
        "filename": filename,
        "name": os.path.splitext(filename)[0],
        "package": "",
        "version": "",
        "min_sdk": "",
        "target_sdk": "",
        "permissions": [],
        "icon_data": b"",
        "size": 0,
        "error": "",
        "details_loaded": False,
    }
    try:
        record["size"] = os.path.getsize(path)
        with zipfile.ZipFile(path) as archive:
            manifest = AXMLPrinter(archive.read("AndroidManifest.xml")).get_xml_obj()
            android_ns = "{http://schemas.android.com/apk/res/android}"
            record["package"] = manifest.get("package", "")
            application = manifest.find("application")
            if application is not None:
                label = application.get(android_ns + "label", "")
                if label and not label.startswith("@"):
                    record["name"] = label
                try:
                    record["icon_data"] = read_apk_icon(
                        archive, application.get(android_ns + "icon", ""), record["package"]
                    )
                except Exception as error:
                    logging.debug("Unable to extract APK icon from %s: %s", path, error, exc_info=True)
        record["name"] = record["name"] or record["package"] or filename
    except Exception as error:
        record["error"] = str(error)
        logging.warning("Unable to read APK manifest from %s: %s", path, error)
    return record


def read_apk_icon(archive, application_icon, package_name):
    if not application_icon:
        return b""
    if not application_icon.startswith("@"):
        try:
            return archive.read(application_icon)
        except KeyError:
            return b""

    if "resources.arsc" not in archive.namelist():
        return b""
    resources = ARSCParser(archive.read("resources.arsc"))
    try:
        resource_id, _ = ARSCParser.parse_id(application_icon)
    except ValueError:
        resource_type, _, resource_name = application_icon[1:].partition("/")
        if not resource_type or not resource_name:
            return b""
        resource_id = resources.get_res_id_by_key(package_name, resource_type, resource_name)
        if resource_id is None:
            return b""

    candidates = []
    archive_names = set(archive.namelist())
    for configuration, resource_path in resources.get_resolved_res_configs(resource_id):
        if resource_path not in archive_names or not resource_path.lower().endswith(
            (".png", ".webp", ".jpg", ".jpeg")
        ):
            continue
        density = configuration.get_density()
        candidates.append((density, resource_path))
    if not candidates:
        return b""

    suitable = [candidate for candidate in candidates if 0 < candidate[0] <= 480]
    _, selected_path = max(suitable or candidates, key=lambda candidate: candidate[0])
    return archive.read(selected_path)


def read_apk_details(path):
    android_ns = "{http://schemas.android.com/apk/res/android}"
    with zipfile.ZipFile(path) as archive:
        manifest = AXMLPrinter(archive.read("AndroidManifest.xml")).get_xml_obj()

    application = manifest.find("application")
    label = application.get(android_ns + "label", "") if application is not None else ""
    permissions = []
    for element in manifest:
        if element.tag.startswith("uses-permission"):
            permission = element.get(android_ns + "name", "")
            if permission and permission not in permissions:
                permissions.append(permission)
    uses_sdk = manifest.find("uses-sdk")
    return {
        "name": label if label and not label.startswith("@") else "",
        "version": manifest.get(android_ns + "versionName", ""),
        "min_sdk": uses_sdk.get(android_ns + "minSdkVersion", "") if uses_sdk is not None else "",
        "target_sdk": uses_sdk.get(android_ns + "targetSdkVersion", "") if uses_sdk is not None else "",
        "permissions": permissions,
    }


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
            apk_paths = []
            for root, directories, filenames in os.walk(self.project_path):
                if self.isInterruptionRequested():
                    break
                directories[:] = [directory for directory in directories if not directory.startswith(".")]
                for filename in filenames:
                    if self.isInterruptionRequested():
                        break
                    if not filename.lower().endswith(".apk"):
                        continue
                    apk_paths.append(os.path.join(root, filename))
            if self.isInterruptionRequested():
                self.scan_finished.emit(self.generation, total, "")
                return
            with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
                futures = [executor.submit(read_apk, path) for path in apk_paths]
                for future in as_completed(futures):
                    if self.isInterruptionRequested():
                        break
                    self.apk_loaded.emit(self.generation, future.result())
                    total += 1
                    self.progress_changed.emit(self.generation, total)
        except OSError as error:
            self.scan_finished.emit(self.generation, total, str(error))
            return
        self.scan_finished.emit(self.generation, total, "")


class ApkManagerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ApkManagerPage")
        self.apk_records = {}
        self._row_paths = []
        self._table_rows = {}
        self._tables = {}
        self._checked_paths = set()
        self._active_partition = ""
        self._tab_partitions = []
        self._workers = set()
        self._generation = 0
        self._selected_path = None
        self._project_path = ""
        self._scan_path = ""
        self._restore_directory = ""
        self.setup_ui()
        cfg.currentProjectName.valueChanged.connect(self.refresh_apks)
        cfg.themeChanged.connect(self._apply_theme)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_workers)
        self.refresh_apks()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 8)
        main_layout.setSpacing(8)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        self.inventory_panel = QWidget(self)
        self.inventory_panel.setObjectName("InventoryPanel")
        inventory_layout = QVBoxLayout(self.inventory_panel)
        inventory_layout.setContentsMargins(14, 12, 14, 10)
        inventory_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(StrongBodyLabel(self.tr("Apps"), self))
        self.project_badge = CaptionLabel("", self)
        toolbar.addWidget(self.project_badge)
        toolbar.addStretch(1)
        self.search_entry = SearchLineEdit(self)
        self.search_entry.setPlaceholderText(self.tr("Search name or package"))
        self.search_entry.setClearButtonEnabled(True)
        self.search_entry.setFixedWidth(250)
        self.search_entry.textChanged.connect(self._render_table)
        toolbar.addWidget(self.search_entry)
        self.refresh_button = PushButton(self.tr("Refresh"), self)
        self.refresh_button.clicked.connect(self._rescan)
        toolbar.addWidget(self.refresh_button)
        inventory_layout.addLayout(toolbar)

        filter_toolbar = QHBoxLayout()
        filter_toolbar.setSpacing(4)
        self.partition_tabs = TabWidget(self.inventory_panel)
        self.partition_tabs.setTabsClosable(False)
        self.partition_tabs.tabBar.setAddButtonVisible(False)
        self.partition_tabs.setScrollable(True)
        self.partition_tabs.setTabSelectedBackgroundColor("#363c49", "#303746")
        self.partition_tabs.currentChanged.connect(self._on_partition_tab_changed)
        self._add_partition_tab("", self.tr("All"))
        filter_toolbar.addWidget(self.partition_tabs, 1)
        inventory_layout.addLayout(filter_toolbar)

        self.table = self._tables[""]

        footer = QHBoxLayout()
        self.status_label = CaptionLabel("", self)
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        self.scan_status_label = CaptionLabel("", self)
        footer.addWidget(self.scan_status_label)
        inventory_layout.addLayout(footer)
        content_layout.addWidget(self.inventory_panel, 3)

        self.details_panel = QWidget(self)
        self.details_panel.setObjectName("DetailsPanel")
        self.details_panel.setMinimumWidth(300)
        self.details_panel.setMaximumWidth(380)
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(8, 8, 8, 8)
        details_layout.setSpacing(8)
        details_layout.addWidget(StrongBodyLabel(self.tr("Apps"), self.details_panel))

        list_card = CardWidget(self.details_panel)
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(14, 12, 14, 12)
        list_layout.setSpacing(8)
        list_layout.addWidget(CaptionLabel(self.tr("SELECTIONS AND LISTS"), list_card))
        self.list_tabs = SegmentedWidget(list_card)
        self.list_tabs.addItem(routeKey="presets", text=self.tr("Presets"))
        self.list_tabs.addItem(routeKey="external", text=self.tr("External list"))
        self.list_tabs.setCurrentItem("presets")
        self.list_tabs.currentItemChanged.connect(self._set_list_mode)
        list_layout.addWidget(self.list_tabs)
        self.list_description = CaptionLabel("", list_card)
        self.list_description.setWordWrap(True)
        list_layout.addWidget(self.list_description)
        save_row = QHBoxLayout()
        self.preset_name = LineEdit(list_card)
        self.preset_name.setPlaceholderText(self.tr("Name this selection"))
        save_row.addWidget(self.preset_name, 1)
        self.save_list_button = PushButton(self.tr("Save"), list_card)
        self.save_list_button.clicked.connect(self.save_selection_list)
        save_row.addWidget(self.save_list_button)
        list_layout.addLayout(save_row)
        self.import_debloat_button = PushButton(self.tr("Import debloat list"), list_card)
        self.import_debloat_button.clicked.connect(self.import_debloat_list)
        list_layout.addWidget(self.import_debloat_button)
        details_layout.addWidget(list_card)

        details_layout.addWidget(CaptionLabel(self.tr("SELECTED APK"), self.details_panel))
        self.selected_card = CardWidget(self.details_panel)
        selected_layout = QVBoxLayout(self.selected_card)
        selected_layout.setContentsMargins(14, 12, 14, 12)
        self.detail_name = StrongBodyLabel(self.tr("Select an APK"), self.selected_card)
        selected_layout.addWidget(self.detail_name)
        self.detail_package = CaptionLabel("", self.selected_card)
        self.detail_package.setWordWrap(True)
        selected_layout.addWidget(self.detail_package)
        self.detail_path = CaptionLabel("", self.selected_card)
        self.detail_path.setWordWrap(True)
        selected_layout.addWidget(self.detail_path)
        details_layout.addWidget(self.selected_card)

        details_layout.addWidget(CaptionLabel(self.tr("APK METADATA"), self.details_panel))
        self.metadata_card = CardWidget(self.details_panel)
        metadata_layout = QVBoxLayout(self.metadata_card)
        metadata_layout.setContentsMargins(14, 12, 14, 12)
        self.detail_version = CaptionLabel("", self.metadata_card)
        self.detail_min_sdk = CaptionLabel("", self.metadata_card)
        self.detail_target_sdk = CaptionLabel("", self.metadata_card)
        for label in (
            self.detail_version,
            self.detail_min_sdk,
            self.detail_target_sdk,
        ):
            label.setWordWrap(True)
            metadata_layout.addWidget(label)
        details_layout.addWidget(self.metadata_card)

        details_layout.addWidget(StrongBodyLabel(self.tr("Permissions"), self.details_panel))
        self.permissions_list = ListWidget(self.details_panel)
        details_layout.addWidget(self.permissions_list, 1)

        self.actions_card = CardWidget(self.details_panel)
        actions_layout = QVBoxLayout(self.actions_card)
        actions_layout.setContentsMargins(14, 12, 14, 12)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(CaptionLabel(self.tr("ACTIONS"), self.actions_card))
        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(8)
        self.remove_selected_button = PushButton(self.tr("Remove 0"), self.actions_card)
        self.remove_selected_button.setIcon(FIF.DELETE.icon())
        self.remove_selected_button.clicked.connect(self.remove_selected)
        action_buttons.addWidget(self.remove_selected_button, 1)
        self.restore_button = PushButton(self.tr("Restore 0"), self.actions_card)
        self.restore_button.setIcon(FIF.RETURN.icon())
        self.restore_button.setEnabled(False)
        self.restore_button.setToolTip(self.tr("No APKs are currently available to restore."))
        self.restore_button.clicked.connect(self.restore_apks)
        action_buttons.addWidget(self.restore_button, 1)
        actions_layout.addLayout(action_buttons)
        details_layout.addWidget(self.actions_card)
        content_layout.addWidget(self.details_panel, 1)
        main_layout.addLayout(content_layout, 1)
        self._set_list_mode("presets")
        self._apply_theme()


    @staticmethod
    def _format_size(size):
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}"
            value /= 1024

    def _create_table(self, page):
        table = TableWidget(page)
        table.setColumnCount(7)
        table.setRowCount(0)
        table.setHorizontalHeaderLabels(
            [
                "",
                self.tr("NAME"),
                self.tr("PACKAGE"),
                self.tr("PARTITION"),
                self.tr("TYPE"),
                self.tr("SIZE"),
                self.tr("RISK"),
            ]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(48)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 42)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table.itemChanged.connect(self._on_item_changed)
        table.currentCellChanged.connect(
            lambda row, *_args, current_table=table: self._on_current_row_changed(
                current_table, row
            )
        )
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)
        return table

    def _add_partition_tab(self, partition, label):
        page = QWidget(self.partition_tabs)
        table = self._create_table(page)
        route_key = "all" if not partition else f"partition:{partition}"
        self.partition_tabs.addPage(page, label, routeKey=route_key)
        self._tables[partition] = table
        self._table_rows[table] = []
        self._tab_partitions.append(partition)

    def _on_partition_tab_changed(self, index):
        if not 0 <= index < len(self._tab_partitions):
            return
        self._active_partition = self._tab_partitions[index]
        self.table = self._tables[self._active_partition]
        self._row_paths = self._table_rows[self.table]
        self._update_status()

    def _apply_theme(self, *_):
        pass
        self._render_table()

    def _set_list_mode(self, mode):
        presets = mode == "presets"
        self.list_description.setText(
            self.tr("Save the selected APK packages to a named list for later reference.")
            if presets
            else self.tr("Import a package list and select matching APKs in this project.")
        )
        self.preset_name.setVisible(presets)
        self.save_list_button.setVisible(presets)
        self.import_debloat_button.setVisible(not presets)

    def _rescan(self):
        if self._scan_path and os.path.isdir(self._scan_path):
            self._start_scan(self._scan_path)
        else:
            self.refresh_apks()

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
        self._checked_paths.clear()
        self._selected_path = None
        self._clear_table()

        project_name = cfg.currentProjectName.value
        self._project_path = (
            os.path.join(cfg.workingFolder.value, project_name) if project_name else ""
        )
        self.project_badge.setText(project_name)
        if not project_name or not os.path.isdir(self._project_path):
            self._scan_path = ""
            self._restore_directory = ""
            self._update_restore_button()
            self.status_label.setText(self.tr("Select a project to list its APK files."))
            return

        self._scan_path = self._project_path
        self._restore_directory = os.path.join(self._project_path, ".apk_manager_restore")
        self._update_restore_button()
        self._start_scan(self._scan_path, generation)

    def _start_scan(self, directory, generation=None):
        if generation is None:
            self._generation += 1
            generation = self._generation
            for worker in tuple(self._workers):
                worker.requestInterruption()
            self.apk_records.clear()
            self._checked_paths.clear()
            self._selected_path = None
            self._clear_table()
        self._scan_path = directory
        self.project_badge.setText(os.path.basename(os.path.normpath(directory)))
        self.status_label.setText(self.tr("Loading APKs..."))
        self.scan_status_label.clear()
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
        self._append_row(self.table, record["path"], record)
        if self._selected_path is None:
            self.show_details(record["path"])

    def _on_scan_progress(self, generation, count):
        if generation == self._generation:
            self.scan_status_label.setText(self.tr("{} APKs read").format(count))

    def _on_scan_finished(self, generation, count, error):
        if generation != self._generation:
            return
        self._update_partition_filters()
        self._render_table()
        self._update_status()
        if error:
            self.scan_status_label.setText(self.tr("APK scan failed: {}").format(error))
        self._update_restore_button()

    def _update_status(self):
        visible_size = sum(self.apk_records[path]["size"] for path in self._row_paths)
        self.status_label.setText(
            self.tr("{} shown, {} • {} APK(s) read").format(
                self.table.rowCount(), self._format_size(visible_size), len(self.apk_records)
            )
        )

    def _clear_table(self):
        for table in self._tables.values():
            table.blockSignals(True)
            table.setRowCount(0)
            table.blockSignals(False)
            self._table_rows[table] = []
        self._row_paths = self._table_rows.get(self.table, [])
        self._update_status()
        self._update_remove_selected_button()

    def _partition_for(self, path):
        try:
            relative = os.path.relpath(path, self._scan_path)
        except ValueError:
            relative = os.path.basename(path)
        parent = os.path.dirname(relative)
        return parent.split(os.sep, 1)[0] if parent else self.tr("root")

    def _type_for(self, path):
        folders = {part.casefold() for part in os.path.normpath(path).split(os.sep)}
        if "priv-app" in folders:
            return self.tr("Privileged")
        if "app" in folders:
            return self.tr("App")
        return self.tr("APK")

    def _update_partition_filters(self):
        partitions = sorted({self._partition_for(path) for path in self.apk_records})
        desired = [""] + partitions
        if desired == self._tab_partitions:
            return
        active = self._active_partition if self._active_partition in desired else ""
        while self.partition_tabs.count():
            page = self.partition_tabs.widget(0)
            self.partition_tabs.removeTab(0)
            page.deleteLater()
        self._tables.clear()
        self._table_rows.clear()
        self._tab_partitions.clear()
        self._add_partition_tab("", self.tr("All"))
        for partition in partitions:
            self._add_partition_tab(partition, partition)
        self.partition_tabs.setCurrentIndex(self._tab_partitions.index(active))
        self._on_partition_tab_changed(self.partition_tabs.currentIndex())

    def _append_row(self, table, path, record):
        partition = self._partition_for(path)
        table_partition = next(
            (key for key, value in self._tables.items() if value is table), ""
        )
        if table_partition and partition != table_partition:
            return
        query = self.search_entry.text().strip().casefold()
        searchable = " ".join((record["name"], record["filename"], record["package"], path))
        if query and query not in searchable.casefold():
            return
        row = table.rowCount()
        self._table_rows[table].append(path)
        table.blockSignals(True)
        table.insertRow(row)
        check_item = QTableWidgetItem()
        check_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        check_item.setCheckState(
            Qt.CheckState.Checked if path in self._checked_paths else Qt.CheckState.Unchecked
        )
        check_item.setData(Qt.ItemDataRole.UserRole, path)
        table.setItem(row, 0, check_item)
        name_item = QTableWidgetItem(record["name"])
        name_item.setToolTip(record["filename"])
        name_item.setIcon(FIF.APPLICATION.icon())
        if record["icon_data"]:
            image = QImage.fromData(record["icon_data"])
            if not image.isNull():
                name_item.setIcon(
                    QIcon(
                        QPixmap.fromImage(image).scaled(
                            QSize(30, 30),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                )
        name_item.setData(Qt.ItemDataRole.UserRole, path)
        table.setItem(row, 1, name_item)
        package_item = QTableWidgetItem(record["package"] or self.tr("Unknown package"))
        package_item.setToolTip(record["package"])
        table.setItem(row, 2, package_item)
        table.setItem(row, 3, QTableWidgetItem(partition))
        table.setItem(row, 4, QTableWidgetItem(self._type_for(path)))
        table.setItem(row, 5, QTableWidgetItem(self._format_size(record["size"])))
        status_item = QTableWidgetItem(self.tr("Unknown"))
        if record["error"]:
            status_item.setToolTip(self.tr("Manifest unavailable; risk was not analyzed."))
        else:
            status_item.setToolTip(self.tr("Risk analysis is not available for APK files."))
        table.setItem(row, 6, status_item)
        table.blockSignals(False)

    def _render_table(self, *_):
        if not hasattr(self, "partition_tabs"):
            return
        selected_path = self._selected_path
        for table in self._tables.values():
            table.blockSignals(True)
            table.setRowCount(0)
            table.blockSignals(False)
            self._table_rows[table] = []
            for path, record in self.apk_records.items():
                self._append_row(table, path, record)
        self._row_paths = self._table_rows.get(self.table, [])
        self._update_status()
        if selected_path in self._row_paths:
            self.table.selectRow(self._row_paths.index(selected_path))

    def _on_item_changed(self, item):
        if item.column() != 0:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self._checked_paths.add(path)
        else:
            self._checked_paths.discard(path)
        self._update_remove_selected_button()

    def _on_current_row_changed(self, table, row):
        paths = self._table_rows.get(table, [])
        if 0 <= row < len(paths):
            self.show_details(paths[row])

    def _update_remove_selected_button(self, *_):
        selected_count = len(self._checked_paths)
        self.remove_selected_button.setText(self.tr("Remove {}").format(selected_count))
        self.remove_selected_button.setEnabled(selected_count > 0)

    def _available_restore_paths(self):
        if not self._restore_directory or not os.path.isdir(self._restore_directory):
            return []
        paths = []
        for root, _, filenames in os.walk(self._restore_directory):
            paths.extend(
                os.path.join(root, filename)
                for filename in filenames
                if filename.lower().endswith(".apk")
            )
        return paths

    def _update_restore_button(self):
        count = len(self._available_restore_paths())
        self.restore_button.setText(self.tr("Restore {}").format(count))
        self.restore_button.setEnabled(count > 0)
        self.restore_button.setToolTip(
            self.tr("Restore APKs moved here from this project.")
            if count
            else self.tr("No APKs are currently available to restore.")
        )

    def remove_selected(self):
        selected_paths = list(self._checked_paths)
        if not selected_paths:
            return
        dialog = MessageBox(
            self.tr("Remove APKs"),
            self.tr("Move {} selected APK(s) to the restore area?").format(len(selected_paths)),
            self,
        )
        if dialog.exec() != 1:
            return
        errors = []
        for path in selected_paths:
            try:
                relative_path = os.path.relpath(path, self._project_path)
                restore_path = os.path.join(self._restore_directory, relative_path)
                if os.path.commonpath((self._project_path, path)) != self._project_path:
                    raise OSError(self.tr("APK is outside the current project."))
                if os.path.exists(restore_path):
                    raise FileExistsError(restore_path)
                os.makedirs(os.path.dirname(restore_path), exist_ok=True)
                os.replace(path, restore_path)
            except OSError as error:
                errors.append(f"{path}: {error}")
        if errors:
            InfoBar.error(self.tr("Remove APKs"), "\n".join(errors), parent=self)
        if self._selected_path in selected_paths:
            self._selected_path = None
        self._checked_paths.difference_update(selected_paths)
        if self._scan_path and os.path.isdir(self._scan_path):
            self._start_scan(self._scan_path)
        else:
            self.refresh_apks()

    def restore_apks(self):
        restore_paths = self._available_restore_paths()
        if not restore_paths:
            self._update_restore_button()
            return
        dialog = MessageBox(
            self.tr("Restore APKs"),
            self.tr("Restore {} APK(s) to their original locations?").format(len(restore_paths)),
            self,
        )
        if dialog.exec() != 1:
            return
        errors = []
        for source in restore_paths:
            relative_path = os.path.relpath(source, self._restore_directory)
            destination = os.path.join(self._project_path, relative_path)
            try:
                if os.path.exists(destination):
                    raise FileExistsError(destination)
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                os.replace(source, destination)
            except OSError as error:
                errors.append(f"{destination}: {error}")
        if errors:
            InfoBar.error(self.tr("Restore APKs"), "\n".join(errors), parent=self)
        if self._scan_path and os.path.isdir(self._scan_path):
            self._start_scan(self._scan_path)
        else:
            self.refresh_apks()

    def show_details(self, path):
        record = self.apk_records.get(path)
        if not record:
            return
        self._selected_path = path
        self.detail_name.setText(record["name"])
        self.detail_package.setText(record["package"] or self.tr("Unknown package"))
        try:
            display_path = os.path.relpath(path, self._scan_path)
        except ValueError:
            display_path = path
        self.detail_path.setText(display_path)
        if not record["details_loaded"]:
            try:
                details = read_apk_details(path)
                for key, value in details.items():
                    if value or key == "permissions":
                        record[key] = value
            except Exception as error:
                record["error"] = str(error)
                logging.warning("Unable to read selected APK metadata from %s: %s", path, error)
            record["details_loaded"] = True
        self.detail_name.setText(record["name"])
        self.detail_version.setText(self.tr("Version: {}").format(record["version"] or "?"))
        self.detail_min_sdk.setText(self.tr("Min. SDK Version: {}").format(record["min_sdk"] or "?"))
        self.detail_target_sdk.setText(
            self.tr("Target SDK Version: {}").format(record["target_sdk"] or "?")
        )
        self.detail_name.setToolTip(record["error"])
        self.permissions_list.clear()
        self.permissions_list.addItems(record["permissions"])
        self.list_description.setToolTip(record["error"])

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
                self._checked_paths.add(record["path"])
                matched += 1
        self._render_table()
        self._update_remove_selected_button()
        if not matched:
            InfoBar.warning(
                self.tr("Import debloat list"),
                self.tr("No APKs matched the imported list."),
                parent=self,
            )

    def save_selection_list(self):
        selected_records = [
            self.apk_records[path]
            for path in self._checked_paths
            if path in self.apk_records
        ]
        if not selected_records:
            InfoBar.warning(
                self.tr("Save selection"),
                self.tr("Select at least one APK first."),
                parent=self,
            )
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save selection list"),
            os.path.join(
                self._scan_path or os.getcwd(),
                (self.preset_name.text().strip() or "apk-selection") + ".txt",
            ),
            self.tr("Text files (*.txt)"),
        )
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as file:
                for record in sorted(selected_records, key=lambda item: item["package"]):
                    file.write((record["package"] or record["filename"]) + "\n")
        except OSError as error:
            InfoBar.error(
                self.tr("Save selection"),
                self.tr("Could not save selection list: {}").format(error),
                parent=self,
            )
            return
        InfoBar.success(
            self.tr("Save selection"),
            self.tr("Saved {} APK package(s).").format(len(selected_records)),
            parent=self,
        )

    def closeEvent(self, event):
        self._stop_workers()
        super().closeEvent(event)

    def _stop_workers(self):
        for worker in tuple(self._workers):
            worker.requestInterruption()
            worker.wait()
