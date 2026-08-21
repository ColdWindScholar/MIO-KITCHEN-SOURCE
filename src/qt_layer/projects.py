import logging
import os
import pathlib
import subprocess
import sys
import time
from shutil import rmtree

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QListWidget, QHBoxLayout, QWidget, QListWidgetItem, QTableWidgetItem, QLabel, \
    QHeaderView
from qfluentwidgets import SimpleCardWidget, BodyLabel, CheckBox, ComboBox, RadioButton, PushButton, ScrollArea, \
    SearchLineEdit, FluentIcon as FIF, ListWidget, PrimaryPushButton, SubtitleLabel, TableWidget, MessageBox

import ext4
import imgextractor
import lpunpack
import splituapp
import utils
from payload_extract import extract_partitions_from_payload
from pygpt.gpt_reader import GPTReader
from qt_layer.settings import cfg
from qt_layer.widgets import NewProjectDialog, show_info_bar
from romfs_parse import RomfsParse
from splash_editor.src.logo_gen_decoder import process_splashimg
from utils import gettype
from src.core.aml_image import main as aml_main
try:
    from src.core.pycase import ensure_dir_case_sensitive
except ImportError:
    ensure_dir_case_sensitive = lambda *x: print(f'Cannot sensitive {x}, Not Supported')


class ProjectManager:
    def __init__(self):
        self.hide_items = ['bin', 'src', 'readmes']

    @staticmethod
    def get_work_path(name):
        path = str(os.path.join(cfg.workingFolder.value, name) + os.sep)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def get_projects(self):
        for f in os.listdir(cfg.workingFolder.value):
            if os.path.isdir(f'{cfg.workingFolder.value}/{f}') and f not in self.hide_items and not f.startswith('.'):
                yield f

    def new(self, name: str):
        if ' ' in name:
            name = name.replace(" ", '_')
        path = self.get_work_path(name)
        os.makedirs(path, exist_ok=True)
        return path

    def current_work_path(self, mkdir=False):
        if cfg.projectStructure.value == 'Single':
            path = self.get_work_path(cfg.currentProjectName.value)
        else:
            path = os.path.join(self.get_work_path(cfg.currentProjectName.value), 'Source') + os.sep
            if not os.path.exists(path) and cfg.currentProjectName.value:
                os.makedirs(path, exist_ok=True)
        if mkdir:
            os.makedirs(path, exist_ok=True)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def current_origin_path(self):
        if cfg.projectStructure.value == 'Single':
            path = self.get_work_path(cfg.currentProjectName.value)
        else:
            path = os.path.join(self.get_work_path(cfg.currentProjectName.value), 'Origin') + os.sep
            if not os.path.exists(path) and cfg.currentProjectName.value:
                os.makedirs(path, exist_ok=True)
        return path if os.name == 'nt' else path.replace('\\', '/')

    def current_work_output_path(self):
        if cfg.workingFolder.value == 'Single':
            path = self.get_work_path(cfg.currentProjectName.value)
        else:
            path = os.path.join(self.get_work_path(cfg.currentProjectName.value), 'Output') + os.sep
            if not os.path.exists(path) and cfg.currentProjectName.value:
                os.makedirs(path, exist_ok=True)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def exist(self, name=None):
        current_name = name or cfg.currentProjectName.value
        if not current_name:
            return False
        return os.path.exists(self.get_work_path(current_name))

    def remove(self, name):
        if not self.exist(name):
            return True
        else:
            rmtree(self.get_work_path(name))
        return not self.exist(name)


project_manger = ProjectManager()

def unpack(chose: list | dict, form: str = '') -> bool:
    if os.name == 'nt':
        if windll.shell32.IsUserAnAdmin():
            try:
                ensure_dir_case_sensitive(project_manger.current_work_path())
            except (Exception, BaseException):
                logging.exception('Bugs')
    if not project_manger.exist():
        win.message_pop(lang.warn1)
        return False
    elif not os.path.exists(project_manger.current_work_path()):
        win.message_pop(lang.warn1, "red")
        return False
    json_ = utils.JsonEdit((work := project_manger.current_work_path()) + "config/parts_info")
    parts = json_.read()
    if not chose:
        return False
    if form == 'payload':
        time_start = time.time()
        print(lang.text79 + "payload")
        with open(f"{work}/payload.bin", "rb") as f:
            extract_partitions_from_payload(
                f,
                (
                    chose
                ),
                work,
                os.cpu_count() or 2,
            )
        tooks = time.time() - time_start
        print("Done! tooks: %.2f" % tooks)
        return True
    elif form == 'super':
        print(lang.text79 + "Super")
        file_type = gettype(f"{work}/super.img")
        if file_type == "sparse":
            print(lang.text79 + f"super.img [{file_type}]")
            try:
                utils.simg2img(f"{work}/super.img")
            except (Exception, BaseException):
                win.message_pop(lang.warn11.format("super.img"))
        if gettype(f"{work}/super.img") == 'super':
            # should get info here.
            parts["super_info"] = lpunpack.get_info(os.path.join(work, "super.img"))
            lpunpack.unpack(os.path.join(work, "super.img"), work, chose)
            for file_name in os.listdir(work):
                if file_name.endswith('_a.img') and not os.path.exists(work + file_name.replace('_a', '')):
                    os.rename(work + file_name, work + file_name.replace('_a', ''))
                if file_name.endswith('_b.img'):
                    if not os.path.getsize(work + file_name):
                        os.remove(work + file_name)
            json_.write(parts)
            parts.clear()
        return True
    elif form == 'update.app':
        splituapp.extract(f"{work}/UPDATE.APP", work, chose)
        return True
    for i in chose:
        if os.access(f"{work}/{i}.zst", os.F_OK):
            print(f"{lang.text79} {i}.zst")
            utils.call(['zstd', '--rm', '-d', f"{work}/{i}.zst"])
            return True
        if os.access(f"{work}/{i}.new.dat.xz", os.F_OK):
            print(lang.text79 + f"{i}.new.dat.xz")
            utils.Unxz(f"{work}/{i}.new.dat.xz")
        if os.access(f"{work}/{i}.new.dat.br", os.F_OK):
            print(lang.text79 + f"{i}.new.dat.br")
            utils.call(['brotli', '-dj', f"{work}/{i}.new.dat.br"])
        if os.access(f"{work}/{i}.new.dat.1", os.F_OK):
            with open(f"{work}/{i}.new.dat", 'ab') as ofd:
                for n in range(100):
                    if os.access(f"{work}/{i}.new.dat.{n}", os.F_OK):
                        print(lang.text83 % (i + f".new.dat.{n}", f"{i}.new.dat"))
                        with open(f"{work}/{i}.new.dat.{n}", 'rb') as fd:
                            ofd.write(fd.read())
                        os.remove(f"{work}/{i}.new.dat.{n}")
        if os.access(f"{work}/{i}.new.dat", os.F_OK):
            print(lang.text79 + f"{work}/{i}.new.dat")
            if os.path.getsize(f"{work}/{i}.new.dat") != 0:
                transferfile = f"{work}/{i}.transfer.list"
                if os.access(transferfile, os.F_OK):
                    parts['dat_ver'] = Sdat2img(transferfile, f"{work}/{i}.new.dat", f"{work}/{i}.img").version
                    if os.access(f"{work}/{i}.img", os.F_OK):
                        os.remove(f"{work}/{i}.new.dat")
                        os.remove(transferfile)
                        try:
                            os.remove(f'{work}/{i}.patch.dat')
                        except (Exception, BaseException):
                            logging.exception('Bugs')
                    else:
                        print("File May Not Extracted.")
                else:
                    print("transferfile" + lang.text84)
        if os.access(f"{work}/{i}.img", os.F_OK):
            try:
                if i in parts:
                    parts.pop(i)
            except KeyError:
                logging.exception('Key')
            if gettype(f"{work}/{i}.img") != 'sparse':
                parts[i] = gettype(f"{work}/{i}.img")
            if gettype(f"{work}/{i}.img") == 'dtbo':
                un_dtbo(i)
            if gettype(f"{work}/{i}.img") in ['boot', 'vendor_boot']:
                unpack_boot(i)
            if i == 'logo':
                try:
                    utils.LogoDumper(f"{work}/{i}.img", f'{work}/{i}').check_img(f"{work}/{i}.img")
                except AssertionError:
                    logging.exception('Bugs')
                else:
                    logo_dump(f"{work}/{i}.img", output_name=i)
            if gettype(f"{work}/{i}.img") == 'vbmeta':
                print(f"{lang.text85}AVB:{i}")
                utils.Vbpatch(f"{work}/{i}.img").disavb()
            file_type = gettype(f"{work}/{i}.img")
            if file_type == "sparse":
                print(lang.text79 + f"{i}.img[{file_type}]")
                try:
                    utils.simg2img(f"{work}/{i}.img")
                except (Exception, BaseException) as e:
                    logging.exception(e)
                    win.message_pop(e)
                    continue
            if i not in parts.keys():
                parts[i] = gettype(f"{work}/{i}.img")
            print(lang.text79 + f"{i}.img[{file_type}]")
            if gettype(f"{work}/{i}.img") == 'super':
                parts["super_info"] = lpunpack.get_info(f"{work}/{i}.img")
                lpunpack.unpack(f"{work}/{i}.img", work)
                for file_name in os.listdir(work):
                    file_path = work + file_name
                    if file_name.endswith('_a.img'):
                        if os.path.exists(file_path) and os.path.exists(work + file_name.replace('_a', '')):
                            if pathlib.Path(file_path).samefile(work + file_name.replace('_a', '')):
                                os.remove(file_path)
                            else:
                                os.remove(work + file_name.replace('_a', ''))
                                os.rename(file_path, work + file_name.replace('_a', ''))
                        else:
                            os.rename(file_path, work + file_name.replace('_a', ''))
                    if file_name.endswith('_b.img'):
                        if not os.path.getsize(file_path):
                            os.remove(file_path)
                json_.write(parts)
                parts.clear()
            if (file_type := gettype(f"{work}/{i}.img")) == "ext":
                with open(f"{work}/{i}.img", 'rb+') as e:
                    mount = ext4.Volume(e).get_mount_point
                    if mount[:1] == '/':
                        mount = mount[1:]
                    if '/' in mount:
                        mount = mount.split('/')
                        mount = mount[len(mount) - 1]
                    if mount != i and mount and i != 'mi_ext':
                        parts[mount] = 'ext'
                # libutils.ext4_extractor(f'{work}/config', f"/{mount}", project_manger.current_work_path() + i + ".img", f'{work}/{i}', 4096, 'e', False, i)
                imgextractor.Extractor().main(project_manger.current_work_path() + f"{i}.img", f'{work}/{i}', work)
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except Exception as e:
                        win.message_pop(lang.warn11.format(f"{i}.img:{e.__str__()}"))
            if file_type == 'romfs':
                fs = RomfsParse(project_manger.current_work_path() + f"{i}.img")
                fs.extract(work)
            if file_type in ['rkfw', 'rkaf']:
                utils.call(['afptool', 'unpack', f"{project_manger.current_work_path()}/{i}.img", work])
            if file_type == 'guoke_logo':
                utils.GuoKeLogo().unpack(os.path.join(project_manger.current_work_path(), f'{i}.img'), f'{work}/{i}')
            if file_type == 'splash':
                if not os.path.exists(splash_out_dir := os.path.join(work, i)):
                    os.makedirs(splash_out_dir, True)
                process_splashimg(os.path.join(project_manger.current_work_path(), f'{i}.img'),
                                  f"{work}/{i}/splash.png")
            if file_type == 'gpt':
                reader = GPTReader(os.path.join(project_manger.current_work_path(), f'{i}.img'), sector_size=512)
                for partition in reader.partition_table.valid_entries():
                    print('guid/type={} first-block={} size={} name={}'.format(
                        partition.partition_type, partition.first_block, partition.length, partition.name))
                    if True:
                        file_base_name = partition.name if partition.name else str(partition.partition_id)

                        out_file = os.path.join(work, f'{file_base_name}.img')
                        print(f'Writing partition to file {out_file}')

                        with open(out_file, 'wb+') as fout:
                            for block in reader.block_reader.blocks_in_range(partition.first_block, partition.length):
                                fout.write(block)

            if file_type == "erofs":
                if utils.call(exe=['extract.erofs', '-i', os.path.join(project_manger.current_work_path(), f'{i}.img'), '-o',
                                   work,
                             '-x'],
                              out=False) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'f2fs':
                if utils.call(exe=['imgkit', 'unpack', "-i", os.path.join(project_manger.current_work_path(), f'{i}.img'),
                             "-o", work],
                              out=False) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'amlogic':
                aml_main(os.path.join(project_manger.current_work_path(), f'{i}.img'), work)
            if file_type == 'unknown' and utils.is_empty_img(f"{work}/{i}.img"):
                print(lang.text141)
    if not os.path.exists(f"{work}/config"):
        os.makedirs(f"{work}/config")
    json_.write(parts)
    parts.clear()
    print(lang.text8)
    return True

class ProjectsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectsPage")
        self.initUI()

    def initUI(self):
        # 1. 基础布局与极简深色背景
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: #00202020; color: #ffffff;")

        # 使用 QFluentWidgets 原生滚动区域
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        # 核心滚动容器
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)

        # 【关键优化：增加顶部与四周间距】把原本紧凑的区域整体下调，留出透气的空间
        self.scroll_layout.setContentsMargins(32, 40, 32, 32)
        self.scroll_layout.setSpacing(35)  # 模块与模块之间拉开足够的高级感间距
        scroll_area.setWidget(scroll_content)

        # 2. 依次构建去背景、去卡片的扁平化模块
        self._build_project_section(scroll_content)
        self._build_partition_section(scroll_content)
        self._build_tools_section(scroll_content)

        # 底层弹性推力
        self.scroll_layout.addStretch(1)
        self.refresh_projects()

    def _create_section_title(self, text):
        """统一生成无边框、无背景的纯文本全局大标题"""
        title = BodyLabel(text)
        title.setStyleSheet("""
            font-size: 17px; 
            font-weight: 600; 
            color: #ffffff; 
            background: transparent; 
            border: none;
            padding-bottom: 4px;
        """)
        return title
    def refresh_projects(self):
        self.project_combo.clear()
        projects = project_manger.get_projects()
        self.project_combo.addItems(projects)
        if projects:
            self.project_combo.setCurrentIndex(0)
            return
        cfg.set(cfg.currentProjectName, 'empty_project')
        cfg.save()
    def open_dir(self):
        name = self.project_combo.currentText()
        if not project_manger.exist(name):
            show_info_bar(self, "Warning", f"Cannot open folder:\n{name}", 2)
            return

        path = project_manger.get_work_path(name)
        if not path or not os.path.exists(path):
            show_info_bar(self, "Warning", f"Cannot open folder:\n{path}", 2)
            return

        try:
            path = os.path.normpath(path)
            if os.name == 'nt':
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception:
            show_info_bar(self, "Warning", f"Cannot open folder:\n{path}", 2)
    def show_create_dialog(self):
        """显示创建项目对话框"""
        dialog = NewProjectDialog(
            title="创建新项目",
            existing_projects=list(project_manger.get_projects()),
            parent=self
        )
        if dialog.exec():
            project_name = dialog.nameLineEdit.text().strip()
            project_manger.new(project_name)
            self.refresh_projects()

    def show_rename_dialog(self):
        """显示创建项目对话框"""
        project_name = cfg.currentProjectName.value
        if not project_name or not self.project_combo.currentText():
            show_info_bar(self, "提示", "请先选择一个项目", bar_type=2)
            return
        dialog = NewProjectDialog(
            title="重命名项目",
            existing_projects=list(project_manger.get_projects()),
            initial_text=self.project_combo.currentText(),
            parent=self
        )
        if dialog.exec():
            project_name = dialog.nameLineEdit.text().strip()
            project_manger.new(project_name)
            self.refresh_projects()
    def delete_project(self):
        """删除选中的项目并显示提示"""
        project_name = cfg.currentProjectName.value
        if not project_name or not self.project_combo.currentText():
            show_info_bar(self,"提示", "请先选择一个项目", bar_type=2)
            return

        result = MessageBox(
            "确认删除",
            f"确定要删除项目 '{project_name}' 吗?",
            self
        ).exec()

        if result != 1:
            return

        try:
            project_manger.remove(project_name)
            show_info_bar(self,"成功", f"项目{project_name}已删除", bar_type=3)
        except Exception as e:
            show_info_bar(self, "错误", f"删除项目失败: {str(e)}", bar_type=1)
        self.refresh_projects()
    def _build_project_section(self, parent_widget):
        """项目管理模块：去掉 Card 容器，直接将控件平铺在主背景上"""
        container = QWidget(parent_widget)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 标题放外面
        layout.addWidget(self._create_section_title("项目管理"))

        # 下半部分控件区域
        row1 = QHBoxLayout()
        self.project_combo = ComboBox(container)
        self.project_combo.setPlaceholderText("选择或搜索目标项目...")
        self.project_combo.addItems(project_manger.get_projects())
        self.project_combo.currentTextChanged.connect(lambda :cfg.set(cfg.currentProjectName, self.project_combo.currentText()))
        self.open_btn = PushButton("打开", container, FIF.FOLDER)
        self.open_btn.clicked.connect(self.open_dir)
        row1.addWidget(self.project_combo, 1)
        row1.addWidget(self.open_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.new_btn = PushButton("新建", container, FIF.ADD)
        self.new_btn.clicked.connect(self.show_create_dialog)
        self.refresh_btn = PushButton("刷新", container, FIF.SYNC)
        self.refresh_btn.clicked.connect(self.refresh_projects)
        self.rename_btn = PushButton("重命名", container, FIF.EDIT)
        self.rename_btn.clicked.connect(self.show_rename_dialog)
        self.delete_btn = PushButton("删除", container, FIF.DELETE)
        self.delete_btn.clicked.connect(self.delete_project)

        for btn in [self.new_btn, self.refresh_btn, self.rename_btn, self.delete_btn]:
            btn.setMinimumWidth(90)
            row2.addWidget(btn)
        row2.addStretch(1)
        layout.addLayout(row2)

        self.scroll_layout.addWidget(container)

    def _build_partition_section(self, parent_widget):
        """分区控制模块：标题完全独立，仅保留核心高级列表的内部深色背板"""
        container = QWidget(parent_widget)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # 标题放外面
        frame = QHBoxLayout()
        frame.addWidget(self._create_section_title("分区"))
        self.execute_btn = PrimaryPushButton("执行", container, FIF.PLAY)
        self.execute_btn.setFixedWidth(80)
        frame.addWidget(self.execute_btn)
        layout.addLayout(frame)

        # 高级现代列数据集表格（参照上一轮设计的现代化 List 样式）
        self.partition_table = TableWidget(container)
        self.partition_table.setColumnCount(5)
        self.partition_table.setFixedHeight(240)

        self.partition_table.verticalHeader().setVisible(False)
        self.partition_table.setSelectionBehavior(TableWidget.SelectRows)
        self.partition_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 5):
            self.partition_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        layout.addWidget(self.partition_table)

        # 全选与搜索框
        row1 = QHBoxLayout()
        self.select_all_cb = CheckBox("全选", container)
        self.select_all_cb.stateChanged.connect(self._toggle_select_all_partitions)
        self.filter_input = SearchLineEdit(container)
        self.filter_input.setPlaceholderText("根据名称快速检索...")
        self.filter_input.textChanged.connect(self.filter_tabview)
        self.filter_input.setFixedWidth(230)
        self.format_combo = ComboBox(container)
        self.format_combo.addItems(['new.dat.br', 'new.dat.xz', "new.dat", 'img', 'zst', 'payload', 'super',
                                   'update.app'])
        self.format_combo.currentTextChanged.connect(self.refresh_unpack)
        self.partition_table.setHorizontalHeaderLabels(["NAME", "SIZE", "FS", "IMAGE", "ATTRIBUTES"])
        self.unpack_rb = RadioButton("解包", container)
        self.pack_rb = RadioButton("打包", container)
        self.unpack_rb.clicked.connect(self.refresh_unpack)
        self.pack_rb.clicked.connect(self.refresh_repack)
        self.unpack_rb.setChecked(True)
        row1.addWidget(self.select_all_cb)
        row1.addWidget(self.pack_rb)
        row1.addWidget(self.unpack_rb)
        row1.addWidget(self.format_combo)
        row1.addWidget(self.filter_input)
        layout.addLayout(row1)

        self.scroll_layout.addWidget(container)

    def _toggle_select_all_partitions(self, state):
        """Toggles check state of all visible rows based on the Select All checkbox."""
        target_state = Qt.CheckState.Checked if state == Qt.CheckState.Checked.value else Qt.CheckState.Unchecked

        for row_idx in range(self.partition_table.rowCount()):
            if not self.partition_table.isRowHidden(row_idx):
                name_item = self.partition_table.item(row_idx, 0)  # Column 0 has the checkbox
                if name_item is not None:
                    name_item.setCheckState(target_state)

    def _build_tools_section(self, parent_widget):
        """高级工具箱：纯扁平化工具栏，取消卡片框"""
        container = QWidget(parent_widget)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 标题放外面
        layout.addWidget(self._create_section_title("高级工具箱"))

        # 工具按钮行
        tools_layout = QHBoxLayout()
        self.zip_btn = PushButton("打包ZIP", container, FIF.APPLICATION)
        self.super_btn = PushButton("打包Super", container, FIF.ALBUM)
        self.format_conv_btn = PushButton("格式转换", container, FIF.EMBED)
        self.apk_mgr_btn = PushButton("APK 助手", container, FIF.DEVELOPER_TOOLS)

        for btn in [self.zip_btn, self.super_btn, self.format_conv_btn, self.apk_mgr_btn]:
            btn.setMinimumWidth(105)
            tools_layout.addWidget(btn)

        tools_layout.addStretch(1)
        layout.addLayout(tools_layout)

        self.scroll_layout.addWidget(container)

    def refresh_repack(self):
        self.format_combo.setDisabled(True)
        self.partition_table.clearContents()
        self._load_mock_partitions_table(self.refresh_repack_list())

    def refresh_repack_list(self):
        data = []
        work = project_manger.current_work_path()
        if not os.path.exists(work):
            print("Work path does not exist")
            return data
        parts_dict = utils.JsonEdit(f"{work}/config/parts_info").read()
        for folder in os.listdir(work):
            if os.path.isdir(work + folder) and folder in parts_dict.keys():
                data.append(
                    (folder, utils.hum_convert(os.path.getsize(work + folder)), parts_dict.get(folder, 'Unknown'),
                     "Source", "rw"))
        return data

    def refresh_unpack(self):
        self.format_combo.setDisabled(False)
        self.partition_table.clearContents()
        self._load_mock_partitions_table(self.refresh_unpack_list())

    def refresh_unpack_list(self):
        """The actual logic for refreshing the unpack list, runs in a separate thread."""
        data = []
        work = project_manger.current_work_path()
        if not project_manger.exist():
            return data

        form = self.format_combo.currentText()
        if form == 'payload':
            if os.path.exists(f"{work}/payload.bin"):
                with open(f"{work}/payload.bin", 'rb') as pay:
                    for i in utils.payload_reader(pay).partitions:
                        data.append((i.partition_name, utils.hum_convert(i.new_partition_info.size), "Raw", "Unknown",
                                     "Unknown"))

        elif form == 'super':
            if os.path.exists(f"{work}/super.img"):
                if gettype(f"{work}/super.img") == 'sparse':
                    print("The image is sparse, pls convert it to raw first.")
                    return data
                for i in lpunpack.get_parts(f"{work}/super.img"):
                    data.append((i, "Unknown", "Raw", "Unknown", "Unknown"))
        elif form == 'update.app':
            if os.path.exists(f"{work}/UPDATE.APP"):
                for i in splituapp.get_parts(f"{work}/UPDATE.APP"):
                    data.append((i, "Unknown", "Raw", "Unknown", "Unknown"))
        else:
            for file_name in os.listdir(work):
                if file_name.endswith(form):
                    if file_name.endswith("img"):
                        f_type = gettype(work + file_name)
                        if f_type == 'unknown':
                            f_type = form
                    else:
                        f_type = form
                    data.append(
                        (file_name[:-len(f".{form}")], utils.hum_convert(os.path.getsize(work + file_name)), f_type,
                         "Image", "rw" if f_type == 'ext' else "ro",))
        return data

    def filter_tabview(self, query:str):
        search_query = query.strip().lower()
        for row_idx in range(self.partition_table.rowCount()):
            item = self.partition_table.item(row_idx, 0)
            if item is not None:
                cell_text = item.text().strip().lower()

                if search_query in cell_text or not search_query:
                    self.partition_table.setRowHidden(row_idx, False)
                else:
                    self.partition_table.setRowHidden(row_idx, True)


    def _load_mock_partitions_table(self, mock_data):
        """装载高质感的数据集行数据（带彩色胶囊Badge标签）"""
        self.partition_table.setRowCount(len(mock_data))
        for row_idx, (name, size, fs, img_type, attrs) in enumerate(mock_data):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setCheckState(Qt.Unchecked)
            self.partition_table.setItem(row_idx, 0, name_item)
            self.partition_table.setItem(row_idx, 1, QTableWidgetItem(size))
            self.partition_table.setItem(row_idx, 2, QTableWidgetItem(fs))

            # 高级彩色高亮标签
            badge = QLabel(img_type)
            badge.setAlignment(Qt.AlignCenter)
            if img_type == "Build":
                badge.setStyleSheet(
                    "color: #a78bfa; border-radius: 6px; font-weight: bold; font-size: 11px; margin: 3px;")
            else:
                badge.setStyleSheet(
                    "color: #f59e0b; border-radius: 6px; font-weight: bold; font-size: 11px; margin: 3px;")
            self.partition_table.setCellWidget(row_idx, 3, badge)

            attr_item = QTableWidgetItem(attrs)
            self.partition_table.setItem(row_idx, 4, attr_item)
