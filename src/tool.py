#!/usr/bin/env python3
# pylint: disable=line-too-long, missing-class-docstring, missing-function-docstring
# Copyright (C) 2024 The MIO-KITCHEN-SOURCE Project
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
import gzip
import json
import platform
import shutil
import subprocess
import threading
from collections import deque
from functools import wraps
from random import randrange
from tkinter.ttk import Scrollbar

import tarsafe
from PyQt6.QtWidgets import QApplication

from .core.Magisk import Magisk_patch
from .core.romfs_parse import RomfsParse
from .core.unkdz import KDZFileTools
from .qtui import MainWindow

if platform.system() != 'Darwin':
    try:
        import pyi_splash

        pyi_splash.update_text('Loading ...')
        pyi_splash.close()
    except ModuleNotFoundError:
        ...
import os.path
import pathlib
import shlex
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
from tkinter import (BOTH, LEFT, RIGHT, Canvas, Text, X, Y, BOTTOM, StringVar, IntVar, TOP, Toplevel,
                     HORIZONTAL, TclError, Frame, Label, Listbox, DISABLED, Menu, BooleanVar, CENTER)
from shutil import rmtree, copy, move
import pygments.lexers
import requests
from requests import ConnectTimeout, HTTPError
import sv_ttk
from PIL.Image import open as open_img
from PIL.ImageTk import PhotoImage
from .core.dumper import Dumper
from .core.utils import lang, LogoDumper, States, terminate_process, calculate_md5_file, calculate_sha256_file, JsonEdit

if os.name == 'nt':
    from ctypes import windll
    from tkinter import filedialog
    import pywinstyles
else:
    from .core import mkc_filedialog as filedialog

from .core import imgextractor
from .core import lpunpack
from .core import mkdtboimg
from .core import ozipdecrypt
from .core import splituapp
from .core import ofp_qc_decrypt
from .core import ofp_mtk_decrypt
from . import editor
from .core import opscrypto
from .core import images
from .core import extra
from . import AI_engine
from .core import ext4
from .core.config_parser import ConfigParser
from .core import utils
if os.name == 'nt':
    from .sv_ttk_fixes import *
from .core.extra import fspatch, re, contextpatch
from .core.utils import create_thread, move_center, v_code, gettype, is_empty_img, findfile, findfolder, Sdat2img, Unxz
from .controls import ListBox, ScrollFrame
from .core.undz import DZFileTools
from .core.selinux_audit_allow import main as selinux_audit_allow
import logging
is_pro = False
try:
    from .pro.sn import v as verify
    is_pro = True
except ImportError:
    is_pro = False
if is_pro:
    from .pro.active_ui import Active

try:
    from . import imp
except ImportError:
    imp = None
try:
    from .core.pycase import ensure_dir_case_sensitive
except ImportError:
    ensure_dir_case_sensitive = lambda *x: print(f'Cannot sensitive {x}, Not Supported')

cwd_path = utils.prog_path








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
        if self.task_num_index > self.task_num_max:
            self.task_num_index = 0
        while self.task_num_index in self.tasks:
            self.task_num_index += 1
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
            create_thread(self.run())
            task_num = self.get_task_num()
            task_real = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
            info = [func.__name__, args, task_real]
            if task_num in self.tasks:
                print(f"The Same task_num {task_num} was used by {task_real.native_id} with args {info[2]}...\n")
                return
            else:
                self.tasks[task_num] = info
            task_real.start()
            task_real.join()
            if task_num in self.tasks:
                del self.tasks[task_num]
            del info, task_num
            if not self.tasks:
                self.stop()

        return call_func


def warn_win(text: str = '', color: str = 'orange', title: str = "Warn", wait: int = 1500):
    ask = ttk.LabelFrame(win)
    ask.configure(text=title)
    ask.place(relx=0.5, rely=0.5, anchor="nw")
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20), foreground=color).pack(side=TOP)
    ask.after(wait, ask.destroy)

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
        ]
        width_controls = 3
        #
        index_row = 0
        index_column = 0
        for text, func in functions:
            ttk.Button(self.label_frame, text=text, command=func, width=17).grid(row=index_row, column=index_column,
                                                                                 padx=5, pady=5)
            if index_column < (width_controls - 1):
                index_column += 1
            else:
                index_column = 0
                index_row += 1
        self.update_ui()

    def update_ui(self):
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

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
            magiskboot = settings.tool_bin + os.sep + "magiskboot"
            with Magisk_patch(self.boot_file.get(), None, magiskboot, local_path, self.IS64BIT.get(),
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
            self.patch_bu = ttk.Button(self, text=lang.patch, style='Accent.TButton', command=lambda: create_thread(self.patch))
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
            self.values = ("B", "KB", "MB", "GB", 'TB')
            self.title(lang.t60)
            self.gui()

        def gui(self):
            self.f = Frame(self)
            self.f.pack(pady=5, padx=5, fill=X)
            self.origin_size = ttk.Entry(self.f)
            self.origin_size.bind("<KeyRelease>", lambda *x: self.calc())
            self.origin_size.pack(side='left', padx=5)
            self.h = ttk.Combobox(self.f, values=self.values, state='readonly', width=3)
            self.h.current(0)
            self.h.bind("<<ComboboxSelected>>", lambda *x: self.calc())
            self.h.pack(side='left', padx=5)
            Label(self.f, text='=').pack(side='left', padx=5)
            self.result_size = ttk.Entry(self.f)
            self.result_size.pack(side='left', padx=5)
            self.f_ = ttk.Combobox(self.f, values=self.values, state='readonly', width=3)
            self.f_.current(0)
            self.f_.bind("<<ComboboxSelected>>", lambda *x: self.calc())
            self.f_.pack(side='left', padx=5)
            ttk.Button(self, text=lang.text17, command=self.destroy).pack(fill=BOTH, padx=5, pady=5)
            move_center(self)

        def calc(self):
            self.result_size.delete(0, tk.END)
            self.result_size.insert(0, self.__calc(self.h.get(), self.f_.get(), self.origin_size.get()))

        @staticmethod
        def __calc(origin: str, convert: str, size) -> str:
            if origin == convert:
                return size
            try:
                origin_size = float(size)
            except ValueError:
                return "0"

            units = {
                "B": 1,
                "KB": 2 ** 10,
                "MB": 2 ** 20,
                "GB": 2 ** 30,
                "TB": 2 ** 40
            }

            return str(origin_size * units[origin] / units[convert])

    class GetFileInfo(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.t59)
            self.controls = []
            self.gui()
            self.geometry("400x450")
            self.resizable(False, False)
            self.dnd = lambda file_list:create_thread(self.__dnd, file_list)
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
        ttk.Button(frame, text=lang.text17, command=frame.destroy).pack(anchor="ne")
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
        self.tab = ttk.Frame(self.notepad)
        self.tab2 = ttk.Frame(self.notepad)
        self.tab3 = ttk.Frame(self.notepad)
        self.tab4 = ttk.Frame(self.notepad)
        self.tab5 = ttk.Frame(self.notepad)
        self.tab6 = ttk.Frame(self.notepad)
        self.tab7 = ttk.Frame(self.notepad)
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
        self.tab_content()
        self.notepad.pack(fill=BOTH, expand=True)
        self.rzf = ttk.Frame(self.sub_win3)
        self.tsk = Label(self.sub_win3, text="MIO-KITCHEN", font=(None, 15))
        self.tsk.pack(padx=10, pady=10, side='top')
        tr = ttk.LabelFrame(self.sub_win3, text=lang.text131)
        tr2 = Label(tr, text=lang.text132 + '\n(ozip zip tar.md5 tar tar.gz kdz dz ops ofp ext4 erofs boot img)')
        tr2.pack(padx=10, pady=10, side='bottom')
        tr.bind('<Button-1>', lambda *x: dndfile([filedialog.askopenfilename()]))
        tr.pack(padx=5, pady=5, side='top', expand=True, fill=BOTH)
        tr2.bind('<Button-1>', lambda *x: dndfile([filedialog.askopenfilename()]))
        tr2.pack(padx=5, pady=5, side='top', expand=True, fill=BOTH)
        self.scroll = ttk.Scrollbar(self.rzf)
        self.show = Text(self.rzf)
        self.show.pack(side=LEFT, fill=BOTH, expand=True)
        sys.stdout = StdoutRedirector(self.show)
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
        if settings.custom_system == 'Android' and os.geteuid() != 0:
            ask_win(lang.warn16, wait=False)
            if call(['su', '-c', 'echo ok'], extra_path=False) != 0:
                ask_win(lang.warn17)
        if settings.custom_system == 'Android' and os.geteuid() == 0:
            os.makedirs('/data/local/MIO', exist_ok=True)

    def tab_content(self):
        global kemiaojiang
        kemiaojiang_img = open_img(open(f'{cwd_path}/bin/kemiaojiang.png', 'rb'))
        kemiaojiang = PhotoImage(kemiaojiang_img.resize((280, 540)))
        Label(self.tab, image=kemiaojiang).pack(side='left', padx=0, expand=True)
        Label(self.tab, text="Ambassador: KeMiaoJiang\nPainter: HY-惠\nWelcome To MIO-KITCHEN", justify='left',
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
            self.rotate_angle -= 10
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

    def support(self):
        if states.donate_window:
            return
        states.donate_window = True
        tab = ttk.LabelFrame(text=lang.text16)
        tab.place(relx=0.5, rely=0.5, anchor="center")
        Label(tab,
              text=lang.t62,
              font=(None, 20), fg='#008000').pack(padx=10, pady=10)
        self.photo = PhotoImage(data=images.wechat_byte)
        Label(tab, image=self.photo).pack(padx=5, pady=5)
        Label(tab, text=lang.text109, font=(None, 12), fg='#00aafA').pack(padx=10, pady=10)
        ttk.Button(tab, text=lang.text17,
                   command=lambda: tab.destroy() == setattr(states, 'donate_window', False)).pack(
            fill=X, side='bottom')

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
                if ask_win2(
                        lang.warn18):
                    settings.set_value('contextpatch', context.get())
                else:
                    context.set('0')
                    settings.set_value('contextpatch', context.get())
                    enable_cp.configure(state='off')
            else:
                settings.set_value('contextpatch', context.get())

        context.trace("w", lambda *x: enable_contextpatch())
        get_setting_button('ai_engine', sf4, lang.ai_engine)
        if os.name == 'nt':
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
        ttk.Button(self.tab3, text=lang.text16, command=self.support).pack(padx=10, pady=10, fill=X, side=BOTTOM)


# win = Tool()
animation = LoadAnim()
start = dti()

tool_self = os.path.normpath(os.path.abspath(sys.argv[0]))
temp = os.path.join(cwd_path, "bin", "temp").replace(os.sep, '/')
tool_log = f'{temp}/{time.strftime("%Y%m%d_%H-%M-%S", time.localtime())}_{v_code()}.log'
states = States()
module_exec = os.path.join(cwd_path, 'bin', "exec.sh").replace(os.sep, '/')
# Some Functions for Upgrade



class Updater(Toplevel):

    def __init__(self):
        if states.update_window:
            self.destroy()
        super().__init__()
        if os.name == 'nt' and settings.treff == '1':
            pywinstyles.apply_style(self, 'acrylic')
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
        package = f'{self.package_head}'
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
                        update_files.append([os.path.join(temp, file), file])
                else:
                    zip_ref.extract(file, os.path.join(cwd_path, "bin"))
        update_dict = {
            'updating': '1',
            'language': settings.language,
            'oobe': settings.oobe,
            'new_tool': os.path.join(cwd_path, "bin", "tool" + ('' if os.name != 'nt' else '.exe')),
            "version_old": settings.version,
            "update_files": update_files
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
            for i in settings.update_files:
                try:
                    path, real = i
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
        self.frame = None
        oobe = int(settings.oobe)
        states.in_oobe = True
        frames = {
            1: self.main,
            2: self.license,
            3: self.private,
            4: self.support,
            5: self.done
        }
        if frames.get(oobe):
            frames.get(oobe, self.main)()
        else:
            ttk.Label(self, text=lang.text135, font=(None, 40)).pack(padx=10, pady=10, fill=X)
            ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
            ttk.Label(self, text=lang.text137, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)
            ttk.Button(self, text=lang.text136, command=self.main).pack(fill=X)
        move_center(win)
        self.wait_window()
        states.in_oobe = False

    def reframe(self):
        if self.frame:
            self.frame.destroy()
        self.frame = ttk.Frame(self)
        move_center(win)
        self.frame.pack(expand=1, fill=BOTH)

    def main(self):
        settings.set_value("oobe", 1)
        for i in self.winfo_children():
            i.destroy()
        self.reframe()
        ttk.Label(self.frame, text=lang.text129, font=(None, 20)).pack(padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb3_ = ttk.Combobox(self.frame, state='readonly', textvariable=language,
                            values=[i.rsplit('.', 1)[0] for i in
                                    os.listdir(f"{cwd_path}/bin/languages")])
        lb3_.pack(padx=10, pady=10, side='top', fill=BOTH)
        lb3_.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())
        ttk.Button(self.frame, text=lang.text138, command=self.license).pack(fill=X, side='bottom')

    def license(self):
        settings.set_value("oobe", 2)
        lce = StringVar()

        def load_license():
            te.delete(1.0, tk.END)
            with open(f"{cwd_path}/bin/licenses/{lce.get()}.txt", 'r',
                      encoding='UTF-8') as f:
                te.insert('insert', f.read())

        self.reframe()
        lb = ttk.Combobox(self.frame, state='readonly', textvariable=lce,
                          values=[i.rsplit('.')[0] for i in os.listdir(f"{cwd_path}/bin/licenses") if
                                  i != 'private.txt'])
        lb.bind('<<ComboboxSelected>>', lambda *x: load_license())
        lb.current(0)
        ttk.Label(self.frame, text=lang.text139, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb.pack(padx=10, pady=10, side='top', fill=X)
        te = Text(self.frame, height=10)
        te.pack(fill=BOTH, side='top', expand=True)
        load_license()
        ttk.Label(self.frame, text=lang.t1).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.private).pack(fill=BOTH, side='bottom')

    def private(self):
        settings.set_value("oobe", 3)
        self.reframe()
        ttk.Label(self.frame, text=lang.t2, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        with open(os.path.join(cwd_path, "bin", "licenses", "private.txt"), 'r',
                  encoding='UTF-8') as f:
            (te := Text(self.frame, height=10)).insert('insert', f.read())
        te.pack(fill=BOTH, expand=True)
        ttk.Label(self.frame, text=lang.t3).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.support).pack(fill=BOTH, side='bottom')

    def support(self):
        settings.set_value("oobe", 4)
        self.reframe()
        ttk.Label(self.frame, text=lang.text16, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X
                                                                      )
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        self.photo = PhotoImage(data=images.wechat_byte)
        Label(self.frame, image=self.photo).pack(padx=5, pady=5)
        ttk.Label(self.frame, text=lang.text109).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.done).pack(fill=BOTH, side='bottom')

    def done(self):
        settings.set_value("oobe", 5)
        self.reframe()
        ttk.Label(self.frame, text=lang.t4, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.t5, font=(None, 20)).pack(
            side='top', fill=BOTH, padx=10, pady=10, expand=True)
        ttk.Button(self, text=lang.text34, command=self.destroy).pack(fill=BOTH, side='bottom')


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
        self.updating = ''
        self.new_tool = ''
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
        if os.name != 'nt':
            win.attributes("-alpha", self.bar_level)
        else:
            if self.treff == '1':
                pywinstyles.apply_style(win, 'acrylic')
            else:
                pywinstyles.apply_style(win, 'normal')
                pywinstyles.apply_style(win, 'mica')

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
        [setattr(lang, i, _lang[i]) for i in _lang]

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
    if not (dtboimg := findfile(f"{bn}.img", work := ProjectManager.current_work_path())):
        print(lang.warn3.format(bn))
        return
    re_folder(work + bn)
    re_folder(f"{work}{bn}/dtbo")
    re_folder(work + bn + "/dts")
    try:
        mkdtboimg.dump_dtbo(dtboimg, work + bn + "/dtbo/dtbo")
    except Exception as e:
        logging.exception("Bugs")
        print(lang.warn4.format(e))
        return
    for dtbo in os.listdir(work + bn + os.sep + "dtbo"):
        if dtbo.startswith("dtbo."):
            print(lang.text4.format(dtbo))
            call(
                exe=['dtc', '-@', '-I', 'dtb', '-O', 'dts', f'{work}{bn}/dtbo/{dtbo}', '-o',
                     os.path.join(work, bn, 'dts', 'dts.' + os.path.basename(dtbo).rsplit('.', 1)[1])],
                out=1)
    print(lang.text5)
    try:
        os.remove(dtboimg)
    except (Exception, BaseException):
        logging.exception('Bugs')
    rmdir(work + "dtbo/dtbo")


@animation
def pack_dtbo() -> bool:
    work = ProjectManager.current_work_path()
    if not os.path.exists(work + "dtbo/dts") or not os.path.exists(work + "dtbo"):
        print(lang.warn5)
        return False
    re_folder(work + "dtbo/dtbo")
    for dts in os.listdir(work + "dtbo/dts"):
        if dts.startswith("dts."):
            print(f"{lang.text6}:{dts}")
            call(
                exe=['dtc', '-@', '-I', 'dts', '-O', 'dtb', os.path.join(work, 'dtbo', 'dts', dts), '-o',
                     os.path.join(work, 'dtbo', 'dtbo', 'dtbo.' + os.path.basename(dts).rsplit('.', 1)[1])],
                out=1)
    print(f"{lang.text7}:dtbo.img")
    list_ = [os.path.join(work, "dtbo", "dtbo", f) for f in os.listdir(work + "dtbo/dtbo") if
             f.startswith("dtbo.")]
    mkdtboimg.create_dtbo(ProjectManager.current_work_output_path() + "dtbo.img",
                          sorted(list_, key=lambda x: int(x.rsplit('.')[1])), 4096)
    rmdir(work + "dtbo")
    print(lang.text8)
    return True


@animation
def logo_dump(file_path, output: str = None, output_name: str = "logo"):
    if output is None:
        output = ProjectManager.current_work_path()
    if not os.path.exists(file_path):
        win.message_pop(lang.warn3.format(output_name))
        return False
    re_folder(output + output_name)
    LogoDumper(file_path, output + output_name).unpack()

@animation
def logo_pack(origin_logo=None) -> int:
    work = ProjectManager.current_work_path()
    if not origin_logo:
        origin_logo = findfile('logo.img', work)
    logo = work + "logo-new.img"
    if not os.path.exists(dir_ := work + "logo") or not os.path.exists(origin_logo):
        print(lang.warn6)
        return 1
    utils.LogoDumper(origin_logo, logo, dir_).repack()
    os.remove(origin_logo)
    os.rename(logo, origin_logo)
    rmdir(dir_)


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


class ModuleManager:
    def __init__(self):
        self.module_dir = os.path.join(cwd_path, "bin", "module")
        self.uninstall_gui = self.UninstallMpk
        self.new = self.New
        self.new.module_dir = self.module_dir
        self.uninstall_gui.module_dir = self.module_dir
        self.MshParse.module_dir = self.module_dir
        self.errorcodes = self.ErrorCodes()
        self.get_name = lambda id_: name if (name := self.get_info(id_, 'name')) else id_
        self.get_installed = lambda id_: os.path.exists(os.path.join(self.module_dir, id_))
        self.startlist = os.path.join(self.module_dir, 'start.list')
        self.start_list_lock = False
        create_thread(self.exec_start_list)

    class ErrorCodes(int):
        Normal = 0
        PlatformNotSupport = 1
        DependsMissing = 2
        IsBroken = 3

    def write_start_list(self, id, remove=False):
        if self.start_list_lock:
            print("Waiting For Lock...")
            while self.start_list_lock:
                time.sleep(1)
        self.start_list_lock = True
        s_list = JsonEdit(self.startlist)
        data = s_list.read()
        if data is not list:
            data = list(data)
        if not id in data:
            data.append(id)
        if remove and id in data:
            data.remove(id)
        s_list.write(data)
        del data
        self.start_list_lock = False

    def exec_start_list(self):
        if self.start_list_lock:
            print("Waiting For Lock...")
            while self.start_list_lock:
                time.sleep(1)
        self.start_list_lock = True
        while not states.inited:
            time.sleep(1)
        for i in JsonEdit(self.startlist).read():
            if not self.get_installed(i):
                continue
            create_thread(self.run, i)
        self.start_list_lock = False


    def get_info(self, id_: str, item: str) -> str:
        info_file = f'{self.module_dir}/{id_}/info.json'
        if not os.path.exists(info_file):
            return ''
        with open(info_file, 'r', encoding='UTF-8') as f:
            return json.load(f).get(item, '')

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

        name = self.get_name(id_)
        script_path = self.module_dir + f"/{value}/"
        with open(os.path.join(script_path, "info.json"), 'r', encoding='UTF-8') as f:
            data = json.load(f)
            for n in data['depend'].split():
                if not os.path.exists(os.path.join(self.module_dir, n)):
                    print(lang.text36 % (name, n, n))
                    return 2
        if os.path.exists(script_path + "main.sh") or os.path.exists(script_path + "main.msh"):
            values = self.Parse(script_path + "main.json", os.path.exists(script_path + "main.msh")) if os.path.exists(
                script_path + "main.json") else None
            if not os.path.exists(temp):
                re_folder(temp)
            exports = ''
            if os.path.exists(script_path + "main.sh"):
                if values:
                    for va in values.gavs.keys():
                        if gva := values.gavs[va].get():
                            exports += f"export {va}='{gva}';"
                    values.gavs.clear()
                exports += f"export tool_bin='{settings.tool_bin.replace(os.sep, '/')}';export version='{settings.version}';export language='{settings.language}';export bin='{script_path.replace(os.sep, '/')}';"
                exports += f"export moddir='{self.module_dir.replace(os.sep, '/')}';export project_output='{ProjectManager.current_work_output_path()}';export project='{ProjectManager.current_work_path()}';"
            if os.path.exists(script_path + "main.msh"):
                self.MshParse(script_path + "main.msh")
            if os.path.exists(script_path + "main.sh"):
                shell = 'ash' if os.name == 'posix' else 'bash'
                call(['busybox', shell, '-c',
                      f"{exports}exec {module_exec} {(script_path + 'main.sh').replace(os.sep, '/')}"])
            del exports
        elif os.path.exists(script_path + "main.py") and imp:
            try:
                imp.load_source('__mkc_module__', script_path + "main.py")
            except Exception:
                logging.exception('Bugs')
        elif not os.path.exists(self.module_dir + os.sep + value):
            win.message_pop(lang.warn7.format(value))
            list_pls_plugin()
            win.tab7.lift()
        else:
            print(lang.warn8)
        return 0

    def check_mpk(self, mpk):
        if not mpk or not os.path.exists(mpk) or not zipfile.is_zipfile(mpk):
            return self.errorcodes.IsBroken, ''
        with zipfile.ZipFile(mpk) as f:
            if 'info' not in f.namelist():
                return self.errorcodes.IsBroken, ''
        return self.errorcodes.Normal, ''

    def install(self, mpk):
        check_mpk_result = self.check_mpk(mpk)
        if check_mpk_result[0] != self.errorcodes.Normal:
            return check_mpk_result
        mconf = ConfigParser()
        with zipfile.ZipFile(mpk) as f:
            with f.open('info') as info_file:
                mconf.read_string(info_file.read().decode('utf-8'))
        try:
            supports = mconf.get('module', 'supports').split()
            if platform.system() not in supports:
                return self.errorcodes.PlatformNotSupport, ''
        except (Exception, BaseException):
            logging.exception('Bugs')
        for dep in mconf.get('module', 'depend').split():
            if not os.path.isdir(os.path.join(cwd_path, "bin", "module", dep)):
                return self.errorcodes.DependsMissing, dep
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
            start_auto = mconf.get('module', 'start_auto')
        except:
            start_auto = 'False'
        if start_auto in ['True', 'true', '1']:
            self.write_start_list(mconf.get('module', 'identifier'))
        try:
            depends = mconf.get('module', 'depend')
        except (Exception, BaseException):
            depends = ''
        minfo = {}
        for i in mconf.items('module'):
            minfo[i[0]] = i[1]
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
        return self.errorcodes.Normal, ''

    @animation
    def export(self, id_: str):
        name: str = self.get_name(id_)
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
        print(lang.t15 % (settings.path + os.sep + name + ".mpk")) if os.path.exists(
            settings.path + os.sep + name + ".mpk") else print(
            lang.t16 % (settings.path + os.sep + name + ".mpk"))

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
            entry.pack(padx=5, pady=5, side=LEFT)
            frame.pack(padx=5, pady=5, fill=X, side=side)
            return entry_value

        def editor_(self, id_=None):
            if not id_:
                win.message_pop(lang.warn2)
                return
            path = os.path.join(self.module_dir, id_) + os.sep
            if os.path.exists(path + "main.py"):
                editor.main(path, 'main.py', lexer=pygments.lexers.PythonLexer)
            elif not os.path.exists(path + "main.msh") and not os.path.exists(path + 'main.sh'):
                s = "main.sh" if ask_win(lang.t18, 'SH', 'MSH') == 1 else "main.msh"
                with open(path + s, 'w+', encoding='utf-8', newline='\n') as sh:
                    sh.write("echo 'MIO-KITCHEN'")
                editor.main(path, s)
            else:
                editor.main(path, 'main.msh' if os.path.exists(path + "main.msh") else 'main.sh')

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
            if ModuleManager.get_installed(self.identifier.get()):
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
            if not os.path.exists(self.module_dir + os.sep + iden):
                os.makedirs(self.module_dir + os.sep + iden)
            with open(self.module_dir + f"/{iden}/info.json", 'w+', encoding='utf-8',
                      newline='\n') as js:
                json.dump(data, js, ensure_ascii=False, indent=4)
            list_pls_plugin()
            self.editor_(iden)

    class MshParse:
        extra_envs = {}
        grammar_words = {"echo": lambda strings: print(strings),
                         "rmdir": lambda path: rmdir(path.strip()),
                         "run": lambda cmd: call(exe=str(cmd), extra_path=False),
                         'gettype': lambda file_: gettype(file_),
                         'exist': lambda x: '1' if os.path.exists(x) else '0'}

        def __init__(self, sh):
            self.sfor = lambda vn, vs, do: [self.runline(do.replace(f'@{vn}@', v)) for v in
                                            vs.split(',' if ',' in vs else None)]
            if not hasattr(self, 'module_dir'):
                self.module_dir = os.path.join(cwd_path, "bin", "module")
            self.envs = {'version': settings.version, 'tool_bin': settings.tool_bin.replace('\\', '/'),
                         'project': ProjectManager.current_work_path(),
                         'project_output': ProjectManager.current_work_output_path(),
                         'moddir': self.module_dir.replace('\\', '/'), 'bin': os.path.dirname(sh).replace('\\', '/')}
            for n, v in self.extra_envs.items():
                self.envs[n] = v
            with open(sh, 'r+', encoding='utf-8', newline='\n') as shell:
                for i in shell.readlines():
                    try:
                        self.runline(i)
                    except AttributeError as e:
                        print(f"Unknown Order：{i}\nReason：{e}")
                    except ValueError as e:
                        print(f"Exception:{e}")
                        return
                    except Exception as e:
                        print(f"Runtime Error:{i}\nReason：{e}")
                    except (Exception, BaseException):
                        print(f"Runtime Error:{i}")
            self.envs.clear()

        def set(self, cmd):
            try:
                vn, va = cmd.strip().split("=" if "=" in cmd else None)
            except Exception as e:
                print(f"SetValue Exception：{e}\nSentence：{cmd}")
                return 1
            self.envs[vn] = str(va)

        def runline(self, i):
            for key, value in self.envs.items():
                if "@" in i:
                    i = i.replace(f'@{key}@', str(value)).strip()
            if i[:1] != "#" and i not in ["", '\n', "\r\n"]:
                if i.split()[0] == "if":
                    self.sif(i.split()[1], i.split()[2], ' '.join(i.split()[3:]))
                elif i.split()[0] == "for":
                    self.sfor(i.split()[1], shlex.split(i)[3], shlex.split(i)[4])
                else:
                    if i.split()[0] in self.grammar_words.keys():
                        self.envs["result"] = self.grammar_words[i.split()[0]](' '.join(i.split()[1:]))
                    else:
                        self.envs["result"] = getattr(self, i.split()[0])(' '.join(i.split()[1:]))
                    if not self.envs['result']:
                        self.envs['result'] = ""

        def sh(self, cmd):
            exports = ''
            sh = "ash" if os.name == 'posix' else "bash"
            for i in self.envs:
                exports += f"export {i}='{self.envs.get(i, '')}';"
            call(['busybox', sh, '-c', f"{exports}exec {module_exec} {cmd.replace(os.sep, '/')}"])
            del exports

        def msh(self, cmd):
            try:
                cmd_, argv = cmd.split()
            except Exception:
                raise ValueError(f"MSH: Unsupported {cmd}")
            if cmd_ == 'run':
                if not os.path.exists(argv.replace("\\", '/')):
                    print(f"Script Not Exist：{argv}")
                    return 1
                else:
                    self.__init__(argv)
            else:
                print('Usage：\nmsh run [script]')

        @staticmethod
        def exit(value):
            raise ValueError(value)

        def sif(self, mode, var_, other):
            modes = {
                'exist': lambda var: os.path.exists(str(var)),
                'equ': lambda var: var.split('--')[0] == var.split('--')[1],
                'gettype': lambda var: gettype(var.split('--')[0]) == var.split('--')[1]
            }
            if mode[:1] == "!":
                if not modes[mode[1:]](var_):
                    self.runline(other)
            elif modes[mode](var_):
                self.runline(other)

    class Parse(Toplevel):
        gavs = {}

        def __init__(self, jsons, msh=False):
            super().__init__()

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
                if height != 'none' and width != 'none':
                    self.geometry(f"{width}x{height}")
                resizable = data['main']['info']['resize']
                try:
                    self.attributes('-topmost', 'true')
                except (Exception, BaseException):
                    logging.exception('Bugs')
                self.resizable(True, True) if resizable == '1' else self.resizable(False, False)
                for group_name, group_data in data['main'].items():
                    if group_name != "info":
                        group_frame = ttk.LabelFrame(self, text=group_data['title'])
                        group_frame.pack(padx=10, pady=10)
                        for con in group_data['controls']:
                            if con["type"] == "text":
                                ttk.Label(group_frame, text=con['text'],
                                          font=(None, int(con['fontsize']))).pack(side=con['side'], padx=5, pady=5)
                            elif con["type"] == "button":
                                ttk.Button(group_frame, text=con['text'],
                                           command=lambda: print(con['command'])).pack(side='left')
                            elif con["type"] == "filechose":
                                ft = ttk.Frame(group_frame)
                                ft.pack(fill=X)
                                file_var_name = con['set']
                                self.gavs[file_var_name] = StringVar()
                                ttk.Label(ft, text=con['text']).pack(side='left', padx=10, pady=10)
                                ttk.Entry(ft, textvariable=self.gavs[file_var_name]).pack(side='left', padx=5, pady=5)
                                ttk.Button(ft, text=lang.text28,
                                           command=lambda: self.gavs[file_var_name].set(
                                               filedialog.askopenfilename())).pack(side='left', padx=10, pady=10)
                            elif con["type"] == "radio":
                                radio_var_name = con['set']
                                self.gavs[radio_var_name] = StringVar()
                                options = con['opins'].split()
                                pft1 = ttk.Frame(group_frame)
                                pft1.pack(padx=10, pady=10)
                                for option in options:
                                    text, value = option.split('|')
                                    self.gavs[radio_var_name].set(value)
                                    ttk.Radiobutton(pft1, text=text, variable=self.gavs[radio_var_name],
                                                    value=value).pack(side=con['side'])
                            elif con["type"] == 'input':
                                input_frame = Frame(group_frame)
                                input_frame.pack(fill=X)
                                input_var_name = con['set']
                                self.gavs[input_var_name] = StringVar()
                                if 'text' in con:
                                    ttk.Label(input_frame, text=con['text']).pack(side=LEFT, padx=5, pady=5, fill=X)
                                ttk.Entry(input_frame, textvariable=self.gavs[input_var_name]).pack(side=LEFT, pady=5,
                                                                                                    padx=5,
                                                                                                    fill=X)
                            elif con['type'] == 'checkbutton':
                                b_var_name = con['set']
                                self.gavs[b_var_name] = IntVar()
                                text = '' if 'text' not in con else con['text']
                                ttk.Checkbutton(group_frame, text=text, variable=self.gavs[b_var_name], onvalue=1,
                                                offvalue=0,
                                                style="Switch.TCheckbutton").pack(
                                    padx=5, pady=5, fill=BOTH)
                            else:
                                print(lang.warn14.format(con['type']))
            ttk.Button(self, text=lang.ok, command=lambda: create_thread(self.generate_msh if msh else self.generate_sh)).pack(
                fill=X,
                side='bottom')
            move_center(self)
            self.wait_window()

        def generate_sh(self):
            if not os.path.exists(temp):
                os.mkdir(temp)
            self.destroy()

        def generate_msh(self):
            for va in self.gavs.keys():
                if gva := self.gavs[va].get():
                    ModuleManager.MshParse.extra_envs[va] = gva
                    if gva is str and os.path.isabs(gva) and os.name == 'nt':
                        if '\\' in gva:
                            ModuleManager.MshParse.extra_envs[va] = gva.replace("\\", '/')
            self.destroy()
            self.gavs.clear()

    class UninstallMpk(Toplevel):

        def __init__(self, id_: str):
            super().__init__()
            self.arr = {}
            if not hasattr(self, 'module_dir'):
                self.module_dir = os.path.join(cwd_path, "bin", "module")
            if id_:
                self.value = id_
                self.value2 = ModuleManager.get_name(id_)
                self.lfdep()
                self.ask()
            else:
                win.message_pop(lang.warn2)

        def ask(self):
            try:
                self.attributes('-topmost', 'true')
            except (Exception, BaseException):
                logging.exception('Bugs')
            self.title(lang.t6)
            move_center(self)
            ttk.Label(self, text=lang.t7 % self.value2, font=(None, 30)).pack(padx=10, pady=10, fill=BOTH,
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
            ttk.Button(self, text=lang.ok, command=self.uninstall, style="Accent.TButton").pack(fill=X, expand=True,
                                                                                                side=LEFT, pady=10,
                                                                                                padx=10)

        def lfdep(self, name=None):
            if not name:
                name = self.value
            for i in [i for i in os.listdir(self.module_dir) if os.path.isdir(self.module_dir + os.sep + i)]:
                if not os.path.exists(os.path.join(self.module_dir, i, "info.json")):
                    continue
                with open(os.path.join(self.module_dir, i, "info.json"), 'r', encoding='UTF-8') as f:
                    data = json.load(f)
                    for n in data['depend'].split():
                        if name == n:
                            self.arr[i] = data['name']
                            self.lfdep(i)
                            # 检测到依赖后立即停止
                            break

        def uninstall(self):
            self.destroy()
            for i in self.arr.keys():
                self.remove(i, self.arr.get(i, 'None'))
            self.remove(self.value, self.value2)

        def remove(self, name=None, show_name='') -> None:
            ModuleManager.write_start_list(name, remove=True)
            if name:
                print(lang.text29.format(name if not show_name else show_name))
                if os.path.exists(self.module_dir + os.sep + name):
                    try:
                        rmtree(self.module_dir + os.sep + name)
                    except PermissionError as e:
                        logging.exception('Bugs')
                        print(e)
                if os.path.exists(self.module_dir + os.sep + name):
                    win.message_pop(lang.warn9, 'red')
                else:
                    print(lang.text30)
                    try:
                        list_pls_plugin()
                    except (Exception, BaseException):
                        logging.exception('Bugs')
            else:
                win.message_pop(lang.warn2)


ModuleManager = ModuleManager()


class MpkMan(ttk.Frame):
    def __init__(self):
        super().__init__(master=win.tab7)
        self.pack(padx=10, pady=10, fill=BOTH)
        self.chosen = tk.StringVar(value='')
        self.moduledir = ModuleManager.module_dir
        if not os.path.exists(self.moduledir):
            os.makedirs(self.moduledir)
        self.images_ = {}

    def list_pls(self):
        # self.pls.clean()
        for i in self.pls.apps.keys():
            if not ModuleManager.get_installed(i):
                self.pls.remove(i)
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
                icon.bind('<Double-Button-1>', lambda event, ar=i: create_thread(ModuleManager.run, ar))
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
        rmenu.add_command(label=lang.text115, command=lambda: create_thread(ModuleManager.new))
        self.rmenu2 = Menu(self.pls, tearoff=False, borderwidth=0)
        self.rmenu2.add_command(label=lang.text20,
                                command=lambda: create_thread(ModuleManager.uninstall_gui, self.chosen.get()))
        self.rmenu2.add_command(label=lang.text22,
                                command=lambda: create_thread(ModuleManager.run, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t14, command=lambda: create_thread(ModuleManager.export, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t17,
                                command=lambda: create_thread(ModuleManager.new.editor_, ModuleManager, self.chosen.get()))
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
        self.installb = ttk.Button(self, text=lang.text41, style="Accent.TButton", command=lambda: create_thread(self.install))
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
        ret, reason = ModuleManager.install(self.mpk)
        if ret == ModuleManager.errorcodes.PlatformNotSupport:
            self.state['text'] = lang.warn15.format(platform.system())
        elif ret == ModuleManager.errorcodes.DependsMissing:
            self.state['text'] = lang.text36 % (self.mconf.get('module', 'name'), reason, reason)
            self.installb['text'] = lang.text37
            self.installb.config(state='normal')
        elif ret == ModuleManager.errorcodes.IsBroken:
            self.state['text'] = lang.warn2
            self.installb['text'] = lang.text37
            self.installb.config(state='normal')
        elif ret == ModuleManager.errorcodes.Normal:
            self.state['text'] = lang.text39
            self.installb['text'] = lang.text34
            self.installb.config(state='normal')
        self.prog.stop()
        self.prog['mode'] = 'determinate'
        self.prog['value'] = 100

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
            f.write(f'Python: {sys.version}\n')
            f.write(f'Platform: {sys.platform}\n')
            f.write(f'Exec Command: {sys.argv}\n')
            f.write(f'Tool Version: {settings.version}\n')
            f.write(f'Source code running: {states.run_source}\n')
            f.write(f'python Implementation: {platform.python_implementation()}\n')
            f.write(f'Uname: {platform.uname()}\n')
        pack_zip(inner, bugreport:=os.path.join(output, f"Mio_Bug_Report{time.strftime('%Y%m%d_%H-%M-%S', time.localtime())}_{v_code()}.zip"), slient=True)
        re_folder(inner,quiet=True)
        print(f"\tThe Bug Report Was Saved:{bugreport}")

class Debugger(Toplevel):
    def __init__(self):
        super().__init__()
        self.title("MIO-KITCHEN Debugger")
        self.gui()
        move_center(self)

    def gui(self):
        row = 0
        num = 3
        num_c = 0
        functions = [
            ('Globals', self.loaded_module),
            ('Settings', self.settings),
            ('Info', self.show_info),
            ('Crash it!', self.crash),
            ('Hacker panel', lambda: openurl('https://vdse.bdstatic.com/192d9a98d782d9c74c96f09db9378d93.mp4')),
            ('Generate Bug Report', lambda: create_thread(Generate_Bug_Report)),
        ]
        for index, (text, func) in enumerate(functions):
            ttk.Button(self, text=text, command=func).grid(row=row, column=num_c, padx=5, pady=5)
            num_c += 1
            if num_c >= num:
                row += 1
                num_c = 0

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
        ttk.Label(ck, text='Open Source License: GNU AFFERO GENERAL PUBLIC LICENSE V3', foreground='gray').grid(row=5,
                                                                                                                column=0,
                                                                                                                padx=5,
                                                                                                                pady=5,
                                                                                                                sticky='nw')
        ttk.Label(ck, text=f'Python: {sys.version}', foreground='gray').grid(row=1, column=0, padx=5, pady=5,
                                                                             sticky='nw')
        ttk.Label(ck, text=f'Platform: {sys.platform}', foreground='gray').grid(row=2, column=0, padx=5, pady=5,
                                                                                sticky='nw')
        ttk.Label(ck, text=f'Exec Command: {sys.argv}', foreground='gray').grid(row=2, column=0, padx=5, pady=5,
                                                                                sticky='nw')
        ttk.Label(ck, text=f'Tool Version: {settings.version}', foreground='gray').grid(row=3, column=0, padx=5, pady=5,
                                                                                        sticky='nw')
        ttk.Label(ck, text=f'Source code running: {states.run_source}',
                  foreground='gray').grid(row=3, column=0, padx=5, pady=5,
                                          sticky='nw')
        ttk.Label(ck, text=f'python Implementation: {platform.python_implementation()}', foreground='gray').grid(row=4,
                                                                                                                 column=0,
                                                                                                                 padx=5,
                                                                                                                 pady=5,
                                                                                                                 sticky='nw')
        ttk.Label(ck, text=f'Uname: {platform.uname()}', foreground='gray').grid(row=5, column=0, padx=5, pady=5,
                                                                                 sticky='nw')
        ttk.Label(ck, text=f"Log File: {tool_log}", foreground='gray').grid(row=6, column=0, padx=5, pady=5,
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
                    if f.get().split()[0] == 'load':
                        try:
                            globals()[h.get()] = __import__(f.get().split()[1])
                            read_value()
                        except ImportError:
                            logging.exception('Bugs')
                    elif f.get().split()[0] == 'global':
                        try:
                            globals()[h.get()] = globals()[f.get().split()[1]]
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


def hum_convert(value):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = 1024.0
    for i in range(len(units)):
        if (value / size) < 1:
            return f"{value:.2f}{units[i]}"
        value = value / size


class MpkStore(Toplevel):
    def __init__(self):
        if states.mpk_store:
            return
        states.mpk_store = True
        super().__init__()
        if os.name == 'nt' and settings.treff == '1':
            pywinstyles.apply_style(self, 'acrylic')
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
        self.deque = deque()
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
            f = ttk.LabelFrame(self.label_frame, text=data.get('name'), width=590, height=100)
            f.pack_propagate(False)
            self.app_infos[data.get('id')] = f
            self.deque.append(f)
            ttk.Label(f, image=self.logo).pack(side=LEFT, padx=5, pady=5)
            fb = ttk.Frame(f)
            f2 = ttk.Frame(fb)
            ttk.Label(f, image=PhotoImage(data=images.none_byte)).pack(side=LEFT, padx=5, pady=5)
            # ttk.Label(f2, text=f"{data.get('name')[:6]}").pack(side=LEFT, padx=5, pady=5)
            o = ttk.Label(f2,
                          text=f"{lang.t21}{data.get('author')} {lang.t22}{data.get('version')} Size:{hum_convert(data.get('size'))}"[
                               :50])
            o.pack_propagate(False)
            o.pack(side=LEFT, padx=5, pady=5)
            f2.pack(side=TOP)
            f3 = ttk.Frame(fb)
            ttk.Label(f3, text=f"{data.get('desc')[:27]}").pack(padx=5, pady=5)
            f3.pack(side=BOTTOM)
            fb.pack(side=LEFT, padx=5, pady=5)
            args = data.get('files'), data.get('size'), data.get('id'), data.get('depend')
            bu = ttk.Button(f, text=lang.text21,
                            command=lambda a=args: create_thread(self.download, *a))
            if not ModuleManager.get_installed(data.get('id')):
                bu.config(style="Accent.TButton")
            self.control[data.get('id')] = bu
            bu.pack(side=RIGHT, padx=5, pady=5)
            f.pack(padx=5, pady=5, anchor='nw', expand=1)
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

    def clear(self):
        for i in self.deque:
            try:
                i.destroy()
            except (TclError, ValueError):
                logging.exception('Bugs')

    def modify_repo(self):
        (input_var := StringVar()).set(settings.plugin_repo)
        a = Toplevel(width=200)
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
            control = self.control.get(id_)
            control.config(state='disabled')
        else:
            control = None
        if depends:
            for i in depends:
                for i_ in self.data:
                    if i == i_.get('id') and not ModuleManager.get_installed(i):
                        self.download(i_.get('files'), i_.get('size'), i_.get('id'), i_.get('depend'))
        try:
            for i in files:
                for percentage, _, _, _, _ in download_api(self.repo + i, temp, size_=size):
                    if control and states.mpk_store:
                        control.config(text=f"{percentage} %")
                    else:
                        return False

                create_thread(ModuleManager.install, os.path.join(temp, i), join=True)
                try:
                    os.remove(os.path.join(temp, i))
                except (Exception, BaseException):
                    logging.exception('Bugs')
        except (ConnectTimeout, HTTPError, BaseException, Exception, TclError):
            logging.exception('Bugs')
            return
        control.config(state='normal', text=lang.text21)
        if ModuleManager.get_installed(id_):
            control.config(style="")

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
        if not ProjectManager.exist():
            win.message_pop(lang.warn1)
            return
        if os.path.exists((dir_ := ProjectManager.current_work_output_path()) + "firmware-update"):
            os.rename(dir_ + "firmware-update", dir_ + "images")
        if not os.path.exists(dir_ + "images"):
            os.makedirs(dir_ + 'images')
        if os.path.exists(os.path.join(ProjectManager.current_work_output_path(), 'payload.bin')):
            print("Found payload.bin ,Stop!")
            return
        if os.path.exists(dir_ + 'META-INF'):
            rmdir(dir_ + 'META-INF')
        shutil.copytree(f"{cwd_path}/bin/extra_flash", dir_, dirs_exist_ok=True)
        right_device = input_(lang.t26, 'olive')
        with open(dir_ + "bin/right_device", 'w', encoding='gbk') as rd:
            rd.write(right_device + "\n")
        with open(
                dir_ + 'META-INF/com/google/android/update-binary',
                'r+', encoding='utf-8', newline='\n') as script:
            lines = script.readlines()
            lines.insert(45, f'right_device="{right_device}"\n')
            add_line = self.get_line_num(lines, '#Other images')
            for t in os.listdir(dir_ + "images"):
                if t.endswith('.img') and not os.path.isdir(dir_ + t):
                    print(f"Add Flash method {t} to update-binary")
                    if os.path.getsize(os.path.join(dir_ + 'images', t)) > 209715200:
                        self.zstd_compress(os.path.join(dir_ + 'images', t))
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
                        move(os.path.join(dir_, t + ".zst"), os.path.join(dir_ + "images", t + ".zst"))
                        lines.insert(add_line,
                                     f'package_extract_zstd "images/{t}.zst" "/dev/block/by-name/{t[:-4]}"\n')
                    else:
                        lines.insert(add_line,
                                     f'package_extract_file "images/{t}" "/dev/block/by-name/{t[:-4]}"\n')
                        move(os.path.join(dir_, t), os.path.join(dir_ + "images", t))
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
        if os.path.exists(path):
            if gettype(path) == "sparse":
                print(f"[INFO] {os.path.basename(path)} is (sparse), converting to (raw)")
                utils.simg2img(path)
            try:
                print(f"[Compress] {os.path.basename(path)}...")
                call(['zstd', '-5', '--rm', path, '-o', f'{path}.zst'])
            except Exception as e:
                logging.exception('Bugs')
                print(f"[Fail] Compress {os.path.basename(path)} Fail:{e}")


class PackSuper(Toplevel):
    def __init__(self):
        super().__init__()
        if os.name == 'nt' and settings.treff == '1':
            pywinstyles.apply_style(self, 'acrylic')
        self.title(lang.text53)
        self.supers = IntVar(value=9126805504)
        self.ssparse = IntVar()
        self.supersz = IntVar()
        self.attrib = StringVar(value='readonly')
        self.sdbfz = StringVar()
        self.scywj = IntVar()
        self.selected = []
        (lf1 := ttk.LabelFrame(self, text=lang.text54)).pack(fill=BOTH)
        (lf1_r := ttk.LabelFrame(self, text=lang.attribute)).pack(fill=BOTH)
        (lf2 := ttk.LabelFrame(self, text=lang.settings)).pack(fill=BOTH)
        (lf3 := ttk.LabelFrame(self, text=lang.text55)).pack(fill=BOTH, expand=True)
        self.supersz.set(1)

        radios = [("A-only", 1), ("Virtual-ab", 2), ("Virtual-ab", 3)]
        for text, value in radios:
            ttk.Radiobutton(lf1, text=text, variable=self.supersz, value=value).pack(side='left', padx=10, pady=10)

        ttk.Radiobutton(lf1_r, text="Readonly", variable=self.attrib, value='readonly').pack(side='left', padx=10,
                                                                                             pady=10)
        ttk.Radiobutton(lf1_r, text="None", variable=self.attrib, value='none').pack(side='left', padx=10, pady=10)
        Label(lf2, text=lang.text56).pack(side='left', padx=10, pady=10)
        (sdbfzs := ttk.Combobox(lf2, textvariable=self.sdbfz,
                                values=("qti_dynamic_partitions", "main", "mot_dp_group"))).pack(
            side='left',
            padx=10,
            pady=10,
            fill='both')
        sdbfzs.current(0)
        Label(lf2, text=lang.text57).pack(side='left', padx=10, pady=10)
        (super_size := ttk.Entry(lf2, textvariable=self.supers)).pack(side='left', padx=10, pady=10)
        super_size.bind("<KeyRelease>",
                        lambda *x: super_size.state(["!invalid" if super_size.get().isdigit() else "invalid"]))

        self.tl = ListBox(lf3)
        self.tl.gui()
        self.work = ProjectManager.current_work_path()

        self.tl.pack(padx=10, pady=10, expand=True, fill=BOTH)

        ttk.Checkbutton(self, text=lang.text58, variable=self.ssparse, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=10, pady=10, fill=BOTH)
        t_frame = Frame(self)
        ttk.Checkbutton(t_frame, text=lang.t11, variable=self.scywj, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(side=LEFT,
                                                          padx=10, pady=10, fill=BOTH)
        ttk.Button(t_frame, text=lang.text23, command=self.refresh).pack(side=RIGHT, padx=10, pady=10)
        self.g_b = ttk.Button(t_frame, text=lang.t27, command=lambda: create_thread(self.generate))
        self.g_b.pack(side=LEFT, padx=10, pady=10, fill=BOTH)
        t_frame.pack(fill=X)
        self.read_list()
        create_thread(self.refresh)
        move_center(self)

        ttk.Button(self, text=lang.cancel, command=self.destroy).pack(side='left', padx=10, pady=10,
                                                                      fill=X,
                                                                      expand=True)
        ttk.Button(self, text=lang.pack, command=lambda: create_thread(self.start_), style="Accent.TButton").pack(side='left',
                                                                                                                  padx=5,
                                                                                                                  pady=5, fill=X,
                                                                                                                  expand=True)

    def start_(self):
        try:
            self.supers.get()
        except (Exception, BaseException):
            self.supers.set(0)
            logging.exception('Bugs')
        if not self.versize():
            ask_win2(lang.t10.format(self.supers.get()))
            return False
        lbs = self.tl.selected.copy()
        sc = self.scywj.get()
        self.destroy()
        packsuper(sparse=self.ssparse, dbfz=self.sdbfz, size=self.supers, set_=self.supersz, lb=lbs, del_=sc,
                  attrib=self.attrib.get())

    def versize(self):
        size = sum([os.path.getsize(self.work + i + ".img") for i in self.tl.selected])
        diff_size = size
        if size > self.supers.get():
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
            self.supers.set(int(size))
            return False
        else:
            return True

    def generate(self):
        self.g_b.config(text=lang.t28, state='disabled')
        utils.generate_dynamic_list(dbfz=self.sdbfz.get(), size=self.supers.get(), set_=self.supersz.get(),
                                    lb=self.tl.selected.copy(), work=ProjectManager.current_work_path())
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
        if os.path.exists(self.work + "dynamic_partitions_op_list"):
            try:
                data = utils.dynamic_list_reader(self.work + "dynamic_partitions_op_list")
            except (Exception, BaseException):
                logging.exception('Bugs')
                return
            if len(data) > 1:
                fir, sec = data
                if fir[:-2] == sec[:-2]:
                    self.sdbfz.set(fir[:-2])
                    self.supersz.set(2)
                    self.supers.set(int(data[fir]['size']))
                    self.selected = data[fir].get('parts', [])
                    selected = []
                    for i in self.selected:
                        selected.append(i[:-2]) if i.endswith('_a') or i.endswith('_b') else selected.append(i)
                    self.selected = selected

            else:
                dbfz, = data
                self.sdbfz.set(dbfz)
                self.supers.set(int(data[dbfz]['size']))
                self.selected = data[dbfz].get('parts', [])
                self.supersz.set(1)


@animation
def packsuper(sparse, dbfz, size, set_, lb: list, del_=0, return_cmd=0, attrib='readonly'):
    if not ProjectManager.exist():
        warn_win(text=lang.warn1)
        return False
    work = ProjectManager.current_work_output_path()
    lb_c = []
    for part in lb:
        if part.endswith('_b') or part.endswith('_a'):
            part = part.replace('_a', '').replace('_b', '')
        if part not in lb_c:
            lb_c.append(part)
    lb = lb_c
    for part in lb:
        if not os.path.exists(work + part + '.img') and os.path.exists(work + part + '_a.img'):
            try:
                os.rename(work + part + '_a.img', work + part + '.img')
            except:
                logging.exception('Bugs')
    command = ['lpmake', '--metadata-size', '65536', '-super-name', 'super', '-metadata-slots']
    if set_.get() == 1:
        command += ['2', '-device', f'super:{size.get()}', "--group", f"{dbfz.get()}:{size.get()}"]
        for part in lb:
            command += ['--partition', f"{part}:{attrib}:{os.path.getsize(work + part + '.img')}:{dbfz.get()}",
                        '--image', f'{part}={work + part}.img']
    else:
        command += ["3", '-device', f'super:{size.get()}', '--group', f"{dbfz.get()}_a:{size.get()}"]
        for part in lb:
            command += ['--partition', f"{part}_a:{attrib}:{os.path.getsize(work + part + '.img')}:{dbfz.get()}_a",
                        '--image', f'{part}_a={work + part}.img']
        command += ["--group", f"{dbfz.get()}_b:{size.get()}"]
        for part in lb:
            if not os.path.exists(f"{work + part}_b.img"):
                command += ['--partition', f"{part}_b:{attrib}:0:{dbfz.get()}_b"]
            else:
                command += ['--partition',
                            f"{part}_b:{attrib}:{os.path.getsize(work + part + '_b.img')}:{dbfz.get()}_b",
                            '--image', f'{part}_b={work + part}_b.img']
        if set_.get() == 2:
            command += ["--virtual-ab"]
    if sparse.get() == 1:
        command += ["--sparse"]
    command += ['--out', work + 'super.img']
    if return_cmd == 1:
        return command
    if call(command) == 0:
        if os.access(work + "super.img", os.F_OK):
            print(lang.text59 % (work + "super.img"))
            if del_ == 1:
                for img in lb:
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
        self.flush = lambda : error(1, self.error_info) if self.error_info else ...

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


def call(exe, extra_path=True, out=0):
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
            if out == 0:
                try:
                    out_put = i.decode("utf-8").strip()
                except (Exception, BaseException):
                    out_put = i.decode("gbk").strip()
                print(out_put)
                logging.info(out_put)
        states.open_pids.remove(pid)
    except subprocess.CalledProcessError as e:
        for i in iter(e.stdout.readline, b""):
            if out == 0:
                try:
                    out_put = i.decode("utf-8").strip()
                except (Exception, BaseException):
                    out_put = i.decode("gbk").strip()
                print(out_put)
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
    if file_size == 0 and size_:
        file_size = size_
    with open((settings.path if path is None else path) + os.sep + os.path.basename(url), "wb") as f:
        chunk_size = 2048576
        bytes_downloaded = 0
        for data in response.iter_content(chunk_size=chunk_size):
            f.write(data)
            bytes_downloaded += len(data)
            elapsed = time.time() - start_time
            speed = bytes_downloaded / (1024 * elapsed)
            percentage = (int((bytes_downloaded / file_size) * 100) if int_ else (bytes_downloaded / file_size) * 100) if file_size != 0 else "None"
            yield percentage, speed, bytes_downloaded, file_size, elapsed


def download_file():
    var1 = BooleanVar(value=False)
    down = win.get_frame(lang.text61 + os.path.basename(url := input_(title=lang.text60)))
    win.message_pop(lang.text62, "green")
    progressbar = ttk.Progressbar(down, length=200, mode="determinate")
    progressbar.pack(padx=10, pady=10)
    ttk.Label(down, textvariable=(jd := StringVar())).pack(padx=10, pady=10)
    c1 = ttk.Checkbutton(down, text=lang.text63, variable=var1, onvalue=True, offvalue=False)
    c1.pack(padx=10, pady=10)
    start_time = time.time()
    try:
        for percentage, speed, bytes_downloaded, file_size, elapsed in download_api(url):
            progressbar["value"] = percentage
            jd.set(lang.text64.format(str(percentage), str(speed), str(bytes_downloaded), str(file_size)))
            progressbar.update()
        elapsed = time.time() - start_time
        print(lang.text65.format(os.path.basename(url), str(elapsed)))
        down.destroy()
        if var1.get():
            unpackrom(settings.path + os.sep + os.path.basename(url))
            os.remove(settings.path + os.sep + os.path.basename(url))
    except Exception as e:
        print(lang.text66, str(e))
        try:
            os.remove(os.path.basename(url))
        except (Exception, BaseException):
            if os.access(os.path.basename(url), os.F_OK):
                print(lang.text67 + os.path.basename(url))
            else:
                try:
                    down.destroy()
                except Exception as e:
                    win.message_pop(str(e))
                win.message_pop(lang.text68, "red")


@animation
def jboot(bn: str = 'boot'):
    if not (boot := findfile(f"{bn}.img", (work := ProjectManager.current_work_path()))):
        print(lang.warn3.format(bn))
        return
    if not os.path.exists(boot):
        win.message_pop(lang.warn3.format(bn))
        return
    if os.path.exists(work + bn):
        if rmdir(work + bn) != 0:
            print(lang.text69)
            return
    re_folder(work + bn)
    os.chdir(work + bn)
    if call(['magiskboot', 'unpack', '-h', '-n', boot]) != 0:
        print(f"Unpack {boot} Fail...")
        os.chdir(cwd_path)
        rmtree(work + bn)
        return
    if os.access(work + bn + "/ramdisk.cpio", os.F_OK):
        comp = gettype(work + bn + "/ramdisk.cpio")
        print(f"Ramdisk is {comp}")
        with open(work + bn + "/comp", "w", encoding='utf-8') as f:
            f.write(comp)
        if comp != "unknown":
            os.rename(work + bn + "/ramdisk.cpio",
                      work + bn + "/ramdisk.cpio.comp")
            if call(["magiskboot", "decompress", work + bn + '/ramdisk.cpio.comp',
                     work + bn + '/ramdisk.cpio']) != 0:
                print("Failed to decompress Ramdisk...")
                return
        if not os.path.exists(work + bn + "/ramdisk"):
            os.mkdir(work + bn + "/ramdisk")
        os.chdir(work + bn)
        print("Unpacking Ramdisk...")
        call(['cpio', '-i', '-d', '-F', 'ramdisk.cpio', '-D', 'ramdisk'])
        os.chdir(cwd_path)
    else:
        print("Unpack Done!")
    os.chdir(cwd_path)


@animation
def dboot(name: str = 'boot', source: str = None, boot: str = None):
    work = ProjectManager.current_work_path()
    flag = ''
    if boot is None:
        boot = findfile(f"{name}.img", work)
    if source is None:
        source = work + name
    if not os.path.exists(source):
        print(f"Cannot Find {name}...")
        return
    cpio = findfile("cpio.exe" if os.name != 'posix' else 'cpio',
                    settings.tool_bin).replace(
        '\\', "/")

    if os.path.isdir(f"{source}/ramdisk"):
        os.chdir(f"{source}/ramdisk")
        call(exe=["busybox", "ash", "-c", f"find | sed 1d | {cpio} -H newc -R 0:0 -o -F ../ramdisk-new.cpio"])
        os.chdir(source)
        with open(f"{source}/comp", "r", encoding='utf-8') as compf:
            comp = compf.read()
        print(f"Compressing:{comp}")
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
        os.rename(source + "/new-boot.img", ProjectManager.current_work_output_path() + f"/{name}.img")
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

        self.erofs_old_kernel = IntVar(value=0)
        if not self.verify():
            self.start_()
            return
        super().__init__()
        if os.name == 'nt' and settings.treff == '1':
            pywinstyles.apply_style(self, 'acrylic')
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
        self.xgdx = ttk.Button(lf1, text=lang.t37, command=self.modify_custom_size)
        self.xgdx.pack(
            side='left', padx=5, pady=5)
        self.show_modify_size = lambda: self.xgdx.pack_forget() if self.ext4_method.get() == lang.t32 else self.xgdx.pack(
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
        ttk.Checkbutton(lf2, text=lang.t35, variable=self.erofs_old_kernel, onvalue=1, offvalue=0,
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
        ttk.Button(self, text=lang.pack, command=lambda: create_thread(self.start_), style="Accent.TButton").pack(side='left',
                                                                                                                  padx=2, pady=2,
                                                                                                                  fill=X,
                                                                                                                  expand=True)
        move_center(self)

    def start_(self):
        try:
            self.destroy()
        except AttributeError:
            logging.exception('Bugs')
        self.packrom()

    def verify(self):
        parts_dict = JsonEdit(ProjectManager.current_work_path() + "config/parts_info").read()
        for i in self.lg:
            if i not in parts_dict.keys():
                parts_dict[i] = 'unknown'
            if parts_dict[i] in ['ext', 'erofs', 'f2fs']:
                return True
        return False

    def modify_custom_size(self):
        work = ProjectManager.current_work_path()

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
                    if os.path.exists(work + "dynamic_partitions_op_list"):
                        with open(work + "dynamic_partitions_op_list", 'r', encoding='utf-8') as t:
                            for _i_ in t.readlines():
                                _i = _i_.strip().split()
                                if len(_i) < 3:
                                    continue
                                if _i[0] != 'resize':
                                    continue
                                if _i[1] in [dname, f'{dname}_a', f'{dname}_b']:
                                    ext4_size_value = max(ext4_size_value, int(_i[2]))
                    elif os.path.exists(work + f"config/{dname}_size.txt"):
                        with open(work + f"config/{dname}_size.txt", encoding='utf-8') as size_f:
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
        if not ProjectManager.exist():
            win.message_pop(lang.warn1, "red")
            return False
        parts_dict = JsonEdit((work := ProjectManager.current_work_path()) + "config/parts_info").read()
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
            if os.access(os.path.join(work + "config", f"{dname}_fs_config"), os.F_OK):
                if os.name == 'nt':
                    try:
                        if folder := findfolder(work, "com.google.android.apps.nbu."):
                            call(['mv', folder,
                                  folder.replace('com.google.android.apps.nbu.', 'com.google.android.apps.nbu')])
                    except Exception:
                        logging.exception('Bugs')
                fspatch.main(work + dname, os.path.join(work + "config", f"{dname}_fs_config"))
                utils.qc(work + f"config/{dname}_fs_config")
                if settings.contextpatch == "1":
                    contextpatch.main(work + dname, work + f"config/{dname}_file_contexts")
                utils.qc(work + f"config/{dname}_file_contexts")
                if self.fs_conver.get():
                    if parts_dict[dname] == self.origin_fs.get():
                        parts_dict[dname] = self.modify_fs.get()
                if parts_dict[dname] == 'erofs':
                    if mkerofs(dname, str(self.edbgs.get()), work=work,
                               work_output=ProjectManager.current_work_output_path(), level=int(self.scale_erofs.get()),
                               old_kernel=self.erofs_old_kernel.get(), UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.delywj.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.dbgs.get() in ["dat", "br", "sparse"]:
                            img2simg(ProjectManager.current_work_output_path() + dname + ".img")
                            if self.dbgs.get() == 'dat':
                                datbr(ProjectManager.current_work_output_path(), dname, "dat",
                                      int(parts_dict.get('dat_ver', 4)))
                            elif self.dbgs.get() == 'br':
                                datbr(ProjectManager.current_work_output_path(), dname, self.scale.get(),
                                      int(parts_dict.get('dat_ver', 4)))
                            else:
                                print(lang.text3.format(dname))
                elif parts_dict[dname] == 'f2fs':
                    if make_f2fs(dname, work=work, work_output=ProjectManager.current_work_output_path(),
                                 UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.delywj.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.dbgs.get() in ["dat", "br", "sparse"]:
                            img2simg(ProjectManager.current_work_output_path() + dname + ".img")
                            if self.dbgs.get() == 'dat':
                                datbr(ProjectManager.current_work_output_path(), dname, "dat",
                                      int(parts_dict.get('dat_ver', 4)))
                            elif self.dbgs.get() == 'br':
                                datbr(ProjectManager.current_work_output_path(), dname, self.scale.get(),
                                      int(parts_dict.get('dat_ver', 4)))
                            else:
                                print(lang.text3.format(dname))

                else:
                    ext4_size_value = self.custom_size.get(dname, 0)
                    if self.ext4_method.get() == lang.t33 and not self.custom_size.get(dname, ''):
                        if os.path.exists(work + "dynamic_partitions_op_list"):
                            with open(work + "dynamic_partitions_op_list", 'r', encoding='utf-8') as t:
                                for _i_ in t.readlines():
                                    _i = _i_.strip().split()
                                    if len(_i) < 3:
                                        continue
                                    if _i[0] != 'resize':
                                        continue
                                    if _i[1] in [dname, f'{dname}_a', f'{dname}_b']:
                                        ext4_size_value = max(ext4_size_value, int(_i[2]))
                        elif os.path.exists(work + f"config/{dname}_size.txt"):
                            with open(work + f"config/{dname}_size.txt", encoding='utf-8') as f:
                                try:
                                    ext4_size_value = int(f.read().strip())
                                except ValueError:
                                    ext4_size_value = 0

                    if make_ext4fs(name=dname, work=work, work_output=ProjectManager.current_work_output_path(),
                                   sparse="-s" if self.dbgs.get() in ["dat", "br", "sparse"] else '',
                                   size=ext4_size_value,
                                   UTC=self.UTC.get()) if self.dbfs.get() == "make_ext4fs" else mke2fs(
                        name=dname, work=work,
                        work_output=ProjectManager.current_work_output_path(),
                        sparse="y" if self.dbgs.get() in [
                            "dat",
                            "br",
                            "sparse"] else 'n',
                        size=ext4_size_value,
                        UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                        continue
                    if self.delywj.get() == 1:
                        rdi(work, dname)
                    if self.dbgs.get() == "dat":
                        datbr(ProjectManager.current_work_output_path(), dname, "dat",
                              int(parts_dict.get('dat_ver', '4')))
                    elif self.dbgs.get() == "br":
                        datbr(ProjectManager.current_work_output_path(), dname, self.scale.get(),
                              int(parts_dict.get('dat_ver', '4')))
                    else:
                        print(lang.text3.format(dname))
            elif parts_dict[i] in ['boot', 'vendor_boot']:
                dboot(i)
            elif parts_dict[i] == 'dtbo':
                pack_dtbo()
            elif parts_dict[i] == 'logo':
                logo_pack()
            else:
                print(f"Unsupported {i}:{parts_dict[i]}")



def rdi(work, part_name) -> bool:
    if not os.listdir(work + "config"):
        rmtree(work + "config")
        return False
    if os.access(work + part_name + ".img", os.F_OK):
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


def input_(title: str = lang.text76, text: str = "") -> str:
    (input_var := StringVar()).set(text)
    input__ = ttk.LabelFrame(win, text=title)
    input__.place(relx=0.5, rely=0.5, anchor="center")
    entry__ = ttk.Entry(input__, textvariable=input_var)
    entry__.pack(pady=5, padx=5, fill=BOTH)
    entry__.bind("<Return>", lambda *x: input__.destroy())
    ttk.Button(input__, text=lang.ok, command=input__.destroy).pack(padx=5, pady=5, fill=BOTH, side='bottom')
    input__.wait_window()
    return input_var.get()


def script2fs(path):
    if os.path.exists(os.path.join(path, "system", "app")):
        if not os.path.exists(path + "/config"):
            os.makedirs(path + "/config")
        extra.script2fs_context(findfile("updater-script", path + "/META-INF"), path + "/config", path)
        json_ = JsonEdit(os.path.join(path, "config", "parts_info"))
        parts = json_.read()
        for v in os.listdir(path):
            if os.path.exists(path + f"/config/{v}_fs_config"):
                if v not in parts.keys():
                    parts[v] = 'ext'
        json_.write(parts)


@animation
def unpackrom(ifile) -> None:
    print(lang.text77 + ifile, f'Type:[{(ftype := gettype(ifile))}]')
    if ftype == 'gzip':
        print(lang.text79 + ifile)
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not ProjectManager.exist():
            re_folder(ProjectManager.current_work_path())
        if os.path.basename(ifile).endswith(".gz"):
            output_file_name = os.path.basename(ifile)[:-3]
        else:
            output_file_name = os.path.basename(ifile)
        output_file_ = os.path.join(ProjectManager.current_work_path(), output_file_name)
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
    elif ftype == "ozip":
        print(lang.text78 + ifile)
        ozipdecrypt.main(ifile)
        try:
            os.remove(ifile)
        except (PermissionError, IOError) as e:
            win.message_pop(lang.warn11.format(e))
        unpackrom(os.path.dirname(ifile) + os.sep + os.path.basename(ifile)[:-4] + "zip")
    elif ftype == 'tar':
        print(lang.text79 + ifile)
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not ProjectManager.exist():
            re_folder(ProjectManager.current_work_path())
        with tarsafe.TarSafe(ifile) as f:
            f.extractall(ProjectManager.current_work_path())
        return
    elif ftype == 'kdz':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not ProjectManager.exist():
            re_folder(ProjectManager.current_work_path())
        KDZFileTools(ifile, ProjectManager.current_work_path(), extract_all=True)
        for i in os.listdir(ProjectManager.current_work_path()):
            if not os.path.isfile(ProjectManager.current_work_path() + os.sep + i):
                continue
            if i.endswith('.dz') and gettype(ProjectManager.current_work_path() + os.sep + i) == 'dz':
                DZFileTools(ProjectManager.current_work_path() + os.sep + i, ProjectManager.current_work_path(),
                            extract_all=True)
        return
    elif os.path.splitext(ifile)[1] == '.ofp':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if ask_win(lang.t12) == 1:
            ofp_mtk_decrypt.main(ifile, ProjectManager.current_work_path())
        else:
            ofp_qc_decrypt.main(ifile, ProjectManager.current_work_path())
            script2fs(ProjectManager.current_work_path())
        unpackg.refs(True)
        return
    elif os.path.splitext(ifile)[1] == '.ops':
        current_project_name.set(os.path.basename(ifile).split('.')[0])
        args = {'decrypt': True,
                "<filename>": ifile,
                'outdir': os.path.join(settings.path, ProjectManager.current_work_path())}
        opscrypto.main(args)
        unpackg.refs(True)
        return
    if gettype(ifile) == 'zip':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        fz = zipfile.ZipFile(ifile, 'r')
        for fi in fz.namelist():
            try:
                file_ = fi.encode('cp437').decode('gbk')
            except (Exception, BaseException):
                try:
                    file_ = fi.encode('cp437').decode('utf-8')
                except (Exception, BaseException):
                    file_ = fi
            print(lang.text79 + file_)
            try:
                fz.extract(fi, ProjectManager.current_work_path())
                if fi != file_:
                    os.rename(os.path.join(ProjectManager.current_work_path(), fi),
                              os.path.join(ProjectManager.current_work_path(), file_))
            except Exception as e:
                print(lang.text80 % (file_, e))
                win.message_pop(lang.warn4.format(file_))
        print(lang.text81)
        if os.path.isdir(ProjectManager.current_work_path()):
            project_menu.set_project(os.path.splitext(os.path.basename(ifile))[0])
        script2fs(ProjectManager.current_work_path())
        unpackg.refs(True)
        fz.close()
        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(ProjectManager.current_work_path())])
        return
    elif ftype != 'unknown':
        folder = os.path.join(settings.path, os.path.splitext(os.path.basename(ifile))[0] + v_code()) if os.path.exists(
            os.path.join(
                settings.path, os.path.splitext(os.path.basename(ifile))[0])) else os.path.join(settings.path,
                                                                                                os.path.splitext(
                                                                                                    os.path.basename(
                                                                                                        ifile))[0])
        try:
            current_project_name.set(os.path.basename(folder))
            os.mkdir(folder)
            ProjectManager.current_work_path()
            ProjectManager.current_work_output_path()
        except Exception as e:
            win.message_pop(str(e))
        copy(ifile, str(folder) if settings.project_struct != 'split' else str(folder + '/Source/'))
        project_menu.listdir()
        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(ProjectManager.current_work_path())])
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


ProjectManager = ProjectManager()


@animation
def unpack(chose, form: str = '') -> bool:
    if os.name == 'nt':
        if windll.shell32.IsUserAnAdmin():
            try:
                ensure_dir_case_sensitive(ProjectManager.current_work_path())
            except (Exception, BaseException):
                logging.exception('Bugs')
    if not ProjectManager.exist():
        win.message_pop(lang.warn1)
        return False
    elif not os.path.exists(ProjectManager.current_work_path()):
        win.message_pop(lang.warn1, "red")
        return False
    json_ = JsonEdit((work := ProjectManager.current_work_path()) + "config/parts_info")
    parts = json_.read()
    if not chose:
        return False
    if form == 'payload':
        print(lang.text79 + "payload")
        Dumper(work + "payload.bin", work, diff=False, old='old', images=chose).run()
        return True
    elif form == 'super':
        print(lang.text79 + "Super")
        file_type = gettype(work + "super.img")
        if file_type == "sparse":
            print(lang.text79 + f"super.img [{file_type}]")
            try:
                utils.simg2img(work + "super.img")
            except (Exception, BaseException):
                win.message_pop(lang.warn11.format("super.img"))
        if gettype(work + "super.img") == 'super':
            lpunpack.unpack(os.path.join(work, "super.img"), work, chose)
            for wjm in os.listdir(work):
                if wjm.endswith('_a.img') and not os.path.exists(work + wjm.replace('_a', '')):
                    os.rename(work + wjm, work + wjm.replace('_a', ''))
                if wjm.endswith('_b.img'):
                    if not os.path.getsize(work + wjm):
                        os.remove(work + wjm)
        return True
    elif form == 'update.app':
        splituapp.extract(work + "UPDATE.APP", work, chose)
        return True
    for i in chose:
        if os.access(work + i + ".zst", os.F_OK):
            print(lang.text79 + i + ".zst")
            call(['zstd', '--rm', '-d', work + i + '.zst'])
            return True
        if os.access(work + i + ".new.dat.xz", os.F_OK):
            print(lang.text79 + i + ".new.dat.xz")
            Unxz(work + i + ".new.dat.xz")
        if os.access(work + i + ".new.dat.br", os.F_OK):
            print(lang.text79 + i + ".new.dat.br")
            call(['brotli', '-dj', work + i + ".new.dat.br"])
        if os.access(work + i + ".new.dat.1", os.F_OK):
            with open(work + i + ".new.dat", 'ab') as ofd:
                for n in range(100):
                    if os.access(work + i + f".new.dat.{n}", os.F_OK):
                        print(lang.text83 % (i + f".new.dat.{n}", f"{i}.new.dat"))
                        with open(work + i + f".new.dat.{n}", 'rb') as fd:
                            ofd.write(fd.read())
                        os.remove(work + i + f".new.dat.{n}")
        if os.access(work + i + ".new.dat", os.F_OK):
            print(lang.text79 + work + i + ".new.dat")
            if os.path.getsize(work + i + ".new.dat") != 0:
                transferfile = os.path.abspath(os.path.dirname(work)) + os.sep + i + ".transfer.list"
                if os.access(transferfile, os.F_OK):
                    parts['dat_ver'] = Sdat2img(transferfile, work + i + ".new.dat", work + i + ".img").version
                    if os.access(work + i + ".img", os.F_OK):
                        os.remove(work + i + ".new.dat")
                        os.remove(transferfile)
                        try:
                            os.remove(work + i + '.patch.dat')
                        except (Exception, BaseException):
                            logging.exception('Bugs')
                    else:
                        print("transferfile" + lang.text84)
        if os.access(work + i + ".img", os.F_OK):
            try:
                parts.pop(i)
            except KeyError:
                ...
            if gettype(work + i + ".img") != 'sparse':
                parts[i] = gettype(work + i + ".img")
            if gettype(work + i + ".img") == 'dtbo':
                un_dtbo(i)
            if gettype(work + i + ".img") in ['boot', 'vendor_boot']:
                jboot(i)
            if i == 'logo':
                try:
                    utils.LogoDumper(work + i + ".img", work + i).check_img(work + i + ".img")
                except AssertionError:
                    logging.exception('Bugs')
                else:
                    logo_dump(work + i + ".img", output_name=i)
            if gettype(work + i + ".img") == 'vbmeta':
                print(f"{lang.text85}AVB:{i}")
                utils.Vbpatch(work + i + ".img").disavb()
            file_type = gettype(work + i + ".img")
            if file_type == "sparse":
                print(lang.text79 + i + f".img[{file_type}]")
                try:
                    utils.simg2img(work + i + ".img")
                except (Exception, BaseException):
                    win.message_pop(lang.warn11.format(i + ".img"))
            if i not in parts.keys():
                parts[i] = gettype(work + i + ".img")
            print(lang.text79 + i + f".img[{file_type}]")
            if gettype(work + i + ".img") == 'super':
                lpunpack.unpack(work + i + ".img", work)
                for wjm in os.listdir(work):
                    if wjm.endswith('_a.img'):
                        if os.path.exists(work + wjm) and os.path.exists(work + wjm.replace('_a', '')):
                            if pathlib.Path(work + wjm).samefile(work + wjm.replace('_a', '')):
                                os.remove(work + wjm)
                            else:
                                os.remove(work + wjm.replace('_a', ''))
                                os.rename(work + wjm, work + wjm.replace('_a', ''))
                        else:
                            os.rename(work + wjm, work + wjm.replace('_a', ''))
                    if wjm.endswith('_b.img'):
                        if os.path.getsize(work + wjm) == 0:
                            os.remove(work + wjm)
            if (file_type := gettype(work + i + ".img")) == "ext":
                with open(work + i + ".img", 'rb+') as e:
                    mount = ext4.Volume(e).get_mount_point
                    if mount[:1] == '/':
                        mount = mount[1:]
                    if '/' in mount:
                        mount = mount.split('/')
                        mount = mount[len(mount) - 1]
                    if mount != i and mount and i != 'mi_ext':
                        parts[mount] = 'ext'
                imgextractor.Extractor().main(ProjectManager.current_work_path() + i + ".img", work + i, work)
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except Exception as e:
                        win.message_pop(lang.warn11.format(i + ".img:" + e))
            if file_type == 'romfs':
                fs = RomfsParse(ProjectManager.current_work_path() + i + ".img")
                fs.extract(work)
            if file_type == "erofs":
                if call(exe=['extract.erofs', '-i', os.path.join(ProjectManager.current_work_path(), i + '.img'), '-o',
                             work,
                             '-x'],
                        out=1) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'f2fs':
                if call(exe=['extract.f2fs', '-o', work, os.path.join(ProjectManager.current_work_path(), i + '.img')],
                        out=1) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'unknown' and is_empty_img(work + i + ".img"):
                print(lang.text141)
    if not os.path.exists(work + "config"):
        os.makedirs(work + "config")
    json_.write(parts)
    parts.clear()
    print(lang.text8)
    return True


def ask_win(text='', ok=None, cancel=None, wait=True) -> int:
    if not ok:
        ok = lang.ok
    if not cancel:
        cancel = lang.cancel
    value = IntVar()
    ask = ttk.LabelFrame(win)
    ask.place(relx=0.5, rely=0.5, anchor="center")
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20), wraplength=400).pack(side=TOP)
    frame_button = ttk.Frame(frame_inner)

    ttk.Button(frame_button, text=cancel, command=lambda: close_ask(0)).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                             expand=True)
    ttk.Button(frame_button, text=ok, command=lambda: close_ask(1), style="Accent.TButton").pack(side='left', padx=5,
                                                                                                 pady=5,
                                                                                                 fill=BOTH,
                                                                                                 expand=True)
    frame_button.pack(side=TOP, fill=BOTH)

    def close_ask(value_=1):
        value.set(value_)
        ask.destroy()

    if wait:
        ask.wait_window()
    return value.get()


def ask_win2(text='', ok=lang.ok, cancel=lang.cancel) -> int:
    value = IntVar()
    ask = Toplevel()
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20), wraplength=400).pack(side=TOP)
    frame_button = ttk.Frame(frame_inner)

    ttk.Button(frame_button, text=cancel, command=lambda: close_ask(0)).pack(padx=5, pady=5, fill=X, side='left',
                                                                             expand=True)
    ttk.Button(frame_button, text=ok, command=lambda: close_ask(1), style="Accent.TButton").pack(padx=5,
                                                                                                 pady=5,
                                                                                                 fill=X, side='left',
                                                                                                 expand=True)
    frame_button.pack(fill=X, expand=True, padx=10, pady=5)

    def close_ask(value_=1):
        value.set(value_)
        ask.destroy()

    move_center(ask)
    ask.wait_window()
    return value.get()


def info_win(text: str, ok: str = lang.ok):
    ask = Toplevel()
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20), wraplength=400).pack(side=TOP)
    ttk.Button(frame_inner, text=ok, command=ask.destroy, style="Accent.TButton").pack(padx=5, pady=5,
                                                                                       fill=X, side='left',
                                                                                       expand=True)
    move_center(ask)
    ask.wait_window()


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
        for root, _, files in os.walk(dir_):
            try:
                self.size += sum([os.path.getsize(os.path.join(root, name)) for name in files if
                                  not os.path.islink(os.path.join(root, name))])
            except (PermissionError, BaseException, Exception):
                logging.exception('Bugs')
        if self.get == 1:
            self.rsize_v = self.size
        else:
            self.rsize(self.size, self.num)

    def rsize(self, size: int, num: int):
        if size <= 2097152:
            size_ = 2097152
            bs = 1
        else:
            size_ = int(size + 10086)
            if size_ > 2684354560:
                bs = 1.0658
            elif size_ <= 2684354560:
                bs = 1.0758
            elif size_ <= 1073741824:
                bs = 1.0858
            elif size_ <= 536870912:
                bs = 1.0958
            elif size_ <= 104857600:
                bs = 1.1158
            else:
                bs = 1.1258
        print(f"Multiple:{bs}")
        if self.get == 3:
            self.rsizelist(self.dname, int(size_ * bs), self.list_f)
        self.rsize_v = int(size_ * bs / num)

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
    print(lang.text86 % (name, name))
    if not os.path.exists(work + name + ".img"):
        print(work + name + ".img" + lang.text84)
        return
    else:
        utils.img2sdat(work + name + ".img", work, dat_ver, name)
    if os.access(work + name + ".new.dat", os.F_OK):
        try:
            os.remove(work + name + ".img")
        except Exception:
            logging.exception('Bugs')
            os.remove(work + name + ".img")
    if brl == "dat":
        print(lang.text87 % name)
    else:
        print(lang.text88 % (name, 'br'))
        call(['brotli', '-q', str(brl), '-j', '-w', '24', f"{work + name}.new.dat", '-o', f"{work + name}.new.dat.br"])
        if os.access(work + name + ".new.dat", os.F_OK):
            try:
                os.remove(work + name + ".new.dat")
            except Exception:
                logging.exception('Bugs')
        print(lang.text89 % (name, 'br'))


def mkerofs(name: str, format_, work, work_output, level, old_kernel=0, UTC=None):
    if not UTC:
        UTC = int(time.time())
    print(lang.text90 % (name, format_ + f',{level}', "1.x"))
    extra_ = f'{format_},{level}' if format_ != 'lz4' else format_
    other_ = '-E legacy-compress' if old_kernel else ''
    cmd = ['mkfs.erofs', *other_.split(), f'-z{extra_}', '-T', f'{UTC}', f'--mount-point=/{name}',
           f'--product-out={work}',
           f'--fs-config-file={work}config{os.sep}{name}_fs_config',
           f'--file-contexts={work}config{os.sep}{name}_file_contexts',
           f'{work_output + name}.img', work + name + os.sep]
    return call(cmd, out=1)


@animation
def make_ext4fs(name: str, work: str, work_output, sparse='', size=0, UTC=None):
    print(lang.text91 % name)
    if not UTC:
        UTC = int(time.time())
    if not size:
        size = GetFolderSize(work + name, 1, 3, work + "dynamic_partitions_op_list").rsize_v
    print(f"{name}:[{size}]")
    return call(
        ['make_ext4fs', '-J', '-T', f'{UTC}', sparse, '-S', f'{work}config/{name}_file_contexts', '-l', f'{size}',
         '-C', f'{work}config{os.sep}{name}_fs_config', '-L', name, '-a', name, f"{work_output + name}.img",
         work + name])


@animation
def make_f2fs(name: str, work: str, work_output, UTC=None):
    print(lang.text91 % name)
    size = GetFolderSize(work + name, 1, 1).rsize_v
    print(f"{name}:[{size}]")
    size_f2fs = (54 * 1024 * 1024) + size
    size_f2fs = int(size_f2fs * 1.15) + 1
    if not UTC:
        UTC = int(time.time())
    with open(f"{work + name}.img", 'wb') as f:
        f.truncate(size_f2fs)
    if call(['mkfs.f2fs', f"{work_output + name}.img", '-O', 'extra_attr', '-O', 'inode_checksum', '-O', 'sb_checksum',
             '-O',
             'compression', '-f']) != 0:
        return 1
    # todo:Its A Stupid method, we need a new!
    with open(f'{work}config{os.sep}{name}_file_contexts', 'a+', encoding='utf-8') as f:
        if not [i for i in f.readlines() if f'/{name}/{name} u' in i]:
            f.write(f'/{name}/{name} u:object_r:system_file:s0\n')
    return call(
        ['sload.f2fs', '-f', work + name, '-C', f'{work}config{os.sep}{name}_fs_config', '-T', f'{UTC}', '-s',
         f'{work}config{os.sep}{name}_file_contexts', '-t', f'/{name}', '-c', f'{work_output + name}.img'])


def mke2fs(name, work, sparse, work_output, size=0, UTC=None):
    print(lang.text91 % name)
    size = GetFolderSize(work + name, 4096, 3, work + "dynamic_partitions_op_list").rsize_v if not size else size / 4096
    print(f"{name}:[{size}]")
    if not UTC:
        UTC = int(time.time())
    if call(
            ['mke2fs', '-O',
             '^has_journal,^metadata_csum,extent,huge_file,^flex_bg,^64bit,uninit_bg,dir_nlink,extra_isize', '-L', name,
             '-I', '256', '-M', f'/{name}', '-m', '0', '-t', 'ext4', '-b', '4096', f'{work_output + name}_new.img',
             f'{int(size)}']) != 0:
        rmdir(f'{work_output + name}_new.img')
        print(lang.text75 % name)
        return 1
    ret = call(
        ['e2fsdroid', '-e', '-T', f'{UTC}', '-S', f'{work}config{os.sep}{name}_file_contexts', '-C',
         f'{work}config{os.sep}{name}_fs_config', '-a', f'/{name}', '-f', f'{work + name}',
         f'{work_output + name}_new.img'])
    if ret != 0:
        rmdir(f'{work + name}_new.img')
        print(lang.text75 % name)
        return 1
    if sparse == "y":
        call(['img2simg', f'{work_output + name}_new.img', f'{work_output + name}.img'])
        try:
            os.remove(work_output + name + "_new.img")
        except (Exception, BaseException):
            logging.exception('Bugs')
    else:
        if os.path.isfile(work_output + name + ".img"):
            try:
                os.remove(work_output + name + ".img")
            except (Exception, BaseException):
                logging.exception('Bugs')
        os.rename(work_output + name + "_new.img", work_output + name + ".img")
    return 0


@animation
def rmdir(path, quiet=False):
    if not path:
        if not quiet:
            win.message_pop(lang.warn1)
    else:
        if not quiet:
            print(lang.text97 + os.path.basename(path))
        try:
            try:
                rmtree(path)
            except (Exception, BaseException):
                call(['busybox', 'rm', '-rf', path], out=1 if quiet else 0)
        except (Exception, BaseException):
            print(lang.warn11.format(path))
        if not quiet:
            win.message_pop(lang.warn11.format(path)) if os.path.exists(path) else print(lang.text98 + path)


@animation
def pack_zip(input_dir=None,output_zip=None, slient=False):
    if input_dir is None:
        input_dir = ProjectManager.current_work_output_path()
    if output_zip is None:
        output_zip = settings.path + os.sep + current_project_name.get() + ".zip"
    if not slient:
        if ask_win(lang.t53) != 1:
            return
    if not ProjectManager.exist():
        win.message_pop(lang.warn1)
    else:
        print(lang.text91 % current_project_name.get())
        if not slient:
            if ask_win(lang.t25) == 1:
                PackHybridRom()
        with zipfile.ZipFile(output_zip, 'w',
                             compression=zipfile.ZIP_DEFLATED) as zip_:
            for file in utils.get_all_file_paths(input_dir):
                file = str(file)
                arch_name = file.replace(input_dir, '')
                if not slient:
                    print(f"{lang.text1}:{arch_name}")
                try:
                    zip_.write(file, arcname=arch_name)
                except Exception as e:
                    print(lang.text2.format(file, e))
        if os.path.exists(output_zip):
            print(lang.text3.format(output_zip))


def dndfile(files):
    for fi in files:
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

    def set_project(self, name):
        if not os.path.isdir(os.path.join(settings.path, name)):
            return
        self.listdir()
        current_project_name.set(name)

    def listdir(self):
        array = []
        for f in os.listdir(settings.path):
            if os.path.isdir(settings.path + os.sep + f) and f not in ['bin', 'pyaxmlparser',
                                                                       'src'] and not f.startswith('.'):
                array.append(f)
        self.combobox["value"] = array
        if not array:
            current_project_name.set('')
            self.combobox.current()
        else:
            self.combobox.current(0)

    def rename(self) -> bool:
        if not ProjectManager.exist():
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
        win.message_pop(lang.warn1) if not ProjectManager.exist() else rmdir(
            ProjectManager.get_work_path(current_project_name.get()))
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
        functions = [
            (lang.text122, lambda: create_thread(pack_zip)),
            (lang.text123, lambda: create_thread(PackSuper)),
            (lang.text19, lambda: win.notepad.select(win.tab7)),
            (lang.t13, lambda: create_thread(FormatConversion))
        ]
        for index, (text, func) in enumerate(functions):
            ttk.Button(self, text=text, command=func).grid(row=0, column=index, padx=5, pady=5)


class UnpackGui(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.t57)
        self.ch = BooleanVar()

    def gui(self):
        self.pack(padx=5, pady=5)
        self.ch.set(True)
        self.fm = ttk.Combobox(self, state="readonly",
                               values=(
                               'new.dat.br', 'new.dat.xz', "new.dat", 'img', 'zst', 'payload', 'super', 'update.app'))
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
        f_path = os.path.join(ProjectManager.current_work_path(), self.lsg.selected[0] + ".img")
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

    def refs(self, auto=False):
        self.lsg.clear()
        work = ProjectManager.current_work_path()
        if not ProjectManager.exist():
            return False
        if auto:
            for index, value in enumerate(self.fm.cget("values")):
                self.fm.current(index)
                self.refs()
                if len(self.lsg.vars):
                    return
            self.fm.current(0)
            return
        if self.fm.get() == 'payload':
            if os.path.exists(work + "payload.bin"):
                with open(work + "payload.bin", 'rb') as pay:
                    for i in utils.payload_reader(pay).partitions:
                        self.lsg.insert(f"{i.partition_name}{hum_convert(i.new_partition_info.size):>10}",
                                        i.partition_name)
        elif self.fm.get() == 'super':
            if os.path.exists(work + "super.img"):
                if gettype(work + "super.img") == 'sparse':
                    create_thread(utils.simg2img, work + "super.img", join=True)
                for i in lpunpack.get_parts(work + "super.img"):
                    self.lsg.insert(i, i)
        elif self.fm.get() == 'update.app':
            if os.path.exists(work + "UPDATE.APP"):
                for i in splituapp.get_parts(work + "UPDATE.APP"):
                    self.lsg.insert(i, i)
        else:
            for file_name in os.listdir(work):
                if file_name.endswith(self.fm.get()):
                    f_type = gettype(work + file_name)
                    if f_type == 'unknown':
                        f_type = self.fm.get()
                    self.lsg.insert(f'{file_name.split("." + self.fm.get())[0]} [{f_type}]',
                                    file_name.split("." + self.fm.get())[0])

    def refs2(self):
        self.lsg.clear()
        if not os.path.exists(work := ProjectManager.current_work_path()):
            win.message_pop(lang.warn1)
            return False
        parts_dict = JsonEdit(work + "config/parts_info").read()
        for folder in os.listdir(work):
            if os.path.isdir(work + folder) and folder in parts_dict.keys():
                self.lsg.insert(f"{folder} [{parts_dict.get(folder, 'Unknown')}]", folder)

    def close_(self):
        lbs = self.lsg.selected.copy()
        self.hd()
        if self.ch.get() == 1:
            unpack(lbs, self.fm.get())
            self.refs()
        else:
            Packxx(lbs)


def img2simg(path):
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
        ttk.Button(t, text=lang.ok, command=lambda: create_thread(self.conversion), style='Accent.TButton').pack(side='left',
                                                                                                                 padx=5, pady=5,
                                                                                                                 fill=BOTH,
                                                                                                                 expand=True)
        t.pack(side=BOTTOM, fill=BOTH)

    def relist(self):
        work = ProjectManager.current_work_path()
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
                if os.path.isfile(work + i) and gettype(work + i) == 'sparse':
                    self.list_b.insert(i, i)
        elif self.h.get() == 'raw':
            for i in os.listdir(work):
                if os.path.isfile(work + i):
                    if gettype(work + i) in ['ext', 'erofs', 'super', 'f2fs']:
                        self.list_b.insert(i, i)

    @staticmethod
    def refile(f):
        for i in os.listdir(work := ProjectManager.current_work_output_path()):
            if i.endswith(f) and os.path.isfile(work + i):
                yield i

    @animation
    def conversion(self):
        work = ProjectManager.current_work_output_path()
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
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + i)
                        call(['brotli', '-dj', work + i])
                if hget == 'xz':
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + i)
                        Unxz(work + i)
                if hget == 'dat':
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + work + i)
                        transferfile = os.path.abspath(
                            os.path.dirname(work)) + os.sep + basename + ".transfer.list"
                        if os.access(transferfile, os.F_OK) and os.path.getsize(work + i) != 0:
                            Sdat2img(transferfile, work + i, work + basename + ".img")
                            if os.access(work + basename + ".img", os.F_OK):
                                os.remove(work + i)
                                os.remove(transferfile)
                                try:
                                    os.remove(work + basename + '.patch.dat')
                                except (IOError, PermissionError, FileNotFoundError):
                                    logging.exception('Bugs')
                        else:
                            print("transferpath" + lang.text84)
                    if os.path.exists(work + basename + '.img'):
                        img2simg(work + basename + '.img')
                if hget == 'raw':
                    if os.path.exists(work + basename + '.img'):
                        img2simg(work + basename + '.img')
            elif f_get == 'raw':
                basename = os.path.basename(i).split('.')[0]
                if hget == 'br':
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + i)
                        call(['brotli', '-dj', work + i])
                if hget == 'xz':
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + i)
                        Unxz(work + i)
                if hget in ['dat', 'br', 'xz']:
                    if os.path.exists(work):
                        if hget == 'br':
                            i = i.replace('.br', '')
                        if hget == 'xz':
                            i = i.replace('.xz', '')
                        print(lang.text79 + work + i)
                        transferfile = os.path.abspath(
                            os.path.dirname(work)) + os.sep + basename + ".transfer.list"
                        if os.access(transferfile, os.F_OK) and os.path.getsize(work + i) != 0:
                            Sdat2img(transferfile, work + i, work + basename + ".img")
                            if os.access(work + basename + ".img", os.F_OK):
                                try:
                                    os.remove(work + i)
                                    os.remove(transferfile)
                                    os.remove(work + basename + '.patch.dat')
                                except (PermissionError, IOError, FileNotFoundError, IsADirectoryError):
                                    logging.exception('Bugs')
                        else:
                            print("transferfile" + lang.text84)
                if hget == 'sparse':
                    utils.simg2img(work + i)
            elif f_get == 'dat':
                if hget == 'raw':
                    img2simg(work + i)
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], "dat")
                if hget == 'br':
                    print(lang.text79 + i)
                    call(['brotli', '-dj', work + i])
                if hget == 'xz':
                    print(lang.text79 + i)
                    Unxz(work + i)

            elif f_get == 'br':
                if hget == 'raw':
                    img2simg(work + i)
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], 0)
                if hget in ['dat', 'xz']:
                    if hget == 'xz':
                        print(lang.text79 + i)
                        Unxz(work + i)
                        i = i.rsplit('.xz', 1)[0]

                    print(lang.text88 % (os.path.basename(i).split('.')[0], 'br'))
                    call(['brotli', '-q', '0', '-j', '-w', '24', work + i, '-o', f'{work + i}.br'])
                    if os.access(work + i + '.br', os.F_OK):
                        try:
                            os.remove(work + i)
                        except Exception:
                            logging.exception('Bugs')
        print(lang.text8)


def init_verify():
    if not os.path.exists(settings.tool_bin):
        error(1, 'Sorry,Not support your device yet.')
    if not settings.path.isprintable():
        ask_win2(lang.warn16 % lang.special_words)


def __init__tk():
    if not os.path.exists(temp):
        re_folder(temp, quiet=True)
    if not os.path.exists(tool_log):
        open(tool_log, 'w', encoding="utf-8", newline="\n").close()
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(asctime)s:%(filename)s:%(name)s:%(message)s',
                        filename=tool_log, filemode='w')
    global win
    win = Tool()
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
    if os.name == 'nt' and settings.treff == '1':
        pywinstyles.apply_style(win, 'acrylic')
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
    print(lang.text108)
    if is_pro:
        if not verify.state:
            Active(verify, settings, win, images, lang).gui()
    win.update()
    if settings.custom_system == 'Android':
        win.attributes('-fullscreen', True)
    move_center(win)
    win.get_time()
    print(lang.text134 % (dti() - start))
    if os.name == 'nt':
        do_override_sv_ttk_fonts()
        if sys.getwindowsversion().major <= 6:
            ask_win('Support for Windows 7 and older operating systems will be removed after version 4.0.0')
    if len(sys.argv) > 1:
        dndfile(sys.argv[1:])
    states.inited = True
    win.mainloop()


def init():
    app = QApplication(sys.argv)
    win_qt = MainWindow()
    win_qt.show()
    tool = threading.Thread(target=__init__tk)
    tool.start()
    sys.exit(app.exec())


def restart(er=None):
    try:
        if animation.tasks:
            if not ask_win2("Your operation will not be saved."):
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