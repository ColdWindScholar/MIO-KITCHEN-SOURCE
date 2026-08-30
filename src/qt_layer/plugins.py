import json
import os
from io import StringIO
from shutil import rmtree
from typing import Any

from PySide6.QtWidgets import QWidget, QFileDialog
from qfluentwidgets import IconWidget, CardWidget, BodyLabel, FluentIcon, ScrollArea, \
    SearchLineEdit, TitleLabel, TransparentDropDownToolButton, RoundMenu, Action, InfoBar, InfoBarPosition, \
    MessageBoxBase, GroupHeaderCardWidget, LineEdit, SwitchButton, RadioButton

from avb_disabler import process_fstab
from encryption_disabler import process_fstab_for_encryption
from qsb_imger import process_by_xml
from qt_layer.plugin_allow_selinux_audit import AllowSELinuxAuditMessageBox
from qt_layer.plugin_byte_calc import FileBytesMessageBox
from qt_layer.plugin_decrypt_xtc_xml import DecryptXtcXmlMessageBox
from qt_layer.plugin_dis_avb_in_fstab import DisableAvbMessageBox
from qt_layer.plugin_dis_encryption_in_fstab import DisableEncryptionMessageBox
from qt_layer.plugin_get_file_info import FileInfoMessageBox
from qt_layer.plugin_merge_qcom_partitions import MergeQualcommImageMessageBox
from qt_layer.plugin_trim_raw_image import TrimRawImageMessageBox
from src.core import images
from qt_layer.projects import project_manger
from qt_layer.settings import cfg
from src.core import imp
from src.core import utils
from src.core.addon_register import loader, Entry
from src.core.config_parser import ConfigParser
from src.core.utils import create_thread, ModuleErrorCodes, prog_path, call, temp, re_folder
from src.core.xtc_recovery_helper import decrypt as decrypt_xtc
from src.core.selinux_audit_allow import main as selinux_audit_allow

module_exec = os.path.join(prog_path, 'bin', "exec.sh").replace(os.sep, '/')
module_error_codes = ModuleErrorCodes


class ParseMessageBox(MessageBoxBase):
    def __init__(self, json_file_path, parent=None):
        super().__init__(parent)
        self.gavs = {}
        self.cancel = False
        self.w_assert = "False"

        # ─── 主布局结构 (严格垂直排列) ───
        main_widget = QWidget(self)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)


        # 解析并生成动态 UI
        self.load_json_schema(json_file_path)

        self.viewLayout.addWidget(main_widget)
        self.widget.setMinimumWidth(500)

    def load_json_schema(self, path):
        try:
            with open(path, 'r', encoding='UTF-8') as f:
                data = json.load(f)
        except Exception as e:
            logging.exception("JSON 加载失败")
            print(f"{e}")
            self.reject()
            return

        info = data['main']['info']
        self.w_assert = info.get('assert', "False")

        # 1. 顶部主标题 (从主布局垂直向下排)
        self.custom_title = BodyLabel(info.get('title', 'Dynamic Panel'), self)
        self.custom_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.main_layout.addWidget(self.custom_title)

        # 2. 遍历生成卡片组 (容器内部也采用严格垂直布局)
        for group_name, group_data in data['main'].items():
            if group_name == 'info':
                continue

            card = GroupHeaderCardWidget(self)
            card.setContentsMargins(5,5,5,5)
            card.setTitle(group_data.get('title', 'Group Panel'))

            # 使用干净的垂直布局引擎包裹卡片内部的组件
            v_container = QWidget()
            card_v_layout = QVBoxLayout(v_container)
            card_v_layout.setContentsMargins(0, 0, 0, 0)
            card_v_layout.setSpacing(14)  # 控制垂直组件之间的间距

            # 遍历动态解析 controls 内部的各项组件
            for con in group_data.get('controls', []):
                con_type = con.get('type')
                method_name = f"_{con_type}"

                if hasattr(self, method_name):
                    control_factory = getattr(self, method_name)
                else:
                    control_factory = self.__unknown

                control_factory(card_v_layout, con)

            card.viewLayout.addWidget(v_container)
            self.main_layout.addWidget(card)

        # 3. 底部操作按钮栏 (铺满底部的 OK 按钮)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 8, 0, 0)

        self.custom_ok_btn = self.yesButton
        self.custom_ok_btn.setText("run")
        self.custom_ok_btn.clicked.connect(self.accept)

        self.main_layout.addLayout(button_row)

    # ─── 严格垂直流（VBox）动态组件工厂 ───

    def _text(self, layout, config):
        """对应 JSON 中的文本组件，居中对齐"""
        label = BodyLabel(config.get('text', ''))
        fontsize = int(config.get('fontsize', 14))
        label.setStyleSheet(f"font-size: {fontsize}px;")
        label.setAlignment(Qt.AlignCenter)  # 居中对齐，契合解包界面样式
        layout.addWidget(label)

    def _filechose(self, layout, config):
        """对应 JSON 中的文件选择组件（垂直排布：标签在上，输入框与浏览按钮在下）"""
        v_box = QVBoxLayout()
        v_box.setSpacing(6)

        key = config.get('set')
        self.gavs[key] = ""

        label = BodyLabel(config.get('text', 'File:'))

        # 输入框与浏览按钮水平并排
        h_row = QHBoxLayout()
        line_edit = LineEdit()
        btn = PushButton("浏览")
        btn.setFixedWidth(85)

        line_edit.textChanged.connect(lambda text: self.gavs.__setitem__(key, text))

        def pick_file():
            path, _ = QFileDialog.getOpenFileName(self, "选择镜像文件")
            if path:
                line_edit.setText(path)

        btn.clicked.connect(pick_file)

        h_row.addWidget(line_edit, 1)
        h_row.addWidget(btn)

        v_box.addWidget(label)
        v_box.addLayout(h_row)
        layout.addLayout(v_box)

    def _input(self, layout, config):
        """对应 JSON 中的输入框组件（垂直排布：标签在上，输入框在下）"""
        v_box = QVBoxLayout()
        v_box.setSpacing(6)

        key = config.get('set')
        self.gavs[key] = ""

        text = config.get('text', 'None')
        if text != 'None':
            label = BodyLabel(text)
            v_box.addWidget(label)

        line_edit = LineEdit()
        line_edit.textChanged.connect(lambda val: self.gavs.__setitem__(key, val))

        v_box.addWidget(line_edit)
        layout.addLayout(v_box)

    def _button(self, layout, config):
        btn = PushButton(config.get('text', 'Button'))
        command_str = config.get('command', '')
        btn.clicked.connect(lambda: exec(command_str, globals(), locals()))
        layout.addWidget(btn)

    def _radio(self, layout, config):
        v_box = QVBoxLayout()
        v_box.setSpacing(6)
        key = config.get('set')
        options = config.get('opins', '').split()
        self.gavs[key] = ""

        for op in options:
            if '|' not in op:
                continue
            text, val = op.split('|')
            rb = RadioButton(text)
            rb.toggled.connect(lambda checked, v=val: self.gavs.__setitem__(key, v) if checked else None)
            v_box.addWidget(rb)
        layout.addLayout(v_box)

    def _checkbutton(self, layout, config):
        key = config.get('set')
        self.gavs[key] = 0
        text = config.get('text', '')
        text = '' if text == 'None' else text

        switch = SwitchButton(text)
        switch.checkedChanged.connect(lambda checked: self.gavs.__setitem__(key, 1 if checked else 0))
        layout.addWidget(switch)

    def __unknown(self, layout, config):
        self.cancel = self.w_assert in ['true', 'True', '1', 'Yes', 'yes']
        con_type = config.get('type', 'Unknown')
        label = BodyLabel("不支持的控件：{}".format(con_type))
        label.setStyleSheet("color: #ff4d4f; font-weight: bold;")
        layout.addWidget(label)

    def closeEvent(self, event):
        self.cancel = True
        super().closeEvent(event)


class ModuleManager:
    def __init__(self):
        self.module_dir = os.path.join(prog_path, "bin", "module")
        self.addon_loader = loader
        self.addon_entries = Entry
        self.master = None
        create_thread(self.load_plugins)

    def is_installed(self, id_) -> bool:
        path = os.path.join(self.module_dir, id_)
        if os.path.exists(path) and os.path.isdir(path):
            if os.path.exists(os.path.join(path, 'info.json')):
                return True
        return False

    def is_virtual(self, id_) -> bool:
        return id_ in self.addon_loader.virtual.keys()

    def get_name(self, id_) -> str:
        if self.is_virtual(id_):
            return self.addon_loader.virtual[id_].get("name", id_)
        return self.get_info(id_, 'name') or id_

    def list_packages(self):
        for i in os.listdir(self.module_dir):
            if self.is_installed(i):
                if os.path.isdir(os.path.join(self.module_dir, i)):
                    yield i

    def register_plugin(self, id_: str):
        script_path = f"{self.module_dir}/{id_}"
        if os.path.exists(f"{script_path}/main.py") and imp:
            try:
                module = imp.load_source(id_, f"{script_path}/main.py")
                if hasattr(module, 'entrances'):
                    for entry, func in module.entrances.items():
                        self.addon_loader.register(id_, entry, func)
                elif hasattr(module, 'main'):
                    self.addon_loader.register(id_, self.addon_entries.main, module.main)
                else:
                    print(
                        f"Can't registry Module {self.get_name(id_)} as Plugin, Check if enterances or main function in it.")
            except Exception as e:
                logging.error(f"Load Failed '{self.get_name(id_)}' path '{script_path}/main.py': {e}")
                logging.exception('Bugs')

    def load_plugins(self):
        if not os.path.exists(self.module_dir) or not os.path.isdir(self.module_dir):
            os.makedirs(self.module_dir, exist_ok=True)
        for i in self.list_packages():
            self.register_plugin(i)

    def get_info(self, id_: str, item: str | None = None, default: str | None = None) -> str | dict[Any, Any] | Any:
        if not default:
            default = {}
        info_file = f'{self.module_dir}/{id_}/info.json'
        if not os.path.exists(info_file):
            return default
        try:
            with open(info_file, 'r', encoding='UTF-8') as f:
                return json.load(f).get(item, default) if item else json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {info_file} for plugin {id_}")
            return default
        except Exception as e:
            logging.error(f"Error reading info file {info_file} for plugin {id_}: {e}")
            return default

    def run(self, id_=None) -> int:
        if not id_:
            return 0
        if not cfg.currentProjectName.value:
            print("Please set a project")
            return 1
        if id_:
            value = id_
        else:
            print("id is invaild")
            return 1
        script_path = os.path.join(self.module_dir, value)

        if not self.is_virtual(id_):
            name = self.get_name(id_)
            info_json_path = os.path.join(script_path, "info.json")
            if not os.path.exists(info_json_path):
                logging.error(f"run: info.json not found for plugin {id_} at {info_json_path}")
                print(f"Plugin {name} configuration is missing.")
                return 3

            try:
                with open(info_json_path, 'r', encoding='UTF-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logging.error(f"run: Could not decode info.json for plugin {id_}")
                print(f"Plugin {name} configuration is corrupted.")
                return 4
            except Exception as e:
                logging.error(f"run: Error reading info.json for plugin {id_}: {e}")
                print(f"Error accessing plugin {name} configuration.")
                return 5

            dependencies = data.get('depend', '')
            for n in dependencies.split():
                if n and not os.path.exists(os.path.join(self.module_dir, n)):
                    print("%s 依赖于 %s，但 %s 没有安装" % (name, n, n))
                    return 2

        main_json_path = os.path.join(script_path, "main.json")
        values = {}
        if os.path.exists(main_json_path) and self.master:
            values_parser = ParseMessageBox(main_json_path, self.master)
            if values_parser.exec():
                if values_parser.cancel:
                    return 2
                values = values_parser.gavs
            else:
                return 2
        else:
            logging.warning("Cannot exec gui plugin, bcs master not set or json not exists.")

        main_sh_path = os.path.join(script_path, "main.sh")
        main_py_path = os.path.join(script_path, "main.py")

        if os.path.exists(main_sh_path):
            if not os.path.exists(temp):
                re_folder(temp)
            exports: dict = dict()
            if values:
                for va, string_var in values.items():
                    if string_var:
                        exports[va] = string_var

            norm_tool_bin = os.path.normpath(cfg.tool_bin).replace(os.sep, '/')
            norm_script_path = os.path.normpath(script_path).replace(os.sep, '/')
            norm_module_dir = os.path.normpath(self.module_dir).replace(os.sep, '/')
            norm_project_output = os.path.normpath(project_manger.current_work_output_path()).replace(os.sep, '/')
            norm_project_work = os.path.normpath(project_manger.current_work_path()).replace(os.sep, '/')
            norm_module_exec = os.path.normpath(module_exec).replace(os.sep, '/')
            norm_main_sh_path = os.path.normpath(main_sh_path).replace(os.sep, '/')
            exports['tool_bin'] = norm_tool_bin
            exports['version'] = "b"
            exports['language'] = cfg.language.value
            exports['bin'] = norm_script_path
            exports['moddir'] = norm_module_dir
            exports['project_output'] = norm_project_output
            exports['project'] = norm_project_work

            shell_command_prefix = 'ash' if os.name == 'posix' else 'bash'
            full_shell_command = f"exec {norm_module_exec} {norm_main_sh_path}"

            call_result = call(["busybox", shell_command_prefix, '-c', full_shell_command], env=exports)
            return call_result

        elif os.path.exists(main_py_path) and imp:
            if not self.addon_loader.is_registered(id_):
                self.register_plugin(id_)
            self.addon_loader.run(id_, Entry.main, mapped_args=values)
        elif self.is_virtual(id_):
            self.addon_loader.run(id_, Entry.main, mapped_args=values)
        elif not os.path.exists(os.path.join(self.module_dir, value)):
            print("{} 未完全安装或损坏".format(value))

        else:
            print("此插件不可运行".format(self.get_name(id_)))
        return 0

    @staticmethod
    def check_mpk(mpk):  # Move check progress from InstallMpk to this
        if not mpk or not os.path.exists(mpk) or not zipfile.is_zipfile(mpk):
            return module_error_codes.IsBroken, ''
        try:
            with zipfile.ZipFile(mpk) as f:
                f_list = f.namelist()
                if 'info' not in f_list:
                    return module_error_codes.IsBroken, 'Missing info file'
                if 'icon' not in f_list:
                    return module_error_codes.Normal, 'Missing icon file, use default'
        except zipfile.BadZipFile:
            return module_error_codes.IsBroken, 'Corrupted MPK archive'
        return module_error_codes.Normal, ''

    def install(self, mpk_path):
        logging.info(f"ModuleManager.install: Starting installation from MPK: {mpk_path}")
        check_mpk_result, reason = self.check_mpk(mpk_path)
        if check_mpk_result != module_error_codes.Normal:
            logging.error(
                f"ModuleManager.install: MPK check failed for '{mpk_path}'. Result: {check_mpk_result}, Reason: '{reason}'")
            return check_mpk_result, reason

        mconf = ConfigParser()
        try:
            with zipfile.ZipFile(mpk_path) as f:
                with f.open('info') as info_file:
                    mconf.read_string(info_file.read().decode('utf-8'))
            logging.debug(f"ModuleManager.install: Successfully read 'info' from MPK '{mpk_path}'.")
        except Exception as e:
            logging.exception(f"ModuleManager.install: Error reading 'info' from MPK '{mpk_path}': {e}")
            return module_error_codes.IsBroken, "Error reading MPK info file"

        install_id = mconf.get('module', 'identifier', None)

        if not install_id:
            logging.error(f"ModuleManager.install: Plugin identifier missing in 'info' of MPK '{mpk_path}'.")
            return module_error_codes.IsBroken, "Missing identifier in plugin info"
        logging.debug(f"ModuleManager.install: Plugin ID: '{install_id}'.")

        try:
            supports_str = mconf.get('module', 'supports', '')
            supports = supports_str.split() if supports_str else []
            if supports and platform.system() not in supports:
                logging.warning(
                    f"ModuleManager.install: Platform not supported for plugin '{install_id}'. Required: {supports}, Current: {platform.system()}")
                return module_error_codes.PlatformNotSupport, f"Unsupported platform: {platform.system()}"
        except Exception as e:
            logging.exception(f"ModuleManager.install: Error checking platform support for '{install_id}': {e}")
        system_target = mconf.get("module", 'system', 'all')
        if system_target != 'all':
            if platform.system() not in system_target.split(" "):
                return module_error_codes.PlatformNotSupport, f"Unsupported platform: {system_target}"
        arch_target = mconf.get("module", 'arch', 'all')
        if arch_target != 'all':
            if platform.machine() not in arch_target.split(" "):
                return module_error_codes.ArchNotSupported, f"Unsupported Arch: {arch_target}"
        depend_str = mconf.get('module', 'depend', '')
        logging.debug(f"ModuleManager.install: Dependencies for '{install_id}': '{depend_str}'")
        for dep_id_str in depend_str.split():
            if dep_id_str and not os.path.isdir(os.path.join(self.module_dir, dep_id_str)):
                logging.warning(
                    f"ModuleManager.install: Dependency '{dep_id_str}' for plugin '{install_id}' is missing.")
                return module_error_codes.DependsMissing, dep_id_str

        install_target_path = os.path.join(self.module_dir, install_id)
        logging.info(f"ModuleManager.install: Target install path for '{install_id}': '{install_target_path}'")

        if os.path.exists(install_target_path):
            logging.info(f"ModuleManager.install: Existing installation found at '{install_target_path}'. Removing it.")
            try:
                rmtree(install_target_path)
                if os.path.exists(install_target_path):
                    logging.error(
                        f"ModuleManager.install: Failed to remove existing directory '{install_target_path}'.")
                    return module_error_codes.GenericError, "Failed to remove old version"
            except Exception as e_rm:
                logging.exception(
                    f"ModuleManager.install: Error removing existing directory '{install_target_path}': {e_rm}")
                return module_error_codes.GenericError, "Error removing old version"

        resource_file_name_in_mpk = mconf.get('module', 'resource', None)
        if not resource_file_name_in_mpk:
            logging.error(f"ModuleManager.install: 'resource' field missing in 'info' for plugin '{install_id}'.")
            return module_error_codes.IsBroken, "Missing resource field in plugin info"
        logging.debug(f"ModuleManager.install: Resource file name: '{resource_file_name_in_mpk}'.")

        try:
            with zipfile.ZipFile(mpk_path, 'r') as mpk_zip_file_obj:
                if resource_file_name_in_mpk not in mpk_zip_file_obj.namelist():
                    logging.error(
                        f"ModuleManager.install: Resource file '{resource_file_name_in_mpk}' not found in MPK '{mpk_path}' for plugin '{install_id}'. Namelist: {mpk_zip_file_obj.namelist()}")
                    return module_error_codes.IsBroken, "Resource file specified in info not found in MPK"

                logging.debug(
                    f"ModuleManager.install: Extracting resource '{resource_file_name_in_mpk}' for plugin '{install_id}'.")
                with mpk_zip_file_obj.open(resource_file_name_in_mpk, 'r') as inner_resource_zip_stream:
                    with zipfile.ZipFile(inner_resource_zip_stream, 'r') as resource_content_zip_obj:
                        os.makedirs(install_target_path, exist_ok=True)
                        logging.debug(
                            f"ModuleManager.install: Contents of resource zip '{resource_file_name_in_mpk}': {resource_content_zip_obj.namelist()}")
                        resource_content_zip_obj.extractall(install_target_path)
                        logging.info(
                            f"ModuleManager.install: Successfully extracted all contents of '{resource_file_name_in_mpk}' to '{install_target_path}'.")
                        # Логирование извлеченных файлов
                        if logging.getLogger().isEnabledFor(logging.DEBUG):
                            extracted_items = []
                            for root_dir, _, files_in_dir in os.walk(install_target_path):
                                for file_item in files_in_dir:
                                    extracted_items.append(os.path.join(root_dir, file_item))
                            logging.debug(
                                f"ModuleManager.install: Verifying extracted files in '{install_target_path}': {extracted_items if extracted_items else 'No files found (or directory is empty after extraction).'}")

                plugin_info_data = {n: v for n, v in mconf.items('module')}
                plugin_info_data['depend'] = depend_str

                info_json_target_path = os.path.join(install_target_path, "info.json")
                with open(info_json_target_path, 'w', encoding='utf-8') as f_json:
                    json.dump(plugin_info_data, f_json, indent=2, ensure_ascii=False)
                logging.debug(f"ModuleManager.install: Created info.json at '{info_json_target_path}'")

                if 'icon' in mpk_zip_file_obj.namelist():
                    icon_target_path = os.path.join(install_target_path, "icon")
                    with open(icon_target_path, 'wb') as f_icon:
                        with mpk_zip_file_obj.open('icon') as icon_stream:
                            f_icon.write(icon_stream.read())
                    logging.debug(f"ModuleManager.install: Extracted icon to '{icon_target_path}'")

        except zipfile.BadZipFile as e_zip:
            logging.exception(
                f"ModuleManager.install: Bad ZIP file encountered (MPK or resource) for '{install_id}': {e_zip}")
            return module_error_codes.IsBroken, "Corrupted archive"
        except IOError as e_io:
            logging.exception(f"ModuleManager.install: IOError during extraction for '{install_id}': {e_io}")
            if os.path.exists(install_target_path):
                try:
                    rmtree(install_target_path)
                except:
                    pass
            return module_error_codes.GenericError, f"IO Error: {e_io}"
        except Exception as e_extract:
            logging.exception(
                f"ModuleManager.install: Error during extraction or file operations for '{install_id}': {e_extract}")
            if os.path.exists(install_target_path):
                try:
                    rmtree(install_target_path)
                except:
                    pass
            return module_error_codes.GenericError, f"Extraction error: {e_extract}"

        logging.info(f"ModuleManager.install: Successfully installed plugin '{install_id}' to '{install_target_path}'.")
        return module_error_codes.Normal, ""

    def export(self, id_: str):

        name: str = self.get_name(id_)
        name = name.replace('/', '')
        if self.is_virtual(id_):
            print(f"{name} is a virtual plugin!")
            return 1
        if not id_:
            print("no such plugin!")
            return 1

        plugin_dir_path = os.path.join(self.module_dir, id_)
        info_json_path = os.path.join(plugin_dir_path, "info.json")

        if not os.path.exists(info_json_path):
            print(f"Error: info.json not found for plugin {id_}")
            return 2

        with open(info_json_path, 'r', encoding='UTF-8') as f:
            data: dict = json.load(f)
            data.setdefault('resource', "main.zip")
            (info_ := ConfigParser())['module'] = data

            buffer_info_ini = StringIO()
            info_.write(buffer_info_ini)
            info_ini_content = buffer_info_ini.getvalue()
            buffer_info_ini.close()

        buffer_resource_zip = BytesIO()
        with zipfile.ZipFile(buffer_resource_zip, 'w', compression=zipfile.ZIP_DEFLATED,
                             allowZip64=True) as resource_zip_file:
            for item_path_abs in utils.get_all_file_paths(plugin_dir_path):
                if os.path.basename(item_path_abs) in ['info.json', 'icon']:
                    continue

                arcname = os.path.relpath(item_path_abs, plugin_dir_path)
                print(f"Adding:{arcname}")
                try:
                    resource_zip_file.write(str(item_path_abs), arcname=arcname)
                except Exception as e:
                    logging.exception(f'Error writing {item_path_abs} to resource zip')
                    print("写入 {} 时出现错误 ：{}".format(item_path_abs, e))

        resource_zip_content = buffer_resource_zip.getvalue()
        buffer_resource_zip.close()
        output_mpk_path = os.path.join(cfg.workingFolder.value, f"{name}.mpk")
        with zipfile.ZipFile(output_mpk_path, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk_final_file:
            mpk_final_file.writestr(data['resource'], resource_zip_content)
            mpk_final_file.writestr('info', info_ini_content)

            icon_path = os.path.join(plugin_dir_path, 'icon')
            if os.path.exists(icon_path):
                mpk_final_file.write(icon_path, 'icon')

        if os.path.exists(output_mpk_path):
            print(output_mpk_path, "Done")
        else:
            print(output_mpk_path, "Fail")
        return None


module_manager = ModuleManager()

import zipfile
import platform
from io import BytesIO
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QSizePolicy
from qfluentwidgets import (ProgressBar, ImageLabel)

import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (MessageBoxBase, SubtitleLabel, CaptionLabel, TextBrowser,
                            PushButton)


class UninstallMpk(MessageBoxBase):
    def __init__(self, id_: str, wait=False, parent=None):
        # We inherit MessageBoxBase which provides a beautifully engineered frameless window wrapper
        super().__init__(parent)

        self.arr = {}
        self.uninstall_b = None
        self.wait = wait

        self.value = id_
        self.value2 = None
        self.check_pass = False

        self.module_dir = module_manager.module_dir
        # Execute your core backend validation checks
        if id_ and module_manager.is_installed(id_):
            self.check_pass = True
            self.value2 = module_manager.get_name(id_)
            self.lsdep()
        elif id_:
            self.value2 = id_
            logging.warning(f"UninstallMpk init: Plugin with ID '{id_}' not found by module_manager.get_installed.")

        # Dynamically build up components and text formats
        self.ask()

        # MessageBoxBase handles modal blocking natively with .exec() instead of wait_window()
        # If wait parameter is required downstream, trigger it inside the initialization
        if self.wait:
            self.exec()

    def ask(self):
        # Apply window title
        self.widget.setMinimumWidth(440)

        # Delete default box buttons so we can insert custom full-width controls
        self.buttonLayout.deleteLater()

        # Build dynamic content warning strings
        plugin_display_name_for_message = self.value2 if self.value2 else self.value
        if plugin_display_name_for_message is None:
            plugin_display_name_for_message = getattr(lang, "unknown_plugin_name", "Unknown Plugin")

        if not self.value:
            message_text = "Please select a plugin!"
        elif not self.check_pass:
            msg_template = "Plugin '{plugin_id}' not found or cannot be uninstalled."
            message_text = msg_template.format(plugin_id=plugin_display_name_for_message)
        elif module_manager.is_virtual(self.value):
            msg_template = "Plugin '{plugin_name}' is virtual and cannot be uninstalled this way."
            message_text = msg_template.format(plugin_name=plugin_display_name_for_message)
        else:
            msg_template = "Are you sure you want to uninstall plugin '%s'?"
            name_to_format = str(plugin_display_name_for_message)
            try:
                if "%s" in msg_template or "%S" in msg_template:
                    message_text = msg_template % (name_to_format,)
                elif "{0}" in msg_template:
                    message_text = msg_template.format(name_to_format)
                elif "{plugin_name}" in msg_template or "{name}" in msg_template:
                    message_text = msg_template.format(plugin_name=name_to_format, name=name_to_format)
                else:
                    message_text = msg_template + f" ({name_to_format})"
            except Exception as e_format:
                logging.error(
                    f"Error formatting message for t7: {e_format}. Template: '{msg_template}', Value: '{name_to_format}'")
                message_text = msg_template

        # Primary warning header (Replaces Tkinter Label with auto-wrapping Fluent label)
        self.msgLabel = SubtitleLabel(message_text, self)
        self.msgLabel.setAlignment(Qt.AlignCenter)
        self.msgLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.msgLabel)

        # Dependencies sub-interface (Only visible if secondary broken dependencies exist)
        if self.arr:
            self.depHeader = CaptionLabel("The following dependent plugins will also be removed:",
                                          self)
            self.depHeader.setTextColor(QColor("#ffffff"), QColor("#ffffff"))
            self.viewLayout.addWidget(self.depHeader)

            # Elegant, borderless scrolling viewport inside Fluent ecosystem
            self.dependent_text_widget = TextBrowser(self)
            self.dependent_text_widget.setReadOnly(True)
            self.dependent_text_widget.setMaximumHeight(120)

            # Format and inject text lines
            dep_content = ""
            for dep_id, dep_name in self.arr.items():
                dep_content += f"• {dep_name} ({dep_id})\n"
            self.dependent_text_widget.setText(dep_content.strip())
            self.viewLayout.addWidget(self.dependent_text_widget)

        # Lower control bar setup
        self.bottomLayout = QHBoxLayout()
        self.bottomLayout.setContentsMargins(0, 10, 0, 0)
        self.bottomLayout.setSpacing(12)

        # Standard button actions
        self.cancel_b = self.cancelButton
        self.cancel_b.clicked.connect(self.reject)

        # Conditional binding for validation check-passes
        if self.check_pass and self.value and not module_manager.is_virtual(self.value):
            self.uninstall_b = self.yesButton
            self.uninstall_b.setText("Uninstall")
            self.uninstall_b.clicked.connect(self.uninstall)

        self.viewLayout.addLayout(self.bottomLayout)

    def lsdep(self, name_to_check_deps_for=None):
        """Recursive check module dependencies"""
        if not name_to_check_deps_for:
            name_to_check_deps_for = self.value

        if not name_to_check_deps_for:
            return

        for installed_plugin_id in module_manager.list_packages():
            if installed_plugin_id == name_to_check_deps_for:
                continue
            if installed_plugin_id in self.arr:
                continue

            dependencies_str: str = module_manager.get_info(installed_plugin_id, 'depend', '')
            dependencies_list = dependencies_str.split()

            if name_to_check_deps_for in dependencies_list:
                dependent_plugin_name = module_manager.get_name(installed_plugin_id)
                self.arr[installed_plugin_id] = dependent_plugin_name
                self.lsdep(installed_plugin_id)

    def uninstall(self):
        if not self.uninstall_b:
            self.reject()
            return

        self.uninstall_b.setEnabled(False)
        # Replaces self.update_idletasks() to safely flush structural event frames instantly
        QApplication.processEvents()

        plugin_id_to_remove = self.value
        plugin_show_name_to_remove = self.value2 if self.value2 else self.value

        dependent_ids = list(self.arr.keys())
        for dep_id in dependent_ids:
            dep_name = self.arr.get(dep_id, dep_id)
            self.remove(dep_id, dep_name)

        self.remove(plugin_id_to_remove, plugin_show_name_to_remove)
        self.accept()

    def remove(self, name=None, show_name=''):
        logging.debug(f"UninstallMpk.remove called for: {name} (shown as: {show_name})")

        # 1. Parameter Validation Check
        if not name:
            logging.warning("UninstallMpk.remove: 'name' (plugin ID) is None or empty.")
            return

        module_path = os.path.join(self.module_dir, str(name))
        plugin_successfully_removed_fs = False

        # 2. Update Button Text Dynamically (Uninstallation in progress)
        if self.uninstall_b:
            self.uninstall_b.setText("正在卸载：{}".format(show_name or name))
            # Replaces self.update_idletasks() to instantly force visual updates to screen
            QApplication.processEvents()

        print("正在卸载：{}".format(show_name if show_name else name))

        # 3. File System Removal Process
        if os.path.exists(module_path):
            try:
                rmtree(module_path)
                if not os.path.exists(module_path):
                    plugin_successfully_removed_fs = True
                    logging.info(f"Successfully removed directory: {module_path}")
                else:
                    logging.warning(
                        f"Directory {module_path} reported as existing after rmtree call for plugin '{name}', though no exception was raised.")
                    if not os.path.exists(module_path):
                        plugin_successfully_removed_fs = True
                        logging.info(f"Re-check confirms directory {module_path} is actually gone.")

            except PermissionError as e_perm:
                logging.exception(f"PermissionError removing '{module_path}' for plugin '{name}': {e_perm}")

            except Exception as e_generic:
                logging.exception(f"Generic error removing '{module_path}' for plugin '{name}': {e_generic}")

        else:
            plugin_successfully_removed_fs = True
            logging.info(
                f"Module path '{module_path}' did not exist for plugin '{name}'. Assumed removed or not present on filesystem.")

        # 4. Handle Post-Removal Interface Synchronization Updates
        if not plugin_successfully_removed_fs and os.path.exists(module_path):

            logging.warning(f"Directory '{module_path}' still exists after removal attempt for plugin '{name}'.")

        elif plugin_successfully_removed_fs:
            if self.uninstall_b:
                self.uninstall_b.setText("卸载完成！".format(show_name if show_name else name))
                QApplication.processEvents()

            print("卸载完成！".format(show_name if show_name else name))
            logging.info(f"Plugin '{name}' (DisplayName: '{show_name}') considered removed from filesystem.")

        logging.debug(f"UninstallMpk.remove completed for: {name}")


class InstallMpk(MessageBoxBase):
    """基于 PySide6 + Fluent-Widgets 的 MPK 插件安装器窗口"""

    def __init__(self, mpk_path: str = None, parent=None):
        super().__init__(parent)
        self.parent = parent
        # 1. 迁移原始状态变量与配置解析器
        # (假设 lang, module_manager, module_error_codes, images 等全局对象已在外部 import)
        self.mconf = ConfigParser()
        self.installable = True
        self.mpk = mpk_path

        # 2. 初始化 Fluent 核心界面样式（无 QSS）
        self.widget.setMinimumWidth(540)
        self.widget.setMinimumHeight(420)
        self.buttonLayout.deleteLater()  # 废弃默认按钮组，改用下方通栏布局

        # 3. 构建左右分栏布局
        self.centerLayout = QHBoxLayout()
        self.centerLayout.setContentsMargins(10, 15, 10, 15)
        self.centerLayout.setSpacing(24)

        # 左侧面板 (元数据)
        self.leftPanel = QVBoxLayout()
        self.leftPanel.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.leftPanel.setSpacing(12)

        self.logo = ImageLabel(self)
        self.logo.setFixedSize(128, 128)  # 契合您原代码的 128x128 尺寸

        # 初始化占位文本（防止 load 失败前读出空值引发视觉报错）
        self.name_label = SubtitleLabel("", self)
        self.version = CaptionLabel("", self)
        self.author = CaptionLabel("", self)

        self.version.setTextColor(QColor("#b0b0b0"), QColor("#b0b0b0"))
        self.author.setTextColor(QColor("#b0b0b0"), QColor("#b0b0b0"))

        self.leftPanel.addWidget(self.logo)
        self.leftPanel.addWidget(self.name_label)
        self.leftPanel.addWidget(self.version)
        self.leftPanel.addWidget(self.author)

        # 右侧面板 (详细介绍文本框)
        self.text = TextBrowser(self)
        self.text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.centerLayout.addLayout(self.leftPanel, stretch=2)
        self.centerLayout.addWidget(self.text, stretch=5)

        # 4. 底部控制布局 (进度条 + 状态标签 + 通栏按钮)
        self.bottomLayout = QVBoxLayout()
        self.bottomLayout.setContentsMargins(10, 0, 10, 10)
        self.bottomLayout.setSpacing(12)

        self.prog = ProgressBar(self)
        self.prog.setFixedHeight(4)
        # 对应 tkinter 初始态：mode='indeterminate'，这里通过设置 0-0 开启无限滑动跑马灯
        self.prog.setRange(0, 0)
        self.prog.hide()  # 初始未点击安装时先隐藏隐藏

        self.state = SubtitleLabel("准备就绪", self)
        self.state.setAlignment(Qt.AlignCenter)

        self.installb = self.yesButton
        self.cancelButton.hide()
        self.installb.setText("安装")
        self.installb.setFixedHeight(36)
        self.installb.clicked.connect(self.install)

        self.bottomLayout.addWidget(self.prog)
        self.bottomLayout.addWidget(self.state)
        self.viewLayout.addLayout(self.centerLayout, stretch=1)
        self.viewLayout.addLayout(self.bottomLayout)
        self.load()
        self.finished.connect(self.parent.load_plugin_cards)

    def install(self):
        """核心安装逻辑与状态码转换"""
        # 逻辑 1：如果按钮字样变成了“完成/关闭”，则点击直接退出销毁
        if self.installb.text() == "完成":
            self.accept()  # 对应原代码：self.destroy()
            return 0

        # 逻辑 2：启动无确定时长的跑马灯进度动画
        self.prog.show()
        self.installb.setEnabled(False)  # 对应原代码：state=DISABLED

        # 逻辑 3：调用您的后端管理器执行具体业务
        ret, reason = module_manager.install(self.mpk)

        # 逻辑 4：原汁原味的状态码映射分支
        if ret == module_error_codes.ArchNotSupported:
            self.state.setText(reason)
        elif ret == module_error_codes.PlatformNotSupport:
            self.state.setText("不支持的系统 {}".format(platform.system()))
        elif ret == module_error_codes.DependsMissing:
            self.state.setText("%s 依赖于 %s，但 %s 没有安装" % (self.mconf.get('module', 'name'), reason, reason))
            self.installb.setText("重试")
            self.installb.setEnabled(True)
        elif ret == module_error_codes.IsBroken:
            self.state.setText("请选择一个插件")
            self.installb.setText("重试")
            self.installb.setEnabled(True)
        elif ret == module_error_codes.Normal:
            self.state.setText("安装完毕")
            self.installb.setText("完成")
            self.installb.setEnabled(True)

        # 逻辑 5：安装动作完结，将进度条强行修正为 100% 满格静态长条
        self.prog.setRange(0, 100)
        self.prog.setValue(100)
        return 0

    def load(self):
        """解析 MPK 压缩文件，在内存中提炼出数据与图标"""
        if not self.mpk or not zipfile.is_zipfile(self.mpk):
            self.unavailable()
            return

        try:
            with zipfile.ZipFile(self.mpk, 'r') as myfile:
                if 'info' not in myfile.namelist():
                    self.unavailable()
                    return
                # 读取说明配置
                with myfile.open('info') as info_file:
                    self.mconf.read_string(info_file.read().decode('utf-8'))

                # 读取并处理二进制图片
                try:
                    with myfile.open('icon') as myfi:
                        self.icon_bytes = myfi.read()
                        pixmap = QPixmap()
                        # 利用 loadFromData 避开外部临时磁盘转存，实现内存高效加载
                        if pixmap.loadFromData(self.icon_bytes):
                            self.pyt = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        else:
                            raise Exception("QPixmap parse fail")
                except (Exception, KeyError):
                    logging.exception('Bugs')
                    self.pyt = QPixmap()
                    self.pyt.loadFromData(images.none_byte)
        except (Exception, BaseException):
            logging.exception('Bugs')
            self.pyt = QPixmap()
            self.pyt.loadFromData(images.none_byte)

        # 更新 Fluent UI 组件展示
        self.name_label.setText(self.mconf.get('module', 'name'))
        self.logo.setPixmap(self.pyt)
        self.author.setText("作者：{}".format(self.mconf.get('module', 'author')))
        self.version.setText("版本：{}".format(self.mconf.get('module', 'version')))
        self.text.setText(self.mconf.get('module', 'describe'))

    def unavailable(self):
        """异常和包损坏时的界面安全降级逻辑"""
        self.pyt = QPixmap()
        self.pyt.loadFromData(images.error_logo_byte)

        self.name_label.setText("请选择一个插件")
        self.name_label.setTextColor(QColor("#ffcc00"), QColor("#ffcc00"))
        self.logo.setPixmap(self.pyt)

        self.author.hide()
        self.version.hide()
        self.prog.hide()
        self.installb.setEnabled(False)


class AppCard(CardWidget):

    def __init__(self, icon, title: str, content: str, parent=None):
        super().__init__(parent)
        self.iconWidget = IconWidget(icon)
        self.titleLabel = BodyLabel(title, self)
        self.contentLabel = CaptionLabel(content, self)
        self.openButton = PushButton('Run', self)
        self.moreButton = TransparentDropDownToolButton(FluentIcon.MORE)

        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()

        self.setFixedHeight(73)
        self.iconWidget.setFixedSize(48, 48)
        self.contentLabel.setTextColor("#606060", "#d2d2d2")
        self.openButton.setFixedWidth(120)

        self.hBoxLayout.setContentsMargins(20, 11, 11, 11)
        self.hBoxLayout.setSpacing(15)
        self.hBoxLayout.addWidget(self.iconWidget)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignVCenter)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignVCenter)
        self.vBoxLayout.setAlignment(Qt.AlignVCenter)
        self.hBoxLayout.addLayout(self.vBoxLayout)

        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.openButton, 0, Qt.AlignRight)
        self.hBoxLayout.addWidget(self.moreButton, 0, Qt.AlignRight)


class BuiltInPlugins:
    def __init__(self, master):
        self.master = master
        self.plugins = {
            "download_rom": {"name": "Download ROM", "entry": lambda: print(1)},
            "get_file_info": {"name": "Get File Info", "entry": lambda: FileInfoMessageBox(self.master).exec()},
            "byte_calculator": {"name": "Byte Calculator", "entry": lambda: FileBytesMessageBox(self.master).exec()},
            "allow_selinux_audit": {"name": "Allow Selinux Audit", "entry": lambda: self.allow_selinux_audit()},
            "dis_avb_in_fstab": {"name": "Disable avb in fstab", "entry": lambda: self.disable_avb()},
            "dis_encryption": {"name": "Disable Encryption", "entry": lambda: self.dis_encryption()},
            "trim_raw_image": {"name": "Trim Raw Image", "entry": lambda: self.trim_raw_image()},
            "magisk_patch": {"name": "Magisk Patch", "entry": lambda: None},
            "merge_qualcomm_image": {"name": "Merge Qualcomm Image", "entry": lambda: self.merge_qcom_images()},
            "merge_super": {"name": "Merge Super", "entry": lambda: None},
            "decrypt_xtc_xml": {"name": "Decrypt xtc xml", "entry": lambda: self.decrypt_xtc_xml()},
            "mtk_port_tool": {"name": "Mtk Port Tool", "entry": lambda: None},
        }

    def exec_plugin(self, plugin_id: str):
        if plugin_id not in self.plugins.keys():
            print(f"No such plugin: {plugin_id}")
            return
        entry = self.plugins[plugin_id]["entry"]
        if not callable(entry):
            print(f"{plugin_id} is not callable!")
            return
        entry()

    def merge_qcom_images(self):
        dialog = MergeQualcommImageMessageBox(self.master)
        if dialog.exec():
            result = dialog.get_form_data()
            xml_path = result['xml_path']
            partition = result['partition']
            output_path = result['output_path']
            if not os.path.exists(output_path): os.makedirs(output_path, exist_ok=True)
            try:
                process_by_xml(xml_path, partition, output_path)
                # I inform the user of success.
                InfoBar.success("Merged", 'Image merging completed successfully!', parent=self.master)
            except Exception as e:
                # I log the error and inform the user of failure.
                print(f'Merge failed: {e}')
                logging.exception('MergeQC RAWPROGRAM error')
                InfoBar.warning("Warning", f'Image merging failed: {str(e)}',
                                parent=self.master)  # Displaying the error message to the user.
            # No explicit return None needed here as the function naturally returns None if no other return is hit.

    def dis_encryption(self):
        dialog = DisableEncryptionMessageBox(self.master)
        if dialog.exec():
            fstab_files = dialog.partitions_with_fstab
            selected_parts = dialog.get_selected_partitions()
            for name in selected_parts:
                if name in fstab_files:
                    for fstab_path in fstab_files[name]:
                        process_fstab_for_encryption(fstab_path)
                        InfoBar.success("Disabled encryption", f"Patched fstab at {name}", parent=self.master)

    def disable_avb(self):
        dialog = DisableAvbMessageBox(self.master)
        if dialog.exec():
            fstab_files = dialog.partitions_with_fstab
            selected_parts = dialog.get_selected_partitions()
            for name in selected_parts:
                if name in fstab_files:
                    for fstab_path in fstab_files[name]:
                        process_fstab(fstab_path)
                        InfoBar.success("Disabled Avb", f"Patched fstab at {name}", parent=self.master)

    def allow_selinux_audit(self):
        dialog = AllowSELinuxAuditMessageBox(self.master)
        if dialog.exec():
            input_log = dialog.log_path_edit.text()
            output_dir = dialog.output_path_edit.text()
            if not os.path.exists(input_log) or not os.path.exists(output_dir):
                return
            selinux_audit_allow(input_log, output_dir)
            InfoBar.info(
                title="Processing File",
                content=f"Allowed {input_log}",
                orient=Qt.Horizontal,
                isClosable=False,
                duration=3000,  # Kept active indefinitely
                position=InfoBarPosition.TOP,
                parent=self.master
            )

    def decrypt_xtc_xml(self):
        dialog = DecryptXtcXmlMessageBox(self.master)
        if dialog.exec():
            path = dialog.file_path_edit.text()
            if not os.path.exists(path) or not path.strip():
                InfoBar.warning('Please choose a path.', self.master)
                return
            for root, _, files in os.walk(path, topdown=True):
                for f in files:
                    if f.endswith('.xml'):
                        InfoBar.info(
                            title="Processing File",
                            content=f"Decrypting {f}",
                            orient=Qt.Horizontal,
                            isClosable=False,
                            duration=3000,  # Kept active indefinitely
                            position=InfoBarPosition.TOP,
                            parent=self.master
                        )
                        decrypt_xtc(os.path.join(root, f))

    def trim_raw_image(self):
        dialog = TrimRawImageMessageBox(self.master)
        if dialog.exec():
            file_path = dialog.file_path_edit.text()
            if not os.path.exists(file_path):
                return

            def do_trim(buff_size: int = 8192, file_path: str | None = None):
                if not file_path:
                    return
                orig_size = file_size = os.path.getsize(file_path)
                zeros_ = bytearray(buff_size)
                progress_bar = InfoBar.info(
                    title="Processing File",
                    content="Running - 0%",
                    orient=Qt.Horizontal,
                    isClosable=False,
                    duration=-1,  # Kept active indefinitely
                    position=InfoBarPosition.TOP,
                    parent=self.master
                )
                with open(file_path, 'rb') as f:
                    update_ui = 3000
                    while file_size:
                        n = min(file_size, buff_size)
                        file_size_ = file_size - n
                        f.seek(file_size_)
                        buf = f.read(n)
                        assert len(buf) == n
                        if n != len(zeros_):
                            zeros_ = bytearray(n)
                        if buf != zeros_:
                            for i, b in enumerate(reversed(buf)):
                                if b != 0: break
                            file_size -= i
                            break
                        file_size = file_size_

                        update_ui -= 1
                        if update_ui == 0:
                            update_ui = 3000
                            percentage = 100 - file_size * 100 // orig_size
                            progress_bar.contentLabel.setText(f"Running - {percentage}%")
                os.truncate(file_path, file_size)
                c = orig_size - file_size
                progress_bar.close()
                InfoBar.success(
                    title="Success",
                    content="总共从文件末尾截去了 %d 个零字节（约 %s）" % (c, utils.hum_convert(c)),
                    position=InfoBarPosition.TOP,
                    duration=4000,
                    parent=self.master
                )

            do_trim(file_path=file_path)


class PluginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PluginPage")
        self.built_in_plugins = BuiltInPlugins(self)
        self.cards_data = []  # Track card mappings for easy filtering
        self.initUI()
        self.setStyleSheet("""
                   QWidget#ScrollContent {
                       background-color: #202020;
                   }
                  
               """)
        module_manager.master = self

    def uninstall_plugin(self, plugin_id: str):
        UninstallMpk(plugin_id, True, self)
        self.load_plugin_cards()

    def install_mpk(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "MPK Files (*.mpk)"
        )
        if file_path:
            dialog = InstallMpk(file_path, self)
            if dialog.exec_():
                return

    def initUI(self):
        # 1. Main outer layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(40, 40, 40, 40)
        outer_layout.setSpacing(20)
        # 2. Header Layout (Title and Description)
        header_layout = QHBoxLayout()
        text_header_layout = QVBoxLayout()
        text_header_layout.setSpacing(4)

        title = TitleLabel("插件")
        description = CaptionLabel("单击右键以显示菜单，或在此启动您的功能模块", self)

        text_header_layout.addWidget(title)
        text_header_layout.addWidget(description)
        header_layout.addLayout(text_header_layout)
        header_layout.addStretch()
        self.local_install_btn = PushButton(FluentIcon.ADD, "本地安装", self)
        self.local_install_btn.clicked.connect(self.install_mpk)
        header_layout.addWidget(self.local_install_btn)

        # New Feature: Cloud Download Module Control Trigger
        self.download_btn = PushButton(FluentIcon.DOWNLOAD, "网络下载", self)
        header_layout.addWidget(self.download_btn)
        outer_layout.addLayout(header_layout)

        # 3. Search Bar Integration
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("搜索已安装的插件...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self.filter_plugins)
        outer_layout.addWidget(self.search_bar)

        # 4. Scrollable Container for Cards
        # Using QFluentWidgets' ScrollArea for seamless native scrolling look
        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(ScrollArea.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Inner canvas widget holding the vertical stacked cards
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")
        self.cards_layout = QVBoxLayout(self.scroll_content)
        self.cards_layout.setContentsMargins(0, 5, 0, 0)
        self.cards_layout.setSpacing(5)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 5. Populate Plugin Cards dynamically
        self.load_plugin_cards()

        self.scroll_area.setWidget(self.scroll_content)
        outer_layout.addWidget(self.scroll_area)

    def load_plugin_cards(self):
        # Clear out existing layout elements if re-loading
        for data in self.cards_data:
            data['card_widget'].hide()
            self.cards_layout.removeWidget(data['card_widget'])
            data['card_widget'].destroy()
        self.cards_layout.update()
        self.cards_data.clear()
        for plugin_id in self.built_in_plugins.plugins.keys():
            plugin_icon = FluentIcon.APPLICATION
            plugin_info = self.built_in_plugins.plugins[plugin_id]
            plugin_title = plugin_info.get("name", plugin_info.get("id", "Unknown"))
            card = AppCard(
                icon=plugin_icon,
                title=plugin_title,
                content='Built-In Plugin'
            )
            card.moreButton.clicked.connect(lambda: print("None"))
            # Setup execution bindings (Safe against the signal boolean emission)
            card.openButton.clicked.connect(
                lambda state, plugin_id=plugin_id: self.built_in_plugins.exec_plugin(plugin_id))
            card.clicked.connect(lambda plugin_id=plugin_id: self.built_in_plugins.exec_plugin(plugin_id))

            self.cards_layout.addWidget(card)

            # Store structural references for fast runtime filtering queries
            self.cards_data.append({
                "card_widget": card,
                "title": plugin_title.lower(),
                "author": "Mio-Kitchen"
            })

        for i in module_manager.list_packages():
            plugin = module_manager.get_info(i)
            plugin_icon = os.path.join(module_manager.module_dir, i, 'icon')
            if not os.path.exists(plugin_icon):
                plugin_icon = FluentIcon.APPLICATION

            plugin_title = plugin.get("name", i)
            plugin_author = plugin.get("author", "未知作者")

            card = AppCard(
                icon=plugin_icon,
                title=plugin_title,
                content=plugin_author
            )
            menu = RoundMenu(parent=card.moreButton)
            menu.addAction(Action(FluentIcon.CLOSE, 'Uninstall',
                                  triggered=lambda state, plugin_id=i: self.uninstall_plugin(plugin_id)))
            menu.addAction(Action(FluentIcon.ZOOM_OUT, 'Export',
                                  triggered=lambda state, plugin_id=i: module_manager.export(plugin_id)))
            menu.addAction(Action(FluentIcon.EDIT, 'Edit', triggered=lambda: print("Saved")))

            # Add menu
            card.moreButton.setMenu(menu)
            # Setup execution bindings (Safe against the signal boolean emission)
            card.openButton.clicked.connect(lambda state, plugin_id=i: self.exec_plugin(plugin_id))
            card.clicked.connect(lambda plugin_id=i: self.exec_plugin(plugin_id))

            self.cards_layout.addWidget(card)

            # Store structural references for fast runtime filtering queries
            self.cards_data.append({
                "card_widget": card,
                "title": plugin_title.lower(),
                "author": plugin_author.lower()
            })

    def filter_plugins(self, text):
        """
        Dynamically filters plugin rows based on title or author lookups
        """
        query = text.strip().lower()
        for data in self.cards_data:
            if query in data["title"] or query in data["author"]:
                data["card_widget"].show()
            else:
                data["card_widget"].hide()

    def exec_plugin(self, plugin_id):
        module_manager.run(plugin_id)
