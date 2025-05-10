#!/usr/bin/env python3
# pylint: disable=line-too-long, missing-class-docstring, missing-function-docstring
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import gzip
import json
import platform
import shutil
import subprocess
import threading
from functools import wraps
from random import randrange
from tkinter.ttk import Scrollbar

from ..core import tarsafe, miside_banner
from ..core.Magisk import Magisk_patch
from ..core.addon_register import loader, Entry
from ..core.cpio import extract as cpio_extract, repack as cpio_repack
from ..core.qsb_imger import process_by_xml
from ..core.romfs_parse import RomfsParse
from ..core.unkdz import KDZFileTools

if platform.system() != 'Darwin':
    try:
        import pyi_splash

        pyi_splash.update_text('Loading ...')
        pyi_splash.close()
    except ModuleNotFoundError:
        ...
import os.path
import pathlib
import sys
import time
from platform import machine
from webbrowser import open as openurl
import tkinter as tk
from tkinter import ttk
from timeit import default_timer as dti
import zipfile
from io import BytesIO, StringIO
from .tkinterdnd2_build_in import Tk, DND_FILES
from tkinter import (BOTH, LEFT, RIGHT, Canvas, Text, X, Y, BOTTOM, StringVar, IntVar, TOP, Toplevel as TkToplevel,
                     HORIZONTAL, TclError, Frame, Label, Listbox, DISABLED, Menu, BooleanVar, CENTER)
from shutil import rmtree, copy, move
import pygments.lexers
import requests
from requests import ConnectTimeout, HTTPError
import sv_ttk
from PIL.Image import open as open_img
from PIL.ImageTk import PhotoImage
from ..core.dumper import Dumper
from ..core.utils import lang, LogoDumper, States, terminate_process, calculate_md5_file, calculate_sha256_file, \
    JsonEdit, DevNull, ModuleErrorCodes, hum_convert, GuoKeLogo

if os.name == 'nt':
    from ctypes import windll, c_int, byref, sizeof
    from tkinter import filedialog
else:
    from ..core import mkc_filedialog as filedialog

from ..core import imgextractor
from ..core import lpunpack
from ..core import mkdtboimg
from ..core import ozipdecrypt
from ..core import splituapp
from ..core import ofp_qc_decrypt
from ..core import ofp_mtk_decrypt
from . import editor
from ..core import opscrypto
from ..core import images
from ..core import extra
from . import AI_engine
from ..core import ext4
from ..core.config_parser import ConfigParser
from ..core import utils
from ..core.unpac import MODE as PACMODE, unpac

if os.name == 'nt':
    from .sv_ttk_fixes import *
from ..core.extra import fspatch, re, contextpatch
from ..core.utils import create_thread, move_center, v_code, gettype, is_empty_img, findfile, findfolder, Sdat2img, Unxz
from .controls import ListBox, ScrollFrame
from ..core.undz import DZFileTools
from ..core.selinux_audit_allow import main as selinux_audit_allow
import logging

is_pro = False
try:
    from ..pro.sn import v as verify

    is_pro = True
except ImportError:
    is_pro = False
if is_pro:
    from ..pro.active_ui import Active

try:
    from ..core import imp
except ImportError:
    imp = None
try:
    from ..core.pycase import ensure_dir_case_sensitive
except ImportError:
    ensure_dir_case_sensitive = lambda *x: print(f'Cannot sensitive {x}, Not Supported')

cwd_path = utils.prog_path

if os.name == 'nt':
    # Copy From https://github.com/littlewhitecloud/CustomTkinterTitlebar/
    def set_title_bar_color(window, dark_value: int = 20):
        window.update()
        set_window_attribute = windll.dwmapi.DwmSetWindowAttribute
        get_parent = windll.user32.GetParent
        hwnd = get_parent(window.winfo_id())
        rendering_policy = dark_value
        value = c_int(2)
        set_window_attribute(hwnd, rendering_policy, byref(value), sizeof(value))
        window.update()


class LoadAnim:
    gifs = []

    def __init__(self, master=None):
        self.master = master
        self.frames = []
        self.hide_gif = False
        self.frame = None
        self.tasks = {}
        self.task_num_index = 0
        self.task_num_max = 100

    def set_master(self, master):
        self.master = master

    def run(self, ind: int = 0):
        self.hide_gif = False
        if not self.hide_gif:
            self.master.gif_label.pack(padx=10, pady=10)
        self.frame = self.frames[ind]
        ind += 1
        if ind == len(self.frames):
            ind = 0
        self.master.gif_label.configure(image=self.frame)
        self.gifs.append(self.master.gif_label.after(30, self.run, ind))

    def get_task_num(self):
        self.task_num_index = (self.task_num_index + 1) % self.task_num_max
        return self.task_num_index

    def stop(self):
        for i in self.gifs:
            try:
                self.master.gif_label.after_cancel(i)
            except (Exception, BaseException):
                logging.exception('Bugs')
        self.master.gif_label.pack_forget()
        self.hide_gif = True

    def init(self):
        self.run()
        self.stop()

    def load_gif(self, gif):
        self.frames.clear()
        while True:
            self.frames.append(PhotoImage(gif))
            try:
                gif.seek(len(self.frames))
            except EOFError:
                break

    def __call__(self, func):
        @wraps(func)
        def call_func(*args, **kwargs):
            return_value = None

            def wrapper(*a, **k):
                nonlocal return_value
                return_value = func(*a, **k)

            create_thread(self.run())
            task_num = self.get_task_num()
            task_real = threading.Thread(target=wrapper, args=args, kwargs=kwargs, daemon=True)
            info = [func.__name__, args, task_real]
            if task_num in self.tasks:
                print(f"The Same task_num {task_num} was used by {task_real.native_id} with args {info[2]}...\n")
                return None
            else:
                self.tasks[task_num] = info
            task_real.start()
            task_real.join()
            if task_num in self.tasks:
                del self.tasks[task_num]
            del info, task_num
            if not self.tasks:
                self.stop()
            return return_value

        return call_func


def warn_win(text: str = '', color: str = 'orange', title: str = "Warn", wait: int = 1500, parent=None):
    """
    Displays a temporary window with a warning or informational message.

    This window automatically closes after a specified 'wait' period.
    It can be made transient to a parent window if provided.

    Args:
        text (str): The message text to display.
        color (str): The color of the message text.
        title (str): The title of the window.
        wait (int): Time in milliseconds after which the window will close.
        parent (tk.Widget, optional): The parent window. If specified,
                                     the dialog will be transient with respect to it.
    """
    # Attempt to use the custom Toplevel if 'Toplevel' is defined in the current scope.
    # Otherwise, fall back to the standard tkinter.Toplevel.
    # This assumes the custom Toplevel handles Windows-specific title bar coloring if needed.
    try:
        dialog = Toplevel() 
    except NameError: 
        import tkinter as tk
        dialog = tk.Toplevel()

    dialog.title(title)
    # dialog.resizable(False, False) # Optionally, prevent resizing.

    # If a parent window is provided and exists, make the dialog transient to it.
    # This helps the window manager handle window layering and behavior correctly.
    if parent and hasattr(parent, 'winfo_exists') and parent.winfo_exists():
        try:
            dialog.transient(parent)
        except Exception as e:
            # Log a warning if setting transient fails, but don't interrupt the dialog.
            if 'logging' in globals() and hasattr(globals()['logging'], 'warning'):
                logging.warning(f"Could not set transient for warn_win: {e}")

    frame_inner = ttk.Frame(dialog)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    
    # Default font. Could be customized via 'lang' object if needed, e.g.:
    # font_tuple = getattr(lang, 'font_warn_win_text', (None, 16))
    font_tuple = (None, 16) 

    ttk.Label(frame_inner, text=text, font=font_tuple, foreground=color, wraplength=350).pack(side=TOP, pady=(10,10))
    
    # Center the window on the screen.
    if 'move_center' in globals() and callable(globals()['move_center']):
        move_center(dialog)
    else: 
        # Basic fallback for centering if move_center is not available.
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')

    # Schedule the window to close automatically.
    dialog.after(wait, dialog.destroy)
    
    # Note: grab_set() and wait_window() are typically not used for 'warn_win'
    # as it's intended to be a non-blocking notification.
    # If modal behavior during its display is required:
    # dialog.grab_set()
    # dialog.wait_window() # This would make it blocking, changing its nature.
    
    # To make the window always on top (but not modal in a blocking sense):
    # dialog.attributes('-topmost', True) # Behavior might vary across platforms/WMs.

    return dialog # Return the dialog instance, in case it's needed.


class Toplevel(TkToplevel):
    def __init__(self):
        super().__init__()
        if os.name == 'nt':
            if settings.theme == 'dark':
                set_title_bar_color(self)
            else:
                set_title_bar_color(self, 0)


class CustomControls:
    def __init__(self):
        pass

    @staticmethod
    def filechose(master, textvariable: tk.Variable, text, is_folder: bool = False):
        ft = ttk.Frame(master)
        ft.pack(fill=X)
        ttk.Label(ft, text=text, width=15, font=(None, 12)).pack(side='left', padx=10, pady=10)
        ttk.Entry(ft, textvariable=textvariable).pack(side='left', padx=5, pady=5)
        ttk.Button(ft, text=lang.text28,
                   command=lambda: textvariable.set(
                       filedialog.askopenfilename() if not is_folder else filedialog.askdirectory())).pack(side='left',
                                                                                                           padx=10,
                                                                                                           pady=10)

    @staticmethod
    def combobox(master, textvariable: tk.Variable, values, text, state: str = 'normal'):
        ft = ttk.Frame(master)
        ft.pack(fill=X)
        ttk.Label(ft, text=text, width=15, font=(None, 12)).pack(side='left', padx=10, pady=10)
        ttk.Combobox(ft, textvariable=textvariable,
                     values=values, state=state).pack(side='left', padx=5, pady=5)


ccontrols = CustomControls()


class ToolBox(ttk.Frame):
    def __init__(self, master):
        super().__init__(master=master)
        self.__on_mouse = lambda event: self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

    def pack_basic(self):
        scrollbar = Scrollbar(self, orient='vertical')
        scrollbar.pack(side='right', fill='y', padx=10, pady=10)
        self.canvas = Canvas(self, yscrollcommand=scrollbar.set)
        self.canvas.pack_propagate(False)
        self.canvas.pack(fill='both', expand=True)
        scrollbar.config(command=self.canvas.yview)
        self.label_frame = Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.label_frame, anchor='nw')
        self.canvas.bind_all("<MouseWheel>",
                             lambda event: self.__on_mouse(event))

    def gui(self):
        self.pack_basic()
        functions = [
            (lang.text114, lambda: create_thread(download_file)),
            (lang.t59, self.GetFileInfo),
            (lang.t60, self.FileBytes),
            (lang.audit_allow, self.SelinuxAuditAllow),
            (lang.trim_image, self.TrimImage),
            (lang.magisk_patch, self.MagiskPatcher),
            (lang.mergequalcommimage, self.MergeQualcommImage_old)
        ]
        width_controls = 3
        #
        index_row = 0
        index_column = 0
        for text, func in functions:
            ttk.Button(self.label_frame, text=text, command=func, width=17).grid(row=index_row, column=index_column,
                                                                                 padx=5, pady=5)
            index_column = (index_column + 1) % width_controls
            if not index_column:
                index_row += 1
        self.update_ui()

    def update_ui(self):
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

    class MergeQualcommImage_old(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.mergequalcommimage)
            self.rawprogram_xml = StringVar()
            self.partition_name = StringVar()
            self.output_path = StringVar()
            self.gui()
            move_center(self)

        def gui(self):
            ccontrols.filechose(self, self.rawprogram_xml, 'RawProgram Xml：')
            ccontrols.combobox(self, self.partition_name, ('system', 'userdata', 'cache'), lang.partition_name)
            ccontrols.filechose(self, self.output_path, lang.output_path, is_folder=True)
            ttk.Button(self, text=lang.run, command=lambda: create_thread(self.run)).pack(padx=5, pady=5, fill='both')

        def run(self):
            rawprogram_xml = self.rawprogram_xml.get()
            if not os.path.exists(rawprogram_xml):
                print(f'Raw Program not exist!{rawprogram_xml}')
                return 1
            partition_name = self.partition_name.get()
            output_path = self.output_path.get()
            if not output_path:
                print('Please Choose OutPut Path.')
                return 1
            if not os.path.exists(output_path):
                os.makedirs(output_path, exist_ok=True)
            self.destroy()
            try:
                process_by_xml(rawprogram_xml, partition_name, output_path)
                return None
            except (Exception, BaseException) as e:
                print('Merge Fail!')
                logging.exception('MergeQC RAWPROGRAM')
                return None

    class MagiskPatcher(Toplevel):
        def __init__(self):
            super().__init__()
            self.magisk_apk = None
            self.boot_file = None
            self.title(lang.magisk_patch)
            self.gui()
            move_center(self)

        def get_arch(self, apk=None) -> list:
            if not apk:
                apk = self.magisk_apk.get()
            if not apk or not os.path.exists(apk):
                return ["arm64-v8a"]
            with Magisk_patch(None, None, None, None, MAGISAPK=apk) as m:
                return m.get_arch()

        def chose_file_refresh(self):
            file = filedialog.askopenfilename()
            self.magisk_apk.set(
                file)
            self.archs.configure(value=self.get_arch(file))
            self.lift()
            self.focus_force()

        def patch(self):
            self.patch_bu.configure(state="disabled", text=lang.running)
            local_path = str(os.path.join(temp, v_code()))
            re_folder(local_path)
            with Magisk_patch(self.boot_file.get(), None, f"{settings.tool_bin}/magiskboot", local_path,
                              self.IS64BIT.get(),
                              self.KEEPVERITY.get(), self.KEEPFORCEENCRYPT.get(),
                              self.RECOVERYMODE.get(), self.magisk_apk.get(), self.magisk_arch.get()
                              ) as m:
                m.auto_patch()
                if m.output:
                    output_file = os.path.join(cwd_path,
                                               os.path.basename(self.boot_file.get()[:-4]) + "_magisk_patched.img")
                    if os.path.exists(output_file):
                        output_file = os.path.join(cwd_path,
                                                   os.path.basename(
                                                       self.boot_file.get()[:-4]) + v_code() + "_magisk_patched.img")
                    os.rename(m.output, output_file)
                    print(f"Done!Patched Boot:{output_file}")
                    info_win(f"Patched Boot:\n{output_file}")
            self.patch_bu.configure(state="normal", text=lang.patch)

        def gui(self):
            ttk.Label(self, text=lang.magisk_patch).pack()
            ft = ttk.Frame(self)
            ft.pack(fill=X)

            self.boot_file = StringVar()
            ttk.Label(ft, text=lang.boot_file).pack(side='left', padx=10, pady=10)
            ttk.Entry(ft, textvariable=self.boot_file).pack(side='left', padx=5, pady=5)
            ttk.Button(ft, text=lang.text28,
                       command=lambda: self.boot_file.set(
                           filedialog.askopenfilename())).pack(side='left', padx=10, pady=10)

            ft = ttk.Frame(self)
            ft.pack(fill=BOTH)

            self.magisk_apk = StringVar()
            ttk.Label(ft, text=lang.magisk_apk).pack(side='left', padx=10, pady=10)
            ttk.Entry(ft, textvariable=self.magisk_apk).pack(side='left', padx=5, pady=5)
            ttk.Button(ft, text=lang.text28,
                       command=lambda: self.chose_file_refresh()).pack(side='left', padx=10, pady=10)
            ft = ttk.Frame(self)
            ft.pack(fill=X)

            self.magisk_arch = StringVar(value='arm64-v8a')
            ttk.Label(ft, text=lang.arch).pack(side='left', padx=10, pady=10)
            self.archs = ttk.Combobox(ft, state='readonly', textvariable=self.magisk_arch,
                                      values=["arm64-v8a"])
            self.archs.pack(side='left', padx=5, pady=5)
            ttk.Button(ft, text=lang.text23,
                       command=lambda: self.archs.configure(value=self.get_arch())).pack(side='left', padx=10, pady=10)
            # Options
            # IS64BIT=True, KEEPVERITY=False, KEEPFORCEENCRYPT=False, RECOVERYMODE=False
            self.IS64BIT = BooleanVar(value=True)
            self.KEEPVERITY = BooleanVar(value=False)
            self.KEEPFORCEENCRYPT = BooleanVar(value=False)
            self.RECOVERYMODE = BooleanVar(value=False)
            ft = ttk.Frame(self)
            ft.pack(fill=X)
            ttk.Checkbutton(ft, onvalue=True, offvalue=False, text='IS64BIT', variable=self.IS64BIT).pack(fill=X,
                                                                                                          padx=5,
                                                                                                          pady=5,
                                                                                                          side=LEFT)
            ttk.Checkbutton(ft, onvalue=True, offvalue=False, text='KEEPVERITY', variable=self.KEEPVERITY).pack(fill=X,
                                                                                                                padx=5,
                                                                                                                pady=5,
                                                                                                                side=LEFT)
            ft = ttk.Frame(self)
            ft.pack(fill=X)
            ttk.Checkbutton(ft, onvalue=True, offvalue=False, text='KEEPFORCEENCRYPT',
                            variable=self.KEEPFORCEENCRYPT).pack(fill=X, padx=5, pady=5, side=LEFT)
            ttk.Checkbutton(ft, onvalue=True, offvalue=False, text='RECOVERYMODE', variable=self.RECOVERYMODE).pack(
                fill=X, padx=5, pady=5, side=LEFT)
            self.patch_bu = ttk.Button(self, text=lang.patch, style='Accent.TButton',
                                       command=lambda: create_thread(self.patch))
            self.patch_bu.pack(fill=X, padx=5, pady=5)

    class SelinuxAuditAllow(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.audit_allow)
            self.gui()
            move_center(self)

        def gui(self):
            f = Frame(self)
            self.choose_file = StringVar(value='')
            ttk.Label(f, text=lang.log_file).pack(side=LEFT, fill=X, padx=5, pady=5)
            ttk.Entry(f, textvariable=self.choose_file).pack(side=LEFT, fill=X, padx=5, pady=5)
            ttk.Button(f, text=lang.choose, command=lambda: self.choose_file.set(
                filedialog.askopenfilename(title=lang.text25, filetypes=(
                    ('Log File', "*.log"), ('Log File', "*.txt")))) == self.lift()).pack(side=LEFT,
                                                                                         fill=X, padx=5,
                                                                                         pady=5)
            f.pack(padx=5, pady=5, anchor='nw', fill=X)
            ##
            f2 = Frame(self)
            self.output_dir = StringVar(value='')
            ttk.Label(f2, text=lang.output_folder).pack(side=LEFT, fill=X, padx=5, pady=5)
            ttk.Entry(f2, textvariable=self.output_dir).pack(side=LEFT, fill=X, padx=5, pady=5)
            ttk.Button(f2, text=lang.choose,
                       command=lambda: self.output_dir.set(filedialog.askdirectory()) == self.lift()).pack(side=LEFT,
                                                                                                           fill=X,
                                                                                                           padx=5,
                                                                                                           pady=5)
            f2.pack(padx=5, pady=5, anchor='nw', fill=X)
            ttk.Label(self, text='By github@Deercall').pack()
            self.button = ttk.Button(self, text=lang.text22, command=self.run, style='Accent.TButton')
            self.button.pack(padx=5, pady=5, fill=X)

        def run(self):
            if self.button.cget('text') == lang.done:
                self.destroy()
            else:
                self.button.configure(text=lang.running, state='disabled')
                create_thread(selinux_audit_allow, self.choose_file.get(), self.output_dir.get())
                self.button.configure(text=lang.done, state='normal', style='')

    class FileBytes(Toplevel):
        def __init__(self):
            super().__init__()
            self.units = {
                "B": 1,  # Use 1 instead of 2**0 for simplicity
                "KB": 1024,
                "MB": 1024**2,
                "GB": 1024**3,
                "TB": 1024**4,
                "PB": 1024**5 # Added PB for completeness
            }
            self.title(lang.t60) # lang.t60 = 'Byte Calculator' (пример)
            self._is_calculating = False # Flag to prevent recursion
            self.origin_size_var = tk.StringVar() # Separate variables for Entry
            self.result_size_var = tk.StringVar()
            self.gui()
            move_center(self) # Make sure that move_center is defined

        def gui(self):
            self.f_main = Frame(self) # The main frame for widgets
            self.f_main.pack(pady=5, padx=5, fill=X, expand=True)

            # Left input field
            self.origin_size = ttk.Entry(self.f_main, textvariable=self.origin_size_var)
            self.origin_size.bind("<KeyRelease>", self.calc_forward) # Binding to the left field
            self.origin_size.pack(side='left', padx=5, expand=True, fill=X)

           # Left combobox
            self.h = ttk.Combobox(self.f_main, values=list(self.units.keys()), state='readonly', width=4)
            self.h.current(0)
            self.h.bind("<<ComboboxSelected>>", self.calc_forward) # Binding to the left combobox
            self.h.pack(side='left', padx=5)

            # Equal sign
            Label(self.f_main, text='=').pack(side='left', padx=5)

            # Right input field
            self.result_size = ttk.Entry(self.f_main, textvariable=self.result_size_var)
            self.result_size.bind("<KeyRelease>", self.calc_reverse) # Binding to the right field
            self.result_size.pack(side='left', padx=5, expand=True, fill=X)

            # Right combobox
            self.f_ = ttk.Combobox(self.f_main, values=list(self.units.keys()), state='readonly', width=4)
            self.f_.current(0)
            self.f_.bind("<<ComboboxSelected>>", self.calc_reverse) # Binding to the right combobox
            self.f_.pack(side='left', padx=5)

            # Close button
            ttk.Button(self, text=lang.text17, command=self.destroy).pack(fill=X, padx=5, pady=5) # lang.text17 = 'Close' (пример)

        def calc_forward(self, event=None):
            """Рассчитывает значение справа налево (из левого поля в правое)."""
            if self._is_calculating:
                return # Prevent recursion

            self._is_calculating = True
            try:
                origin_unit = self.h.get()
                target_unit = self.f_.get()
                origin_value_str = self.origin_size_var.get()

                result_value_str = self.__calc(origin_unit, target_unit, origin_value_str)

                # We update only if the value is different to avoid unnecessary events
                if self.result_size_var.get() != result_value_str:
                    self.result_size_var.set(result_value_str)
            finally:
                self._is_calculating = False # Dropping the flag

        def calc_reverse(self, event=None):
            """Рассчитывает значение справа налево (из правого поля в левое)."""
            if self._is_calculating:
                return # Prevent recursion

            self._is_calculating = True
            try:
                # Units are swapped for calculation
                origin_unit = self.f_.get() # We take a unit from the right combobox
                target_unit = self.h.get() # The target unit is from the left
                origin_value_str = self.result_size_var.get() # Value from the right field

                result_value_str = self.__calc(origin_unit, target_unit, origin_value_str)

                # Update only if the value is different
                if self.origin_size_var.get() != result_value_str:
                    self.origin_size_var.set(result_value_str)
            finally:
                self._is_calculating = False # Dropping the flag

        def __calc(self, origin_unit: str, target_unit: str, size_str: str) -> str:
            """Выполняет конвертацию значения между единицами."""
            # Removing the spaces
            size_str = size_str.strip()

           # Handling empty input
            if not size_str:
                return "" # We return an empty string if the output is empty

            try:
               # Trying to convert to float
                size = float(size_str)
            except ValueError:
                # If it's not a float, check if it's a partially entered number.
                 if size_str == '.' or size_str == '-' or size_str == '-.' or \
                   (size_str.startswith('-') and size_str.count('.') <= 1 and all(c.isdigit() or c == '.' for c in size_str[1:])) or \
                   (size_str.count('.') <= 1 and all(c.isdigit() or c == '.' for c in size_str)):
                    # If it looks like a number in the input process, we don't return anything yet (or can we return "0"?)
# We return an empty string so as not to interfere with the input
                    return ""
                 else:
                    # If it's not exactly a number, we return "Invalid" or an empty string.
                    return "Invalid"

           # If the units are the same
            if origin_unit == target_unit:
                # We return the number as a string by deleting .0 for integers
                return str(int(size)) if size.is_integer() else str(size)

           # Performing the calculation
            result = size * self.units[origin_unit] / self.units[target_unit]

            # Format the result: delete it .0 for integers, we limit the precision
            if result.is_integer():
                return str(int(result))
            else:
                # We limit the number of decimal places for readability
                return f"{result:.6f}".rstrip('0').rstrip('.')
                
    class GetFileInfo(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.t59)
            self.controls = []
            self.gui()
            self.geometry("400x450")
            self.resizable(False, False)
            self.dnd = lambda file_list: create_thread(self.__dnd, file_list)
            move_center(self)

        def gui(self):
            a = ttk.LabelFrame(self, text='Drop')
            (tl := ttk.Label(a, text=lang.text132_e)).pack(fill=BOTH, padx=5, pady=5)
            tl.bind('<Button-1>', lambda *x: self.dnd([filedialog.askopenfilename()]))
            a.pack(side=TOP, padx=5, pady=5, fill=BOTH)
            a.drop_target_register(DND_FILES)
            a.dnd_bind('<<Drop>>', lambda x: self.dnd([x.data]))
            self.b = ttk.LabelFrame(self, text='INFO')
            self.b.pack(fill=BOTH, side=TOP)

        def put_info(self, name, value):
            f = Frame(self.b)
            self.controls.append(f)
            ttk.Label(f, text=f"{name}:", width=7).pack(fill=X, side='left')
            f_e = ttk.Entry(f)
            f_e.insert(0, value)
            f_e.pack(fill=X, side='left', padx=5, pady=5, expand=True)
            f_b = ttk.Button(f, text=lang.scopy)
            f_b.configure(command=lambda e=f_e, b=f_b: self.copy_to_clipboard(e.get(), b))
            f_b.pack(fill=X, side='left', padx=5, pady=5)
            f.pack(fill=X)

        @staticmethod
        def copy_to_clipboard(value, b: ttk.Button):
            b.configure(text=lang.scopied, state='disabled')
            win.clipboard_clear()
            win.clipboard_append(value)
            b.after(1500, lambda: b.configure(text=lang.scopy, state='normal'))

        def clear(self):
            for i in self.controls:
                try:
                    i.destroy()
                except:
                    logging.exception('Bugs')

        def __dnd(self, file_list: list):
            self.clear()
            self.lift()
            self.focus_force()
            file = file_list[0]
            if isinstance(file, bytes):
                try:
                    file = file_list[0].decode('utf-8')
                except:
                    file = file_list[0].decode('gbk')
            if not os.path.isfile(file) or not file:
                self.put_info('Warn', 'Please Select A File')
                return
            self.put_info(lang.name, os.path.basename(file))
            self.put_info(lang.path, file)
            self.put_info(lang.type, gettype(file))
            self.put_info(lang.size, hum_convert(os.path.getsize(file)))
            self.put_info(f"{lang.size}(B)", os.path.getsize(file))
            self.put_info(lang.time, time.ctime(os.path.getctime(file)))
            self.put_info("MD5", calculate_md5_file(file))
            self.put_info("SHA256", calculate_sha256_file(file))

    class TrimImage(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.trim_image)
            self.gui()
            move_center(self)
            self.resizable(False, False)

        def gui(self):
            ttk.Label(self, text=lang.help_trim_image).pack(padx=5, pady=5)
            f = Frame(self)
            self.choose_file = StringVar(value='')
            ttk.Label(f, text=lang.text77).pack(side=LEFT, fill=X, padx=5, pady=5)
            self.path_edit = ttk.Entry(f, textvariable=self.choose_file)
            self.path_edit.pack(side=LEFT, fill=X, padx=5, pady=5, expand=True)
            self.choose_button = ttk.Button(f, text=lang.choose, command=lambda: self.choose_file.set(
                filedialog.askopenfilename(title=lang.text25)) == self.lift())
            self.choose_button.pack(side=LEFT, fill=X, padx=5, pady=5)
            f.pack(padx=5, pady=5, anchor='nw', fill=X)
            self.button = ttk.Button(self, text=lang.text22, command=self.run, style='Accent.TButton')
            self.button.pack(padx=5, pady=5, fill=X)

        def do_trim(self, buff_size: int = 8192):
            orig_size = file_size = os.path.getsize(self.choose_file.get())
            zeros_ = bytearray(buff_size)
            with open(self.choose_file.get(), 'rb') as f:
                self.button.configure(text=lang.running + ' - 0%')
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
                        self.button.configure(text=lang.running + f' - {percentage}%')
                        self.update_idletasks()
            os.truncate(self.choose_file.get(), file_size)
            c = orig_size - file_size
            info_win(lang.trim_image_summary % (c, hum_convert(c)))

        def run(self):
            if self.button.cget('text') == lang.done:
                self.destroy()
                return
            if not os.path.isfile(self.choose_file.get()):
                return
            self.button.configure(text=lang.running, state='disabled')
            self.path_edit.configure(state='disabled')
            self.choose_button.configure(state='disabled')
            self.do_trim()
            self.button.configure(text=lang.done, state='normal', style='')


class Tool(Tk):
    def __init__(self):
        super().__init__()
        self.rotate_angle = 0
        if os.name == 'nt':
            do_set_window_deffont(self)
        self.message_pop = warn_win
        self.title('MIO-KITCHEN')
        if os.name != "posix":
            self.iconphoto(True,
                           PhotoImage(
                               data=images.icon_byte))

    def get_time(self):
        self.tsk.config(text=time.strftime("%H:%M:%S"))
        self.after(1000, self.get_time)

    def get_frame(self, title):
        frame = ttk.LabelFrame(self.frame_bg, text=title)
        frame.pack(padx=10, pady=10)
        ttk.Button(frame, text=lang.text17, command=frame.destroy).pack(anchor="ne", padx=5, pady=5)
        self.update_frame()
        self.scrollbar.config(command=self.canvas1.yview)
        return frame

    def update_frame(self):
        self.frame_bg.update_idletasks()
        self.canvas1.config(scrollregion=self.canvas1.bbox('all'))

    def gui(self):
        if os.name == 'posix' and os.geteuid() != 0:
            print(lang.warn13)
        self.sub_win2 = ttk.Frame(self)
        self.sub_win3 = ttk.Frame(self)
        self.sub_win3.pack(fill=BOTH, side=LEFT, expand=True)
        self.sub_win2.pack(fill=BOTH, side=LEFT, expand=True)
        self.notepad = ttk.Notebook(self.sub_win2)
        if not is_pro:
            self.tab = ttk.Frame(self.notepad)
        self.tab2 = ttk.Frame(self.notepad)
        self.tab3 = ttk.Frame(self.notepad)
        self.tab4 = ttk.Frame(self.notepad)
        self.tab5 = ttk.Frame(self.notepad)
        self.tab6 = ttk.Frame(self.notepad)
        self.tab7 = ttk.Frame(self.notepad)
        if not is_pro:
            self.notepad.add(self.tab, text=lang.text11)
        self.notepad.add(self.tab2, text=lang.text12)
        self.notepad.add(self.tab7, text=lang.text19)
        self.notepad.add(self.tab3, text=lang.text13)
        self.notepad.add(self.tab4, text=lang.text14)
        self.notepad.add(self.tab5, text=lang.text15)
        self.notepad.add(self.tab6, text=lang.toolbox)
        self.scrollbar = ttk.Scrollbar(self.tab5, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas1 = Canvas(self.tab5, yscrollcommand=self.scrollbar.set)
        self.canvas1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.frame_bg = ttk.Frame(self.canvas1)
        self.canvas1.create_window((0, 0), window=self.frame_bg, anchor='nw')
        self.canvas1.config(highlightthickness=0)
        self.tab4_content()
        self.tab6_content()
        self.setting_tab()
        if not is_pro:
            self.tab_content()
        self.notepad.pack(fill=BOTH, expand=True)
        self.rzf = ttk.Frame(self.sub_win3)
        self.tsk = Label(self.sub_win3, text="MIO-KITCHEN", font=(None, 15))
        self.tsk.pack(padx=10, pady=10, side='top')
        tr = ttk.LabelFrame(self.sub_win3, text=lang.text131)
        tr2 = Label(tr, text=lang.text132 + '\n(pac ozip zip tar.md5 tar tar.gz kdz dz ops ofp ext4 erofs boot img)')
        tr2.pack(padx=10, pady=10, side='bottom')
        tr.bind('<Button-1>', lambda *x: dndfile([filedialog.askopenfilename()]))
        tr.pack(padx=5, pady=5, side='top', expand=True, fill=BOTH)
        tr2.bind('<Button-1>', lambda *x: dndfile([filedialog.askopenfilename()]))
        tr2.pack(padx=5, pady=5, side='top', expand=True, fill=BOTH)
        self.scroll = ttk.Scrollbar(self.rzf)
        self.show = Text(self.rzf)
        self.show.pack(side=LEFT, fill=BOTH, expand=True)
        data: str = sys.stdout.data
        sys.stdout = StdoutRedirector(self.show)
        sys.stdout.write(data)
        del data
        sys.stderr = StdoutRedirector(self.show, error_=True)
        tr.drop_target_register(DND_FILES)
        tr.dnd_bind('<<Drop>>', lambda x: dndfile([x.data]))
        tr2.drop_target_register(DND_FILES)
        tr2.dnd_bind('<<Drop>>', lambda x: dndfile([x.data]))
        self.scroll.pack(side=LEFT, fill=BOTH)
        self.scroll.config(command=self.show.yview)
        self.show.config(yscrollcommand=self.scroll.set)
        self.rzf.pack(padx=5, pady=5, fill=BOTH, side='bottom')
        self.gif_label = Label(self.rzf)
        self.gif_label.pack(padx=10, pady=10)
        ttk.Button(self.rzf, text=lang.text105, command=lambda: self.show.delete(1.0, tk.END)).pack(padx=10, pady=10)
        MpkMan().gui()

    def tab_content(self):
        global kemiaojiang
        kemiaojiang_img = open_img(open(f'{cwd_path}/bin/kemiaojiang.png', 'rb'))
        kemiaojiang = PhotoImage(kemiaojiang_img.resize((280, 540)))
        Label(self.tab, image=kemiaojiang).pack(side='left', padx=0, expand=True)
        Label(self.tab, text=lang.welcome_text % ("KeMiaoJiang", "HY-惠", "MIO-KITCHEN"), justify='left',
              foreground='#87CEFA', font=(None, 12)).pack(side='top', padx=5, pady=120, expand=True)

    def tab6_content(self):
        ttk.Label(self.tab6, text=lang.toolbox, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH)
        ttk.Separator(self.tab6, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        tool_box = ToolBox(self.tab6)
        tool_box.gui()
        tool_box.pack(fill=BOTH, expand=True)

    def tab4_content(self):
        self.rotate_angle = 0
        debugger_num = 0

        def getColor():
            nonlocal debugger_num
            debugger_num += 1
            if debugger_num >= 5:
                debugger_num = 0
                a = Debugger()
                a.lift()
                a.focus_force()
            return f"#{hex(randrange(16, 256))[2:]}{hex(randrange(16, 256))[2:]}{hex(randrange(16, 256))[2:]}"

        def update_angle():
            self.rotate_angle = (self.rotate_angle + 10) % 180
            canvas.itemconfigure(text_item, angle=self.rotate_angle)

        canvas = tk.Canvas(self.tab4, width=400, height=100)
        canvas.pack()
        text_item = canvas.create_text(200, 50, text='MIO-KITCHEN', font=('Arial', 30), fill='white')

        canvas.tag_bind(text_item, '<B1-Motion>', lambda event: update_angle())
        canvas.tag_bind(text_item, '<Button-1>', lambda *x: canvas.itemconfigure(text_item, fill=getColor()))

        Label(self.tab4, text=lang.text111, font=(None, 15), fg='#00BFFF').pack(padx=10, pady=10)
        Label(self.tab4,
              text=lang.text128.format(settings.version, sys.version[:6], platform.system(), machine()),
              font=(None, 11), fg='#00aaff').pack(padx=10, pady=10)
        ttk.Label(self.tab4, text=f"{settings.language} By {lang.language_file_by}", foreground='orange',
                  background='gray').pack()
        Label(self.tab4, text=lang.text110, font=(None, 10)).pack(padx=10, pady=10, side='bottom')
        ttk.Label(self.tab4, text=lang.t63, style="Link.TLabel").pack()
        link = ttk.Label(self.tab4, text="Github: MIO-KITCHEN-SOURCE", cursor="hand2",
                         style="Link.TLabel")
        link.bind("<Button-1>", lambda *x: openurl("https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE"))
        link.pack()

    def setting_tab(self):
        def get_setting_button(item, master, text, on_v='1', off_v='0'):
            a = StringVar(value=getattr(settings, item))
            a.trace("w", lambda *x: settings.set_value(item, a.get()))
            ttk.Checkbutton(master, text=text, variable=a, onvalue=on_v,
                            offvalue=off_v,
                            style="Toggle.TButton").pack(padx=10, pady=10, fill=X)

        def get_cache_size():
            size = 0
            for root, _, files in os.walk(temp):
                try:
                    size += sum([os.path.getsize(os.path.join(root, name)) for name in files if
                                 not os.path.islink(os.path.join(root, name))])
                except:
                    logging.exception("Bugs")
            return size

        def clean_cache():
            try:
                re_folder(temp, quiet=True)
            except:
                logging.exception("Bugs")
            slo2.configure(text=hum_convert(get_cache_size()))

        self.show_local = StringVar()
        self.show_local.set(settings.path)
        Setting_Frame = ScrollFrame(self.tab3)
        Setting_Frame.gui()
        Setting_Frame.pack(fill=BOTH, expand=True)
        sf1 = ttk.Frame(Setting_Frame.label_frame)
        sf2 = ttk.Frame(Setting_Frame.label_frame)
        sf3 = ttk.Frame(Setting_Frame.label_frame)
        sf4 = ttk.Frame(Setting_Frame.label_frame, width=20)
        sf5 = ttk.Frame(Setting_Frame.label_frame)
        sf6 = ttk.Frame(Setting_Frame.label_frame)
        ttk.Label(sf1, text=lang.text124).pack(side='left', padx=10, pady=10)
        self.list2 = ttk.Combobox(sf1, textvariable=theme, state='readonly', values=["light", "dark"])
        self.list2.pack(padx=10, pady=10, side='left')
        self.list2.bind('<<ComboboxSelected>>', lambda *x: settings.set_theme())
        ###
        project_struct = StringVar(value=settings.project_struct)
        ttk.Label(sf5, text=lang.project_struct).pack(padx=10, pady=10, side='left')
        ttk.Radiobutton(sf5, text=lang.single, variable=project_struct, value='single').pack(padx=10, pady=10,
                                                                                             side='left')
        ttk.Radiobutton(sf5, text=lang.split, variable=project_struct, value='split').pack(padx=10, pady=10,
                                                                                           side='left')
        project_struct.trace("w", lambda *x: settings.set_value('project_struct', project_struct.get()))
        ###
        ttk.Label(sf3, text=lang.text125).pack(side='left', padx=10, pady=10)
        slo = ttk.Label(sf3, textvariable=self.show_local, wraplength=200)
        slo.bind('<Button-1>', lambda *x: windll.shell32.ShellExecuteW(None, "open", self.show_local.get(), None, None,
                                                                       1) if os.name == 'nt' else ...)
        slo.pack(padx=10, pady=10, side='left')
        ttk.Button(sf3, text=lang.text126, command=settings.modpath).pack(side="left", padx=10, pady=10)

        ttk.Label(sf2, text=lang.lang).pack(side='left', padx=10, pady=10)
        lb3 = ttk.Combobox(sf2, state='readonly', textvariable=language,
                           values=[str(i.rsplit('.', 1)[0]) for i in
                                   os.listdir(f"{cwd_path}/bin/languages")])
        ###
        ttk.Label(sf6, text=lang.cache_size).pack(side='left', padx=10, pady=10)
        slo2 = ttk.Label(sf6, text=hum_convert(get_cache_size()), wraplength=200)
        slo2.bind('<Button-1>', lambda *x: windll.shell32.ShellExecuteW(None, "open", self.show_local.get(), None, None,
                                                                        1) if os.name == 'nt' else ...)
        slo2.pack(padx=10, pady=10, side='left')
        ttk.Button(sf6, text=lang.clean, command=lambda: create_thread(clean_cache)).pack(side="left", padx=10, pady=10)
        context = StringVar(value=settings.contextpatch)

        def enable_contextpatch():
            if context.get() == '1':
                if ask_win(
                        lang.warn18, is_top=True):
                    settings.set_value('contextpatch', context.get())
                else:
                    context.set('0')
                    settings.set_value('contextpatch', context.get())
                    enable_cp.configure(state='off')
            else:
                settings.set_value('contextpatch', context.get())

        context.trace("w", lambda *x: enable_contextpatch())
        get_setting_button('ai_engine', sf4, lang.ai_engine)
        get_setting_button('magisk_not_decompress', sf4, lang.text142)
        get_setting_button('treff', sf4, lang.t61)
        enable_cp = ttk.Checkbutton(sf4, text=lang.context_patch, variable=context, onvalue='1',
                                    offvalue='0',
                                    style="Toggle.TButton")
        enable_cp.pack(padx=10, pady=10, fill=X)
        get_setting_button('auto_unpack', sf4, lang.auto_unpack)
        lb3.pack(padx=10, pady=10, side='left')
        lb3.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())
        for i in [sf1, sf2, sf3, sf5, sf6, sf4]: i.pack(padx=10, pady=7, fill='both')
        Setting_Frame.update_ui()
        ttk.Button(self.tab3, text=lang.t38, command=Updater).pack(padx=10, pady=10, fill=X)


# win = Tool()
animation = LoadAnim()
start = dti()

tool_self = os.path.normpath(os.path.abspath(sys.argv[0]))
temp = os.path.join(cwd_path, "bin", "temp").replace(os.sep, '/')
tool_log = f'{temp}/{time.strftime("%Y%m%d_%H-%M-%S", time.localtime())}_{v_code()}.log'
context_rule_file = os.path.join(cwd_path, 'bin', "context_rules.json")
states = States()
module_exec = os.path.join(cwd_path, 'bin', "exec.sh").replace(os.sep, '/')


# Some Functions for Upgrade


class Updater(Toplevel):

    def __init__(self):
        if states.update_window:
            self.destroy()
        super().__init__()
        self.title(lang.t38)
        self.protocol("WM_DELETE_WINDOW", self.close)
        states.update_window = True
        self.update_url = settings.update_url if settings.update_url else 'https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest'
        self.package_head = ''
        self.update_download_url = ''
        self.update_size = 0
        self.update_zip = ''
        self.update_assets = []
        f = ttk.Frame(self)
        ttk.Label(f, text='MIO-KITCHEN', font=(None, 20)).pack(side=LEFT, padx=5, pady=2)
        ttk.Label(f, text=settings.version, foreground='gray').pack(side=LEFT, padx=2, pady=2)
        f.pack(padx=5, pady=5, side=TOP)
        f2 = ttk.LabelFrame(self, text=lang.t39)
        self.notice = ttk.Label(f2, text=lang.t42)
        self.notice.pack(padx=5, pady=5)
        if states.run_source:
            ttk.Label(self, text=lang.t64, foreground='gray',
                      justify='center').pack(fill=X, pady=10,
                                             padx=10, anchor='center')
            move_center(self)
            return
        self.change_log = Text(f2, width=50, height=15)
        self.change_log.pack(padx=5, pady=5)
        f2.pack(fill=BOTH, padx=5, pady=5)
        self.progressbar = ttk.Progressbar(self, length=200, mode='determinate', orient=tkinter.HORIZONTAL, maximum=100
                                           )
        self.progressbar.pack(padx=5, pady=10)
        f3 = ttk.Frame(self)
        self.update_button = ttk.Button(f3, text=lang.t38, style='Accent.TButton',
                                        command=lambda: create_thread(self.get_update))
        ttk.Button(f3, text=lang.cancel, command=self.close).pack(fill=X, expand=True, side=LEFT,
                                                                  pady=10,
                                                                  padx=10)
        self.update_button.pack(fill=X, expand=True, side=LEFT,
                                pady=10,
                                padx=10)
        f3.pack(padx=5, pady=5, fill=X)
        if 'upgrade' in os.path.basename(tool_self) and settings.updating == '1':
            self.update_process2()
        elif 'tool' in os.path.basename(tool_self) and settings.updating == '2':
            self.update_process3()
        else:
            create_thread(self.get_update)
        self.resizable(width=False, height=False)
        move_center(self)

    def get_update(self):
        if self.update_button.cget('text') == lang.t40:
            self.update_button.configure(state='disabled', text=lang.t43)
            try:
                self.download()
                self.update_process()
            except (Exception, BaseException):
                self.notice.configure(text=lang.t44, foreground='red')
                self.update_button.configure(state='normal', text=lang.text37)
                self.progressbar.stop()
                logging.exception("Upgrade")
                return
            return
        self.notice.configure(text=lang.t45, foreground='')
        self.change_log.delete(1.0, tk.END)
        try:
            url = requests.get(self.update_url)
        except (Exception, BaseException) as e:
            if states.update_window:
                self.notice.configure(text=lang.t46, foreground='red')
                self.update_button.configure(state='normal', text=lang.text37)
                self.change_log.insert('insert', e)
            return
        if not states.update_window:
            return
        try:
            json_ = json.loads(url.text)
        except (Exception, BaseException):
            self.notice.configure(text=lang.t47, foreground='red')
            return
        new_version = json_.get('name')

        if new_version is None:
            self.notice.configure(text=lang.t46, foreground='red')
            self.update_button.configure(state='normal', text=lang.text37)
            self.change_log.insert('insert', url.text)
            return

        if not new_version.endswith(settings.version):
            self.package_head = new_version
            self.notice.configure(text=lang.t48 % new_version, foreground='orange')
            self.change_log.insert('insert', json_.get('body'))
            self.update_assets = json_.get('assets')
            self.get_download_url()
            self.update_button.configure(text=lang.text37 if not self.update_download_url else lang.t40)
        else:
            self.notice.configure(text=lang.t49, foreground='green')
            self.change_log.insert('insert', json_.get('body'))

    def get_download_url(self):
        package = self.package_head
        if platform.system() == 'Windows':
            package += '-win.zip'
        elif platform.system() == 'Linux':
            package += '-linux.zip'
        elif platform.system() == 'Darwin':
            package += '-macos-intel.zip' if platform.machine() == 'x86_64' else '-macos.zip'
        for i in self.update_assets:
            if i.get('name') == package:
                if platform.machine() in ['AMD64', 'X86_64', 'x86_64']:
                    self.update_download_url = i.get('browser_download_url')
                    self.update_size = i.get('size')
                    return
                else:
                    break
        self.notice.configure(text=lang.t50, foreground='red')

    def download(self):
        if not os.path.exists(temp):
            os.makedirs(temp)
        mode = True
        self.progressbar.configure(mode='indeterminate')
        self.progressbar.start()
        self.update_zip = os.path.normpath(
            os.path.join(temp, os.path.basename(self.update_download_url)))
        for percentage, _, _, _, _ in download_api(self.update_download_url, temp,
                                                   size_=self.update_size):
            if not states.update_window:
                return
            if percentage != 'None':
                if mode:
                    self.progressbar.configure(mode='determinate')
                    mode = False
                    self.progressbar.stop()
                self.progressbar['value'] = percentage
                self.progressbar.update()
        self.progressbar['value'] = 100
        self.progressbar.update()

    # fixme:Rewrite it.
    def update_process(self):
        [terminate_process(i) for i in states.open_pids]
        self.notice.configure(text=lang.t51)
        update_files = []
        with zipfile.ZipFile(self.update_zip, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if file != ('tool' + ('' if os.name == 'posix' else '.exe')):
                    try:
                        zip_ref.extract(file, cwd_path)
                    except PermissionError:
                        zip_ref.extract(file, temp)
                        update_files.append(file)
                else:
                    zip_ref.extract(file, os.path.join(cwd_path, "bin"))
        update_dict = {
            'updating': '1',
            'language': settings.language,
            'oobe': settings.oobe,
            'new_tool': os.path.join(cwd_path, "bin", "tool" + ('' if os.name != 'nt' else '.exe')),
            "version_old": settings.version,
            "update_files": ' '.join(update_files)
        }
        for i in update_dict.keys():
            settings.set_value(i, update_dict.get(i, ''))
        shutil.copy(os.path.join(cwd_path, "bin", "tool" + ('' if os.name != 'nt' else '.exe')),
                    os.path.normpath(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe'))))
        subprocess.Popen(
            [os.path.normpath(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe')))],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        terminate_process(os.getpid())

    def update_process2(self):
        self.notice.configure(text=lang.t51)
        time.sleep(2)
        if hasattr(settings, 'update_files'):
            for i in settings.update_files.split(' '):
                try:
                    real = i
                    path = os.path.join(temp, real)
                except (KeyError, ValueError):
                    continue
                if calculate_md5_file(path) == calculate_md5_file(os.path.join(cwd_path, real)):
                    continue
                if os.path.exists(path):
                    os.rename(path, os.path.join(cwd_path, real))
                else:
                    logging.warning(path)

        if os.path.exists(settings.new_tool):
            shutil.copyfile(settings.new_tool,
                            os.path.normpath(os.path.join(cwd_path, "tool" + ('' if os.name != 'nt' else '.exe'))))
            settings.set_value('updating', '2')
            subprocess.Popen([os.path.normpath(os.path.join(cwd_path, "tool" + ('' if os.name != 'nt' else '.exe')))],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            terminate_process(os.getpid())
        else:
            self.notice.configure(text=lang.t41, foreground='red')
            self.update_button.configure(state='normal', text=lang.text37)
            settings.set_value('version', settings.version_old)

    def update_process3(self):
        self.notice.configure(text=lang.t52)
        time.sleep(2)
        if os.path.exists(settings.new_tool):
            try:
                if os.path.isfile(settings.new_tool):
                    os.remove(settings.new_tool)
                if os.path.isfile(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe'))):
                    os.remove(os.path.normpath(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe'))))
                if os.path.exists(temp):
                    shutil.rmtree(temp)
                os.makedirs(temp, exist_ok=True)
            except (IOError, IsADirectoryError, FileNotFoundError, PermissionError):
                logging.exception('Bugs')
            settings.set_value('updating', '')
            settings.set_value('new_tool', '')
            subprocess.Popen([os.path.normpath(os.path.join(cwd_path, "tool" + ('' if os.name != 'nt' else '.exe')))],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            terminate_process(os.getpid())
        else:
            self.notice.configure(text=lang.t41, foreground='red')
            self.update_button.configure(state='normal', text=lang.text37)
            settings.set_value('version', settings.version_old)

    def close(self):
        states.update_window = False
        self.destroy()


def error(code, desc="unknown error"):
    if settings.debug_mode == 'No':
        win.withdraw()
    sv_ttk.use_dark_theme()
    er: Toplevel = Toplevel()
    img = open_img(BytesIO(images.error_logo_byte)).resize((100, 100))
    pyt = PhotoImage(img)
    Label(er, image=pyt).pack(padx=10, pady=10)
    er.protocol("WM_DELETE_WINDOW", win.destroy)
    er.title(f"Program crash! [{settings.version}]")
    er.lift()
    er.resizable(False, False)
    ttk.Label(er, text=f"Error:0x{code}", font=(None, 20), foreground='red').pack(padx=10, pady=10)
    ttk.Label(er, text="Dont Worry! Its not your problem.\nYou just need to Report the bug to us.",
              font=(None, 10)).pack(
        padx=10, pady=10)
    scroll = ttk.Scrollbar(er)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    te = Text(er, height=20, width=60)
    sys.stdout = StdoutRedirector(te)
    scroll.config(command=te.yview)
    te.pack(padx=10, pady=10, fill=BOTH)
    te.insert('insert', desc)
    te.config(yscrollcommand=scroll.set)
    ttk.Label(er, text=f"The Log File Is: {tool_log}", font=(None, 10)).pack(padx=10, pady=10)
    ttk.Button(er, text="Report",
               command=lambda: openurl("https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/issues"),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Generate Bug Report",
               command=lambda: create_thread(Generate_Bug_Report),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Restart",
               command=lambda: restart(er),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Exit", command=win.destroy).pack(side=LEFT, padx=10, pady=10, expand=True, fill=BOTH)
    move_center(er)
    er.wait_window()
    sys.exit()


class Welcome(ttk.Frame):
    def __init__(self):
        super().__init__(master=win)
        self.pack(fill=BOTH, expand=True)

        self.oobe = int(settings.oobe)
        states.in_oobe = True

        self.frames = {
            0: self.hello,
            1: self.main,
            2: self.set_workdir,
            3: self.license,
            4: self.private,
            5: self.done
        }
        self.frame = ttk.Frame(self)
        self.frame.pack(expand=1, fill=BOTH)
        self.button_frame = ttk.Frame(self)
        self.back = ttk.Button(self.button_frame, text=lang.back_step, command=lambda: self.change_page(self.oobe - 1))
        self.back.pack(fill=X, padx=5, pady=5, side='left', expand=1)
        self.next = ttk.Button(self.button_frame, text=lang.text138, command=lambda: self.change_page(self.oobe + 1))
        self.next.pack(fill=X, padx=5, pady=5, side='right', expand=1)
        self.button_frame.pack(expand=1, fill=X, padx=5, pady=5, side='bottom')
        self.change_page(self.oobe)
        move_center(win)
        self.wait_window()
        states.in_oobe = False

    def change_page(self, step: int = None):
        if not step or step not in self.frames.keys():
            step = 0
        self.oobe = step
        settings.set_value('oobe', step)
        for i in self.frame.winfo_children():
            i.destroy()
        move_center(win)
        self.frames[step]()
        if step == min(self.frames.keys()):
            self.back.config(state='disabled')
        else:
            self.back.config(state='normal')
        if step == max(self.frames.keys()):
            self.next.config(text=lang.text34, command=self.destroy)
        else:
            if self.next.cget('text') != lang.text138:
                self.next.config(text=lang.text138, command=lambda: self.change_page(self.oobe + 1))

    def hello(self):
        ttk.Label(self.frame, text=lang.text135, font=(None, 40)).pack(padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.text137, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)

    def main(self):
        ttk.Label(self.frame, text=lang.text129, font=(None, 20)).pack(padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb3_ = ttk.Combobox(self.frame, state='readonly', textvariable=language,
                            values=[i.rsplit('.', 1)[0] for i in
                                    os.listdir(f"{cwd_path}/bin/languages")])
        lb3_.pack(padx=10, pady=10, side='top', fill=BOTH)
        lb3_.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())

    def set_workdir(self):
        def modpath():
            if not (folder := filedialog.askdirectory()):
                return
            settings.set_value("path", folder)
            show_local.set(folder)

        show_local = StringVar()
        show_local.set(settings.path)
        ttk.Label(self.frame, text=lang.text125, font=(None, 20)).pack(padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        slo = ttk.Label(self.frame, textvariable=show_local, wraplength=200)
        slo.bind('<Button-1>', lambda *x: windll.shell32.ShellExecuteW(None, "open", show_local.get(), None, None,
                                                                       1) if os.name == 'nt' else ...)
        slo.pack(padx=10, pady=10, side='left')
        ttk.Button(self.frame, text=lang.text126, command=modpath).pack(side="left", padx=10, pady=10)

    def license(self):
        lce = StringVar()

        def load_license():
            te.delete(1.0, tk.END)
            with open(f"{cwd_path}/bin/licenses/{lce.get()}.txt", 'r',
                      encoding='UTF-8') as f:
                te.insert('insert', f.read())

        lb = ttk.Combobox(self.frame, state='readonly', textvariable=lce,
                          values=[i.rsplit('.')[0] for i in os.listdir(f"{cwd_path}/bin/licenses") if
                                  i != 'private.txt'])
        lb.bind('<<ComboboxSelected>>', lambda *x: load_license())
        lb.current(0)
        ttk.Label(self.frame, text=lang.text139, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb.pack(padx=10, pady=10, side='top', fill=X)
        f = Frame(self.frame)
        scrollbar = ttk.Scrollbar(f, orient='vertical')
        te = Text(f, height=10)
        te.pack(fill=BOTH, side=LEFT, expand=True)
        scrollbar.config(command=te.yview)
        scrollbar.pack(fill=BOTH, side='right', expand=True)
        te.config(yscrollcommand=scrollbar.set)
        f.pack(fill=BOTH, side='top', expand=True)
        load_license()
        ttk.Label(self.frame, text=lang.t1).pack()

    def private(self):
        ttk.Label(self.frame, text=lang.t2, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        with open(os.path.join(cwd_path, "bin", "licenses", "private.txt"), 'r',
                  encoding='UTF-8') as f:
            (te := Text(self.frame, height=10)).insert('insert', f.read())
        te.pack(fill=BOTH, expand=True)
        ttk.Label(self.frame, text=lang.t3).pack()

    def done(self):
        ttk.Label(self.frame, text=lang.t4, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.t5, font=(None, 20)).pack(
            side='top', fill=BOTH, padx=10, pady=10, expand=True)


class SetUtils:
    def __init__(self, set_ini: str = None, load=True):
        self.project_struct = 'single'
        self.auto_unpack = '0'
        self.treff = '0'
        if set_ini:
            self.set_file = set_ini
        else:
            self.set_file = os.path.join(cwd_path, "bin", "setting.ini")
        self.plugin_repo = None
        self.contextpatch = '0'
        self.oobe = '0'
        self.path = None
        self.bar_level = '0.9'
        self.ai_engine = '0'
        self.version = 'basic'
        self.version_old = 'unknown'
        self.language = 'English'
        self.magisk_not_decompress = '0'
        self.updating = ''
        self.new_tool = ''
        self.cmd_exit = '0'
        self.cmd_invisible = '0'
        self.debug_mode = 'No'
        self.theme = 'dark'
        self.update_url = 'https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest'
        self.config = ConfigParser()
        if os.access(self.set_file, os.F_OK):
            if load:
                self.load()
        else:
            sv_ttk.set_theme("dark")
            error(1,
                  'Some necessary files were lost, please reinstall this software to fix the problem!')
        if hasattr(self, 'custom_system'):
            if not self.custom_system.strip():
                self.custom_system = platform.system()
        else:
            self.custom_system = platform.system()
        self.tool_bin = os.path.join(cwd_path, 'bin', self.custom_system, platform.machine()) + os.sep

    def load(self):
        self.config.read(self.set_file)
        for i in self.config.items('setting'):
            setattr(self, i[0], i[1])
        if os.path.exists(self.path):
            if not self.path:
                self.path = os.getcwd()
        else:
            self.path = utils.prog_path
        language.set(self.language)
        self.load_language(language.get())
        theme.set(self.theme)
        sv_ttk.set_theme(self.theme)
        if is_pro:
            if 'active_code' not in self.__dir__():
                self.active_code = 'None'
            verify.verify(self.active_code)
        if self.treff == "1":
            win.attributes("-alpha", self.bar_level)
        else:
            win.attributes("-alpha", 1)

    @staticmethod
    def load_language(name):
        lang_file = f'{cwd_path}/bin/languages/{name}.json'
        _lang: dict = {}
        if not name and not os.path.exists(f'{cwd_path}/bin/languages/English.json'):
            error(1)
        elif not os.path.exists(lang_file):
            _lang = JsonEdit(f'{cwd_path}/bin/languages/English.json').read()
        else:
            _lang = JsonEdit(lang_file).read()
        lang.second = JsonEdit(f'{cwd_path}/bin/languages/English.json').read()
        [setattr(lang, n, v) for n, v in _lang.items()]

    def set_value(self, name, value):
        self.config.read(self.set_file)
        self.config.set("setting", name, value)
        with open(self.set_file, 'w', encoding='utf-8') as fil:
            self.config.write(fil)
        setattr(self, name, value)
        if name in ['treff', 'barlevel', 'theme']:
            self.load()

    def set_theme(self):
        print(lang.text100 + theme.get())
        try:
            self.set_value("theme", theme.get())
            sv_ttk.set_theme(theme.get())
            animation.load_gif(open_img(BytesIO(getattr(images, f"loading_{win.list2.get()}_byte"))))
        except Exception as e:
            logging.exception('Bugs')
            win.message_pop(lang.text101 % (theme.get(), e))

    def set_language(self):
        print(lang.text129 + language.get())
        try:
            self.set_value("language", language.get())
            self.load_language(language.get())
            if not states.in_oobe:
                if ask_win(lang.t36):
                    restart()
        except Exception as e:
            logging.exception('Bugs')
            print(lang.t130, e)

    def modpath(self):
        if not (folder := filedialog.askdirectory()):
            return
        self.set_value("path", folder)
        win.show_local.set(folder)
        self.load()


settings = SetUtils(load=False)


def re_folder(path, quiet=False):
    if os.path.exists(path): rmdir(path, quiet)
    os.makedirs(path, exist_ok=True)


@animation
def un_dtbo(bn: str = 'dtbo') -> None:
    if not (dtboimg := findfile(f"{bn}.img", work := project_manger.current_work_path())):
        print(lang.warn3.format(bn))
        return
    re_folder(f"{work}/{bn}")
    re_folder(f"{work}/{bn}/dtbo")
    re_folder(f"{work}/{bn}/dts")
    try:
        mkdtboimg.dump_dtbo(dtboimg, f"{work}/{bn}/dtbo/dtbo")
    except Exception as e:
        logging.exception("Bugs")
        print(lang.warn4.format(e))
        return
    for dtbo in os.listdir(f"{work}/{bn}/dtbo"):
        if dtbo.startswith("dtbo."):
            print(lang.text4.format(dtbo))
            call(
                exe=['dtc', '-@', '-I', 'dtb', '-O', 'dts', f'{work}/{bn}/dtbo/{dtbo}', '-o',
                     os.path.join(work, bn, 'dts', 'dts.' + os.path.basename(dtbo).rsplit('.', 1)[1])],
                out=False)
    print(lang.text5)
    try:
        os.remove(dtboimg)
    except (Exception, BaseException):
        logging.exception('Bugs')
    rmdir(f"{work}/dtbo/dtbo")


@animation
def pack_dtbo() -> bool:
    work = project_manger.current_work_path()
    if not os.path.exists(f"{work}/dtbo/dts") or not os.path.exists(f"{work}/dtbo"):
        print(lang.warn5)
        return False
    re_folder(f"{work}/dtbo/dtbo")
    for dts in os.listdir(f"{work}/dtbo/dts"):
        if dts.startswith("dts."):
            print(f"{lang.text6}:{dts}")
            call(
                exe=['dtc', '-@', '-I', 'dts', '-O', 'dtb', os.path.join(work, 'dtbo', 'dts', dts), '-o',
                     os.path.join(work, 'dtbo', 'dtbo', 'dtbo.' + os.path.basename(dts).rsplit('.', 1)[1])],
                out=False)
    print(f"{lang.text7}:dtbo.img")
    list_ = [os.path.join(work, "dtbo", "dtbo", f) for f in os.listdir(f"{work}/dtbo/dtbo") if
             f.startswith("dtbo.")]
    mkdtboimg.create_dtbo(project_manger.current_work_output_path() + "dtbo.img",
                          sorted(list_, key=lambda x: int(x.rsplit('.')[1])), 4096)
    rmdir(f"{work}/dtbo")
    print(lang.text8)
    return True


@animation
def logo_dump(file_path, output: str = None, output_name: str = "logo"):
    if output is None:
        output = project_manger.current_work_path()
    if not os.path.exists(file_path):
        win.message_pop(lang.warn3.format(output_name))
        return False
    re_folder(output + output_name)
    LogoDumper(file_path, output + output_name).unpack()


@animation
def logo_pack(origin_logo=None) -> int:
    work = project_manger.current_work_path()
    if not origin_logo:
        origin_logo = findfile('logo.img', work)
    logo = f"{work}/logo-new.img"
    if not os.path.exists(dir_ := f"{work}/logo") or not os.path.exists(origin_logo):
        print(lang.warn6)
        return 1
    utils.LogoDumper(origin_logo, logo, dir_).repack()
    os.remove(origin_logo)
    os.rename(logo, origin_logo)
    rmdir(dir_)
    return 1


class IconGrid(tk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.icons = []
        self.apps = {}
        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both")
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scrollable_frame.bind("<Configure>", lambda *x: self.on_frame_configure())
        # Bind mouse wheel event to scrollbar
        self.master.bind_all("<MouseWheel>",
                             lambda event: self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

    def add_icon(self, icon, id_, num=4):
        self.icons.append(icon)
        self.apps[id_] = icon
        row = (len(self.icons) - 1) // num
        col = (len(self.icons) - 1) % num
        icon.grid(row=row, column=col, padx=10, pady=10)

    def clean(self):
        for i in self.icons:
            try:
                i.destroy()
            except TclError:
                pass
        self.icons.clear()
        self.update_idletasks()

    def remove(self, id_):
        try:
            self.apps.get(id_).destroy()
        except (TclError, Exception):
            logging.exception("Bugs")

    def on_frame_configure(self):
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"), highlightthickness=0)


module_error_codes = ModuleErrorCodes


class ModuleManager:
    def __init__(self):
        sys.stdout_origin = sys.stdout
        sys.stdout = DevNull()
        self.module_dir = os.path.join(cwd_path, "bin", "module")
        self.uninstall_gui = self.UninstallMpk
        self.new = self.New
        self.new.module_dir = self.module_dir
        self.uninstall_gui.module_dir = self.module_dir
        self.get_installed = lambda id_: os.path.exists(os.path.join(self.module_dir, id_))
        self.addon_loader = loader
        self.addon_entries = Entry
        create_thread(self.load_plugins)

    def is_virtual(self, id_):
        return id_ in self.addon_loader.virtual.keys()

    def get_name(self, id_):
        if self.is_virtual(id_):
            return self.addon_loader.virtual[id_].get("name", id_)
        return name if (name := self.get_info(id_, 'name')) else id_

    def list_packages(self):
        for i in os.listdir(self.module_dir):
            if self.get_installed(i):
                yield i

    def load_plugins(self):
        if not os.path.exists(self.module_dir) or not os.path.isdir(self.module_dir):
            os.makedirs(self.module_dir, exist_ok=True)
        for i in self.list_packages():
            script_path = f"{self.module_dir}/{i}"
            if os.path.exists(f"{script_path}/main.py") and imp:
                try:
                    module = imp.load_source('__maddon__', f"{script_path}/main.py")
                    if hasattr(module, 'entrances'):
                        for entry, func in module.entrances.items():
                            self.addon_loader.register(i, entry, func)
                    elif hasattr(module, 'main'):
                        self.addon_loader.register(i, self.addon_entries.main, module.main)
                    else:
                        print(
                            f"Can't registry Module {self.get_name(i)} as Plugin, Check if enterances or main function in it.")
                except Exception:
                    logging.exception('Bugs')

    def get_info(self, id_: str, item: str, default: str = None) -> str:
        if not default:
            default = ''
        info_file = f'{self.module_dir}/{id_}/info.json'
        if not os.path.exists(info_file):
            return default
        with open(info_file, 'r', encoding='UTF-8') as f:
            return json.load(f).get(item, default)

    @animation
    def run(self, id_) -> int:
        if not current_project_name.get():
            print(lang.warn1)
            return 1
        if id_:
            value = id_
        else:
            print(lang.warn2)
            return 1
        script_path = self.module_dir + f"/{value}/"
        if not self.is_virtual(id_):
            name = self.get_name(id_)
            with open(os.path.join(script_path, "info.json"), 'r', encoding='UTF-8') as f:
                data = json.load(f)
                for n in data['depend'].split():
                    if not os.path.exists(os.path.join(self.module_dir, n)):
                        print(lang.text36 % (name, n, n))
                        return 2
        if os.path.exists(f"{script_path}/main.json"):
            values = self.Parse(f"{script_path}/main.json")
            if values.cancel:
                return 1
            values = values.gavs
        else:
            values = {}
        if os.path.exists(script_path + "main.sh"):
            if not os.path.exists(temp):
                re_folder(temp)
            exports = ''
            if os.path.exists(script_path + "main.sh"):
                if values:
                    for va in values.keys():
                        if gva := values[va].get():
                            exports += f"export {va}='{gva}';"
                    values.clear()
                exports += f"export tool_bin='{settings.tool_bin.replace(os.sep, '/')}';export version='{settings.version}';export language='{settings.language}';export bin='{script_path.replace(os.sep, '/')}';"
                exports += f"export moddir='{self.module_dir.replace(os.sep, '/')}';export project_output='{project_manger.current_work_output_path()}';export project='{project_manger.current_work_path()}';"

            if os.path.exists(script_path + "main.sh"):
                shell = 'ash' if os.name == 'posix' else 'bash'
                call(['busybox', shell, '-c',
                      f"{exports}exec {module_exec} {(script_path + 'main.sh').replace(os.sep, '/')}"])
            del exports
        elif os.path.exists(script_path + "main.py") and imp:
            self.addon_loader.run(id_, Entry.main, mapped_args=values)
        elif self.is_virtual(id_):
            self.addon_loader.run(id_, Entry.main, mapped_args=values)
        elif not os.path.exists(self.module_dir + os.sep + value):
            win.message_pop(lang.warn7.format(value))
            list_pls_plugin()
            win.tab7.lift()
        else:
            print(lang.warn8)
        return 0

    @staticmethod
    def check_mpk(mpk):
        if not mpk or not os.path.exists(mpk) or not zipfile.is_zipfile(mpk):
            return module_error_codes.IsBroken, ''
        with zipfile.ZipFile(mpk) as f:
            if 'info' not in f.namelist():
                return module_error_codes.IsBroken, ''
        return module_error_codes.Normal, ''

    def install(self, mpk):
        check_mpk_result = self.check_mpk(mpk)
        if check_mpk_result[0] != module_error_codes.Normal:
            return check_mpk_result
        mconf = ConfigParser()
        with zipfile.ZipFile(mpk) as f:
            with f.open('info') as info_file:
                mconf.read_string(info_file.read().decode('utf-8'))
        try:
            supports = mconf.get('module', 'supports').split()
            if platform.system() not in supports:
                return module_error_codes.PlatformNotSupport, ''
        except (Exception, BaseException):
            logging.exception('Bugs')
        for dep in mconf.get('module', 'depend').split():
            if not os.path.isdir(os.path.join(cwd_path, "bin", "module", dep)):
                return module_error_codes.DependsMissing, dep
        if os.path.exists(os.path.join(self.module_dir, mconf.get('module', 'identifier'))):
            rmtree(os.path.join(self.module_dir, mconf.get('module', 'identifier')))
        install_dir = mconf.get('module', 'identifier')
        with zipfile.ZipFile(mpk, 'r') as myfile:
            with myfile.open(mconf.get('module', 'resource'), 'r') as inner_file:
                fz = zipfile.ZipFile(inner_file, 'r')
                extracted_size = 0
                for file in fz.namelist():
                    try:
                        file = str(file).encode('cp437').decode('gbk')
                    except (Exception, BaseException):
                        file = str(file).encode('utf-8').decode('utf-8')
                    info = fz.getinfo(file)
                    extracted_size += info.file_size
                    fz.extract(file, str(os.path.join(cwd_path, "bin", "module", install_dir)))
        try:
            depends = mconf.get('module', 'depend')
        except (Exception, BaseException):
            depends = ''
        minfo = {}
        for n, v in mconf.items('module'):
            minfo[n] = v
        minfo['depend'] = depends
        with open(os.path.join(cwd_path, "bin", "module", mconf.get('module', 'identifier'), "info.json"),
                  'w', encoding='utf-8') as f:
            json.dump(minfo, f, indent=2, ensure_ascii=False)
        with zipfile.ZipFile(mpk) as mpk_f:
            if 'icon' in mpk_f.namelist():
                with open(os.path.join(self.module_dir, mconf.get('module', 'identifier'), "icon"),
                          'wb') as f:
                    with mpk_f.open('icon') as i:
                        f.write(i.read())

        list_pls_plugin()
        return module_error_codes.Normal, ''

    @animation
    def export(self, id_: str):
        name: str = self.get_name(id_)
        if self.is_virtual(id_):
            print(f"{name} is a virtual plugin!")
            return
        if not id_:
            win.message_pop(lang.warn2)
            return 1
        with open(os.path.join(self.module_dir, (value := id_), "info.json"), 'r',
                  encoding='UTF-8') as f:
            data: dict = json.load(f)
            data.setdefault('resource', "main.zip")
            (info_ := ConfigParser())['module'] = data
            info_.write(buffer2 := StringIO())
        with zipfile.ZipFile((buffer := BytesIO()), 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk:
            for i in utils.get_all_file_paths(self.module_dir + os.sep + value):
                arch_name = str(i).replace(self.module_dir + os.sep + value, '')
                if os.path.basename(i) in ['info.json', 'icon']:
                    continue
                print(f"{lang.text1}:{arch_name}")
                try:
                    mpk.write(str(i), arcname=arch_name)
                except Exception as e:
                    logging.exception('Bugs')
                    print(lang.text2.format(i, e))
        with zipfile.ZipFile(os.path.join(settings.path, str(name) + ".mpk"), 'w',
                             compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk2:
            mpk2.writestr('main.zip', buffer.getvalue())
            mpk2.writestr('info', buffer2.getvalue())
            if os.path.exists(os.path.join(self.module_dir, value, 'icon')):
                mpk2.write(os.path.join(self.module_dir, value, 'icon'), 'icon')
            del buffer2, buffer
        print(lang.t15 % f"{settings.path}/{name}.mpk") if os.path.exists(f"{settings.path}/{name}.mpk") else print(
            lang.t16 % f"{settings.path}/{name}.mpk")

    class New(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.text115)
            if not hasattr(self, 'module_dir'):
                self.module_dir = os.path.join(cwd_path, "bin", "module")
            self.gui()
            move_center(self)

        @staticmethod
        def label_entry(master, text, side, value: str = ''):
            frame = Frame(master)
            ttk.Label(frame, text=text).pack(padx=5, pady=5, side=LEFT)
            entry_value = tk.StringVar(value=value)
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
                editor.main(path, 'main.py', lexer=pygments.lexers.PythonLexer)
            elif not os.path.exists(f'{path}/main.sh'):
                with open(f'{path}/main.sh', 'w+', encoding='utf-8', newline='\n') as sh:
                    sh.write("echo 'MIO-KITCHEN'")
                editor.main(path, "main.sh")
            else:
                editor.main(path, 'main.sh')

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
            f.pack(padx=5, pady=5, side=LEFT)
            f = ttk.Frame(f_b)
            ttk.Label(f, text=lang.t24).pack(padx=5, pady=5, expand=1)
            self.intro = Text(f, width=40, height=15)
            self.intro.pack(fill=BOTH, padx=5, pady=5, side=RIGHT)
            f.pack(padx=5, pady=5, side=LEFT)
            f_b.pack(padx=5, pady=5)
            ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
            ttk.Button(self, text=lang.text115, command=self.create).pack(fill=X, padx=5, pady=5)

        def create(self):
            if not self.identifier.get():
                return
            if module_manager.get_installed(self.identifier.get()):
                info_win(lang.warn19 % self.identifier.get())
                return
            data = {
                "name": self.name.get(),
                "author": 'MIO-KITCHEN' if not self.aou.get() else self.aou.get(),
                "version": self.ver.get(),
                "identifier": (iden := self.identifier.get()),
                "describe": self.intro.get(1.0, tk.END),
                "depend": self.dep.get()
            }
            self.destroy()

            if not os.path.exists(f'{self.module_dir}/{iden}'):
                os.makedirs(f'{self.module_dir}/{iden}')
            with open(self.module_dir + f"/{iden}/info.json", 'w+', encoding='utf-8',
                      newline='\n') as js:
                json.dump(data, js, ensure_ascii=False, indent=4)
            list_pls_plugin()
            self.editor_(iden)

    # fixme:Rewrite it!!!
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
                       command=lambda: print(command)).pack(side='left')

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
            input_frame.pack(fill=X)
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
                       command=lambda: create_thread(self.creat_temp)).pack(
                fill=X,
                side='bottom')
            move_center(self)
            self.wait_window()

        def creat_temp(self):
            os.makedirs(temp, exist_ok=True)
            self.destroy()

    class UninstallMpk(Toplevel):

        def __init__(self, id_: str, wait=False):
            super().__init__()
            self.arr = {}
            self.uninstall_b = None
            self.wait = wait
            if not hasattr(self, 'module_dir'):
                self.module_dir = os.path.join(cwd_path, "bin", "module")
            if id_ and module_manager.get_installed(id_):
                self.check_pass = True
                self.value = id_
                self.value2 = module_manager.get_name(id_)
                self.lsdep()
            else:
                self.check_pass = False
                self.value = None
            self.ask()

        def ask(self):
            try:
                self.attributes('-topmost', 'true')
            except (Exception, BaseException):
                logging.exception('Bugs')
            self.title(lang.t6)
            move_center(self)
            if not module_manager.is_virtual(self.value) and self.check_pass:
                ttk.Label(self, text=lang.t7 % self.value2, font=(None, 30)).pack(padx=10, pady=10, fill=BOTH,
                                                                                  expand=True)
            elif not self.check_pass:
                ttk.Label(self, text=lang.warn2, font=(None, 30)).pack(padx=10, pady=10, fill=BOTH,
                                                                       expand=True)
            else:
                ttk.Label(self, text="The Plugin %s is virtual." % self.value2, font=(None, 30)).pack(padx=10, pady=10,
                                                                                                      fill=BOTH,
                                                                                                      expand=True)
            if self.arr:
                ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
                ttk.Label(self, text=lang.t8, font=(None, 15)).pack(padx=10, pady=10, fill=BOTH,
                                                                    expand=True)
                te = Listbox(self, highlightthickness=0, activestyle='dotbox')
                for i in self.arr.keys():
                    te.insert("end", self.arr.get(i, 'None'))
                te.pack(fill=BOTH, padx=10, pady=10)
            ttk.Button(self, text=lang.cancel, command=self.destroy).pack(fill=X, expand=True, side=LEFT,
                                                                          pady=10,
                                                                          padx=10)
            if not module_manager.is_virtual(self.value) and self.check_pass:
                self.uninstall_b = ttk.Button(self, text=lang.ok, command=self.uninstall, style="Accent.TButton")
                self.uninstall_b.pack(fill=X, expand=True, side=LEFT, pady=10, padx=10)
            if self.wait:
                self.wait_window()

        def lsdep(self, name=None):
            if not name:
                name = self.value
            for i in [i for i in module_manager.list_packages()]:
                for n in module_manager.get_info(i, 'depend').split():
                    if name == n:
                        self.arr[i] = module_manager.get_info(i, 'name')
                        self.lsdep(i)
                        # 检测到依赖后立即停止
                        break

        def uninstall(self):
            if not self.uninstall_b:
                return
            else:
                self.uninstall_b.config(state='disabled')
            for i in self.arr.keys():
                self.remove(i, self.arr.get(i, 'None'))
            self.remove(self.value, self.value2)
            self.destroy()

        def remove(self, name=None, show_name='') -> None:
            module_path = f"{self.module_dir}/{name}"
            if name:
                print(lang.text29.format(name if not show_name else show_name))
                self.uninstall_b.config(text=lang.text29.format(name if not show_name else show_name))
                if os.path.exists(module_path):
                    try:
                        rmtree(module_path)
                    except PermissionError as e:
                        logging.exception('Bugs')
                        print(e)
                if os.path.exists(module_path):
                    win.message_pop(lang.warn9, 'orange')
                else:
                    print(lang.text30)
                    self.uninstall_b.config(text=lang.text30)
                    try:
                        list_pls_plugin()
                    except (Exception, BaseException):
                        logging.exception('Bugs')
            else:
                win.message_pop(lang.warn2)


module_manager = ModuleManager()


class MpkMan(ttk.Frame):
    def __init__(self):
        super().__init__(master=win.tab7)
        self.pack(padx=10, pady=10, fill=BOTH)
        self.chosen = StringVar(value='')
        self.moduledir = module_manager.module_dir
        if not os.path.exists(self.moduledir):
            os.makedirs(self.moduledir)
        self.images_ = {}

    def list_pls(self):
        # self.pls.clean()
        for i in self.pls.apps.keys():
            if not module_manager.get_installed(i):
                self.pls.remove(i)
        for i in module_manager.addon_loader.virtual.keys():
            if i in self.pls.apps.keys():
                continue
            self.images_[i] = PhotoImage(data=images.none_byte)
            icon = tk.Label(self.pls.scrollable_frame,
                            image=self.images_[i],
                            compound="center",
                            text=module_manager.addon_loader.virtual[i].get('name'),
                            bg="#4682B4",
                            wraplength=70,
                            justify='center')
            icon.bind('<Double-Button-1>', lambda event, ar=i: create_thread(module_manager.run, ar))
            icon.bind('<Button-3>', lambda event, ar=i: self.popup(ar, event))
            self.pls.add_icon(icon, i)

        for i in os.listdir(self.moduledir):
            if i in self.pls.apps.keys():
                continue
            if not os.path.isdir(os.path.join(self.moduledir, i)):
                continue
            if not os.path.exists(os.path.join(self.moduledir, i, "info.json")):
                try:
                    rmtree(os.path.join(self.moduledir, i))
                finally:
                    continue
            if os.path.isdir(self.moduledir + os.sep + i):
                self.images_[i] = PhotoImage(
                    open_img(os.path.join(self.moduledir, i, 'icon')).resize((70, 70))) if os.path.exists(
                    os.path.join(self.moduledir, i, 'icon')) else PhotoImage(data=images.none_byte)
                data = JsonEdit(os.path.join(self.moduledir, i, "info.json")).read()
                icon = tk.Label(self.pls.scrollable_frame,
                                image=self.images_[i],
                                compound="center",
                                text=data.get('name'),
                                bg="#4682B4",
                                wraplength=70,
                                justify='center')
                icon.bind('<Double-Button-1>', lambda event, ar=i: create_thread(module_manager.run, ar))
                icon.bind('<Button-3>', lambda event, ar=i: self.popup(ar, event))
                self.pls.add_icon(icon, i)

    def refresh(self):
        self.pls.clean()
        self.pls.apps.clear()
        self.list_pls()

    def popup(self, name, event):
        self.chosen.set(name)
        self.rmenu2.post(event.x_root, event.y_root)

    def gui(self):
        global list_pls_plugin
        list_pls_plugin = self.list_pls

        ttk.Label(self, text=lang.text19, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH, side=LEFT)
        ttk.Button(self, text='Mpk Store', command=lambda: create_thread(MpkStore)).pack(side="right", padx=10, pady=10)
        ttk.Separator(win.tab7, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        a = Label(win.tab7, text=lang.text24)
        a.bind('<Button-3>', lambda event: rmenu.post(event.x_root, event.y_root))
        a.pack(padx=5, pady=5)
        self.pls = IconGrid(win.tab7)
        lf1 = Frame(win.tab7)
        self.pls.pack(padx=5, pady=5, fill=BOTH, side=LEFT, expand=True)
        self.pls.canvas.bind('<Button-3>', lambda event: rmenu.post(event.x_root, event.y_root))
        self.pls.bind('<Button-3>', lambda event: rmenu.post(event.x_root, event.y_root))
        rmenu = Menu(self.pls, tearoff=False, borderwidth=0)
        rmenu.add_command(label=lang.text21, command=lambda: InstallMpk(
            filedialog.askopenfilename(title=lang.text25, filetypes=((lang.text26, "*.mpk"),))) == self.list_pls())
        rmenu.add_command(label=lang.text23, command=lambda: create_thread(self.refresh))
        rmenu.add_command(label=lang.text115, command=lambda: create_thread(module_manager.new))
        self.rmenu2 = Menu(self.pls, tearoff=False, borderwidth=0)
        self.rmenu2.add_command(label=lang.text20,
                                command=lambda: create_thread(module_manager.uninstall_gui, self.chosen.get()))
        self.rmenu2.add_command(label=lang.text22,
                                command=lambda: create_thread(module_manager.run, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t14, command=lambda: create_thread(module_manager.export, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t17,
                                command=lambda: create_thread(module_manager.new.editor_, module_manager,
                                                              self.chosen.get()))
        self.list_pls()
        lf1.pack(padx=10, pady=10)


class InstallMpk(Toplevel):
    def __init__(self, mpk=None):
        super().__init__()
        self.mconf = ConfigParser()
        self.installable = True
        self.mpk = mpk
        self.title(lang.text31)
        self.resizable(False, False)
        f = Frame(self)
        self.logo = Label(f)
        self.logo.pack(padx=10, pady=10)
        self.name_label = Label(f, text=self.mconf.get('module', 'name'), font=(None, 14))
        self.name_label.pack(padx=10, pady=10)
        self.version = Label(f, text=lang.text32.format(self.mconf.get('module', 'version')), font=(None, 12))
        self.version.pack(padx=10, pady=10)
        self.author = Label(f, text=lang.text33.format(self.mconf.get('module', 'author')), font=(None, 12))
        self.author.pack(padx=10, pady=10)
        f.pack(side=LEFT)
        self.text = Text(self, width=50, height=20)
        self.text.pack(padx=10, pady=10)
        self.prog = ttk.Progressbar(self, length=200, mode='indeterminate', orient=HORIZONTAL, maximum=100, value=0)
        self.prog.pack()
        self.state = Label(self, text=lang.text40, font=(None, 12))
        self.state.pack(padx=10, pady=10)
        self.installb = ttk.Button(self, text=lang.text41, style="Accent.TButton",
                                   command=lambda: create_thread(self.install))
        self.installb.pack(padx=10, pady=10, expand=True, fill=X)
        self.load()
        move_center(self)
        self.wait_window()
        create_thread(list_pls_plugin)

    def install(self):
        if self.installb.cget('text') == lang.text34:
            self.destroy()
            return 0
        self.prog.start()
        self.installb.config(state=DISABLED)
        ret, reason = module_manager.install(self.mpk)
        if ret == module_error_codes.PlatformNotSupport:
            self.state['text'] = lang.warn15.format(platform.system())
        elif ret == module_error_codes.DependsMissing:
            self.state['text'] = lang.text36 % (self.mconf.get('module', 'name'), reason, reason)
            self.installb['text'] = lang.text37
            self.installb.config(state='normal')
        elif ret == module_error_codes.IsBroken:
            self.state['text'] = lang.warn2
            self.installb['text'] = lang.text37
            self.installb.config(state='normal')
        elif ret == module_error_codes.Normal:
            self.state['text'] = lang.text39
            self.installb['text'] = lang.text34
            self.installb.config(state='normal')
        self.prog.stop()
        self.prog['mode'] = 'determinate'
        self.prog['value'] = 100
        return 0

    def load(self):
        if not self.mpk:
            self.unavailable()
            return
        if not zipfile.is_zipfile(self.mpk):
            self.unavailable()
            return
        with zipfile.ZipFile(self.mpk, 'r') as myfile:
            if 'info' not in myfile.namelist():
                self.unavailable()
                return
            with myfile.open('info') as info_file:
                self.mconf.read_string(info_file.read().decode('utf-8'))
            try:
                with myfile.open('icon') as myfi:
                    self.icon = myfi.read()
                    try:
                        self.pyt = PhotoImage(data=self.icon)
                    except Exception:
                        logging.exception('Bugs')
                        self.pyt = PhotoImage(data=images.none_byte)
            except (Exception, BaseException):
                logging.exception('Bugs')
                self.pyt = PhotoImage(data=images.none_byte)
        self.name_label.config(text=self.mconf.get('module', 'name'))
        self.logo.config(image=self.pyt)
        self.author.config(text=lang.text33.format(self.mconf.get('module', 'author')))
        self.version.config(text=lang.text32.format(self.mconf.get('module', 'version')))
        self.text.insert("insert", self.mconf.get('module', 'describe'))

    def unavailable(self):
        self.pyt = PhotoImage(data=images.error_logo_byte)
        self.name_label.config(text=lang.warn2, foreground='yellow')
        self.logo.config(image=self.pyt)
        self.author.destroy()
        self.version.destroy()
        self.prog.destroy()
        self.state.config()
        self.installb.config(state=DISABLED)


def Generate_Bug_Report():
    if os.name == 'nt':
        output = filedialog.askdirectory(title="Path To Save Bug Report")
    else:
        output = cwd_path
    output = str(output)
    if not output:
        return
    if not os.path.isdir(output) or not os.path.exists(output):
        return
    re_folder(inner := os.path.join(temp, v_code()))
    shutil.copyfile(tool_log, os.path.join(inner, os.path.basename(tool_log)))
    with open(os.path.join(inner, 'detail.txt'), 'w+', encoding='utf-8', newline='\n') as f:

        f.write(f"""
        ----BasicInfo-----
        Python: {sys.version}
        Platform: {sys.platform}
        Exec Command: {sys.argv}
        Tool Version: {settings.version}
        Source code running: {states.run_source}
        python Implementation: {platform.python_implementation()}
        Uname: {platform.uname()}
        ----Settings-------
        """)
        [f.write(f'\t{i}={getattr(settings, i) if not hasattr(i, "get") else i.get()}\n') for i in dir(settings)]
    pack_zip(inner, bugreport := os.path.join(output,
                                              f"Mio_Bug_Report{time.strftime('%Y%m%d_%H-%M-%S', time.localtime())}_{v_code()}.zip"),
             silent=True)
    re_folder(inner, quiet=True)
    print(f"\tThe Bug Report Was Saved:{bugreport}")


class Debugger(Toplevel):
    def __init__(self):
        super().__init__()
        self.title("MIO-KITCHEN Debugger")
        self.gui()
        move_center(self)

    def gui(self):
        if not is_pro:
            img = open_img(BytesIO(miside_banner.img)).resize((640, 206))
            states.miside_banner = PhotoImage(img)
            Label(self, image=states.miside_banner).grid(row=0, column=0, columnspan=3)
        row = 1
        num_max = 3
        num_c = 0
        functions = [
            ('Globals', self.loaded_module),
            ('Settings', self.settings),
            ('Info', self.show_info),
            ('Crash it!', self.crash),
            ('Hacker panel', lambda: openurl('https://vdse.bdstatic.com/192d9a98d782d9c74c96f09db9378d93.mp4')),
            ('Generate Bug Report', lambda: create_thread(Generate_Bug_Report)),
            ('米塔 MiSide', lambda: openurl('https://store.steampowered.com/app/2527500/')),
            ('米塔 MiSide(Demo)', lambda: openurl('steam://install/2527520')),
            ('No More Room in Hell', lambda: openurl('steam://install/224260')),
        ]
        for index, (text, func) in enumerate(functions):
            ttk.Button(self, text=text, command=func, width=20, style="Toggle.TButton").grid(row=row, column=num_c,
                                                                                             padx=5, pady=5)
            num_c = (num_c + 1) % num_max
            if not num_c:
                row += 1

    @staticmethod
    def crash():
        sys.stderr.write('Crashed!')
        sys.stderr.flush()

    @staticmethod
    def show_info():
        ck = Toplevel()
        ck.title('Info')
        ttk.Label(ck, text='MIO-KITCHEN', font=(None, 15), foreground='orange').grid(row=0, column=0, padx=5, pady=5,
                                                                                     sticky='nw')
        text = f"""
        Open Source License: {states.open_source_license}
        Python: {sys.version}
        Platform: {sys.platform}
        Exec Command: {sys.argv}
        Tool Version: {settings.version}
        Source code running: {states.run_source}
        python Implementation: {platform.python_implementation()}
        Uname: {platform.uname()}
        Log File: {tool_log}
        """
        # _base_executable: {sys._base_executable}
        if hasattr(sys, '_base_executable'):
            text += f'_base_executable: {sys._base_executable}'
        ttk.Label(ck, text=text, foreground='gray').grid(row=1, column=0, padx=5, pady=5,
                                                         sticky='nw')
        move_center(ck)

    @staticmethod
    def settings():
        save = lambda: settings.set_value(h.get(), f.get()) if f.get() else read_value()

        def read_value():
            f.delete(0, tk.END)
            f.insert(0, getattr(settings, h.get()))

        ck = Toplevel()
        ck.title('Settings')
        f1 = Frame(ck)
        f1.pack(pady=5, padx=5, fill=X, expand=True)
        h = ttk.Combobox(f1, values=[i for i in dir(settings) if isinstance(getattr(settings, i), str)],
                         state='readonly')
        h.current(0)
        h.bind("<<ComboboxSelected>>", lambda *x: read_value())
        h.pack(side='left', padx=5)
        Label(f1, text=':').pack(side='left', padx=5)
        f = ttk.Entry(f1, state='normal')
        f.bind("<KeyRelease>", lambda x: save())
        f.pack(padx=5, fill=BOTH)
        read_value()
        ttk.Button(ck, text=lang.ok, command=ck.destroy).pack(fill=X, side=BOTTOM)
        move_center(ck)
        ck.wait_window()

    @staticmethod
    def loaded_module():
        def save():
            if f.get():
                if len(f.get().split()) >= 2:
                    command, argv, *_ = f.get().split()
                    if command == 'import':
                        try:
                            globals()[h.get()] = __import__(argv)
                            read_value()
                        except ImportError:
                            logging.exception('Bugs')
                    elif command == 'global':
                        try:
                            globals()[h.get()] = globals()[argv]
                            read_value()
                        except (Exception, BaseException):
                            logging.exception('Bugs')

                else:
                    globals()[h.get()] = f.get()
            else:
                read_value()

        def read_value():
            f.delete(0, tk.END)
            f.insert(0, str(globals().get(h.get(), 0)))

        ck = Toplevel()
        ck.title('Globals')
        f1 = Frame(ck)
        f1.pack(pady=5, padx=5, fill=X, expand=True)
        h = ttk.Combobox(f1, values=list(globals().keys()), state='readonly')
        h.current(0)
        h.bind("<<ComboboxSelected>>", lambda *x: read_value())
        h.pack(side='left', padx=5)
        Label(f1, text=':').pack(side='left', padx=5)
        f = ttk.Entry(f1, state='normal')
        f.bind("<KeyRelease>", lambda x: save())
        f.pack(padx=5, fill=BOTH)
        read_value()
        ttk.Button(ck, text=lang.ok, command=ck.destroy).pack(fill=X, side=BOTTOM)
        move_center(ck)
        ck.wait_window()


class MpkStore(Toplevel):
    def __init__(self):
        if states.mpk_store:
            return
        states.mpk_store = True
        super().__init__()
        self.title('Mpk Store')
        self.data = []
        self.tasks = []
        self.apps = []
        self.app_infos = {}
        self.protocol("WM_DELETE_WINDOW", lambda: setattr(states, 'mpk_store', False) == self.destroy())
        self.repo = ''
        self.init_repo()
        ff = ttk.Frame(self)
        ttk.Label(ff, text="Mpk Store", font=(None, 20)).pack(padx=10, pady=10, side=LEFT)
        ttk.Button(ff, text=lang.t58, command=self.modify_repo).pack(padx=10, pady=10, side=RIGHT)
        ttk.Button(ff, text=lang.text23, command=lambda: create_thread(self.get_db)).pack(padx=10, pady=10, side=RIGHT)
        ff.pack(padx=10, pady=10, fill=BOTH)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        self.search = ttk.Entry(self)
        self.search.pack(fill=X, padx=5, pady=5)
        self.search.bind("<Return>",
                         lambda *x: self.search_apps())
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        self.logo = PhotoImage(data=images.none_byte)
        self.deque = []
        self.control = {}
        frame = tk.Frame(self)
        frame.pack(fill='both', padx=10, pady=10, expand=True)
        scrollbar = ttk.Scrollbar(frame, orient='vertical')
        scrollbar.pack(side='right', fill='y', padx=10, pady=10)
        self.canvas = tk.Canvas(frame, yscrollcommand=scrollbar.set, width=600)
        self.canvas.pack(fill='both', expand=True)
        scrollbar.config(command=self.canvas.yview)
        self.label_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.label_frame, anchor='nw')
        create_thread(self.get_db)
        self.label_frame.update_idletasks()
        self.canvas.bind_all("<MouseWheel>",
                             lambda event: self.canvas.yview_scroll(-1 * (int(event.delta / 120)), "units"))
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)
        move_center(self)

    def init_repo(self):
        if not hasattr(settings, 'plugin_repo'):
            self.repo = "https://raw.githubusercontent.com/ColdWindScholar/MPK_Plugins/main/"
        else:
            if not settings.plugin_repo:
                self.repo = "https://raw.githubusercontent.com/ColdWindScholar/MPK_Plugins/main/"
            else:
                self.repo = settings.plugin_repo

    def search_apps(self):
        for i in self.data:
            self.app_infos.get(i.get('id')).pack_forget() if self.search.get() not in i.get(
                'name') else self.app_infos.get(i.get('id')).pack(padx=5, pady=5, anchor='nw')
        self.canvas.yview_moveto(0.0)
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

    def add_app(self, app_dict=None):
        self.clear()
        if app_dict is None:
            app_dict = []
        for data in app_dict:
            if data.get('id') in self.app_infos:
                continue
            f = ttk.LabelFrame(self.label_frame, text=data.get('name'), width=590, height=150)
            f.pack_propagate(False)
            self.app_infos[data.get('id')] = f
            self.deque.append(f)
            ttk.Label(f, image=self.logo).pack(side=LEFT, padx=5, pady=5)
            fb = ttk.Frame(f)
            f2 = ttk.Frame(fb)
            ttk.Label(f, image=PhotoImage(data=images.none_byte)).pack(side=LEFT, padx=5, pady=5)
            # ttk.Label(f2, text=f"{data.get('name')[:6]}").pack(side=LEFT, padx=5, pady=5)
            o = ttk.Label(f2,
                          text=f"{lang.t21}{data.get('author')} {lang.t22}{data.get('version')} {lang.size}:{hum_convert(data.get('size'))}"
                          , wraplength=250)
            o.pack_propagate(False)
            o.pack(side=LEFT, padx=5, pady=5)
            f2.pack(side=TOP)
            f3 = ttk.Frame(fb)
            desc = data.get('desc')
            if not desc:
                desc = 'No Description.'
            ttk.Label(f3, text=f"{desc}", wraplength=250).pack(padx=5, pady=5)
            f3.pack(side=BOTTOM)
            fb.pack(side=LEFT, padx=5, pady=5)
            args = data.get('files'), data.get('size'), data.get('id'), data.get('depend')

            bu = ttk.Button(f, text=lang.text21,
                            command=lambda a=args: create_thread(self.download, *a), width=5)
            uninstall_button = ttk.Button(f, text=lang.text20,
                                          command=lambda a=data.get('id'): create_thread(self.uninstall,
                                                                                         a), width=5)
            if not module_manager.get_installed(data.get('id')):
                bu.config(style="Accent.TButton")
                uninstall_button.config(state='disabled')
            else:
                bu.config(width=5)
                uninstall_button.config(style="Accent.TButton")
            self.control[data.get('id')] = bu, uninstall_button
            uninstall_button.pack(side=RIGHT, padx=5, pady=5)
            bu.pack(side=RIGHT, padx=5, pady=5)
            f.pack(padx=5, pady=5, anchor='nw', expand=1)
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

    def uninstall(self, id_):
        bu, uninstall_button = self.control.get(id_)
        module_manager.uninstall_gui(id_, wait=True)
        if not module_manager.get_installed(id_):
            bu.config(style="Accent.TButton")
            uninstall_button.config(state='disabled')
        else:
            bu.config(width=5)
            uninstall_button.config(style="Accent.TButton")

    def clear(self):
        for i in self.deque:
            try:
                i.destroy()
            except (TclError, ValueError):
                logging.exception('Bugs')

    def modify_repo(self):
        (input_var := StringVar()).set(settings.plugin_repo)
        a = Toplevel()
        a.title(lang.t58)
        ttk.Entry(a, textvariable=input_var, width=60).pack(pady=5, padx=5, fill=BOTH)
        ttk.Button(a, text=lang.ok,
                   command=lambda: settings.set_value('plugin_repo', input_var.get()) == a.destroy()).pack(pady=5,
                                                                                                           padx=5,
                                                                                                           fill=BOTH)
        move_center(a)
        a.wait_window()
        if settings.plugin_repo != self.repo:
            self.init_repo()
            create_thread(self.get_db)

    def download(self, files, size, id_, depends):
        if id_ not in self.tasks:
            self.tasks.append(id_)
        else:
            return
        if id_ in self.control.keys():
            control = self.control.get(id_)[0]
            control.config(state='disabled')
        else:
            control = None
        if depends:
            for i in depends:
                for i_ in self.data:
                    if i == i_.get('id') and not module_manager.get_installed(i):
                        self.download(i_.get('files'), i_.get('size'), i_.get('id'), i_.get('depend'))
        try:
            for i in files:
                info = {}
                for data in self.data:
                    if id_ == data.get('id'):
                        info = data
                        break
                if os.path.exists(os.path.join(temp, i)) and os.path.isfile(os.path.join(temp, i)) and os.path.getsize(
                        os.path.join(temp, i)) == info.get('size', -1):
                    logging.info('Using Cached Package.')
                else:
                    for percentage, _, _, _, _ in download_api(self.repo + i, temp, size_=size):
                        if control and states.mpk_store:
                            control.config(text=f"{percentage} %")
                        else:
                            return False

                create_thread(module_manager.install, os.path.join(temp, i), join=True)
        except (ConnectTimeout, HTTPError, BaseException, Exception, TclError):
            logging.exception('Bugs')
            return
        control.config(state='normal', text=lang.text21)
        if module_manager.get_installed(id_):
            control.config(style="")
            self.control.get(id_)[1].config(state='normal', style="Accent.TButton")
        if id_ in self.tasks:
            self.tasks.remove(id_)

    def get_db(self):
        self.clear()
        try:
            url = requests.get(self.repo + 'plugin.json')
            self.data = json.loads(url.text)
        except (Exception, BaseException):
            logging.exception('Bugs')
            self.apps = self.data = []
        else:
            self.apps = self.data
        try:
            self.add_app(self.apps)
        except (TclError, Exception, BaseException):
            if not states.mpk_store:
                return
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)


@animation
class PackHybridRom:
    def __init__(self):
        if not project_manger.exist():
            win.message_pop(lang.warn1)
            return
        if os.path.exists((dir_ := project_manger.current_work_output_path()) + "firmware-update"):
            os.rename(f"{dir_}/firmware-update", f"{dir_}/images")
        if not os.path.exists(f"{dir_}/images"):
            os.makedirs(f'{dir_}/images')
        if os.path.exists(os.path.join(project_manger.current_work_output_path(), 'payload.bin')):
            print("Found payload.bin ,Stop!")
            return
        if os.path.exists(f'{dir_}/META-INF'):
            rmdir(f'{dir_}/META-INF')
        shutil.copytree(f"{cwd_path}/bin/extra_flash", dir_, dirs_exist_ok=True)
        right_device = input_(lang.t26, 'olive')
        with open(f"{dir_}/bin/right_device", 'w', encoding='gbk') as rd:
            rd.write(right_device + "\n")
        with open(
                f'{dir_}/META-INF/com/google/android/update-binary',
                'r+', encoding='utf-8', newline='\n') as script:
            lines = script.readlines()
            lines.insert(45, f'right_device="{right_device}"\n')
            add_line = self.get_line_num(lines, '#Other images')
            for t in os.listdir(f"{dir_}/images"):
                if t.endswith('.img') and not os.path.isdir(dir_ + t):
                    print(f"Add Flash method {t} to update-binary")
                    if os.path.getsize(os.path.join(f'{dir_}/images', t)) > 209715200:
                        self.zstd_compress(os.path.join(f'{dir_}/images', t))
                        lines.insert(add_line,
                                     f'package_extract_zstd "images/{t}.zst" "/dev/block/by-name/{t[:-4]}"\n')
                    else:
                        lines.insert(add_line,
                                     f'package_extract_file "images/{t}" "/dev/block/by-name/{t[:-4]}"\n')
            for t in os.listdir(dir_):
                if not t.startswith("preloader_") and not os.path.isdir(dir_ + t) and t.endswith('.img'):
                    print(f"Add Flash method {t} to update-binary")
                    if os.path.getsize(dir_ + t) > 209715200:
                        self.zstd_compress(dir_ + t)
                        move(os.path.join(dir_, f"{t}.zst"), os.path.join(f"{dir_}/images", f"{t}.zst"))
                        lines.insert(add_line,
                                     f'package_extract_zstd "images/{t}.zst" "/dev/block/by-name/{t[:-4]}"\n')
                    else:
                        lines.insert(add_line,
                                     f'package_extract_file "images/{t}" "/dev/block/by-name/{t[:-4]}"\n')
                        move(os.path.join(dir_, t), os.path.join(f"{dir_}/images", t))
            script.seek(0)
            script.truncate()
            script.writelines(lines)

    @staticmethod
    def get_line_num(data, text):
        for i, t_ in enumerate(data):
            if text in t_:
                return i

    @staticmethod
    def zstd_compress(path):
        basename = os.path.basename(path)
        if os.path.exists(path):
            if gettype(path) == "sparse":
                print(f"[INFO] {basename} is (sparse), converting to (raw)")
                utils.simg2img(path)
            try:
                print(f"[Compress] {basename}...")
                call(['zstd', '-5', '--rm', path, '-o', f'{path}.zst'])
            except Exception as e:
                logging.exception('Bugs')
                print(f"[Fail] Compress {basename} Fail:{e}")


class PackPayload(Toplevel):
    def __init__(self):
        super().__init__()
        self.title("打包Payload")
        self.overhead = 4194304
        # multi group_size must 4194304 less than super
        self.super_size = IntVar(value=17179869184)
        self.group_size = IntVar(value=17175674880)
        self.group_name = StringVar(value="qti_dynamic_partitions")
        self.virtual_ab = BooleanVar(value=True)
        self.part_list = []
        self.gui()
        move_center(self)

    def gui(self):
        """Group Name"""
        group_name_frame = ttk.Frame(self)
        Label(group_name_frame, text="Group Name:").pack(padx=3, pady=5, side='left')
        ttk.Combobox(group_name_frame, textvariable=self.group_name,
                     values=("qti_dynamic_partitions", "main", "mot_dp_group")).pack(side='left', padx=10, pady=10,
                                                                                     fill='both')
        group_name_frame.pack(padx=5, pady=5, fill='both')
        """Super Size"""
        super_size_frame = ttk.Frame(self)
        Label(super_size_frame, text="Super Size:").pack(padx=3, pady=5, side='left')
        super_size_entry = ttk.Entry(super_size_frame, textvariable=self.super_size)
        super_size_entry.pack(side='left', padx=10, pady=10)
        super_size_entry.bind("<KeyRelease>",
                              lambda *x: super_size_entry.state(
                                  ["!invalid" if super_size_entry.get().isdigit() else "invalid"]))
        super_size_frame.pack(padx=5, pady=5, fill='both')
        """Group size"""
        group_size_frame = Frame(self)
        Label(group_size_frame, text="Group Size:").pack(padx=3, pady=5, side='left')
        group_size_entry = ttk.Entry(group_size_frame, textvariable=self.group_size)
        group_size_entry.pack(padx=5, pady=5, fill='both')
        group_size_frame.pack(padx=5, pady=5, fill=BOTH)


class PackSuper(Toplevel):
    def __init__(self):
        super().__init__()
        self.title(lang.text53)
        self.super_size = IntVar(value=9126805504)
        self.is_sparse = BooleanVar()
        self.super_type = IntVar()
        self.attrib = StringVar(value='readonly')
        self.group_name = StringVar()
        self.delete_source_file = IntVar()
        self.block_device_name = StringVar(value='super')
        self.selected = []
        (lf1 := ttk.LabelFrame(self, text=lang.text54)).pack(fill=BOTH)
        (lf1_r := ttk.LabelFrame(self, text=lang.attribute)).pack(fill=BOTH)
        (lf2 := ttk.LabelFrame(self, text=lang.settings)).pack(fill=BOTH)
        (lf3 := ttk.LabelFrame(self, text=lang.text55)).pack(fill=BOTH, expand=True)
        self.super_type.set(1)

        radios = [("A-only", 1), ("Virtual-ab", 2), ("A/B", 3)]
        for text, value in radios:
            ttk.Radiobutton(lf1, text=text, variable=self.super_type, value=value).pack(side='left', padx=10, pady=10)

        ttk.Radiobutton(lf1_r, text="Readonly", variable=self.attrib, value='readonly').pack(side='left', padx=10,
                                                                                             pady=10)
        ttk.Radiobutton(lf1_r, text="None", variable=self.attrib, value='none').pack(side='left', padx=10, pady=10)
        Label(lf2, text=lang.text56).pack(side='left', padx=10, pady=10)
        (show_group_name := ttk.Combobox(lf2, textvariable=self.group_name,
                                         values=("qti_dynamic_partitions", "main", "mot_dp_group"))).pack(
            side='left',
            padx=10,
            pady=10,
            fill='both')
        show_group_name.current(0)
        Label(lf2, text=lang.text57).pack(side='left', padx=10, pady=10)
        (super_size := ttk.Entry(lf2, textvariable=self.super_size)).pack(side='left', padx=10, pady=10)
        super_size.bind("<KeyRelease>",
                        lambda *x: super_size.state(["!invalid" if super_size.get().isdigit() else "invalid"]))

        self.tl = ListBox(lf3)
        self.tl.gui()
        self.work = project_manger.current_work_path()

        self.tl.pack(padx=10, pady=10, expand=True, fill=BOTH)

        ttk.Checkbutton(self, text=lang.text58, variable=self.is_sparse, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(
            padx=10, pady=10, fill=BOTH)
        t_frame = Frame(self)
        ttk.Checkbutton(t_frame, text=lang.t11, variable=self.delete_source_file, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(side=LEFT,
                                                          padx=10, pady=10, fill=BOTH)
        ttk.Button(t_frame, text=lang.text23, command=self.refresh).pack(side=RIGHT, padx=10, pady=10)
        self.g_b = ttk.Button(t_frame, text=lang.t27, command=lambda: create_thread(self.generate))
        self.g_b.pack(side=LEFT, padx=10, pady=10, fill=BOTH)
        t_frame.pack(fill=X)
        move_center(self)

        ttk.Button(self, text=lang.cancel, command=self.destroy).pack(side='left', padx=10, pady=10,
                                                                      fill=X,
                                                                      expand=True)
        ttk.Button(self, text=lang.pack, command=lambda: create_thread(self.start_), style="Accent.TButton").pack(
            side='left',
            padx=5,
            pady=5, fill=X,
            expand=True)
        self.read_list()
        create_thread(self.refresh)

    def start_(self):
        try:
            self.super_size.get()
        except (Exception, BaseException):
            self.super_size.set(0)
            logging.exception('Bugs')
        if not self.verify_size():
            ask_win(lang.t10.format(self.super_size.get()), is_top=True)
            return False
        lbs = self.tl.selected.copy()
        sc = self.delete_source_file.get()
        self.destroy()
        if not project_manger.exist():
            warn_win(text=lang.warn1)
            return False
        pack_super(sparse=self.is_sparse.get(), group_name=self.group_name.get(), size=self.super_size.get(),
                   super_type=self.super_type.get(),
                   part_list=lbs, del_=sc,
                   attrib=self.attrib.get(), block_device_name=self.block_device_name.get())
        return None

    def verify_size(self):
        size = sum([os.path.getsize(f"{self.work}/{i}.img") for i in self.tl.selected])
        diff_size = size
        if size > self.super_size.get():
            for i in range(20):
                if not i:
                    continue
                i = i - 0.25
                t = (1024 ** 3) * i - size
                if t < 0:
                    continue
                if t < diff_size:
                    diff_size = t
                else:
                    size = i * (1024 ** 3)
                    break
            self.super_size.set(int(size))
            return False
        else:
            return True

    def generate(self):
        self.g_b.config(text=lang.t28, state='disabled')
        utils.generate_dynamic_list(group_name=self.group_name.get(), size=self.super_size.get(),
                                    super_type=self.super_type.get(),
                                    part_list=self.tl.selected.copy(), work=project_manger.current_work_path())
        self.g_b.config(text=lang.text34)
        time.sleep(1)
        try:
            self.g_b.config(text=lang.t27, state='normal')
        except TclError:
            logging.exception('Bugs')

    def refresh(self):
        self.tl.clear()
        for file_name in os.listdir(self.work):
            if file_name.endswith(".img"):
                if (file_type := gettype(self.work + file_name)) in ["ext", "erofs", 'f2fs', 'sparse']:
                    name = file_name[:-4]
                    self.tl.insert(f"{name} [{file_type}]", name, name in self.selected)

    def read_list(self):
        #Read parts_config
        parts_info = f"{self.work}/config/parts_info"
        if os.path.exists(parts_info):
            try:
                data: dict = JsonEdit(parts_info).read().get('super_info')
                if data is None:
                    raise AttributeError("super_info is not dict")
            except (Exception, BaseException, AttributeError):
                logging.exception('PackSupper:read_parts_info')
            else:
                # get block device name
                for i in data.get('block_devices', []):
                    self.block_device_name.set(i.get('name', 'super'))
                    if isinstance(i.get('size'), int):
                        self.super_size.set(i.get('size', self.super_size.get()))

                for i in data.get('group_table', []):
                    name = i.get('name')
                    if isinstance(name, str) and name != 'default':
                        self.group_name.set(name)

                selected = []
                for i in data.get('partition_table', []):
                    name = i.get('name')
                    if isinstance(name, str) and name not in selected:
                        selected.append(name)
                self.selected = selected

        #Read dynamic_partitions_op_list
        list_file = f"{self.work}/dynamic_partitions_op_list"
        if os.path.exists(list_file):
            try:
                data = utils.dynamic_list_reader(list_file)
            except (Exception, BaseException):
                logging.exception('Bugs')
                return
            if len(data) > 1:
                fir, sec = data
                if fir[:-2] == sec[:-2]:
                    self.group_name.set(fir[:-2])
                    self.super_type.set(2)
                    self.super_size.set(int(data[fir]['size']))
                    self.selected = data[fir].get('parts', [])
                    selected = self.selected
                    for i in self.selected:
                        name = i[:-2] if i.endswith('_a') or i.endswith('_b') else i
                        if not name in selected:
                            selected.append(name)
                    self.selected = selected

            else:
                group_name, = data
                self.group_name.set(group_name)
                self.super_size.set(int(data[group_name]['size']))
                self.selected = data[group_name].get('parts', [])
                self.super_type.set(1)


@animation
def pack_super(sparse: bool, group_name: str, size: int, super_type, part_list: list, del_=0, return_cmd=0,
               attrib='readonly',
               output_dir: str = None, work: str = None, block_device_name: str = 'None'):
    if not block_device_name:
        block_device_name = 'super'
    if not work:
        work = project_manger.current_work_path()
    if not output_dir:
        output_dir = project_manger.current_work_output_path()
    lb_c = []
    for part in part_list:
        if part.endswith('_b') or part.endswith('_a'):
            part = part[:-2]
        if part not in lb_c:
            lb_c.append(part)
    part_list = lb_c
    for part in part_list:
        if not os.path.exists(f'{work}/{part}.img') and os.path.exists(f'{work}/{part}_a.img'):
            try:
                os.rename(f'{work}/{part}_a.img', f'{work}/{part}.img')
            except:
                logging.exception('Bugs')
    command = ['lpmake', '--metadata-size', '65536', '-super-name', block_device_name, '-metadata-slots']
    if super_type == 1:
        command += ['2', '-device', f'{block_device_name}:{size}', "--group", f"{group_name}:{size}"]
        for part in part_list:
            command += ['--partition', f"{part}:{attrib}:{os.path.getsize(f'{work}/{part}.img')}:{group_name}",
                        '--image', f'{part}={work}/{part}.img']
    else:
        command += ["3", '-device', f'super:{size}', '--group', f"{group_name}_a:{size}"]
        for part in part_list:
            command += ['--partition',
                        f"{part}_a:{attrib}:{os.path.getsize(f'{work}/{part}.img')}:{group_name}_a",
                        '--image', f'{part}_a={work + part}.img']
        command += ["--group", f"{group_name}_b:{size}"]
        for part in part_list:
            if not os.path.exists(f"{work + part}_b.img"):
                command += ['--partition', f"{part}_b:{attrib}:0:{group_name}_b"]
            else:
                command += ['--partition',
                            f"{part}_b:{attrib}:{os.path.getsize(f'{work}/{part}_b.img')}:{group_name}_b",
                            '--image', f'{part}_b={work}/{part}_b.img']
        if super_type == 2:
            command += ["--virtual-ab"]
    if sparse: command += ["--sparse"]
    command += ['--out', f'{output_dir}/super.img']
    if return_cmd == 1:
        return command
    if call(command) == 0:
        if os.access(output_dir + "super.img", os.F_OK):
            print(lang.text59 % (output_dir + "super.img"))
            if del_ == 1:
                for img in part_list:
                    if os.path.exists(f"{work}{img}.img"):
                        try:
                            os.remove(f"{work}{img}.img")
                        except Exception:
                            logging.exception('Bugs')
        else:
            win.message_pop(lang.warn10)
    else:
        win.message_pop(lang.warn10)


class StdoutRedirector:
    def __init__(self, text_widget, error_=False):
        self.text_space = text_widget
        self.error = error_
        self.error_info = ''
        self.flush = lambda: error(1, self.error_info) if self.error_info else ...

    def write(self, string):
        if self.error:
            self.error_info += string
            logging.error(string)
            return
        self.text_space.insert(tk.END, string)
        logging.debug(string)
        self.text_space.see('end')
        if settings.ai_engine == '1':
            AI_engine.suggest(string, language=settings.language, ok=lang.ok)


def call(exe, extra_path=True, out: bool = True):
    logging.info(exe)
    if isinstance(exe, list):
        cmd = exe
        if extra_path:
            cmd[0] = f"{settings.tool_bin}{exe[0]}"
        cmd = [i for i in cmd if i]
    else:
        cmd = f'{settings.tool_bin}{exe}' if extra_path else exe
        if os.name == 'posix':
            cmd = cmd.split()
    conf = subprocess.CREATE_NO_WINDOW if os.name != 'posix' else 0
    try:
        ret = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=conf)
        pid = ret.pid
        states.open_pids.append(pid)
        for i in iter(ret.stdout.readline, b""):
            try:
                out_put = i.decode("utf-8").strip()
            except (Exception, BaseException):
                out_put = i.decode("gbk").strip()
            if out:
                print(out_put)
            else:
                logging.info(out_put)
        states.open_pids.remove(pid)
    except subprocess.CalledProcessError as e:
        for i in iter(e.stdout.readline, b""):
            try:
                out_put = i.decode("utf-8").strip()
            except (Exception, BaseException):
                out_put = i.decode("gbk").strip()
            if out:
                print(out_put)
            else:
                logging.info(out_put)
        return 2
    except FileNotFoundError:
        logging.exception('Bugs')
        return 2
    ret.wait()
    return ret.returncode


def download_api(url, path=None, int_=True, size_=0):
    start_time = time.time()
    response = requests.Session().head(url)
    file_size = int(response.headers.get("Content-Length", 0))
    response = requests.Session().get(url, stream=True, verify=False)
    last_time = time.time()
    if file_size == 0 and size_:
        file_size = size_
    with open((settings.path if path is None else path) + os.sep + os.path.basename(url), "wb") as f:
        chunk_size = 2048576
        chunk_kb = chunk_size / 1024
        bytes_downloaded = 0
        for data in response.iter_content(chunk_size=chunk_size):
            f.write(data)
            bytes_downloaded += len(data)
            elapsed = time.time() - start_time
            # old method
            # speed = bytes_downloaded / 1024 / elapsed
            used_time = time.time() - last_time
            speed = chunk_kb / used_time
            last_time = time.time()
            percentage = (int((bytes_downloaded / file_size) * 100) if int_ else (
                                                                                         bytes_downloaded / file_size) * 100) if file_size != 0 else "None"
            yield percentage, speed, bytes_downloaded, file_size, elapsed


def download_file():
    """
    Handles the process of downloading a file based on a URL provided by the user.
    Displays progress and status messages, and optionally unpacks the file after download.
    """
    unpack_after_finish_var = BooleanVar(value=False) 
    download_progress_frame = None # Will be initialized if URL is valid
    # url_input_value will be determined after user interaction with the input_ dialog

    try:
        # Prepare and display the URL input dialog
        input_dialog_title_key = 'text60' # Localization key for "Enter URL"
        default_input_title = "Enter URL"
        input_dialog_title = getattr(lang, input_dialog_title_key, default_input_title)
        if not isinstance(input_dialog_title, str) or input_dialog_title == "None": 
            input_dialog_title = default_input_title
        
        url_input_raw = input_(title=input_dialog_title) # Can return None (cancel), "" (OK empty), or "text"
        # For production, debug prints should be removed or conditional
        # print(f"[DEBUG] input_ returned: {repr(url_input_raw)} (type: {type(url_input_raw)})")

        # Scenario 1: User explicitly cancelled or closed the input dialog
        if url_input_raw is None:
            cancel_message_key = 'download_cancelled'
            default_cancel_message = "Download cancelled by user."
            cancel_message = getattr(lang, cancel_message_key, default_cancel_message)
            if not isinstance(cancel_message, str) or cancel_message == "None":
                cancel_message = default_cancel_message
            # print(f"[DEBUG] Explicit cancel: '{cancel_message}'") # Debug print removed
            print(cancel_message)
            return

        # At this point, url_input_raw is a string (empty or with text)
        url_input_value = str(url_input_raw)

        # Scenario 2: User pressed OK, but the URL field was empty or contained only whitespace
        if not url_input_value.strip():
            empty_url_message_key = 'download_url_empty'
            default_empty_url_message = "URL cannot be empty. Download aborted."
            empty_url_message = getattr(lang, empty_url_message_key, default_empty_url_message)
            if not isinstance(empty_url_message, str) or empty_url_message == "None":
                empty_url_message = default_empty_url_message
            # print(f"[DEBUG] Empty URL submitted: '{empty_url_message}'") # Debug print removed
            print(empty_url_message)
            
            popup_parent = win if win and win.winfo_exists() else None
            try:
                if hasattr(win, 'message_pop') and callable(win.message_pop):
                     win.message_pop(empty_url_message, "orange", parent=popup_parent) 
                else: 
                     import tkinter.messagebox # Fallback if custom message_pop is not available
                     tkinter.messagebox.showwarning("Input Error", empty_url_message, parent=popup_parent)
            except Exception as popup_ex:
                # print(f"[DEBUG] Exception during popup: {popup_ex}") # Debug print removed
                logging.exception("Exception during popup in download_file (empty URL)")
            return
            
        # Proceed with download if URL is non-empty
        # print(f"[DEBUG] URL for download: '{url_input_value}'") # Debug print removed

        download_frame_title_key = 'text61' # Localization key for "Download File"
        default_download_title = "Download File"
        download_frame_title = getattr(lang, download_frame_title_key, default_download_title)
        if not isinstance(download_frame_title, str) or download_frame_title == "None": 
            download_frame_title = default_download_title
        
        download_progress_frame = win.get_frame(download_frame_title) # Create the download progress UI

        start_download_message_key = 'text62' # Localization key for "Starting download..."
        default_start_message = "Starting download..."
        start_download_message = getattr(lang, start_download_message_key, default_start_message)
        if not isinstance(start_download_message, str) or start_download_message == "None": 
            start_download_message = default_start_message
        
        if hasattr(win, 'message_pop') and callable(win.message_pop):
            win.message_pop(start_download_message, "green") 

        # Setup UI elements for download progress
        progressbar = ttk.Progressbar(download_progress_frame, length=200, mode="determinate")
        progressbar.pack(padx=10, pady=10)
        
        ttk.Label(download_progress_frame, text=os.path.basename(url_input_value), justify='left').pack(padx=10, pady=5)
        ttk.Label(download_progress_frame, text=url_input_value, wraplength=300, justify='left').pack(padx=10, pady=5)

        progress_details_var = StringVar(master=download_progress_frame) 
        ttk.Label(download_progress_frame, textvariable=progress_details_var).pack(padx=10, pady=10)

        unpack_checkbox_text_key = 'text63' # Localization key for "Unpack after download"
        default_unpack_text = "Unpack after download"
        unpack_checkbox_text = getattr(lang, unpack_checkbox_text_key, default_unpack_text)
        if not isinstance(unpack_checkbox_text, str) or unpack_checkbox_text == "None": 
            unpack_checkbox_text = default_unpack_text
        
        unpack_checkbox = ttk.Checkbutton(download_progress_frame, text=unpack_checkbox_text, variable=unpack_after_finish_var, onvalue=True, offvalue=False)
        unpack_checkbox.pack(padx=10, pady=10)
        
        start_time = dti() # Start timing the download

        # Perform the download using download_api
        for percentage, speed, bytes_downloaded, file_size, _ in download_api(url_input_value):
            if not (download_progress_frame and download_progress_frame.winfo_exists()):
                # User closed the download progress window
                abort_message_key = 'download_window_closed'
                default_abort_message = "Download window closed, aborting download."
                abort_message = getattr(lang, abort_message_key, default_abort_message)
                if not isinstance(abort_message, str) or abort_message == "None": 
                    abort_message = default_abort_message
                print(abort_message)
                return # Exit if the progress window is gone

            if progressbar.winfo_exists():
                progressbar["value"] = percentage
                progressbar.update_idletasks() # Ensure immediate UI update
            
            # Update progress details text
            try:
                downloaded_hr = hum_convert(bytes_downloaded)
                total_hr = hum_convert(file_size) if file_size > 0 else "N/A"
                speed_bytes_sec = speed * 1024 if speed is not None else 0 
                speed_hr = hum_convert(speed_bytes_sec) + "/s" if speed is not None else "N/A"
                
                status_format_key = 'download_status_format'
                default_status_format = "{perc}% | Speed: {spd} | {dl}/{tot}"
                status_text_format = getattr(lang, status_format_key, default_status_format)
                if not isinstance(status_text_format, str) or status_text_format == "None": 
                    status_text_format = default_status_format

                status_text = status_text_format.format(perc=int(percentage), spd=speed_hr, dl=downloaded_hr, tot=total_hr)
                if progress_details_var.get() != status_text: 
                    progress_details_var.set(status_text)
            except Exception as e_status_update:
                logging.error(f"Error updating download status text: {e_status_update}")
                current_percentage_text = f"{int(percentage)}%"
                if progress_details_var.get() != current_percentage_text: 
                    progress_details_var.set(current_percentage_text)

        # Download completed successfully
        final_elapsed_time = dti() - start_time
        success_msg_format_key = 'text65' # Localization key for "File {} downloaded..."
        default_success_format = "File {} downloaded in {:.2f} seconds"
        success_msg_format = getattr(lang, success_msg_format_key, default_success_format)
        if not isinstance(success_msg_format, str) or success_msg_format == "None": 
            success_msg_format = default_success_format
        
        success_msg = success_msg_format.format(os.path.basename(url_input_value), final_elapsed_time)
        print(success_msg)
        
        # Optionally unpack the file
        if unpack_after_finish_var.get():
            downloaded_file_path = os.path.join(settings.path, os.path.basename(url_input_value))
            if os.path.exists(downloaded_file_path):
                create_thread(unpackrom, downloaded_file_path)
            else:
                not_found_msg_key = 'downloaded_file_not_found'
                default_not_found_msg = "Error: Downloaded file {} not found for unpacking."
                not_found_msg_format = getattr(lang, not_found_msg_key, default_not_found_msg)
                if not isinstance(not_found_msg_format, str) or not_found_msg_format == "None": 
                    not_found_msg_format = default_not_found_msg
                print(not_found_msg_format.format(downloaded_file_path))

    except requests.exceptions.MissingSchema:
        # Handle invalid URL schema (e.g., no http/https)
        err_msg_key = 'download_invalid_url_scheme'
        default_err_msg = "Error: Invalid URL '{}'. No schema (e.g., http://, https://) supplied."
        err_msg_format = getattr(lang, err_msg_key, default_err_msg)
        if not isinstance(err_msg_format, str) or err_msg_format == "None": 
            err_msg_format = default_err_msg
        
        url_for_error_msg = repr(url_input_raw) if 'url_input_raw' in locals() else "''"
        error_msg = err_msg_format.format(url_for_error_msg) 
        print(error_msg)
        
        popup_parent = win if win and win.winfo_exists() else None
        if not (download_progress_frame and download_progress_frame.winfo_exists()): 
            import tkinter.messagebox
            tkinter.messagebox.showerror("Error", error_msg, parent=popup_parent)
        elif download_progress_frame.winfo_exists():
             if hasattr(win, 'message_pop') and callable(win.message_pop):
                win.message_pop(error_msg, "red", parent=popup_parent)

    except requests.exceptions.ConnectionError as e_conn:
        # Handle network connection errors
        err_msg_key = 'download_connection_error'
        default_err_msg = "Download Error: Could not connect. {}"
        err_msg_format = getattr(lang, err_msg_key, default_err_msg)
        if not isinstance(err_msg_format, str) or err_msg_format == "None": 
            err_msg_format = default_err_msg
        
        error_msg = err_msg_format.format(str(e_conn))
        print(error_msg)
        popup_parent = win if win and win.winfo_exists() else None
        if not (download_progress_frame and download_progress_frame.winfo_exists()):
            import tkinter.messagebox
            tkinter.messagebox.showerror("Connection Error", error_msg, parent=popup_parent)
        elif download_progress_frame.winfo_exists():
             if hasattr(win, 'message_pop') and callable(win.message_pop):
                win.message_pop(error_msg, "red", parent=popup_parent)
             
    except Exception as e_general:
        # Handle other general exceptions during download
        err_msg_key = 'text66' # Localization key for "Download failed: {}"
        default_err_msg = "Download failed: {}"
        err_msg_format = getattr(lang, err_msg_key, default_err_msg)
        if not isinstance(err_msg_format, str) or err_msg_format == "None": 
            err_msg_format = default_err_msg
        
        error_msg = err_msg_format.format(str(e_general))
        print(error_msg)
        logging.exception("Download file general exception") # Log the full traceback
        
        # Attempt to clean up partially downloaded file
        url_val_for_cleanup = url_input_value if 'url_input_value' in locals() and url_input_value else None
        if url_val_for_cleanup: 
            failed_download_path = os.path.join(settings.path, os.path.basename(url_val_for_cleanup))
            if os.path.exists(failed_download_path):
                try:
                    os.remove(failed_download_path)
                    removed_msg_key = 'partially_downloaded_removed'
                    default_removed_msg = "Partially downloaded file {} removed."
                    removed_msg_format = getattr(lang, removed_msg_key, default_removed_msg)
                    if not isinstance(removed_msg_format, str) or removed_msg_format == "None": 
                        removed_msg_format = default_removed_msg
                    print(removed_msg_format.format(os.path.basename(url_val_for_cleanup)))
                except Exception as remove_err:
                    failed_remove_key = 'text67' # Localization key for "Failed to remove..."
                    default_failed_remove = "Failed to remove partially downloaded file {}: {}"
                    failed_remove_format = getattr(lang, failed_remove_key, default_failed_remove)
                    if not isinstance(failed_remove_format, str) or failed_remove_format == "None": 
                        failed_remove_format = default_failed_remove
                    print(failed_remove_format.format(os.path.basename(url_val_for_cleanup), str(remove_err)))
                
    finally:
        # Ensure the download progress frame is destroyed if it was created
        if download_progress_frame and download_progress_frame.winfo_exists():
            download_progress_frame.destroy()
            if hasattr(win, 'update_frame') and callable(win.update_frame):
                win.update_frame() # Update parent UI if necessary


@animation
def unpack_boot(name: str = 'boot', boot: str = None, work: str = None):
    if not work:
        work = project_manger.current_work_path()
    if not boot:
        if not (boot := findfile(f"{name}.img", work)):
            print(lang.warn3.format(name))
            return
    if not os.path.exists(boot):
        win.message_pop(lang.warn3.format(name))
        return
    if os.path.exists(work + name):
        if rmdir(work + name) != 0:
            print(lang.text69)
            return
    re_folder(work + name)
    os.chdir(work + name)
    if call(['magiskboot', 'unpack', '-h', '-n' if settings.magisk_not_decompress == '1' else '', boot]) != 0:
        print(f"Unpack {boot} Fail...")
        os.chdir(cwd_path)
        rmtree(work + name)
        return
    if os.access(f"{work}/{name}/ramdisk.cpio", os.F_OK):
        comp = gettype(f"{work}/{name}/ramdisk.cpio")
        print(f"Ramdisk is {comp}")
        with open(f"{work}/{name}/comp", "w", encoding='utf-8') as f:
            f.write(comp)
        if comp != "unknown":
            os.rename(f"{work}/{name}/ramdisk.cpio", f"{work}/{name}/ramdisk.cpio.comp")
            if call(["magiskboot", "decompress", f'{work}/{name}/ramdisk.cpio.comp',
                     f'{work}/{name}/ramdisk.cpio']) != 0:
                print("Failed to decompress Ramdisk...")
                return
        if not os.path.exists(f"{work}/{name}/ramdisk"):
            os.mkdir(f"{work}/{name}/ramdisk")
        print("Unpacking Ramdisk...")
        cpio_extract(os.path.join(work, name, 'ramdisk.cpio'), os.path.join(work, name, 'ramdisk'),
                     os.path.join(work, name, 'ramdisk.txt'))
    else:
        print("Unpack Done!")
    os.chdir(cwd_path)


@animation
def dboot(name: str = 'boot', source: str = None, boot: str = None):
    work = project_manger.current_work_path()
    flag = ''
    if boot is None:
        boot = findfile(f"{name}.img", work)
    if source is None:
        source = work + name
    if not os.path.exists(source):
        print(f"Cannot Find {name}...")
        return

    if os.path.isdir(f"{source}/ramdisk"):
        cpio_repack(f"{source}/ramdisk", f"{source}/ramdisk.txt", f"{source}/ramdisk-new.cpio")
        with open(f"{source}/comp", "r", encoding='utf-8') as compf:
            comp = compf.read()
        print(f"Compressing:{comp}")
        os.chdir(source)
        if comp != "unknown":
            if call(['magiskboot', f'compress={comp}', 'ramdisk-new.cpio']) != 0:
                print("Failed to pack Ramdisk...")
                os.remove("ramdisk-new.cpio")
            else:
                try:
                    os.remove("ramdisk.cpio")
                except (Exception, BaseException):
                    logging.exception('Bugs')
                if comp == 'gzip':
                    comp = 'gz'
                os.rename(f"ramdisk-new.cpio.{comp.split('_')[0]}", "ramdisk.cpio")
        else:
            if os.path.exists('ramdisk.cpio'):
                os.remove("ramdisk.cpio")
            os.rename("ramdisk-new.cpio", "ramdisk.cpio")
        print(f"Ramdisk Compression:{comp}")
        if comp == "unknown":
            flag = "-n"
        print("Successfully packed Ramdisk..")
    os.chdir(source)
    if call(['magiskboot', 'repack', flag, boot]) != 0:
        print("Failed to Pack boot...")
    else:
        os.remove(boot)
        os.rename(source + "/new-boot.img", project_manger.current_work_output_path() + f"/{name}.img")
        os.chdir(cwd_path)
        try:
            rmdir(source)
        except (Exception, BaseException):
            print(lang.warn11.format(name))
        print("Successfully packed Boot...")


class Packxx(Toplevel):
    def __init__(self, list_):
        if not list_:
            return
        self.lg = list_
        self.spatchvb = IntVar()
        self.custom_size = {}
        self.dbfs = StringVar(value='make_ext4fs')
        self.dbgs = StringVar(value='raw')
        self.edbgs = StringVar(value='lz4hc')
        self.scale = IntVar(value=0)
        self.UTC = IntVar(value=int(time.time()))
        self.scale_erofs = IntVar()
        self.delywj = IntVar()
        self.ext4_method = StringVar(value=lang.t32)

        self.origin_fs = StringVar(value='ext')
        self.modify_fs = StringVar(value='ext')

        self.fs_conver = BooleanVar(value=False)

        self.erofs_old_kernel = BooleanVar(value=False)
        if not self.verify():
            self.start_()
            return
        super().__init__()

        self.title(lang.text42)
        lf1 = ttk.LabelFrame(self, text=lang.text43)
        lf1.pack(fill=BOTH, padx=5, pady=5)
        lf2 = ttk.LabelFrame(self, text=lang.text44)
        lf2.pack(fill=BOTH, padx=5, pady=5)
        lf3 = ttk.LabelFrame(self, text=lang.text45)
        lf3.pack(fill=BOTH, padx=5, pady=5)
        lf4 = ttk.LabelFrame(self, text=lang.text46)
        lf4.pack(fill=BOTH, pady=5, padx=5)
        (sf1 := Frame(lf3)).pack(fill=X, padx=5, pady=5, side=TOP)
        # EXT4 Settings
        Label(lf1, text=lang.text48).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf1, state="readonly", values=("make_ext4fs", "mke2fs+e2fsdroid"), textvariable=self.dbfs).pack(
            side='left', padx=5, pady=5)
        Label(lf1, text=lang.t31).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf1, state="readonly", values=(lang.t32, lang.t33), textvariable=self.ext4_method).pack(
            side='left', padx=5, pady=5)
        self.modify_size_button = ttk.Button(lf1, text=lang.t37, command=self.modify_custom_size)
        self.modify_size_button.pack(
            side='left', padx=5, pady=5)
        self.show_modify_size = lambda: self.modify_size_button.pack_forget() if self.ext4_method.get() == lang.t32 else self.modify_size_button.pack(
            side='left', padx=5, pady=5)
        self.ext4_method.trace('w', lambda *x: self.show_modify_size())
        create_thread(self.show_modify_size)
        #
        Label(lf3, text=lang.text49).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf3, state="readonly", textvariable=self.dbgs, values=("raw", "sparse", "br", "dat")).pack(padx=5,
                                                                                                                pady=5,
                                                                                                                side='left')
        Label(lf2, text=lang.text50).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf2, state="readonly", textvariable=self.edbgs,
                     values=("lz4", "lz4hc", "lzma", "deflate", "zstd")).pack(side='left', padx=5, pady=5)
        ttk.Checkbutton(lf2, text=lang.t35, variable=self.erofs_old_kernel, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)
        # --
        scales_erofs = ttk.Scale(lf2, from_=0, to=9, orient="horizontal",
                                 command=lambda x: self.label_e.config(text=lang.t30.format(int(float(x)))),
                                 variable=self.scale_erofs)
        self.label_e = tk.Label(lf2, text=lang.t30.format(int(scales_erofs.get())))
        self.label_e.pack(side='left', padx=5, pady=5)
        scales_erofs.pack(fill="x", padx=5, pady=5)
        # --
        scales = ttk.Scale(sf1, from_=0, to=9, orient="horizontal",
                           command=lambda x: self.label.config(text=lang.text47.format(int(float(x))) % "Brotli"),
                           variable=self.scale)
        self.label = ttk.Label(sf1, text=lang.text47.format(int(scales.get())) % "Brotli")
        self.label.pack(side='left', padx=5, pady=5)
        scales.pack(fill="x", padx=5, pady=5)
        f = Frame(lf3)
        ttk.Label(f, text='UTC:').pack(side=LEFT, fill=X, padx=5, pady=5)
        ttk.Entry(f, textvariable=self.UTC).pack(side=LEFT, fill=X, padx=5, pady=5)
        f.pack(fill=X, padx=5, pady=5)

        frame_t = Frame(lf3)
        ttk.Checkbutton(frame_t, text=lang.text52, variable=self.spatchvb, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=X, side=LEFT)
        ttk.Checkbutton(frame_t, text=lang.t11, variable=self.delywj, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=X, side=LEFT)
        frame_t.pack(fill=X, padx=5, pady=5, side=BOTTOM)
        ttk.Checkbutton(lf3, text='Fs Converter', variable=self.fs_conver, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)
        fs_conver = ttk.Frame(lf3, width=20)
        ttk.Combobox(fs_conver, textvariable=self.origin_fs, values=('ext', 'f2fs', 'erofs'), width=6,
                     state='readonly').pack(
            padx=2, pady=2, fill=X, side=LEFT)
        ttk.Label(fs_conver, text='==>').pack(side=LEFT, fill=X, padx=1, pady=1)
        ttk.Combobox(fs_conver, textvariable=self.modify_fs, values=('ext', 'f2fs', 'erofs'), width=6,
                     state='readonly').pack(
            padx=2, pady=2, fill=X, side=LEFT)
        self.fs_conver.trace('w', lambda *z: fs_conver.pack_forget() if not self.fs_conver.get() else fs_conver.pack(
            padx=5, pady=5, fill=X))

        ttk.Button(self, text=lang.cancel, command=self.destroy).pack(side='left', padx=2,
                                                                      pady=2,
                                                                      fill=X,
                                                                      expand=True)
        ttk.Button(self, text=lang.pack, command=lambda: create_thread(self.start_), style="Accent.TButton").pack(
            side='left',
            padx=2, pady=2,
            fill=X,
            expand=True)
        move_center(self)
        module_manager.addon_loader.run_entry(module_manager.addon_entries.before_pack)

    def start_(self):
        module_manager.addon_loader.run_entry(module_manager.addon_entries.packing)
        try:
            self.destroy()
        except AttributeError:
            logging.exception('Bugs')
        self.packrom()

    def verify(self):
        parts_dict = JsonEdit(project_manger.current_work_path() + "config/parts_info").read()
        for i in self.lg:
            if i not in parts_dict.keys():
                parts_dict[i] = 'unknown'
            if parts_dict[i] in ['ext', 'erofs', 'f2fs']:
                return True
        return False

    def modify_custom_size(self):
        work = project_manger.current_work_path()

        def save():
            if f.get().isdigit():
                self.custom_size[h.get()] = f.get()
            elif not f.get():
                return
            else:
                read_value()

        def read_value():
            f.delete(0, tk.END)
            f.insert(0, str(self.custom_size.get(h.get(), 0)))

        def load():
            for dname in self.lg:
                if self.custom_size.get(dname, ''):
                    continue
                ext4_size_value = 0
                if self.ext4_method.get() == lang.t33:
                    if os.path.exists(f"{work}/dynamic_partitions_op_list"):
                        with open(f"{work}/dynamic_partitions_op_list", 'r', encoding='utf-8') as t:
                            for _i_ in t.readlines():
                                _i = _i_.strip().split()
                                if len(_i) < 3:
                                    continue
                                if _i[0] != 'resize':
                                    continue
                                if _i[1] in [dname, f'{dname}_a', f'{dname}_b']:
                                    ext4_size_value = max(ext4_size_value, int(_i[2]))
                    elif os.path.exists(f"{work}/config/{dname}_size.txt"):
                        with open(f"{work}/config/{dname}_size.txt", encoding='utf-8') as size_f:
                            try:
                                ext4_size_value = int(size_f.read().strip())
                            except ValueError:
                                ext4_size_value = 0
                self.custom_size[dname] = ext4_size_value

        ck = Toplevel()
        load()
        ck.title(lang.t37)
        f1 = Frame(ck)
        f1.pack(pady=5, padx=5, fill=X)
        h = ttk.Combobox(f1, values=list(self.custom_size.keys()), state='readonly')
        h.current(0)
        h.bind("<<ComboboxSelected>>", lambda *x: read_value())
        h.pack(side='left', padx=5)
        Label(f1, text=':').pack(side='left', padx=5)
        f = ttk.Entry(f1, state='normal')
        f.bind("<KeyRelease>", lambda x: save())
        f.pack(side='left', padx=5)
        read_value()
        ttk.Button(ck, text=lang.ok, command=ck.destroy).pack(fill=X, side=BOTTOM)
        move_center(ck)
        ck.wait_window()

    @animation
    def packrom(self) -> bool:
        if not project_manger.exist():
            win.message_pop(lang.warn1, "red")
            return False
        parts_dict = JsonEdit((work := project_manger.current_work_path()) + "config/parts_info").read()
        for i in self.lg:
            dname = os.path.basename(i)
            if dname not in parts_dict.keys():
                parts_dict[dname] = 'unknown'
            if self.spatchvb.get() == 1:
                for j in "vbmeta.img", "vbmeta_system.img", "vbmeta_vendor.img":
                    file = findfile(j, work)
                    if gettype(file) == 'vbmeta':
                        print(lang.text71 % file)
                        utils.Vbpatch(file).disavb()
            if os.access(os.path.join(f"{work}/config", f"{dname}_fs_config"), os.F_OK):
                if os.name == 'nt':
                    try:
                        if folder := findfolder(work, "com.google.android.apps.nbu."):
                            call(['mv', folder,
                                  folder.replace('com.google.android.apps.nbu.', 'com.google.android.apps.nbu')])
                    except Exception:
                        logging.exception('Bugs')
                fspatch.main(work + dname, os.path.join(f"{work}/config", f"{dname}_fs_config"))
                utils.qc(f"{work}/config/{dname}_fs_config")
                contexts_file = f"{work}/config/{dname}_file_contexts"
                if os.path.exists(contexts_file):
                    if settings.contextpatch == "1":
                        contextpatch.main(work + dname, contexts_file, context_rule_file)
                        new_rules = contextpatch.scan_context(contexts_file)
                        rules = JsonEdit(context_rule_file)
                        rules.write(new_rules | rules.read())

                    utils.qc(contexts_file)
                if self.fs_conver.get():
                    if parts_dict[dname] == self.origin_fs.get():
                        parts_dict[dname] = self.modify_fs.get()
                if parts_dict[dname] == 'erofs':
                    if mkerofs(dname, str(self.edbgs.get()), work=work,
                               work_output=project_manger.current_work_output_path(), level=int(self.scale_erofs.get()),
                               old_kernel=self.erofs_old_kernel.get(), UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.delywj.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.dbgs.get() in ["dat", "br", "sparse"]:
                            img2simg(project_manger.current_work_output_path() + dname + ".img")
                            if self.dbgs.get() == 'dat':
                                datbr(project_manger.current_work_output_path(), dname, "dat",
                                      int(parts_dict.get('dat_ver', 4)))
                            elif self.dbgs.get() == 'br':
                                datbr(project_manger.current_work_output_path(), dname, self.scale.get(),
                                      int(parts_dict.get('dat_ver', 4)))
                            else:
                                print(lang.text3.format(dname))
                elif parts_dict[dname] == 'f2fs':
                    if make_f2fs(dname, work=work, work_output=project_manger.current_work_output_path(),
                                 UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.delywj.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.dbgs.get() in ["dat", "br", "sparse"]:
                            img2simg(project_manger.current_work_output_path() + dname + ".img")
                            if self.dbgs.get() == 'dat':
                                datbr(project_manger.current_work_output_path(), dname, "dat",
                                      int(parts_dict.get('dat_ver', 4)))
                            elif self.dbgs.get() == 'br':
                                datbr(project_manger.current_work_output_path(), dname, self.scale.get(),
                                      int(parts_dict.get('dat_ver', 4)))
                            else:
                                print(lang.text3.format(dname))

                else:
                    ext4_size_value = self.custom_size.get(dname, 0)
                    if self.ext4_method.get() == lang.t33 and not self.custom_size.get(dname, ''):
                        list_file = f"{work}/dynamic_partitions_op_list"
                        if os.path.exists(list_file):
                            with open(list_file, 'r', encoding='utf-8') as t:
                                for _i_ in t.readlines():
                                    _i = _i_.strip().split()
                                    if len(_i) < 3:
                                        continue
                                    if _i[0] != 'resize':
                                        continue
                                    if _i[1] in [dname, f'{dname}_a', f'{dname}_b']:
                                        ext4_size_value = max(ext4_size_value, int(_i[2]))
                        elif os.path.exists(f"{work}/config/{dname}_size.txt"):
                            with open(f"{work}/config/{dname}_size.txt", encoding='utf-8') as f:
                                try:
                                    ext4_size_value = int(f.read().strip())
                                except ValueError:
                                    ext4_size_value = 0
                    if self.dbfs.get() == "make_ext4fs":
                        exit_code = make_ext4fs(name=dname, work=work,
                                                work_output=project_manger.current_work_output_path(),
                                                sparse=self.dbgs.get() in ["dat", "br", "sparse"], size=ext4_size_value,
                                                UTC=self.UTC.get(), has_contexts=os.path.exists(contexts_file))

                    else:
                        exit_code = mke2fs(
                            name=dname, work=work,
                            work_output=project_manger.current_work_output_path(),
                            sparse=self.dbgs.get() in [
                                "dat",
                                "br",
                                "sparse"],
                            size=ext4_size_value,
                            UTC=self.UTC.get())
                    if exit_code:
                        print(lang.text75 % dname)
                        continue

                    if self.delywj.get() == 1:
                        rdi(work, dname)
                    if self.dbgs.get() == "dat":
                        datbr(project_manger.current_work_output_path(), dname, "dat",
                              int(parts_dict.get('dat_ver', '4')))
                    elif self.dbgs.get() == "br":
                        datbr(project_manger.current_work_output_path(), dname, self.scale.get(),
                              int(parts_dict.get('dat_ver', '4')))
                    else:
                        print(lang.text3.format(dname))
            elif parts_dict[i] in ['boot', 'vendor_boot']:
                dboot(i)
            elif parts_dict[i] == 'dtbo':
                pack_dtbo()
            elif parts_dict[i] == 'logo':
                logo_pack()
            elif parts_dict[i] == 'guoke_logo':
                GuoKeLogo().pack(os.path.join(work, dname), os.path.join(work, f"{dname}.img"))
            else:
                if os.path.exists(os.path.join(work, i)):
                    print(f"Unsupported {i}:{parts_dict[i]}")
                logging.warning(f"{i} Not Supported.")


def rdi(work, part_name) -> bool:
    if not os.listdir(f"{work}/config"):
        rmtree(f"{work}/config")
        return False
    if os.access(f"{work}/{part_name}.img", os.F_OK):
        print(lang.text72 % part_name)
        try:
            rmdir(work + part_name)
            for i_ in ["%s_size.txt", "%s_file_contexts", '%s_fs_config', '%s_fs_options']:
                path_ = os.path.join(work, "config", i_ % part_name)
                if os.access(path_, os.F_OK):
                    os.remove(path_)
        except Exception:
            logging.exception(lang.text73 % (part_name, 'E'))
        print(lang.text3.format(part_name))
    else:
        win.message_pop(lang.text75 % part_name, "red")


def input_(title: str = None, text: str = "") -> str: # Тип возвращаемого значения изменен для ясности, но может быть и Optional[str]
    if not title:
        title_text_key = 'text76' # Используем ключ, если есть
        default_title_text = "Input"
        title_text = getattr(lang, title_text_key, default_title_text)
        if not isinstance(title_text, str) or title_text == "None":
            title_text = default_title_text
    else:
        title_text = title

    parent_window = win 

    dialog = Toplevel() 
    dialog.title(title_text)

    if parent_window and parent_window.winfo_exists():
        dialog.transient(parent_window)

    input_var = StringVar(master=dialog)
    input_var.set(text)

    # ИЗМЕНЕНИЕ: result_container["value"] изначально None
    result_container = {"value": None} 

    frame_inner = ttk.Frame(dialog)
    frame_inner.pack(expand=True, fill=BOTH, padx=15, pady=10)

    ttk.Label(frame_inner, text=title_text, font=(None, 12)).pack(side=TOP, pady=(0, 10))

    entry = ttk.Entry(frame_inner, textvariable=input_var, font=(None, 10))
    entry.pack(pady=5, padx=5, fill=X, ipady=4)

    button_frame = ttk.Frame(frame_inner)
    button_frame.pack(fill=X, pady=(10, 0), side=BOTTOM)

    def on_ok(event=None):
        # При ОК, мы берем значение из поля ввода.
        # Если поле пустое, input_var.get() вернет "" (пустую строку).
        result_container["value"] = input_var.get() 
        dialog.destroy()

    def on_cancel(event=None):
        # При Отмене, result_container["value"] остается None (как было инициализировано)
        # или можно явно: result_container["value"] = None
        dialog.destroy()

    ok_button_text_key = 'ok'
    default_ok_text = "OK"
    ok_button_text = getattr(lang, ok_button_text_key, default_ok_text)
    if not isinstance(ok_button_text, str) or ok_button_text == "None":
        ok_button_text = default_ok_text

    cancel_button_text_key = 'cancel'
    default_cancel_text = "Cancel"
    cancel_button_text = getattr(lang, cancel_button_text_key, default_cancel_text)
    if not isinstance(cancel_button_text, str) or cancel_button_text == "None":
        cancel_button_text = default_cancel_text
        
    ok_button = ttk.Button(button_frame, text=ok_button_text, command=on_ok, style="Accent.TButton")
    ok_button.pack(side=LEFT, padx=(0, 5), expand=True, fill=X)

    cancel_button = ttk.Button(button_frame, text=cancel_button_text, command=on_cancel)
    cancel_button.pack(side=LEFT, padx=(5, 0), expand=True, fill=X)

    entry.bind("<Return>", on_ok)
    dialog.bind("<Escape>", on_cancel)
    dialog.protocol("WM_DELETE_WINDOW", on_cancel) # Обработка закрытия окна крестиком как отмена

    move_center(dialog)    
    dialog.after(10, lambda: entry.focus_set()) 
    dialog.grab_set()
    dialog.wait_window()

    return result_container["value"] # Вернет None при отмене, "" при ОК с пустым полем, или "текст"


def script2fs(path):
    if os.path.exists(os.path.join(path, "system", "app")):
        if not os.path.exists(path + "/config"):
            os.makedirs(path + "/config")
        extra.script2fs_context(findfile("updater-script", f"{path}/META-INF"), f"{path}/config", path)
        json_ = JsonEdit(os.path.join(path, "config", "parts_info"))
        parts = json_.read()
        for v in os.listdir(path):
            if os.path.exists(path + f"/config/{v}_fs_config"):
                if v not in parts.keys():
                    parts[v] = 'ext'
        json_.write(parts)


# fixme:Rewrite it.
@animation
def unpackrom(ifile) -> None:
    print(lang.text77 + ifile, f'Type:[{(ftype := gettype(ifile))}]')
    # gzip
    if ftype == 'gzip':
        print(lang.text79 + ifile)
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not project_manger.exist():
            re_folder(project_manger.current_work_path())
        if os.path.basename(ifile).endswith(".gz"):
            output_file_name = os.path.basename(ifile)[:-3]
        else:
            output_file_name = os.path.basename(ifile)
        output_file_ = os.path.join(project_manger.current_work_path(), output_file_name)
        with open(output_file_, "wb") as output, gzip.open(ifile, "rb") as input_file:
            data = input_file.read(8192)
            while len(data) == 8192:
                output.write(data)
                data = input_file.read(8192)
            else:
                if len(data) > 0:
                    output.write(data)
        old_project_name = os.path.splitext(os.path.basename(ifile))[0]
        unpackrom(output_file_)
        if old_project_name != (new_project_name := current_project_name.get()):
            current_project_name.set(old_project_name)
            project_menu.remove()
        current_project_name.set(new_project_name)
        return
    # ozip
    if ftype == "ozip":
        print(lang.text78 + ifile)
        ozipdecrypt.main(ifile)
        decrypted = os.path.dirname(ifile) + os.sep + os.path.basename(ifile)[:-4] + "zip"
        if not os.path.exists(decrypted):
            print(f"{ifile} decrypt Fail!!!")
            return
        unpackrom(decrypted)
        try:
            os.remove(decrypted)
        except:
            print(f"{ifile} remove Fail!!!")
        return
    # tar
    if ftype == 'tar':
        print(lang.text79 + ifile)
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not project_manger.exist():
            re_folder(project_manger.current_work_path())
        with tarsafe.TarSafe(ifile) as f:
            f.extractall(project_manger.current_work_path())
        return
    # kdz
    if ftype == 'kdz':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not project_manger.exist():
            re_folder(project_manger.current_work_path())
        KDZFileTools(ifile, project_manger.current_work_path(), extract_all=True)
        for i in os.listdir(project_manger.current_work_path()):
            file = project_manger.current_work_path() + os.sep + i
            if not os.path.isfile(file):
                continue
            if i.endswith('.dz') and gettype(file) == 'dz':
                DZFileTools(file, project_manger.current_work_path(),
                            extract_all=True)
        return
    # ofp
    if os.path.splitext(ifile)[1] == '.ofp':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if ask_win(lang.t12) == 1:
            ofp_mtk_decrypt.main(ifile, project_manger.current_work_path())
        else:
            ofp_qc_decrypt.main(ifile, project_manger.current_work_path())
            script2fs(project_manger.current_work_path())
        unpackg.refs(True)
        return
    # ops
    if os.path.splitext(ifile)[1] == '.ops':
        current_project_name.set(os.path.basename(ifile).split('.')[0])
        args = {'decrypt': True,
                "<filename>": ifile,
                'outdir': os.path.join(settings.path, project_manger.current_work_path())}
        opscrypto.main(args)
        unpackg.refs(True)
        return
    # pac
    if gettype(ifile) == 'pac':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        unpac(ifile, project_manger.current_work_path(), PACMODE.EXTRACT)
        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(project_manger.current_work_path())])
        return
    #zip
    if gettype(ifile) == 'zip':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        with zipfile.ZipFile(ifile, 'r') as fz:
            for fi in fz.namelist():
                try:
                    member_name = fi.encode('cp437').decode('gbk')
                except (Exception, BaseException):
                    try:
                        member_name = fi.encode('cp437').decode('utf-8')
                    except (Exception, BaseException):
                        member_name = fi
                print(lang.text79 + member_name)
                try:
                    fz.extract(fi, project_manger.current_work_path())
                    if fi != member_name:
                        os.rename(os.path.join(project_manger.current_work_path(), fi),
                                  os.path.join(project_manger.current_work_path(), member_name))
                except Exception as e:
                    print(lang.text80 % (member_name, e))
                    win.message_pop(lang.warn4.format(member_name))
            print(lang.text81)
            if os.path.isdir(project_manger.current_work_path()):
                project_menu.listdir()
                project_menu.set_project(os.path.splitext(os.path.basename(ifile))[0])
            script2fs(project_manger.current_work_path())
            unpackg.refs(True)

        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(project_manger.current_work_path())])
        return

    # othters.
    if ftype != 'unknown':
        file_name: str = os.path.basename(ifile)
        project_folder = os.path.join(settings.path, os.path.splitext(file_name)[0])
        folder = os.path.join(settings.path, os.path.splitext(file_name)[0] + v_code()) if os.path.exists(
            project_folder) else project_folder
        try:
            current_project_name.set(os.path.basename(folder))
            os.mkdir(folder)
            project_manger.current_work_path()
            project_manger.current_work_output_path()
        except Exception as e:
            win.message_pop(str(e))
        project_dir = str(folder) if settings.project_struct != 'split' else str(folder + '/Source/')
        copy(ifile, project_dir)
        # File Rename
        if os.path.exists(os.path.join(project_dir, file_name)):
            if not '.' in file_name:
                shutil.move(os.path.join(project_dir, file_name), os.path.join(project_dir, file_name + ".img"))
            if file_name.endswith(".bin"):
                shutil.move(os.path.join(project_dir, file_name), os.path.join(project_dir, file_name[:-4] + ".img"))
        current_project_name.set(os.path.basename(folder))
        project_menu.listdir()
        project_menu.set_project(current_project_name.get())
        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(project_manger.current_work_path())])
    else:
        print(lang.text82 % ftype)
    unpackg.refs(True)


class ProjectManager:
    def __init__(self):
        ...

    @staticmethod
    def get_work_path(name):
        path = str(os.path.join(settings.path, name) + os.sep)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def current_work_path(self):
        if settings.project_struct == 'single':
            path = self.get_work_path(current_project_name.get())
        else:
            path = os.path.join(self.get_work_path(current_project_name.get()), 'Source') + os.sep
            if not os.path.exists(path) and current_project_name.get():
                os.makedirs(path, exist_ok=True)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def current_origin_path(self):
        if settings.project_struct == 'single':
            path = self.get_work_path(current_project_name.get())
        else:
            path = os.path.join(self.get_work_path(current_project_name.get()), 'Origin') + os.sep
            if not os.path.exists(path) and current_project_name.get():
                os.makedirs(path, exist_ok=True)
        return path if os.name == 'nt' else path.replace('\\', '/')

    def current_work_output_path(self):
        if settings.project_struct == 'single':
            path = self.get_work_path(current_project_name.get())
        else:
            path = os.path.join(self.get_work_path(current_project_name.get()), 'Output') + os.sep
            if not os.path.exists(path) and current_project_name.get():
                os.makedirs(path, exist_ok=True)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def exist(self, name=None):
        if not current_project_name.get():
            return False
        return os.path.exists(self.current_work_path()) if name is None else os.path.exists(
            self.get_work_path(current_project_name.get()))


project_manger = ProjectManager()


@animation
def unpack(chose, form: str = '') -> bool:
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
    json_ = JsonEdit((work := project_manger.current_work_path()) + "config/parts_info")
    parts = json_.read()
    if not chose:
        return False
    if form == 'payload':
        print(lang.text79 + "payload")
        dumper = Dumper(f"{work}/payload.bin", work, diff=False, old='old', images=chose)
        try:
            dumper.run()
        except RuntimeError:
            dumper.run(slow=True)
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
            #should get info here.
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
            call(['zstd', '--rm', '-d', f"{work}/{i}.zst"])
            return True
        if os.access(f"{work}/{i}.new.dat.xz", os.F_OK):
            print(lang.text79 + f"{i}.new.dat.xz")
            Unxz(f"{work}/{i}.new.dat.xz")
        if os.access(f"{work}/{i}.new.dat.br", os.F_OK):
            print(lang.text79 + f"{i}.new.dat.br")
            call(['brotli', '-dj', f"{work}/{i}.new.dat.br"])
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
                except (Exception, BaseException):
                    win.message_pop(lang.warn11.format(f"{i}.img"))
            if i not in parts.keys():
                parts[i] = gettype(f"{work}/{i}.img")
            print(lang.text79 + i + f".img[{file_type}]")
            if gettype(f"{work}/{i}.img") == 'super':
                parts["super_info"] = lpunpack.get_info(f"{work}/{i}.img")
                lpunpack.unpack(f"{work}/{i}.img", work)
                for file_name in os.listdir(work):
                    if file_name.endswith('_a.img'):
                        if os.path.exists(work + file_name) and os.path.exists(work + file_name.replace('_a', '')):
                            if pathlib.Path(work + file_name).samefile(work + file_name.replace('_a', '')):
                                os.remove(work + file_name)
                            else:
                                os.remove(work + file_name.replace('_a', ''))
                                os.rename(work + file_name, work + file_name.replace('_a', ''))
                        else:
                            os.rename(work + file_name, work + file_name.replace('_a', ''))
                    if file_name.endswith('_b.img'):
                        if os.path.getsize(work + file_name) == 0:
                            os.remove(work + file_name)
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
                imgextractor.Extractor().main(project_manger.current_work_path() + i + ".img", f'{work}/{i}', work)
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except Exception as e:
                        win.message_pop(lang.warn11.format(f"{i}.img:{e.__str__()}"))
            if file_type == 'romfs':
                fs = RomfsParse(project_manger.current_work_path() + f"{i}.img")
                fs.extract(work)
            if file_type == 'guoke_logo':
                GuoKeLogo().unpack(os.path.join(project_manger.current_work_path(), f'{i}.img'), f'{work}/{i}')
            if file_type == "erofs":
                if call(exe=['extract.erofs', '-i', os.path.join(project_manger.current_work_path(), f'{i}.img'), '-o',
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
                if call(exe=['extract.f2fs', '-o', work, os.path.join(project_manger.current_work_path(), f'{i}.img')],
                        out=False) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'unknown' and is_empty_img(f"{work}/{i}.img"):
                print(lang.text141)
    if not os.path.exists(f"{work}/config"):
        os.makedirs(f"{work}/config")
    json_.write(parts)
    parts.clear()
    print(lang.text8)
    return True


def cprint(*args, **kwargs):
    if not hasattr(sys, 'stdout_origin'):
        print("stdout_origin not defined!")
    else:
        print(*args, **kwargs, file=sys.stdout_origin)


def ask_win(text: str = '', ok: str = None, cancel: str = None, wait: bool = True, is_top: bool = False) -> int: # is_top is deprecated
    if ok is None:
        ok_text = lang.ok if hasattr(lang, 'ok') else "OK"
    else:
        ok_text = ok
        
    if cancel is None:
        cancel_text = lang.cancel if hasattr(lang, 'cancel') else "Cancel"
    else:
        cancel_text = cancel

    parent_window = win

    dialog = Toplevel()
    dialog.title(lang.confirm_title if hasattr(lang, 'confirm_title') else "Confirm")
    
    if parent_window and parent_window.winfo_exists():
        dialog.transient(parent_window)
    
    # dialog.resizable(False, False) # Опционально

    result_var = IntVar(master=dialog) 

    frame_inner = ttk.Frame(dialog)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=15)

    ttk.Label(frame_inner, text=text, font=(None, 12), wraplength=350).pack(side=TOP, pady=(0, 15))

    button_frame = ttk.Frame(frame_inner)
    button_frame.pack(fill=X, pady=(10,0), side=BOTTOM)

    def on_ok(event=None):
        result_var.set(1)
        dialog.destroy()

    def on_cancel(event=None):
        result_var.set(0)
        dialog.destroy()

    ok_button = ttk.Button(button_frame, text=ok_text, command=on_ok, style="Accent.TButton")
    ok_button.pack(side=LEFT, padx=(0,5), expand=True, fill=X) 
    
    cancel_button = ttk.Button(button_frame, text=cancel_text, command=on_cancel)
    cancel_button.pack(side=LEFT, padx=(5,0), expand=True, fill=X)
    
    dialog.bind("<Return>", on_ok) 
    dialog.bind("<Escape>", on_cancel)

    # dialog.update_idletasks()
    move_center(dialog)
    
    dialog.after(10, lambda: ok_button.focus_set()) # Фокус на кнопку OK

    dialog.grab_set()
    
    if wait:
        dialog.wait_window()
        
    return result_var.get()

def info_win(text: str, ok: str = None, title: str = None):
    if ok is None:
        ok_text = lang.ok if hasattr(lang, 'ok') else "OK"
    else:
        ok_text = ok
        
    if title is None:
        title_text = lang.info_title if hasattr(lang, 'info_title') else "Information"
    else:
        title_text = title

    parent_window = win

    dialog = Toplevel()
    dialog.title(title_text)
    
    if parent_window and parent_window.winfo_exists():
        dialog.transient(parent_window)
        
    # dialog.resizable(False, False) # Опционально

    frame_inner = ttk.Frame(dialog)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=15)

    ttk.Label(frame_inner, text=text, font=(None, 12), wraplength=350).pack(side=TOP, pady=(0, 20))

    button_frame = ttk.Frame(frame_inner) 
    button_frame.pack(fill=X, pady=(0,5), side=BOTTOM)

    ok_button = ttk.Button(button_frame, text=ok_text, command=dialog.destroy, style="Accent.TButton")
    ok_button.pack(ipadx=10) 
    
    dialog.bind("<Return>", lambda event: dialog.destroy())
    dialog.bind("<Escape>", lambda event: dialog.destroy())

    # dialog.update_idletasks()
    move_center(dialog)
    
    dialog.after(10, lambda: ok_button.focus_set()) # Фокус на кнопку OK

    dialog.grab_set()
    dialog.wait_window()


class GetFolderSize:
    # get-command
    # 1 - return True value of dir size
    # 2 - return Rsize value of dir size
    # 3 - return Rsize value of dir size and modify dynampic_partition_list
    def __init__(self, dir_: str, num: int = 1, get: int = 2, list_f: str = None):
        self.rsize_v: int
        self.num = num
        self.get = get
        self.list_f = list_f
        self.dname = os.path.basename(dir_)
        self.size = 0

        def get_dir_size(path):
            for root, _, files in os.walk(path):
                for name in files:
                    try:
                        file_path = os.path.join(root, name)
                        if not os.path.isfile(file_path):
                            self.size += len(name)
                        self.size += os.path.getsize(file_path)
                    except (PermissionError, BaseException, Exception):
                        logging.exception(f"Getsize {name}")
                        self.size += 1
            self.size += (self.size / 16384) * 256
            if self.size > 100 * 1024 * 1024:
                self.size += 16 * (1024 ** 2)

        get_dir_size(dir_)
        if self.get == 1:
            self.rsize_v = self.size
        else:
            self.rsize(self.size, self.num)

    def rsize(self, size: int, num: int):
        print(f"{self.dname} Size : {hum_convert(size)}")
        if size <= 2097152:
            self.rsize_v = 2097152
        elif size <= 1048576:
            self.rsize_v = 1048576
        else:
            size_ = int(size)
            if size_ % 4096:
                size_ = size_ + (4096 - size_ % 4096)
            self.rsize_v = size_
        if self.get == 3:
            self.rsizelist(self.dname, self.rsize_v, self.list_f)
        self.rsize_v = int(self.rsize_v / num)

    @staticmethod
    def rsizelist(part_name, size, file):
        if os.access(file, os.F_OK):
            print(lang.text74 % (part_name, size))
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(file, 'w', encoding='utf-8', newline='\n') as ff:
                content = re.sub(f"resize {part_name} \\d+",
                                 f"resize {part_name} {size}", content)
                content = re.sub(f"resize {part_name}_a \\d+",
                                 f"resize {part_name}_a {size}", content)
                content = re.sub(f"# Grow partition {part_name} from 0 to \\d+",
                                 f"# Grow partition {part_name} from 0 to {size}",
                                 content)
                content = re.sub(f"# Grow partition {part_name}_a from 0 to \\d+",
                                 f"# Grow partition {part_name}_a from 0 to {size}", content)
                ff.write(content)


@animation
def datbr(work, name, brl: any, dat_ver=4):
    """

    :param work: working dir
    :param name: the name of the partitition
    :param brl: if its a int , will convert the file to br, if "dat" just convert to dat
    :param dat_ver: dat version
    :return:None
    """
    print(lang.text86 % (name, name))
    if not os.path.exists(f"{work}/{name}.img"):
        print(f"{work}/{name}.img" + lang.text84)
        return
    else:
        utils.img2sdat(f"{work}/{name}.img", work, dat_ver, name)
    if os.access(f"{work}/{name}.new.dat", os.F_OK):
        try:
            os.remove(f"{work}/{name}.img")
        except Exception:
            logging.exception('Bugs')
            os.remove(f"{work}/{name}.img")
    if brl == "dat":
        print(lang.text87 % name)
    else:
        print(lang.text88 % (name, 'br'))
        call(['brotli', '-q', str(brl), '-j', '-w', '24', f"{work}/{name}.new.dat", '-o', f"{work}/{name}.new.dat.br"])
        if os.access(f"{work}/{name}.new.dat", os.F_OK):
            try:
                os.remove(f"{work}/{name}.new.dat")
            except Exception:
                logging.exception('Bugs')
        print(lang.text89 % (name, 'br'))


def mkerofs(name: str, format_, work, work_output, level, old_kernel: bool = False, UTC: int = None):
    if not UTC:
        UTC = int(time.time())
    print(lang.text90 % (name, format_ + f',{level}', "1.x"))
    extra_ = f'{format_},{level}' if format_ != 'lz4' else format_
    other_ = ['-E', 'legacy-compress'] if old_kernel else []
    cmd = ['mkfs.erofs', *other_, f'-z{extra_}', '-T', f'{UTC}', f'--mount-point=/{name}',
           f'--product-out={work}',
           f'--fs-config-file={work}/config/{name}_fs_config',
           f'--file-contexts={work}/config/{name}_file_contexts',
           f'{work_output}/{name}.img', f'{work}/{name}/']
    return call(cmd, out=False)


@animation
def make_ext4fs(name: str, work: str, work_output, sparse: bool = False, size: int = 0, UTC: int = None,
                has_contexts: bool = True):
    if not has_contexts:
        print('Warning:file_context not found!!!')
    print(lang.text91 % name)
    if not UTC:
        UTC = int(time.time())
    if not size:
        size = GetFolderSize(work + name, 1, 3, f"{work}/dynamic_partitions_op_list").rsize_v
    print(f"{name}:[{size}]")
    context_cmd = ['-S', f'{work}/config/{name}_file_contexts'] if has_contexts else []
    command = ['make_ext4fs', '-J', '-T', f'{UTC}', '-s' if sparse else '', *context_cmd, '-l',
               f'{size}',
               '-C', f'{work}/config/{name}_fs_config', '-L', name, '-a', f'/{name}', f"{work_output}/{name}.img",
               work + name]
    return call(command)


@animation
def make_f2fs(name: str, work: str, work_output: str, UTC: int = None):
    print(lang.text91 % name)
    size = GetFolderSize(work + name, 1, 1).rsize_v
    print(f"{name}:[{size}]")
    size_f2fs = (54 * 1024 * 1024) + size
    size_f2fs = int(size_f2fs * 1.15) + 1
    if not UTC:
        UTC = int(time.time())
    with open(f"{work + name}.img", 'wb') as f:
        f.truncate(size_f2fs)
    if call(['mkfs.f2fs', f"{work_output}/{name}.img", '-O', 'extra_attr', '-O', 'inode_checksum', '-O', 'sb_checksum',
             '-O',
             'compression', '-f']) != 0:
        return 1
    # todo:Its A Stupid method, we need a new!
    with open(f'{work}/config/{name}_file_contexts', 'a+', encoding='utf-8') as f:
        if not [i for i in f.readlines() if f'/{name}/{name} u' in i]:
            f.write(f'/{name}/{name} u:object_r:system_file:s0\n')
    return call(
        ['sload.f2fs', '-f', work + name, '-C', f'{work}/config/{name}_fs_config', '-T', f'{UTC}', '-s',
         f'{work}/config/{name}_file_contexts', '-t', f'/{name}', '-c', f'{work_output}/{name}.img'])


def mke2fs(name: str, work: str, sparse: bool, work_output: str, size: int = 0, UTC: int = None):
    if isinstance(size, str): size = int(size)
    print(lang.text91 % name)
    size = GetFolderSize(work + name, 4096, 3,
                         f"{work}/dynamic_partitions_op_list").rsize_v if not size else size / 4096
    print(f"{name}:[{size}]")
    if not UTC:
        UTC = int(time.time())
    if call(
            ['mke2fs', '-O',
             '^has_journal,^metadata_csum,extent,huge_file,^flex_bg,^64bit,uninit_bg,dir_nlink,extra_isize', '-L', name,
             '-I', '256', '-M', f'/{name}', '-m', '0', '-t', 'ext4', '-b', '4096', f'{work_output}/{name}_new.img',
             f'{int(size)}']) != 0:
        rmdir(f'{work_output}/{name}_new.img')
        print(lang.text75 % name)
        return 1
    ret = call(
        ['e2fsdroid', '-e', '-T', f'{UTC}', '-S', f'{work}/config/{name}_file_contexts', '-C',
         f'{work}/config/{name}_fs_config', '-a', f'/{name}', '-f', f'{work}/{name}',
         f'{work_output}/{name}_new.img'], out=not os.name == 'posix')
    if ret != 0:
        rmdir(f'{work}/{name}_new.img')
        print(lang.text75 % name)
        return 1
    if sparse:
        call(['img2simg', f'{work_output}/{name}_new.img', f'{work_output}/{name}.img'])
        try:
            os.remove(f"{work_output}/{name}_new.img")
        except (Exception, BaseException):
            logging.exception('Bugs')
    else:
        if os.path.isfile(f"{work_output}/{name}.img"):
            try:
                os.remove(f"{work_output}/{name}.img")
            except (Exception, BaseException):
                logging.exception('Bugs')
        os.rename(f"{work_output}/{name}_new.img", f"{work_output}/{name}.img")
    return 0


@animation
def rmdir(path: str, quiet: bool = False):
    if not path:
        if not quiet:
            win.message_pop(lang.warn1)
    else:
        if not quiet:
            print(f"{lang.text97} {path}")
        try:
            try:
                rmtree(path)
            except (Exception, BaseException):
                logging.exception("Rmtree")
                call(['busybox', 'rm', '-rf', path], out=False if quiet else True)
        except (Exception, BaseException):
            print(lang.warn11.format(path))
        if not quiet:
            win.message_pop(lang.warn11.format(path)) if os.path.exists(path) else print(lang.text98 + path)


@animation
def pack_zip(input_dir: str = None, output_zip: str = None, silent: bool = False):
    if input_dir is None:
        input_dir = project_manger.current_work_output_path()
        if not project_manger.exist():
            win.message_pop(lang.warn1)
            return
    if output_zip is None:
        output_zip = f"{settings.path}/{current_project_name.get()}.zip"
    if not silent:
        if ask_win(lang.t53) != 1:
            return
    print(lang.text91 % current_project_name.get())
    if not silent:
        if ask_win(lang.t25) == 1:
            PackHybridRom()
    with zipfile.ZipFile(output_zip, 'w',
                         compression=zipfile.ZIP_DEFLATED) as zip_:
        for file in utils.get_all_file_paths(input_dir):
            file = str(file)
            arch_name = file.replace(input_dir, '')
            if not silent:
                print(f"{lang.text1}:{arch_name}")
            try:
                zip_.write(file, arcname=arch_name)
            except Exception as e:
                print(lang.text2.format(file, e))
    if os.path.exists(output_zip):
        print(lang.text3.format(output_zip))


def dndfile(files: list):
    for fi in files:
        if fi.endswith('}') and fi.startswith('{'):
            fi = fi[1:-1]
        try:
            if hasattr(fi, 'decode'):
                fi = fi.decode('gbk')
        except (Exception, BaseException):
            logging.exception('fI')
        if os.path.exists(fi):
            if fi.endswith(".mpk"):
                InstallMpk(fi)
            else:
                create_thread(unpackrom, fi)
        else:
            print(fi + lang.text84)


class ProjectMenuUtils(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text12)
        self.combobox: ttk.Combobox
        self.pack(padx=5, pady=5)

    def gui(self):
        self.combobox = ttk.Combobox(self, textvariable=current_project_name, state='readonly')
        self.combobox.pack(side="top", padx=10, pady=10, fill=X)
        self.combobox.bind('<<ComboboxSelected>>', lambda *x: print(lang.text96 + current_project_name.get()))
        functions = [
            (lang.text23, self.listdir),
            (lang.text115, self.new),
            (lang.text116, lambda: create_thread(self.remove)),
            (lang.text117, lambda: create_thread(self.rename)),
        ]
        for text, func in functions:
            ttk.Button(self, text=text, command=func).pack(side="left", padx=10, pady=10)

    @staticmethod
    def set_project(name):
        if not project_manger.exist(name):
            return
        current_project_name.set(name)

    def listdir(self):
        hide_items = ['bin', 'src']
        array = [f for f in os.listdir(settings.path) if
                 os.path.isdir(settings.path + os.sep + f) and f not in hide_items and not f.startswith('.')]
        origin_project = current_project_name.get()
        self.combobox["value"] = array
        if not array:
            current_project_name.set('')
            self.combobox.current()
        else:
            if origin_project and project_manger.exist(origin_project):
                self.set_project(origin_project)
            else:
                self.combobox.current(0)

    def rename(self) -> bool:
        if not project_manger.exist():
            print(lang.warn1)
            return False
        if os.path.exists(settings.path + os.sep + (
                inputvar := input_(lang.text102 + current_project_name.get(), current_project_name.get()))):
            print(lang.text103)
            return False
        if inputvar != current_project_name.get():
            os.rename(settings.path + os.sep + current_project_name.get(), settings.path + os.sep + inputvar)
            self.listdir()
        else:
            print(lang.text104)
        return True

    def remove(self):
        win.message_pop(lang.warn1) if not project_manger.exist() else rmdir(
            project_manger.get_work_path(current_project_name.get()))
        self.listdir()

    def new(self):
        if not (inputvar := input_()):
            win.message_pop(lang.warn12)
        else:
            inputvar = inputvar.replace(' ', '_')
            if not inputvar.isprintable():
                win.message_pop(lang.warn12)
            print(lang.text99 % inputvar)
            os.mkdir(settings.path + os.sep + inputvar)
        self.listdir()


class Frame3(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text112)
        self.pack(padx=5, pady=5)

    def gui(self):
        row = 0
        functions = [
            (lang.text122, lambda: create_thread(pack_zip)),
            (lang.text123, lambda: create_thread(PackSuper)),
            (lang.text19, lambda: win.notepad.select(win.tab7)),
            (lang.t13, lambda: create_thread(FormatConversion)),
            #("打包 Payload", lambda: create_thread(PackPayload)),
        ]
        for index, (text, func) in enumerate(functions):
            column = index % 4
            if not column:
                row += 1
            ttk.Button(self, text=text, command=func, width=11).grid(row=row, column=column, padx=5, pady=5)


class UnpackGui(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.t57)
        self.ch = BooleanVar()
        # 'current_project_name' must be a global StringVar
        current_project_name.trace_add("write", self._on_project_change)
        
    # New handler method called when changing the project
    def _on_project_change(self, *args):
         """Is called automatically when current_project_name is changed."""
        # Check if the hd method exists and the widget itself before calling
        if hasattr(self, 'hd') and callable(self.hd):
             if self.winfo_exists():
                 # Calling hd() will update the list of partitions for the new project,
                 # Considering the current mode (Unpack/Pack)
                 self.hd()
                 
    def gui(self):
        self.pack(padx=5, pady=5)
        self.ch.set(True)
        self.fm = ttk.Combobox(self, state="readonly",
                               values=(
                                   'new.dat.br', 'new.dat.xz', "new.dat", 'img', 'zst', 'payload', 'super',
                                   'update.app'))
        self.lsg = ListBox(self)
        self.menu = Menu(self.lsg, tearoff=False, borderwidth=0)
        self.menu.add_command(label=lang.attribute, command=self.info)
        self.lsg.bind('<Button-3>', self.show_menu)
        self.fm.current(0)
        self.fm.bind("<<ComboboxSelected>>", lambda *x: self.refs())
        self.lsg.gui()
        self.lsg.canvas.bind('<Button-3>', self.show_menu)
        self.lsg.pack(padx=5, pady=5, fill=X, side='top', expand=True)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=50, fill=X)
        ff1 = ttk.Frame(self)
        ttk.Radiobutton(ff1, text=lang.unpack, variable=self.ch,
                        value=True).pack(padx=5, pady=5, side='left')
        ttk.Radiobutton(ff1, text=lang.pack, variable=self.ch,
                        value=False).pack(padx=5, pady=5, side='left')
        ff1.pack(padx=5, pady=5, fill=X)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=50, fill=X)
        self.fm.pack(padx=5, pady=5, fill=Y, side='left')
        ttk.Button(self, text=lang.run, command=lambda: create_thread(self.close_)).pack(padx=5, pady=5, side='left')
        self.refs()
        self.ch.trace("w", lambda *x: self.hd())

    def show_menu(self, event):
        if len(self.lsg.selected) == 1 and self.fm.get() == 'img':
            self.menu.post(event.x_root, event.y_root)

    def info(self):
        ck_ = Toplevel()
        move_center(ck_)
        ck_.title(lang.attribute)
        if not self.lsg.selected:
            ck_.destroy()
            return
        f_path = os.path.join(project_manger.current_work_path(), self.lsg.selected[0] + ".img")
        if not os.path.exists(f_path):
            ck_.destroy()
            return
        f_type = gettype(f_path)
        info = [["Path", f_path], ['Type', f_type], ["Size", os.path.getsize(f_path)]]
        if f_type == 'ext':
            with open(f_path, 'rb') as e:
                for i in ext4.Volume(e).get_info_list:
                    info.append(i)
        scroll = ttk.Scrollbar(ck_, orient='vertical')
        columns = [lang.name, 'Value']
        table = ttk.Treeview(master=ck_, height=10, columns=columns, show='headings', yscrollcommand=scroll.set)
        for column in columns:
            table.heading(column=column, text=column, anchor=CENTER)
            table.column(column=column, anchor=CENTER)
        scroll.config(command=table.yview)
        scroll.pack(side=RIGHT, fill=Y)
        table.pack(fill=BOTH, expand=True)
        for data in info:
            table.insert('', tk.END, values=data)
        ttk.Button(ck_, text=lang.ok, command=ck_.destroy).pack(padx=5, pady=5, fill=X)

    def hd(self):
        if self.ch.get():
            self.fm.configure(state='readonly')
            self.refs()
        else:
            self.fm.configure(state="disabled")
            self.refs2()

    def refs(self, auto: bool = False):
        self.lsg.clear()
        work = project_manger.current_work_path()
        if not project_manger.exist():
            return False
        if auto:
            for index, value in enumerate(self.fm.cget("values")):
                self.fm.current(index)
                self.refs()
                if len(self.lsg.vars):
                    return True
            self.fm.current(0)
            return True
        form = self.fm.get()
        if form == 'payload':
            if os.path.exists(f"{work}/payload.bin"):
                with open(f"{work}/payload.bin", 'rb') as pay:
                    for i in utils.payload_reader(pay).partitions:
                        self.lsg.insert(f"{i.partition_name}{hum_convert(i.new_partition_info.size):>10}",
                                        i.partition_name)
        elif form == 'super':
            if os.path.exists(f"{work}/super.img"):
                if gettype(f"{work}/super.img") == 'sparse':
                    create_thread(utils.simg2img, f"{work}/super.img", join=True)
                for i in lpunpack.get_parts(f"{work}/super.img"):
                    self.lsg.insert(i, i)
        elif form == 'update.app':
            if os.path.exists(f"{work}/UPDATE.APP"):
                for i in splituapp.get_parts(f"{work}/UPDATE.APP"):
                    self.lsg.insert(i, i)
        else:
            for file_name in os.listdir(work):
                if file_name.endswith(form):
                    f_type = gettype(work + file_name)
                    if f_type == 'unknown':
                        f_type = form
                    self.lsg.insert(f'{file_name.split(f".{form}")[0]} [{f_type}]',
                                    file_name.split(f".{form}")[0])
        return True

    def refs2(self):
        self.lsg.clear()
        if not os.path.exists(work := project_manger.current_work_path()):
            win.message_pop(lang.warn1)
            return False
        parts_dict = JsonEdit(f"{work}/config/parts_info").read()
        for folder in os.listdir(work):
            if os.path.isdir(work + folder) and folder in parts_dict.keys():
                self.lsg.insert(f"{folder} [{parts_dict.get(folder, 'Unknown')}]", folder)
        return True

    def close_(self):
        lbs = self.lsg.selected.copy()
        self.hd()
        if self.ch.get() == 1:
            unpack(lbs, self.fm.get())
            self.refs()
        else:
            Packxx(lbs)


def img2simg(path: str):
    call(['img2simg', path, f'{path}s'])
    if os.path.exists(path + 's'):
        try:
            os.remove(path)
            os.rename(path + 's', path)
        except Exception:
            logging.exception('Bugs')


class FormatConversion(ttk.LabelFrame):
    def __init__(self):
        super().__init__(text=lang.t13)
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.f = Frame(self)
        self.f.pack(pady=5, padx=5, fill=X)
        self.h = ttk.Combobox(self.f, values=("raw", "sparse", 'dat', 'br', 'xz'), state='readonly')
        self.h.current(0)
        self.h.bind("<<ComboboxSelected>>", lambda *x: self.relist())
        self.h.pack(side='left', padx=5)
        Label(self.f, text='>>>>>>').pack(side='left', padx=5)
        self.f = ttk.Combobox(self.f, values=("raw", "sparse", 'dat', 'br'), state='readonly')
        self.f.current(0)
        self.f.pack(side='left', padx=5)
        self.list_b = ListBox(self)
        self.list_b.gui()
        self.list_b.pack(padx=5, pady=5, fill=BOTH)
        create_thread(self.relist)
        t = Frame(self)
        ttk.Button(t, text=lang.cancel, command=self.destroy).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                   expand=True)
        ttk.Button(t, text=lang.ok, command=lambda: create_thread(self.conversion), style='Accent.TButton').pack(
            side='left',
            padx=5, pady=5,
            fill=BOTH,
            expand=True)
        t.pack(side=BOTTOM, fill=BOTH)

    def relist(self):
        work = project_manger.current_work_path()
        self.list_b.clear()
        if self.h.get() == "br":
            for i in self.refile(".new.dat.br"):
                self.list_b.insert(i, i)
        elif self.h.get() == 'xz':
            for i in self.refile(".new.dat.xz"):
                self.list_b.insert(i, i)
        elif self.h.get() == 'dat':
            for i in self.refile(".new.dat"):
                self.list_b.insert(i, i)
        elif self.h.get() == 'sparse':
            for i in os.listdir(work):
                if os.path.isfile(f'{work}/{i}') and gettype(f'{work}/{i}') == 'sparse':
                    self.list_b.insert(i, i)
        elif self.h.get() == 'raw':
            for i in os.listdir(work):
                if os.path.isfile(f'{work}/{i}'):
                    if gettype(f'{work}/{i}') in ['ext', 'erofs', 'super', 'f2fs']:
                        self.list_b.insert(i, i)

    @staticmethod
    def refile(f):
        for i in os.listdir(work := project_manger.current_work_output_path()):
            if i.endswith(f) and os.path.isfile(f'{work}/{i}'):
                yield i

    @animation
    def conversion(self):
        work = project_manger.current_work_output_path()
        f_get = self.f.get()
        hget = self.h.get()
        selection = self.list_b.selected.copy()
        self.destroy()
        if f_get == hget:
            return
        for i in selection:
            print(f'[{hget}->{f_get}]{i}')
            if f_get == 'sparse':
                basename = os.path.basename(i).split('.')[0]
                if hget == 'br':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        call(['brotli', '-dj', f'{work}/{i}'])
                if hget == 'xz':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        Unxz(f'{work}/{i}')
                if hget == 'dat':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + f'{work}/{i}')
                        transferfile = os.path.abspath(
                            os.path.dirname(work)) + f"/{basename}.transfer.list"
                        if os.access(transferfile, os.F_OK) and os.path.getsize(f'{work}/{i}') != 0:
                            Sdat2img(transferfile, f'{work}/{i}', f"{work}/{basename}.img")
                            if os.access(f"{work}/{basename}.img", os.F_OK):
                                os.remove(f'{work}/{i}')
                                os.remove(transferfile)
                                try:
                                    os.remove(f'{work}/{basename}.patch.dat')
                                except (IOError, PermissionError, FileNotFoundError):
                                    logging.exception('Bugs')
                        else:
                            print("transferpath" + lang.text84)
                    if os.path.exists(f'{work}/{basename}.img'):
                        img2simg(f'{work}/{basename}.img')
                if hget == 'raw':
                    if os.path.exists(f'{work}/{basename}.img'):
                        img2simg(f'{work}/{basename}.img')
            elif f_get == 'raw':
                basename = os.path.basename(i).split('.')[0]
                if hget == 'br':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        call(['brotli', '-dj', f'{work}/{i}'])
                if hget == 'xz':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        Unxz(f'{work}/{i}')
                if hget in ['dat', 'br', 'xz']:
                    if os.path.exists(work):
                        if hget == 'br':
                            i = i.replace('.br', '')
                        if hget == 'xz':
                            i = i.replace('.xz', '')
                        print(lang.text79 + f'{work}/{i}')
                        transferfile = os.path.abspath(
                            os.path.dirname(work)) + f"/{basename}.transfer.list"
                        if os.access(transferfile, os.F_OK) and os.path.getsize(f'{work}/{i}') != 0:
                            Sdat2img(transferfile, f'{work}/{i}', f"{work}/{basename}.img")
                            if os.access(f"{work}/{basename}.img", os.F_OK):
                                try:
                                    os.remove(f'{work}/{i}')
                                    os.remove(transferfile)
                                    if not os.path.getsize(f'{work}/{basename}.patch.dat'):
                                        os.remove(f'{work}/{basename}.patch.dat')
                                except (PermissionError, IOError, FileNotFoundError, IsADirectoryError):
                                    logging.exception('Bugs')
                        else:
                            print("transferfile" + lang.text84)
                if hget == 'sparse':
                    utils.simg2img(f'{work}/{i}')
            elif f_get == 'dat':
                if hget == 'raw':
                    img2simg(f'{work}/{i}')
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], "dat")
                if hget == 'br':
                    print(lang.text79 + i)
                    call(['brotli', '-dj', f'{work}/{i}'])
                if hget == 'xz':
                    print(lang.text79 + i)
                    Unxz(f'{work}/{i}')

            elif f_get == 'br':
                if hget == 'raw':
                    img2simg(f'{work}/{i}')
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], 0)
                if hget in ['dat', 'xz']:
                    if hget == 'xz':
                        print(lang.text79 + i)
                        Unxz(f'{work}/{i}')
                        i = i.rsplit('.xz', 1)[0]

                    print(lang.text88 % (os.path.basename(i).split('.')[0], 'br'))
                    call(['brotli', '-q', '0', '-j', '-w', '24', f'{work}/{i}', '-o', f'{work}/{i}.br'])
                    if os.access(f'{work}/{i}.br', os.F_OK):
                        try:
                            os.remove(f'{work}/{i}')
                        except Exception:
                            logging.exception('Bugs')
        print(lang.text8)


def init_verify():
    if not os.path.exists(settings.tool_bin):
        error(1, 'Sorry,Not support your device yet.')
    if not settings.path.isprintable():
        ask_win(lang.warn16 % lang.special_words, is_top=True)


def exit_tool():
    module_manager.addon_loader.run_entry(module_manager.addon_entries.close)
    win.destroy()


class ParseCmdline:
    def __init__(self, args_list):
        self.args_list = args_list
        self.cmd_exit = settings.cmd_exit
        if settings.cmd_invisible == '1':
            win.withdraw()
            win.iconify()
        self.parser = argparse.ArgumentParser(prog='tool', description='A cool tool like hat-Mita!',
                                              exit_on_error=False)
        subparser = self.parser.add_subparsers(title='subcommand',
                                               description='Valid subcommands')
        # Unpack Rom
        unpack_rom_parser = subparser.add_parser('unpack', add_help=False, help="Unpack Suported File")
        unpack_rom_parser.set_defaults(func=dndfile)
        # Set Config
        set_config_parse = subparser.add_parser('set', help="Set Config")
        set_config_parse.set_defaults(func=self.set)
        get_config_parse = subparser.add_parser('get', help="Get Config")
        get_config_parse.set_defaults(func=self.get)
        # Help
        help_parser = subparser.add_parser('help', help="Print Help")
        help_parser.set_defaults(func=self.help)
        # Lpmake
        lpmake_parser = subparser.add_parser('lpmake', help='To make super image')
        lpmake_parser.set_defaults(func=self.lpmake)
        # End
        if len(args_list) == 1 and args_list[0] not in ["help", '--help', '-h']:
            dndfile(args_list)
        if len(args_list) == 1 and args_list[0] in ['--help', '-h']:
            self.help([])
        else:
            try:
                self.__parse()
            except (argparse.ArgumentError, ValueError):
                logging.exception('CMD')
                self.help([])
                self.cmd_exit = '1'
        if self.cmd_exit == '1':
            sys.exit(1)

    # Hidden Methods
    def __parse(self):
        subcmd, subcmd_args = self.parser.parse_known_args(self.args_list)
        if not hasattr(subcmd, 'func'):
            self.parser.print_help()
            return
        subcmd.func(subcmd_args)

    def __pass(self):
        pass

    # Export Methods
    def set(self, args):
        if len(args) > 2:
            print('Many Args!')
            return
        name, value = args
        settings.set_value(name, value)
        logging.info(f'Set Config ({name})[{getattr(settings, name, "")}] ==> [{value}]')
        self.__pass()

    def get(self, args):
        if len(args) > 1:
            cprint('Many Args!')
            return
        name, = args
        cprint(getattr(settings, name))
        self.__pass()

    def help(self, args):
        if hasattr(sys, 'stdout_origin'):
            self.parser.print_help(sys.stdout_origin)
        else:
            logging.warning('sys.stdout_origin not defined!')

    def lpmake(self, arglist):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('outputdir', nargs='?',
                            type=str,
                            default=None)
        parser.add_argument('workdir', type=str, help='The Work Dir', action='store', default=None)
        parser.add_argument('--sparse', type=int, dest='Sparse:1.enable 0.disable', action='store', default=0)
        # dbfz...
        parser.add_argument('--group-name', type=str, action='store',
                            help='qti_dynamic_partitions main mot_dp_group',
                            default='qti_dynamic_partitions')
        parser.add_argument('--size', type=int, help='Super Size (Bytes)',
                            action='store',
                            default=9126805504)
        parser.add_argument('--list', type=str,
                            help='the including parts of the super, use "," to split, like"odm,system"',
                            action='store',
                            default=None)
        # Wheather remove source files
        parser.add_argument('--delete', type=int, help='Delete Source Images:1.del 0.no_del',
                            action='store',
                            default=0)
        # V-AB AB A-ONLY
        parser.add_argument('--part_type', type=int, help='[1] A-only [2] V-ab [3] a/b',
                            action='store',
                            default=1)
        # the attrib of super
        parser.add_argument('--attrib', type=str, help='The Attrib Of the super',
                            action='store',
                            default='readonly')
        args = parser.parse_args(arglist)
        if not args.workdir or not args.outputdir \
                or not os.path.exists(args.workdir) or not os.path.exists(args.outputdir):
            cprint("Workdir or Output Dir Not Exist!")
            return


def __init__tk(args: list):
    if not os.path.exists(temp):
        re_folder(temp, quiet=True)
    if not os.path.exists(tool_log):
        open(tool_log, 'w', encoding="utf-8", newline="\n").close()
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(asctime)s:%(filename)s:%(name)s:%(message)s',
                        filename=tool_log, filemode='w')
    global win
    win = Tool()
    if os.name == 'nt':
        set_title_bar_color(win)
    animation.set_master(win)
    global current_project_name, theme, language
    current_project_name = utils.project_name = StringVar()
    theme = StringVar()
    language = StringVar()
    settings.load()
    if settings.updating in ['1', '2']:
        Updater()
    if int(settings.oobe) < 5:
        Welcome()
    init_verify()
    try:
        win.winfo_exists()
    except TclError:
        logging.exception('TclError')
        return
    win.gui()
    global unpackg
    unpackg = UnpackGui()
    global project_menu
    project_menu = ProjectMenuUtils()
    project_menu.gui()
    project_menu.listdir()
    unpackg.gui()
    Frame3().gui()
    animation.load_gif(open_img(BytesIO(getattr(images, f"loading_{win.list2.get()}_byte"))))
    animation.init()
    if not is_pro:
        print(lang.text108)
    if is_pro:
        if not verify.state:
            Active(verify, settings, win, images, lang).gui()
    win.update()

    move_center(win)
    win.get_time()
    print(lang.text134 % (dti() - start))
    if os.name == 'nt':
        do_override_sv_ttk_fonts()
        if sys.getwindowsversion().major <= 6:
            ask_win(lang.warn20)
    states.inited = True
    win.protocol("WM_DELETE_WINDOW", exit_tool)
    if len(args) > 1 and is_pro:
        win.after(1000, ParseCmdline, args[1:])
    win.mainloop()


# Cool Init
# Miside 米塔
# Link: https://store.steampowered.com/app/2527500/
init = lambda args: __init__tk(args)


def restart(er: Toplevel = None):
    try:
        if animation.tasks:
            if not ask_win("Your operation will not be saved.", is_top=True):
                return
    except (TclError, ValueError, AttributeError):
        logging.exception('Restart')

    def _inner():
        argv = [sys.executable]
        if not pathlib.Path(tool_self).samefile(pathlib.Path(argv[0])):
            # only needed when running within a Python intepreter
            argv.append(tool_self)
        argv.extend(sys.argv[1:])
        p = subprocess.Popen(argv)
        p.wait()
        sys.exit(p.returncode)

    if er: er.destroy()
    try:
        for i in win.winfo_children():
            try:
                i.destroy()
            except (TclError, ValueError, AttributeError):
                logging.exception('Restart')
        win.destroy()
    except (Exception, BaseException):
        logging.exception('Restart')

    threading.Thread(target=_inner).start()
