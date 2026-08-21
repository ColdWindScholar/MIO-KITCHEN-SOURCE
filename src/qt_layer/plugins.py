import json
import logging
import os
import platform
import tkinter
import zipfile
from shutil import rmtree
from tkinter import Toplevel, ttk, HORIZONTAL, BOTH, TOP, X, Frame, RIGHT, LEFT
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import IconWidget, CardWidget, BodyLabel, CaptionLabel, PushButton, TransparentToolButton, \
    FluentIcon

import images
from addon_register import loader, Entry
from config_parser import ConfigParser
from qt_layer.settings import cfg
from src.core import imp
from utils import create_thread, ModuleErrorCodes, prog_path, call, temp, re_folder, JsonEdit, lang, move_center
from src.qt_layer.widgets import show_info_bar
module_exec = os.path.join(prog_path, 'bin', "exec.sh").replace(os.sep, '/')
import _tkinter as tk
module_error_codes = ModuleErrorCodes
class New(Toplevel):

    def __init__(self, create_gui_on_init=True):
        super().__init__()
        self.title(lang.text115)
        if not hasattr(self, 'module_dir'):
            self.module_dir = os.path.join(prog_path, "bin", "module")

        if create_gui_on_init:
            self.gui()
            move_center(self)

    @staticmethod
    def label_entry(master, text, side, value: str = ''):
        frame = Frame(master)
        ttk.Label(frame, text=text).pack(padx=5, pady=5, side=LEFT)
        entry_value = tkinter.StringVar(value=value)
        entry = ttk.Entry(frame, textvariable=entry_value)
        entry.pack(padx=5, pady=5, side=RIGHT)
        frame.pack(padx=5, pady=5, fill=X, side=side)
        return entry_value

    def editor_(self, id_=None):
        if not id_:
            win.message_pop(lang.warn2)
            return False
        if module_manager.is_virtual(id_):
            print(f"{id_} is a virtual plugin.")
            return False
        path = os.path.join(self.module_dir, id_)
        if os.path.exists(f"{path}/main.py"):
            return editor.main(path, 'main.py', lexer=pygments.lexers.Python3Lexer)
        elif not os.path.exists(f'{path}/main.sh'):
            with open(f'{path}/main.sh', 'w+', encoding='utf-8', newline='\n') as sh:
                sh.write("echo 'MIO-KITCHEN'")
        return editor.main(path, "main.sh")

    def gui(self):
        ttk.Label(self, text=lang.t19, font=(None, 25)).pack(fill=BOTH, expand=0, padx=10, pady=10)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        f_b = ttk.Frame(self)
        f = ttk.Frame(f_b)
        self.name = self.label_entry(f, lang.t20, TOP, "example")
        self.aou = self.label_entry(f, lang.t21, TOP, "MIO-KITCHEN")
        self.ver = self.label_entry(f, lang.t22, TOP, "1.0")
        self.dep = self.label_entry(f, lang.t23, TOP, '')
        self.identifier = self.label_entry(f, lang.identifier, TOP, 'example.mio_kitchen.plugin')
        #
        self.system = self.label_entry(f, lang.supported_system, TOP, platform.system())
        self.arch = self.label_entry(f, lang.supported_arch, TOP, platform.machine())
        ###
        f.pack(padx=5, pady=5, side=LEFT)
        f = ttk.Frame(f_b)
        ttk.Label(f, text=lang.t24).pack(padx=5, pady=5, expand=1)
        self.intro = tkinter.Text(f, width=40, height=15)
        self.intro.pack(fill=BOTH, padx=5, pady=5, side=RIGHT)
        f.pack(padx=5, pady=5, side=LEFT)
        f_b.pack(padx=5, pady=5)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Button(self, text=lang.text115, command=self.create, style='Accent.TButton').pack(fill=X, padx=5,
                                                                                              pady=5)

    def create(self):
        if not self.identifier.get():
            return
        if module_manager.is_installed(self.identifier.get()):
            info_win(lang.warn19 % self.identifier.get())
            return
        data = {
            "name": self.name.get(),
            "author": self.aou.get() or 'MIO-KITCHEN',
            "version": self.ver.get(),
            "identifier": (iden := self.identifier.get()),
            "describe": self.intro.get(1.0, tk.END),
            "depend": self.dep.get(),
            "system": self.system.get(),
            "arch": self.arch.get()
        }
        self.destroy()

        os.makedirs(f'{self.module_dir}/{iden}', exist_ok=True)
        with open(f"{self.module_dir}/{iden}/info.json", 'w+', encoding='utf-8',
                  newline='\n') as js:
            json.dump(data, js, ensure_ascii=False, indent=4)
        if callable(list_pls_plugin):
            list_pls_plugin()
        self.editor_(iden)
class UninstallMpk(Toplevel):
    def __init__(self, id_: str, wait=False):
        super().__init__()
        self.arr = {}
        self.uninstall_b = None
        self.wait = wait

        self.value = id_
        self.value2 = None
        self.check_pass = False

        self.module_dir = module_manager.module_dir

        if id_ and module_manager.is_installed(id_):
            self.check_pass = True
            self.value2 = module_manager.get_name(id_)
            self.lsdep()
        elif id_:
            self.value2 = id_
            logging.warning(f"UninstallMpk init: Plugin with ID '{id_}' not found by module_manager.get_installed.")

        self.ask()

    def ask(self):
        try:
            if self.winfo_exists():
                self.attributes('-topmost', 'true')
        except tk.TclError:
            logging.exception('Uninstall Mpk')

        self.title(lang.t6)

        content_frame = ttk.Frame(self)
        content_frame.pack(padx=15, pady=15, fill=BOTH, expand=True)

        plugin_display_name_for_message = self.value2 or self.value
        if not self.value:
            message_text = getattr(lang, "warn2", "Please select a plugin!")
        elif not self.check_pass:
            msg_template = getattr(lang, "plugin_not_found_for_uninstall",
                                   "Plugin '{plugin_id}' not found or cannot be uninstalled.")
            message_text = msg_template.format(plugin_id=plugin_display_name_for_message)
        elif module_manager.is_virtual(self.value):
            msg_template = getattr(lang, "plugin_virtual_cannot_uninstall",
                                   "Plugin '{plugin_name}' is virtual and cannot be uninstalled this way.")
            message_text = msg_template.format(plugin_name=plugin_display_name_for_message)
        else:
            msg_template = getattr(lang, "t7", "Are you sure you want to uninstall plugin '%s'?")
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

        ttk.Label(content_frame, text=message_text, font=(None, 14), wraplength=380, justify=CENTER).pack(
            pady=(5, 15), fill=X)

        if self.arr:
            ttk.Separator(content_frame, orient=HORIZONTAL).pack(fill=X, pady=5)
            ttk.Label(content_frame,
                      text=getattr(lang, "t8", "The following dependent plugins will also be removed:"),
                      font=(None, 12, 'bold')).pack(pady=(5, 2), anchor='nw', fill=X)

            dependent_text_frame = ttk.Frame(content_frame, relief="groove", borderwidth=1)
            dependent_text_frame.pack(fill=BOTH, expand=True, pady=5)

            dependent_text_widget = Text(dependent_text_frame, height=min(5, len(self.arr) + 1), width=45,
                                         wrap=tk.WORD, relief="flat", borderwidth=0, takefocus=0,
                                         font=(None, 10), padx=5, pady=5)

            scrollbar_y_deps = ttk.Scrollbar(dependent_text_frame, orient="vertical",
                                             command=dependent_text_widget.yview)
            scrollbar_y_deps.pack(side="right", fill="y")
            dependent_text_widget.pack(side="left", fill=BOTH, expand=True)
            dependent_text_widget.config(yscrollcommand=scrollbar_y_deps.set)

            for dep_id, dep_name in self.arr.items():
                dependent_text_widget.insert(tk.END, f"• {dep_name} ({dep_id})\n")
            dependent_text_widget.config(state=DISABLED)

        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=X, pady=(15, 0), side=BOTTOM)

        ttk.Button(button_frame, text=getattr(lang, "cancel", "Cancel"), command=self.destroy).pack(fill=X,
                                                                                                    expand=True,
                                                                                                    side=LEFT,
                                                                                                    padx=(0, 5))

        if self.check_pass and self.value and not module_manager.is_virtual(self.value):
            self.uninstall_b = ttk.Button(button_frame, text=getattr(lang, "ok", "OK"), command=self.uninstall,
                                          style="Accent.TButton")
            self.uninstall_b.pack(fill=X, expand=True, side=LEFT, padx=(5, 0))


        if self.wait and self.winfo_exists():
            try:
                self.wait_window()
            except tk.TclError:
                logging.exception("UninstallMpk.ask")

    def lsdep(self, name_to_check_deps_for=None):
        if not name_to_check_deps_for:
            name_to_check_deps_for = self.value

        if not name_to_check_deps_for: return

        for installed_plugin_id in module_manager.list_packages():
            if installed_plugin_id == name_to_check_deps_for: continue
            if installed_plugin_id in self.arr: continue

            dependencies_str: str = module_manager.get_info(installed_plugin_id, 'depend', '')
            dependencies_list = dependencies_str.split()

            if name_to_check_deps_for in dependencies_list:
                dependent_plugin_name = module_manager.get_name(installed_plugin_id)
                self.arr[installed_plugin_id] = dependent_plugin_name
                self.lsdep(installed_plugin_id)

    def uninstall(self):
        if not (self.uninstall_b and self.uninstall_b.winfo_exists()):
            if self.winfo_exists(): self.destroy()
            return

        self.uninstall_b.config(state='disabled')
        if self.winfo_exists(): self.update_idletasks()

        plugin_id_to_remove = self.value
        plugin_show_name_to_remove = self.value2 if self.value2 else self.value

        dependent_ids = list(self.arr.keys())
        for dep_id in dependent_ids:
            dep_name = self.arr.get(dep_id, dep_id)
            self.remove(dep_id, dep_name)

        self.remove(plugin_id_to_remove, plugin_show_name_to_remove)

        if self.winfo_exists():
            self.destroy()

    def remove(self, name=None, show_name=''):
        logging.debug(f"UninstallMpk.remove called for: {name} (shown as: {show_name})")
        if not name:
            logging.warning("UninstallMpk.remove: 'name' (plugin ID) is None or empty.")
            win.message_pop(
                getattr(lang, "internal_error_plugin_id_missing",
                        "Internal error: Plugin ID missing for removal."),
                title=getattr(lang, "error_title", "Error"), color="red"
            )
            return

        module_path = os.path.join(self.module_dir, str(name))
        plugin_successfully_removed_fs = False

        if self.uninstall_b and self.uninstall_b.winfo_exists():
            try:
                self.uninstall_b.config(text=lang.text29.format(show_name if show_name else name))
                if self.winfo_exists(): self.update_idletasks()
            except tk.TclError:
                logging.warning(f"TclError updating uninstall_b text for '{name}'. Widget might be destroyed.")

        print(lang.text29.format(show_name if show_name else name))

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
                msg_template = getattr(lang, "warn9_permission", "Permission denied for '{path}'. Error: {error}")
                win.message_pop(msg_template.format(path=module_path, error=str(e_perm)), 'orange',
                                title=getattr(lang, "uninstall_error_title", "Uninstall Error"))
            except Exception as e_generic:
                logging.exception(f"Generic error removing '{module_path}' for plugin '{name}': {e_generic}")
                msg_template = getattr(lang, "warn9_generic", "Failed to remove '{path}'. Error: {error}")
                win.message_pop(msg_template.format(path=module_path, error=str(e_generic)), 'orange',
                                title=getattr(lang, "uninstall_error_title", "Uninstall Error"))
        else:
            plugin_successfully_removed_fs = True
            logging.info(
                f"Module path '{module_path}' did not exist for plugin '{name}'. Assumed removed or not present on filesystem.")

        if not plugin_successfully_removed_fs and os.path.exists(module_path):
            win.message_pop(lang.warn9.format(show_name if show_name else name), 'orange',
                            title=getattr(lang, "uninstall_error_title", "Uninstall Error"))
            logging.warning(f"Directory '{module_path}' still exists after removal attempt for plugin '{name}'.")
        elif plugin_successfully_removed_fs:
            if self.uninstall_b and self.uninstall_b.winfo_exists():
                try:
                    self.uninstall_b.config(text=lang.text30.format(show_name if show_name else name))
                except tk.TclError:
                    pass
            print(lang.text30.format(show_name if show_name else name))
            logging.info(f"Plugin '{name}' (DisplayName: '{show_name}') considered removed from filesystem.")

            if callable(list_pls_plugin):
                win.after(10, list_pls_plugin)
            else:
                logging.warning("list_pls_plugin is NOT callable. MpkMan will not be updated from here.")

            if hasattr(states, 'active_mpk_store_instance') and \
                    states.active_mpk_store_instance and \
                    states.active_mpk_store_instance.winfo_exists():
                logging.debug(f"MpkStore is open. Calling update_plugin_state for plugin_id: '{name}'")
                states.active_mpk_store_instance.update_plugin_state(name)
            else:
                logging.debug(
                    f"MpkStore is not open or instance not available. No update sent to MpkStore for plugin_id: '{name}'.")
        logging.debug(f"UninstallMpk.remove completed for: {name}")




class Parse(Toplevel):
    gavs = {}
    cancel = False

    @staticmethod
    def _text(master, text, fontsize, side):
        ttk.Label(master, text=text,
                  font=(None, int(fontsize))).pack(side=side, padx=5, pady=5)

    @staticmethod
    def _button(master, text, command):
        ttk.Button(master, text=text,
                   command=lambda: exec(command)).pack(side='left')

    def _filechose(self, master, set, text):
        ft = ttk.Frame(master)
        ft.pack(fill=X)
        self.gavs[set] = StringVar()
        ttk.Label(ft, text=text).pack(side='left', padx=10, pady=10)
        ttk.Entry(ft, textvariable=self.gavs[set]).pack(side='left', padx=5, pady=5)
        ttk.Button(ft, text=lang.text28,
                   command=lambda: self.gavs[set].set(
                       filedialog.askopenfilename())).pack(side='left', padx=10, pady=10)

    def _radio(self, master, set, opins, side):
        self.gavs[set] = StringVar()
        pft1 = ttk.Frame(master)
        pft1.pack(padx=10, pady=10)
        for option in opins.split():
            text, value = option.split('|')
            self.gavs[set].set(value)
            ttk.Radiobutton(pft1, text=text, variable=self.gavs[set],
                            value=value).pack(side=side)

    def _input(self, master, set, text):
        input_frame = Frame(master)
        input_frame.pack(fill=X, padx=5, pady=5)
        self.gavs[set] = StringVar()
        if text != 'None':
            ttk.Label(input_frame, text=text).pack(side=LEFT, padx=5, pady=5, fill=X)
        ttk.Entry(input_frame, textvariable=self.gavs[set]).pack(side=LEFT, pady=5,
                                                                 padx=5,
                                                                 fill=X)

    def _checkbutton(self, master, set, text):
        self.gavs[set] = IntVar()
        text = '' if text == 'None' else text
        ttk.Checkbutton(master, text=text, variable=self.gavs[set], onvalue=1,
                        offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)

    def __unknown(self, master, type, side):
        self.cancel = self.w_assert in ['true', 'True', '1', 'Yes', 'yes']
        self._text(master, lang.warn14.format(type), 10, side if side != 'None' else 'bottom')

    def _cancel(self):
        self.cancel = True
        self.destroy()

    def __init__(self, jsons):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", lambda: self._cancel())
        with open(jsons, 'r', encoding='UTF-8') as f:
            try:
                data = json.load(f)
            except Exception as e:
                win.message_pop(lang.text133 + str(e))
                print(lang.text133 + str(e))
                self.destroy()
            self.title(data['main']['info']['title'])
            height = data['main']['info']['height']
            width = data['main']['info']['weight']
            self.w_assert = data['main']['info'].get('assert', "False")
            if height != 'none' and width != 'none':
                self.geometry(f"{width}x{height}")
            resizable = data['main']['info']['resize']
            try:
                self.attributes('-topmost', 'true')
            except (Exception, BaseException):
                logging.exception('Bugs')
            self.resizable(True, True) if resizable == '1' else self.resizable(False, False)
            for group_name, group_data in data['main'].items():
                if group_name == 'info':
                    continue
                group_frame = ttk.LabelFrame(self, text=group_data['title'])
                group_frame.pack(padx=10, pady=10)
                for con in group_data['controls']:
                    if hasattr(self, f'_{con["type"]}'):
                        control = getattr(self, f'_{con["type"]}')
                    else:
                        control = self.__unknown
                    try:
                        varnames = control.__code__.co_varnames[:control.__code__.co_argcount]
                    except AttributeError:
                        logging.exception('Var')
                        continue
                    args = [group_frame]
                    args += [con.get(i, 'None') for i in varnames if i not in ['master', 'self']]
                    try:
                        control(*args)
                    except (AttributeError, TypeError):
                        logging.exception('V!')
                        print(con, args, varnames)
        ttk.Button(self, text=lang.ok,
                   command=lambda: self.destroy()).pack(
            fill=X,
            side='bottom')
        move_center(self)
        self.wait_window()
class ModuleManager:
    def __init__(self):
        self.module_dir = os.path.join(prog_path, "bin", "module")
        self.uninstall_gui = UninstallMpk
        self.new = New()
        self.new.module_dir = self.module_dir
        self.addon_loader = loader
        self.addon_entries = Entry
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

    def get_info(self, id_: str, item: str, default: str | None = None) -> str | dict[Any, Any] | Any:
        if not default:
            default = {}
        info_file = f'{self.module_dir}/{id_}/info.json'
        if not os.path.exists(info_file):
            return default
        try:
            with open(info_file, 'r', encoding='UTF-8') as f:
                return json.load(f).get(item, default)
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {info_file} for plugin {id_}")
            return default
        except Exception as e:
            logging.error(f"Error reading info file {info_file} for plugin {id_}: {e}")
            return default

    def run(self, id_=None) -> int:
        if not id_:
            return 0
        if not current_project_name.get():
            print(lang.warn1)
            return 1
        if id_:
            value = id_
        else:
            print(lang.warn2)
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
                    print(lang.text36 % (name, n, n))
                    return 2

        main_json_path = os.path.join(script_path, "main.json")
        if os.path.exists(main_json_path):
            values_parser = Parse(main_json_path)
            if values_parser.cancel:
                return 1
            values = values_parser.gavs
        else:
            values = {}

        main_sh_path = os.path.join(script_path, "main.sh")
        main_py_path = os.path.join(script_path, "main.py")

        if os.path.exists(main_sh_path):
            if not os.path.exists(temp):
                re_folder(temp)
            exports: dict = dict()
            if values:
                for va, string_var in values.items():
                    gva = string_var.get()
                    if gva:
                        exports[va] = gva

            norm_tool_bin = os.path.normpath(cfg.tool_bin).replace(os.sep, '/')
            norm_script_path = os.path.normpath(script_path).replace(os.sep, '/')
            norm_module_dir = os.path.normpath(self.module_dir).replace(os.sep, '/')
            norm_project_output = os.path.normpath(project_manger.current_work_output_path()).replace(os.sep, '/')
            norm_project_work = os.path.normpath(project_manger.current_work_path()).replace(os.sep, '/')
            norm_module_exec = os.path.normpath(module_exec).replace(os.sep, '/')
            norm_main_sh_path = os.path.normpath(main_sh_path).replace(os.sep, '/')
            exports['tool_bin'] = norm_tool_bin
            exports['version'] = settings.version
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
            win.message_pop(lang.warn7.format(value))
            list_pls_plugin()
            win.tab7.lift()
        else:
            print(lang.warn8.format(self.get_name(id_)))
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

        if callable(list_pls_plugin):
            list_pls_plugin()

        if hasattr(states, 'active_mpk_store_instance') and \
                states.active_mpk_store_instance and \
                states.active_mpk_store_instance.winfo_exists():
            logging.debug(
                f"ModuleManager.install: MpkStore is open. Calling update_plugin_state for installed plugin_id: '{install_id}'")
            states.active_mpk_store_instance.update_plugin_state(install_id)

        logging.info(f"ModuleManager.install: Successfully installed plugin '{install_id}' to '{install_target_path}'.")
        return module_error_codes.Normal, ""

    def export(self, id_: str):

        name: str = self.get_name(id_)
        name = name.replace('/', '')
        if self.is_virtual(id_):
            print(f"{name} is a virtual plugin!")
            return 1
        if not id_:
            win.message_pop(lang.warn2)
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
                print(f"{lang.text1}:{arcname}")
                try:
                    resource_zip_file.write(str(item_path_abs), arcname=arcname)
                except Exception as e:
                    logging.exception(f'Error writing {item_path_abs} to resource zip')
                    print(lang.text2.format(item_path_abs, e))

        resource_zip_content = buffer_resource_zip.getvalue()
        buffer_resource_zip.close()
        output_mpk_path = os.path.join(settings.path, f"{name}.mpk")
        with zipfile.ZipFile(output_mpk_path, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk_final_file:
            mpk_final_file.writestr(data['resource'], resource_zip_content)
            mpk_final_file.writestr('info', info_ini_content)

            icon_path = os.path.join(plugin_dir_path, 'icon')
            if os.path.exists(icon_path):
                mpk_final_file.write(icon_path, 'icon')

        if os.path.exists(output_mpk_path):
            print(lang.t15 % output_mpk_path)
        else:
            print(lang.t16 % output_mpk_path)
        return None


module_manager = ModuleManager()
class MpkMan(object):
    def __init__(self):
        self.moduledir = module_manager.module_dir
        if not os.path.exists(self.moduledir):
            os.makedirs(self.moduledir)
        self.images_ = {}

    def list_pls(self):
        logging.debug("DEBUG: MpkMan.list_pls - ENTERED")
        if not hasattr(self, 'pls') or not self.pls.winfo_exists():
            logging.error(
                "DEBUG: MpkMan.list_pls - IconGrid (self.pls) does not exist or has been destroyed. Aborting.")
            return

        # --- Phase 1: Remove icons for plugins that are no longer installed or are not virtual ---
        current_displayed_ids = list(self.pls.apps.keys())  # Copy keys as the dictionary might change during iteration
        logging.debug(f"DEBUG: MpkMan.list_pls - Phase 1: Currently displayed plugin IDs: {current_displayed_ids}")

        for displayed_id in current_displayed_ids:
            is_physical_installed = module_manager.is_installed(displayed_id)
            is_virtual = module_manager.is_virtual(displayed_id)
            logging.debug(
                f"DEBUG: MpkMan.list_pls - Checking ID '{displayed_id}': physical_installed={is_physical_installed}, virtual={is_virtual}")

            if not is_physical_installed and not is_virtual:
                logging.info(
                    f"DEBUG: MpkMan.list_pls - Removing icon for '{displayed_id}' as it's no longer installed or virtual.")
                self.pls.remove_icon(
                    displayed_id)  # IconGrid.remove_icon should update both self.pls.apps and self.pls.icons
                if displayed_id in self.images_:
                    del self.images_[displayed_id]  # Delete the PhotoImage if it's no longer needed
                    logging.debug(f"DEBUG: MpkMan.list_pls - Removed PhotoImage for '{displayed_id}'.")

        # --- Phase 2: Add/Update icons for virtual plugins ---
        logging.debug(
            f"DEBUG: MpkMan.list_pls - Phase 2: Processing virtual plugins. Found: {list(module_manager.addon_loader.virtual.keys())}")
        for virtual_id in module_manager.addon_loader.virtual.keys():
            plugin_data = module_manager.addon_loader.virtual[virtual_id]
            display_name = plugin_data.get('name', virtual_id)

            # Use a default icon for virtual plugins
            # Ensure PhotoImage is created only once or updated correctly
            if virtual_id not in self.images_ or not self.images_[virtual_id]:  # If PhotoImage doesn't exist or is None
                self.images_[virtual_id] = images.none_byte
            current_photo_image = self.images_[virtual_id]

            if virtual_id in self.pls.apps:
                existing_label_widget = self.pls.apps[virtual_id]
                if existing_label_widget.winfo_exists():
                    existing_label_widget.configure(image=current_photo_image, text=display_name)
                    logging.debug(f"DEBUG: MpkMan.list_pls - Updated virtual plugin widget for '{virtual_id}'.")
            else:
                icon_label_widget = tk.Label(self.pls.scrollable_frame,
                                             image=current_photo_image,
                                             compound="center",
                                             text=display_name,
                                             bg="#4682B4",
                                             wraplength=70,
                                             justify='center')
                icon_label_widget.bind('<Double-Button-1>',
                                       lambda e, ar=virtual_id: create_thread(module_manager.run, ar))
                icon_label_widget.bind('<Button-3>', lambda e, ar=virtual_id: self.popup(ar, e))
                self.pls.add_icon(icon_label_widget, virtual_id)
                logging.debug(f"DEBUG: MpkMan.list_pls - Added new virtual plugin widget for '{virtual_id}'.")

        # --- Phase 3: Add/Update icons for physical plugins from module_dir ---
        logging.debug(f"DEBUG: MpkMan.list_pls - Phase 3: Processing physical plugins from '{self.moduledir}'.")
        if not os.path.exists(self.moduledir) or not os.path.isdir(self.moduledir):
            logging.warning(f"MpkMan.list_pls: Module directory '{self.moduledir}' does not exist.")
            self.pls.on_frame_configure()
            logging.debug("DEBUG: MpkMan.list_pls - EXITED early due to missing module directory.")
            return

        physical_plugins_on_disk = [pid for pid in os.listdir(self.moduledir) if
                                    os.path.isdir(os.path.join(self.moduledir, pid))]
        logging.debug(f"DEBUG: MpkMan.list_pls - Physical plugins found on disk: {physical_plugins_on_disk}")

        for plugin_id in physical_plugins_on_disk:
            plugin_path = os.path.join(self.moduledir, plugin_id)
            info_json_path = os.path.join(plugin_path, "info.json")

            if not os.path.exists(info_json_path):
                logging.warning(f"Plugin '{plugin_id}' in '{plugin_path}' is missing info.json and will be skipped.")
                continue

            try:
                plugin_metadata = JsonEdit(info_json_path).read()
                display_name = plugin_metadata.get('name', plugin_id)
            except Exception as e:
                logging.error(f"Error reading info.json for plugin '{plugin_id}': {e}. Using ID as name.")
                display_name = plugin_id

            icon_file_path = os.path.join(plugin_path, 'icon')
            loaded_photo_image = None

            if os.path.exists(icon_file_path):
                try:
                    pil_image = open_img(icon_file_path)
                    if pil_image:
                        resized_pil_image = pil_image.resize((70, 70))  # Ensure the size is correct
                        loaded_photo_image = PhotoImage(resized_pil_image)
                    else:
                        logging.warning(
                            f"Failed to open icon file (open_img returned None) for plugin '{plugin_id}' at '{icon_file_path}'.")
                except Exception as e:
                    logging.error(f"Error processing icon for plugin '{plugin_id}' at '{icon_file_path}': {e}")

            if loaded_photo_image is None:  # If the icon failed to load, use the default one
                if plugin_id not in self.images_ or not self.images_[plugin_id]:  # Create if it doesn't exist
                    self.images_[plugin_id] = PhotoImage(data=images.none_byte)
                loaded_photo_image = self.images_[plugin_id]  # Use the existing or new default icon
            else:  # If a new icon was loaded successfully, save it
                self.images_[plugin_id] = loaded_photo_image

            current_photo_image = self.images_[plugin_id]  # The final PhotoImage for this plugin

            if plugin_id in self.pls.apps:  # If the widget already exists
                existing_label_widget = self.pls.apps[plugin_id]
                if existing_label_widget.winfo_exists():
                    existing_label_widget.configure(image=current_photo_image, text=display_name)
                    logging.debug(f"DEBUG: MpkMan.list_pls - Updated physical plugin widget for '{plugin_id}'.")
            else:  # Create a new widget
                icon_label_widget = tk.Label(self.pls.scrollable_frame,
                                             image=current_photo_image,
                                             compound="center",
                                             text=display_name,
                                             bg="#4682B4",
                                             wraplength=70,
                                             justify='center')
                icon_label_widget.bind('<Double-Button-1>',
                                       lambda event, ar=plugin_id: create_thread(module_manager.run, ar))
                icon_label_widget.bind('<Button-3>', lambda event, ar=plugin_id: self.popup(ar, event))
                self.pls.add_icon(icon_label_widget, plugin_id)
                logging.debug(f"DEBUG: MpkMan.list_pls - Added new physical plugin widget for '{plugin_id}'.")

        # Update IconGrid configuration (e.g., scrollregion)
        self.pls.on_frame_configure()

        logging.debug(f"DEBUG: MpkMan.list_pls - EXITED. Final apps count in IconGrid: {len(self.pls.apps)}")

    def refresh(self):
        logging.debug("DEBUG: MpkMan.refresh() - ENTERED")
        if not hasattr(self, 'pls') or not self.pls.winfo_exists():
            logging.error(
                "DEBUG: MpkMan.refresh - IconGrid (self.pls) does not exist or has been destroyed. Aborting refresh.")
            return

        # To be absolutely sure of a clean state before a full redraw:
        if hasattr(self.pls, 'clean') and callable(self.pls.clean):
            logging.debug("DEBUG: MpkMan.refresh - Calling self.pls.clean()")
            self.pls.clean()  # IconGrid.clean should destroy old widgets and clear self.pls.icons

        if hasattr(self.pls, 'apps') and isinstance(self.pls.apps, dict):
            logging.debug("DEBUG: MpkMan.refresh - Clearing self.pls.apps")
            self.pls.apps.clear()  # Clear the ID -> widget dictionary in IconGrid

        # Clearing the self.images_ dictionary here could be risky
        # if PhotoImages are used elsewhere or if list_pls expects to find them.
        # It's better for list_pls to manage additions/deletions from self.images_ itself.
        # If list_pls completely recreates everything, then it can be cleared:
        # self.images_.clear()
        # logging.debug("DEBUG: MpkMan.refresh - Cleared self.images_")

        logging.debug("DEBUG: MpkMan.refresh - Calling self.list_pls() to rebuild.")
        self.list_pls()  # list_pls will rebuild all icons based on the current state
        logging.debug("DEBUG: MpkMan.refresh - EXITED")

    def popup(self, name, event):
        self.chosen.set(name)
        if hasattr(self, 'rmenu2') and self.rmenu2:  # Check if the menu exists
            self.rmenu2.post(event.x_root, event.y_root)

    def _prepare_and_launch_editor(self, plugin_id_to_edit: str):
        if not plugin_id_to_edit:
            logging.warning("MpkMan._prepare_and_launch_editor: plugin_id_to_edit is empty.")
            win.message_pop(
                lang.editor_no_plugin_selected_warn,
                title=getattr(lang, "editor_warn_title", "Editor Warning"),
                color="orange"
            )
            return

        try:
            new_plugin_dialog_instance = module_manager.new(create_gui_on_init=False)
            if new_plugin_dialog_instance.winfo_exists():
                new_plugin_dialog_instance.withdraw()
            create_thread(new_plugin_dialog_instance.editor_, plugin_id_to_edit)
        except Exception as e:
            error_message = f"MpkMan._prepare_and_launch_editor: Error preparing editor for plugin '{plugin_id_to_edit}': {e}"
            logging.error(error_message)
            logging.exception("Detailed stack trace for editor launch failure:")
            title_key = "editor_launch_error_title"
            message_key = "editor_launch_error_message"
            default_title = "Editor Launch Error"
            default_message_template = "Could not launch editor for plugin '{plugin_id}'.\nError: {error}"
            title_text = getattr(lang, title_key, default_title)
            message_template = getattr(lang, message_key, default_message_template)
            try:
                final_message = message_template.format(plugin_id=plugin_id_to_edit, error=str(e))
            except (KeyError, AttributeError, IndexError) as format_error:
                logging.warning(f"Could not format localized error message '{message_key}': {format_error}")
            if "{plugin_id}" in message_template or "{error}" in message_template:
                final_message = f"{message_template} (plugin: {plugin_id_to_edit}, raw error: {str(e)})"
            else:
                final_message = message_template + f"\n(Plugin: {plugin_id_to_edit}, Error: {str(e)})"
            win.message_pop(final_message, title=title_text, color="red")

    def _handle_uninstall_plugin(self, plugin_id_to_uninstall):
        if not plugin_id_to_uninstall:
            logging.warning("MpkMan._handle_uninstall_plugin: plugin_id_to_uninstall is empty.")
            # A user notification could be added here
            return

        current_plugin_id = plugin_id_to_uninstall

        def uninstall_thread_target():
            # This code runs in a separate thread
            module_manager.uninstall_gui(current_plugin_id, wait=True)
            # After uninstall_gui has finished (the UninstallMpk window is closed),
            # schedule a call to self.refresh() in the main GUI thread.
            # Use self.after because MpkMan is a ttk.Frame.
            self.after(0, self.refresh)

        create_thread(uninstall_thread_target)

    def install_mpk_wrapper(self):
        file_path = filedialog.askopenfilename(
            title=lang.text25,
            filetypes=((lang.text26, "*.mpk"),)
        )
        check_mpk_result, reason = module_manager.check_mpk(file_path)
        if check_mpk_result == module_error_codes.Normal:  # 检查路径是否有效
            InstallMpk(file_path)

    def gui(self):


        # Frame for the header and MpkStore button
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=X, padx=0, pady=0)  # Remove extra padding if not needed

        ttk.Label(header_frame, text=lang.text19, font=(None, 20)).pack(padx=10, pady=10, side=LEFT)
        ttk.Button(header_frame, text='Mpk Store', command=lambda: create_thread(MpkStore)).pack(side="right", padx=10,
                                                                                                 pady=10)

        # Separator below the header; if it was in win.tab7, it should now be in MpkMan
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=(0, 5), fill=X)  # Smaller bottom padding

        # "Available plugins" label
        # Label - from tkinter, not ttk.Label, to match old code if important
        plugins_label = Label(self, text=lang.text24)
        plugins_label.pack(padx=5, pady=(5, 0), anchor='nw')  # Smaller top padding, align to northwest

        # IconGrid is now a child of self (MpkMan)

        # Bind context menu to the "Available plugins" label and to IconGrid/Canvas itself
        rmenu = Menu(self, tearoff=False, borderwidth=0)  # Menu parent is self (MpkMan)
        rmenu.add_command(label=lang.text21, command=self.install_mpk_wrapper)
        rmenu.add_command(label=lang.refresh, command=lambda: create_thread(self.refresh))
        rmenu.add_command(label=lang.text115, command=lambda: create_thread(module_manager.new))

        plugins_label.bind('<Button-3>', lambda event: rmenu.post(event.x_root, event.y_root))
        self.pls.canvas.bind('<Button-3>', lambda event: rmenu.post(event.x_root, event.y_root))
        # self.pls.bind('<Button-3>', lambda event: rmenu.post(event.x_root, event.y_root)) # On IconGrid (Frame) itself

        self.rmenu2 = Menu(self, tearoff=False, borderwidth=0)  # Menu parent is self (MpkMan)
        self.rmenu2.add_command(label=lang.text20,  # Delete
                                command=lambda: self._handle_uninstall_plugin(self.chosen.get()))
        self.rmenu2.add_command(label=lang.text22,  # Run
                                command=lambda: create_thread(module_manager.run, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t14,  # Export
                                command=lambda: create_thread(module_manager.export, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t17,  # Edit
                                command=lambda: self._prepare_and_launch_editor(self.chosen.get()))

        self.list_pls()

class AppCard(CardWidget):

    def __init__(self, icon, title:str, content:str, parent=None):
        super().__init__(parent)
        self.iconWidget = IconWidget(icon)
        self.titleLabel = BodyLabel(title, self)
        self.contentLabel = CaptionLabel(content, self)
        self.openButton = PushButton('Open', self)
        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)

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

        self.moreButton.setFixedSize(32, 32)

class PluginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PluginPage")
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(24)
        card = AppCard(
            icon=":/qfluentwidgets/images/logo.png",
            title="PyQt-Fluent-Widgets",
            content="Shokokawaii Inc."
        )
        card.clicked.connect(lambda: print("Card is clicked"))
        main_layout.addWidget(card)
        self.setLayout(main_layout)