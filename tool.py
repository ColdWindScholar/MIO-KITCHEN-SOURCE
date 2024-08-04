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
import ctypes
import hashlib
import json
import platform
import shutil
import subprocess
import threading
from collections import deque
from functools import wraps
from random import randrange
from tkinter.ttk import Scrollbar

from unkdz import KDZFileTools

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
from timeit import default_timer as dti
import zipfile
from io import BytesIO, StringIO
from tkinter import (Tk, BOTH, LEFT, RIGHT, Canvas, Text, X, Y, BOTTOM, StringVar, IntVar, TOP, Toplevel,
                     HORIZONTAL, TclError, Frame, Label, Listbox, DISABLED, Menu, BooleanVar, CENTER)
from shutil import rmtree, copy, move
import pygments.lexers
import requests
from requests import ConnectTimeout, HTTPError
import sv_ttk
from PIL.Image import open as open_img
from PIL.ImageTk import PhotoImage
from dumper import Dumper
from utils import lang

if os.name == 'nt':
    import windnd
    from ctypes import windll
    from tkinter import filedialog
    import pywinstyles
else:
    import mkc_filedialog as filedialog

if sys.version_info.major == 3:
    if sys.version_info.minor < 8 or sys.version_info.minor > 12:
        input(
            f"Not supported: [{sys.version}] yet\nEnter to quit\nSorry for any inconvenience caused")
        sys.exit(1)
import imgextractor
import lpunpack
import mkdtboimg
import ozipdecrypt
import splituapp
import ofp_qc_decrypt
import ofp_mtk_decrypt
import editor
import opscrypto
import images
import extra
import AI_engine
import ext4
from config_parser import ConfigParser
import utils
from sv_ttk_fixes import *
from extra import fspatch, re, contextpatch
from utils import cz, jzxs, v_code, gettype, findfile, findfolder, Sdat2img
from controls import ListBox, ScrollFrame
from undz import DZFileTools
from selinux_audit_allow import main as selinux_audit_allow

try:
    import imp
except ImportError:
    imp = None
try:
    from pycase import ensure_dir_case_sensitive
except ImportError:
    def ensure_dir_case_sensitive(*x):
        print(f'Cannot sensitive {x}, Not Supported')

cwd_path = utils.prog_path


class States:
    update_window = False
    donate_window = False
    mpk_store = False
    open_pids = []
    run_source = True if gettype(sys.argv[0]) == "unknown" else False
    in_oobe = False


class JsonEdit:
    def __init__(self, j_f):
        self.file = j_f

    def read(self):
        if not os.path.exists(self.file):
            return {}
        with open(self.file, 'r+', encoding='utf-8') as pf:
            try:
                return json.load(pf)
            except (AttributeError, ValueError, json.decoder.JSONDecodeError):
                return {}

    def write(self, data):
        with open(self.file, 'w+', encoding='utf-8') as pf:
            json.dump(data, pf, indent=4)

    def edit(self, name, value):
        data = self.read()
        data[name] = value
        self.write(data)


class LoadAnim:
    gifs = []

    def __init__(self):
        self.frames = []
        self.hide_gif = False
        self.frame = None
        self.tasks = {}

    def run(self, ind: int = 0):
        self.hide_gif = False
        if not self.hide_gif:
            win.gif_label.pack(padx=10, pady=10)
        self.frame = self.frames[ind]
        ind += 1
        if ind == len(self.frames):
            ind = 0
        win.gif_label.configure(image=self.frame)
        self.gifs.append(win.gif_label.after(30, self.run, ind))

    def stop(self):
        for i in self.gifs:
            try:
                win.gif_label.after_cancel(i)
            except (Exception, BaseException):
                ...
        win.gif_label.pack_forget()
        self.hide_gif = True

    def init(self):
        self.run()
        self.stop()

    def load_gif(self, gif):
        try:
            while True:
                self.frames.append(PhotoImage(gif))
                gif.seek(len(self.frames))
        except EOFError:
            ...

    def __call__(self, func):
        @wraps(func)
        def call_func(*args, **kwargs):
            cz(self.run())
            task_num = func.__name__
            task_real = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
            info = [hash(func), args, task_real]
            if task_num in self.tasks:
                try:
                    self.tasks[task_num].index(info)
                except ValueError:
                    self.tasks[task_num].append(info)
                else:
                    print(f"Please Wait for task_{task_real.native_id} with args {info[1]}...\n")
                    return
            else:
                self.tasks[task_num] = [info]
            task_real.start()
            task_real.join()
            if task_num in self.tasks:
                if len(self.tasks.get(task_num)) - 1 >= 0:
                    del self.tasks[task_num][self.tasks[task_num].index(info)]
                else:
                    del self.tasks[task_num]
                if not self.tasks[task_num]:
                    del self.tasks[task_num]
            del info, task_num
            if not self.tasks:
                self.stop()

        return call_func


animation = LoadAnim()


class DevNull:
    def __init__(self):
        ...

    def write(self, string):
        ...

    @staticmethod
    def flush():
        ...


def warn_win(text='', color='orange', title="Warn"):
    ask = Toplevel(win)
    ask.title(title)
    # ask.place(relx=0.5, rely=0.5, anchor="center")
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20), foreground=color).pack(side=TOP)
    frame_button = ttk.Frame(frame_inner)
    frame_button.pack(side=TOP)
    ask.lift()
    ask.focus_force()
    jzxs(ask)
    ask.after(1500, ask.destroy)


class ToolBox(ttk.Frame):
    def __init__(self, master):
        super().__init__(master=master)

    def __on_mouse(self, event):
        self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

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
        """"""
        width = 17
        ttk.Button(self.label_frame, text=lang.text114, command=lambda: cz(download_file), width=width).grid(row=0,
                                                                                                             column=0,
                                                                                                             padx=5,
                                                                                                             pady=5)
        ttk.Button(self.label_frame, text=lang.t59, command=self.GetFileInfo, width=width).grid(row=0, column=1, padx=5,
                                                                                                pady=5)
        ttk.Button(self.label_frame, text=lang.t60, command=self.FileBytes, width=width).grid(row=0, column=2, padx=5,
                                                                                              pady=5)
        ttk.Button(self.label_frame, text=lang.audit_allow, command=self.SelinuxAuditAllow, width=width).grid(row=1,
                                                                                                              column=0,
                                                                                                              padx=5,
                                                                                                              pady=5)
        """"""
        self.update_ui()

    def update_ui(self):
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

    class SelinuxAuditAllow(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.audit_allow)
            self.gui()
            jzxs(self)

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
            self.button.configure(text=lang.running, state='disabled')
            cz(selinux_audit_allow, self.choose_file.get(), self.output_dir.get())
            self.button.configure(text=lang.done, state='normal', style='')

    class FileBytes(Toplevel):
        def __init__(self):
            super().__init__()
            self.values = ("B", "GB", "KB", "MB")
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
            jzxs(self)

        def calc(self):
            self.result_size.delete(0, tk.END)
            self.result_size.insert(0, self.__calc(self.h.get(), self.f_.get(), self.origin_size.get()))

        def __calc(self, origin: str, convert: str, size) -> str:
            if origin == convert:
                return size
            try:
                origin_size = float(size)
            except ValueError as e:
                return "0"

            units = {
                "B": 1,
                "KB": 2 ** 10,
                "MB": 2 ** 20,
                "GB": 2 ** 30
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
            jzxs(self)

        def gui(self):
            a = ttk.LabelFrame(self, text='Drop')
            (tl := ttk.Label(a, text=lang.text132_e)).pack(fill=BOTH, padx=5, pady=5)
            tl.bind('<Button-1>', lambda *x: self.dnd([filedialog.askopenfilename()]))
            a.pack(side=TOP, padx=5, pady=5, fill=BOTH)
            if os.name == 'nt':
                windnd.hook_dropfiles(a, self.dnd)
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
                    pass

        def dnd(self, file_list: list):
            cz(self.__dnd, file_list)

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


class Tool(Tk):
    def __init__(self):
        super().__init__()
        self.tab6 = None
        self.rotate_angle = 0
        do_set_window_deffont(self)
        self.show = None
        self.scroll = None
        self.frame_bg = None
        self.canvas1 = None
        self.scrollbar = None
        self.tab7 = None
        self.tab5 = None
        self.tab4 = None
        self.tab3 = None
        self.tab2 = None
        self.tab = None
        self.sub_win3 = None
        self.sub_win2 = None
        self.rzf = None
        self.tsk = None
        self.gif_label = None
        self.photo = None
        self.show_local = None
        self.list2 = None
        self.notepad = None
        self.message_pop = warn_win
        self.title('MIO-KITCHEN')
        if os.name != "posix":
            self.iconphoto(True,
                           PhotoImage(
                               data=images.icon_byte))
        sys.stdout = DevNull()

    def put_log(self):
        log_ = settings.path + os.sep + v_code() + '.txt'
        with open(log_, 'w', encoding='utf-8', newline='\n') as f:
            f.write(self.show.get(1.0, tk.END))
            self.show.delete(1.0, tk.END)
        print(lang.text95 + log_)

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
        tr2 = Label(tr, text=lang.text132)
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
        if os.name == 'nt':
            windnd.hook_dropfiles(tr, func=dndfile)
            windnd.hook_dropfiles(tr2, func=dndfile)
        else:
            print(f'{platform.system()} Dont Support Drop File.\nReason: I am Lazy.')
        self.scroll.pack(side=LEFT, fill=BOTH)
        self.scroll.config(command=self.show.yview)
        self.show.config(yscrollcommand=self.scroll.set)
        ttk.Button(self.rzf, text=lang.text105, command=lambda: self.show.delete(1.0, tk.END)).pack(side='bottom',
                                                                                                    padx=10,
                                                                                                    pady=5,
                                                                                                    expand=True)
        ttk.Button(self.rzf, text=lang.text106, command=lambda: self.put_log()).pack(side='bottom', padx=10, pady=5,
                                                                                     expand=True)
        self.rzf.pack(padx=5, pady=5, fill=BOTH, side='bottom')
        self.gif_label = Label(self.rzf)
        self.gif_label.pack(padx=10, pady=10)
        MpkMan().gui()

    def tab_content(self):

        global kemiaojiang
        global kemiaojiang_img
        global kemiaojiang_label
        kemiaojiang_img = open_img(open(f'{cwd_path}/bin/kemiaojiang.png', 'rb'))
        kemiaojiang = PhotoImage(kemiaojiang_img.resize((280, 540)))
        kemiaojiang_label = Label(self.tab, image=kemiaojiang)
        kemiaojiang_label.pack(side='left', padx=0, expand=True)
        about_ = Label(self.tab, text="Ambassador: KeMiaoJiang\nPainter: HY-惠\nWelcome To MIO-KITCHEN", justify='left',
                       foreground='#87CEFA', font=(None, 12))
        about_.pack(side='top', padx=5, pady=120, expand=True)

        def change_size(event):
            pass

        self.tab.bind('<Configure>', change_size)

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
            color1 = hex(randrange(16, 256))[2:]
            color2 = hex(randrange(16, 256))[2:]
            color3 = hex(randrange(16, 256))[2:]
            ans = "#" + color1 + color2 + color3
            return ans

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
        # Label(self.tab4,text=lang.text127,font=('楷书', 12), fg='#ff8800').pack(padx=10, pady=10)
        ttk.Label(self.tab4, text=f"{settings.language} By {lang.language_file_by}", foreground='orange',
                  background='gray').pack()
        Label(self.tab4, text=lang.text110, font=(None, 10)).pack(padx=10, pady=10, side='bottom')
        ttk.Label(self.tab4, text="Open Source, Free, Faster", style="Link.TLabel").pack()
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
              text="Wechat Pay",
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

        self.show_local = StringVar()
        self.show_local.set(settings.path)
        Setting_Frame = ScrollFrame(self.tab3)
        Setting_Frame.gui()
        Setting_Frame.pack(fill=BOTH, expand=True)
        sf1 = ttk.Frame(Setting_Frame.label_frame)
        sf2 = ttk.Frame(Setting_Frame.label_frame)
        sf3 = ttk.Frame(Setting_Frame.label_frame)
        sf4 = ttk.Frame(Setting_Frame.label_frame, width=20)
        ttk.Label(sf1, text=lang.text124).pack(side='left', padx=10, pady=10)
        self.list2 = ttk.Combobox(sf1, textvariable=theme, state='readonly', values=["light", "dark"])
        self.list2.pack(padx=10, pady=10, side='left')
        self.list2.bind('<<ComboboxSelected>>', lambda *x: settings.set_theme())
        ttk.Label(sf3, text=lang.text125).pack(side='left', padx=10, pady=10)
        slo = ttk.Label(sf3, textvariable=self.show_local)
        slo.bind('<Button-1>', lambda *x: os.startfile(self.show_local.get()) if os.name == 'nt' else ...)
        slo.pack(padx=10, pady=10, side='left')
        ttk.Button(sf3, text=lang.text126, command=settings.modpath).pack(side="left", padx=10, pady=10)

        ttk.Label(sf2, text=lang.lang).pack(side='left', padx=10, pady=10)
        lb3 = ttk.Combobox(sf2, state='readonly', textvariable=language,
                           values=[str(i.rsplit('.', 1)[0]) for i in
                                   os.listdir(cwd_path + os.sep + "bin" + os.sep + "languages")])
        context = StringVar(value=settings.contextpatch)
        New_Project_Structure = StringVar(value=settings.nps)

        def enable_contextpatch():
            if context.get() == '1':
                if ask_win2(
                        "Are you sure enable it? This feature may cause cannot boot rom!"):
                    settings.set_value('contextpatch', context.get())
                else:
                    context.set('0')
                    settings.set_value('contextpatch', context.get())
                    enable_cp.configure(state='off')
            else:
                settings.set_value('contextpatch', context.get())

        context.trace("w", lambda *x: enable_contextpatch())
        New_Project_Structure.trace("w", lambda *x: settings.set_value('nps', New_Project_Structure.get()))
        get_setting_button('ai_engine', sf4, lang.ai_engine)
        if os.name == 'nt':
            get_setting_button('treff', sf4, 'Transparent effect')
        # ttk.Checkbutton(sf4, text="新项目结构", variable=New_Project_Structure, onvalue='1',
        #             offvalue='0',
        #           style="Toggle.TButton").pack(padx=10, pady=10, fill=X)
        enable_cp = ttk.Checkbutton(sf4, text="Context_Patch", variable=context, onvalue='1',
                                    offvalue='0',
                                    style="Toggle.TButton")
        enable_cp.pack(padx=10, pady=10, fill=X)
        get_setting_button('rm_pay', sf4, lang.t9.format("payload.bin"))
        get_setting_button('auto_unpack', sf4, lang.auto_unpack)
        lb3.pack(padx=10, pady=10, side='left')
        lb3.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())
        sf1.pack(padx=10, pady=10, fill='both')
        sf2.pack(padx=10, pady=10, fill='both')
        sf3.pack(padx=10, pady=10, fill='both')
        sf4.pack(padx=10, pady=10, fill='both')
        Setting_Frame.update_ui()
        ttk.Button(self.tab3, text=lang.t38, command=Updater).pack(padx=10, pady=10, fill=X)
        ttk.Button(self.tab3, text=lang.text16, command=self.support).pack(padx=10, pady=10, fill=X, side=BOTTOM)


win = Tool()
start = dti()
dn = utils.project_name = StringVar()
theme = StringVar()
language = StringVar()
tool_self = os.path.normpath(os.path.abspath(sys.argv[0]))
tool_bin = os.path.join(cwd_path, 'bin', platform.system(), platform.machine()) + os.sep
states = States()

# Some Functions for Upgrade
if os.name == 'nt':
    kernel32 = ctypes.windll.kernel32


    def terminate_process(pid):
        h_process = kernel32.OpenProcess(0x0001, False, pid)
        if h_process:
            kernel32.TerminateProcess(h_process, 0)
            kernel32.CloseHandle(h_process)
        else:
            print(f"Failed to open process with PID {pid}")
else:
    def terminate_process(pid):
        os.kill(pid, 9)


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
        if settings.update_url:
            self.update_url = settings.update_url
        else:
            self.update_url = 'https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest'
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
            ttk.Label(self, text='You are running the source code\nPlease Use "git pull" To Update', foreground='gray',
                      justify='center').pack(fill=X, pady=10,
                                             padx=10, anchor='center')
            jzxs(self)
            return
        self.change_log = Text(f2, width=50, height=15)
        self.change_log.pack(padx=5, pady=5)
        f2.pack(fill=BOTH, padx=5, pady=5)
        self.progressbar = ttk.Progressbar(self, length=200, mode='determinate', orient=tkinter.HORIZONTAL, maximum=100
                                           )
        self.progressbar.pack(padx=5, pady=10)
        f3 = ttk.Frame(self)
        self.update_button = ttk.Button(f3, text=lang.t38, style='Accent.TButton',
                                        command=lambda: cz(self.get_update))
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
            cz(self.get_update)
        self.resizable(width=False, height=False)
        jzxs(self)

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
        if not (new_version := json_.get('name')).endswith(settings.version):
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
            package += '-macos.zip'
        for i in self.update_assets:
            if i.get('name') == package:
                if platform.machine() in ['AMD64', 'X86_64']:
                    self.update_download_url = i.get('browser_download_url')
                    self.update_size = i.get('size')
                    return
                else:
                    break
        self.notice.configure(text=lang.t50, foreground='red')

    def download(self):
        if not os.path.exists(os.path.join(cwd_path, "bin", "temp")):
            os.makedirs(os.path.join(cwd_path, "bin", "temp"))
        mode = True
        self.progressbar.configure(mode='indeterminate')
        self.progressbar.start()
        self.update_zip = os.path.normpath(
            os.path.join(cwd_path, "bin", "temp", os.path.basename(self.update_download_url)))
        for percentage, _, _, _, _ in download_api(self.update_download_url, os.path.join(cwd_path, "bin", "temp"),
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
        if os.path.exists(tool_self):
            shutil.copy(tool_self,
                        os.path.normpath(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe'))))
            self.notice.configure(text=lang.t51)
            with zipfile.ZipFile(self.update_zip, 'r') as zip_ref:
                for file in zip_ref.namelist():
                    if file != ('tool' + ('' if os.name == 'posix' else '.exe')):
                        zip_ref.extract(file, cwd_path)
                    else:
                        zip_ref.extract(file, os.path.join(cwd_path, "bin"))
            update_dict = {
                'updating': '1',
                'language': settings.language,
                'oobe': settings.oobe,
                'new_tool': os.path.join(cwd_path, "bin", "tool" + ('' if os.name != 'nt' else '.exe'))
            }
            for i in update_dict.keys():
                settings.set_value(i, update_dict.get(i, ''))
            subprocess.Popen(
                [os.path.normpath(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe')))],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            terminate_process(os.getpid())
        else:
            self.notice.configure(text=lang.t41, foreground='red')
            self.update_button.configure(state='normal', text=lang.text37)

    def update_process2(self):
        self.notice.configure(text=lang.t51)
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

    def update_process3(self):
        self.notice.configure(text=lang.t52)
        if os.path.exists(settings.new_tool):
            try:
                if os.path.isfile(settings.new_tool):
                    os.remove(settings.new_tool)
                if os.path.isfile(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe'))):
                    os.remove(os.path.normpath(os.path.join(cwd_path, "upgrade" + ('' if os.name != 'nt' else '.exe'))))
                if os.path.exists(os.path.join(cwd_path, "bin", "temp")):
                    shutil.rmtree(os.path.join(cwd_path, "bin", "temp"))
                os.makedirs(os.path.join(cwd_path, "bin", "temp"), exist_ok=True)
            except (IOError, IsADirectoryError, FileNotFoundError, PermissionError) as e:
                print(e)
            settings.set_value('updating', '')
            settings.set_value('new_tool', '')
            subprocess.Popen([os.path.normpath(os.path.join(cwd_path, "tool" + ('' if os.name != 'nt' else '.exe')))],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            terminate_process(os.getpid())
        else:
            self.notice.configure(text=lang.t41, foreground='red')
            self.update_button.configure(state='normal', text=lang.text37)

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
    scroll.config(command=te.yview)
    te.pack(padx=10, pady=10)
    te.insert('insert', desc)
    te.config(yscrollcommand=scroll.set)
    ttk.Button(er, text="Report",
               command=lambda: openurl("https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/issues"),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Restart",
               command=lambda: restart(er),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Exit", command=lambda: win.destroy()).pack(side=LEFT, padx=10, pady=10, expand=True, fill=BOTH)
    jzxs(er)
    er.wait_window()
    sys.exit()


class Welcome(ttk.Frame):
    def __init__(self):
        super().__init__(master=win)
        # self.config(text=lang.text135)
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
            ttk.Label(self, text=lang.text135, font=(None, 40)).pack(padx=10, pady=10, fill=BOTH, expand=True)
            ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
            ttk.Label(self, text=lang.text137, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)
            ttk.Button(self, text=lang.text136, command=self.main).pack(fill=BOTH)
        jzxs(win)
        self.wait_window()
        states.in_oobe = False

    def reframe(self):
        if self.frame:
            self.frame.destroy()
        self.frame = ttk.Frame(self)
        jzxs(win)
        self.frame.pack(expand=1, fill=BOTH)

    def main(self):
        settings.set_value("oobe", 1)
        for i in self.winfo_children():
            i.destroy()
        self.reframe()
        ttk.Label(self.frame, text=lang.text129, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb3_ = ttk.Combobox(self.frame, state='readonly', textvariable=language,
                            values=[i.rsplit('.', 1)[0] for i in
                                    os.listdir(cwd_path + os.sep + "bin" + os.sep + "languages")])
        lb3_.pack(padx=10, pady=10, side='top')
        lb3_.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())
        ttk.Button(self.frame, text=lang.text138, command=self.license).pack(fill=X, side='bottom')

    def license(self):
        settings.set_value("oobe", 2)
        lce = StringVar()

        def load_license():
            te.delete(1.0, tk.END)
            with open(os.path.join(cwd_path, "bin", "licenses", lce.get() + ".txt"), 'r',
                      encoding='UTF-8') as f:
                te.insert('insert', f.read())

        self.reframe()
        lb = ttk.Combobox(self.frame, state='readonly', textvariable=lce,
                          values=[i.rsplit('.')[0] for i in os.listdir(cwd_path + "/bin/licenses") if
                                  i != 'private.txt'])
        lb.bind('<<ComboboxSelected>>', lambda *x: load_license())
        lb.current(0)
        ttk.Label(self.frame, text=lang.text139, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                       expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb.pack(padx=10, pady=10, side='top', fill=X)
        te = Text(self.frame)
        te.pack(fill=BOTH, side='top')
        load_license()
        ttk.Label(self.frame, text=lang.t1).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.private).pack(fill=BOTH, side='bottom')

    def private(self):
        settings.set_value("oobe", 3)
        self.reframe()
        ttk.Label(self.frame, text=lang.t2, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                  expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        with open(os.path.join(cwd_path, "bin", "licenses", "private.txt"), 'r',
                  encoding='UTF-8') as f:
            (te := Text(self.frame)).insert('insert', f.read())
        te.pack(fill=BOTH)
        ttk.Label(self.frame, text=lang.t3).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.support).pack(fill=BOTH, side='bottom')

    def support(self):
        settings.set_value("oobe", 4)
        self.reframe()
        ttk.Label(self.frame, text=lang.text16, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                      expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        self.photo = PhotoImage(data=images.wechat_byte)
        Label(self.frame, image=self.photo).pack(padx=5, pady=5)
        ttk.Label(self.frame, text=lang.text109).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.done).pack(fill=BOTH, side='bottom')

    def done(self):
        settings.set_value("oobe", 5)
        self.reframe()
        ttk.Label(self.frame, text=lang.t4, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                  expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.t5, font=(None, 20)).pack(
            side='top', fill=BOTH, padx=10, pady=10)
        ttk.Button(self, text=lang.text34, command=self.destroy).pack(fill=BOTH, side='bottom')


class SetUtils:
    def __init__(self, set_ini: str = None):
        self.auto_unpack = '0'
        self.treff = '0'
        if set_ini:
            self.set_file = set_ini
        else:
            self.set_file = os.path.join(cwd_path, "bin", "setting.ini")
        self.nps = '0'
        self.rm_pay = '0'
        self.plugin_repo = None
        self.contextpatch = '0'
        self.oobe = '0'
        self.path = None
        self.bar_level = '0.9'
        self.ai_engine = '0'
        self.version = 'basic'
        self.language = 'English'
        self.updating = ''
        self.new_tool = ''
        self.debug_mode = 'No'
        self.theme = 'dark'
        self.update_url = 'https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest'
        self.config = ConfigParser()
        if os.access(self.set_file, os.F_OK):
            self.load()
        else:
            sv_ttk.set_theme("dark")
            error(1,
                  'Some necessary files were lost, please reinstall this software to fix the problem!')

    def load(self):
        self.config.read(self.set_file)
        for i in self.config.items('setting'):
            setattr(self, i[0], i[1])
        if os.path.exists(self.path):
            if not self.path:
                self.path = os.getcwd()
        else:
            self.path = os.getcwd()
        language.set(self.language)
        self.load_language(language.get())
        theme.set(self.theme)
        sv_ttk.set_theme(self.theme)
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
        self.load()

    def set_theme(self):
        print(lang.text100 + theme.get())
        try:
            self.set_value("theme", theme.get())
            sv_ttk.set_theme(theme.get())
            animation.load_gif(open_img(BytesIO(getattr(images, f"loading_{win.list2.get()}_byte"))))
        except Exception as e:
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
            print(lang.t130, e)

    def modpath(self):
        if not (folder := filedialog.askdirectory()):
            return
        self.set_value("path", folder)
        win.show_local.set(folder)
        self.load()


settings = SetUtils()
settings.load()


def re_folder(path):
    if os.path.exists(path):
        rmdir(path)
    os.mkdir(path)


@animation
def un_dtbo(bn: str = 'dtbo') -> None:
    if not (dtboimg := findfile(f"{bn}.img", work := rwork())):
        print(lang.warn3.format(bn))
        return
    re_folder(work + bn)
    re_folder(work + bn + os.sep + "dtbo")
    re_folder(work + bn + os.sep + "dts")
    try:
        mkdtboimg.dump_dtbo(dtboimg, work + bn + os.sep + "dtbo" + os.sep + "dtbo")
    except Exception as e:
        print(lang.warn4.format(e))
        return
    for dtbo in os.listdir(work + bn + os.sep + "dtbo"):
        if dtbo.startswith("dtbo."):
            print(lang.text4.format(dtbo))
            call(
                exe=['dtc', '-@', '-I', 'dtb', '-O', 'dts', work + bn + os.sep + 'dtbo' + os.sep + dtbo, '-o', os.path.join(work, bn, 'dts', 'dts.' + os.path.basename(dtbo).rsplit('.', 1)[1])],
                out=1)
    print(lang.text5)
    try:
        os.remove(dtboimg)
    except (Exception, BaseException):
        ...
    rmdir(work + "dtbo" + os.sep + "dtbo")


@animation
def pack_dtbo() -> bool:
    work = rwork()
    if not os.path.exists(work + "dtbo" + os.sep + "dts") or not os.path.exists(work + "dtbo"):
        print(lang.warn5)
        return False
    re_folder(work + "dtbo" + os.sep + "dtbo")
    for dts in os.listdir(work + "dtbo" + os.sep + "dts"):
        if dts.startswith("dts."):
            print(f"{lang.text6}:{dts}")
            call(
                exe=['dtc', '-@', '-I', 'dts', '-O', 'dtb', f"{os.path.join(work,'dtbo','dts',dts)}", '-o', os.path.join(work,'dtbo','dtbo','dtbo.'+os.path.basename(dts).rsplit('.', 1)[1])],
                out=1)
    print(f"{lang.text7}:dtbo.img")
    list_ = [os.path.join(work, "dtbo", "dtbo", f) for f in os.listdir(work + "dtbo" + os.sep + "dtbo") if
             f.startswith("dtbo.")]
    list_ = sorted(list_, key=lambda x: int(x.rsplit('.')[1]))
    mkdtboimg.create_dtbo(work + "dtbo.img", list_, 4096)
    rmdir(work + "dtbo")
    print(lang.text8)
    return True


@animation
def logo_dump(bn: str = 'logo'):
    if not (logo := findfile(f'{bn}.img', work := rwork())):
        win.message_pop(lang.warn3.format(bn))
        return False
    re_folder(work + bn)
    utils.LogoDumper(logo, work + bn).unpack()


def calculate_md5_file(file_path):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


def calculate_sha256_file(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


@animation
def logo_pack(origin_logo=None) -> int:
    work = rwork()
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
        self.master.bind_all("<MouseWheel>", self.on_mousewheel)

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
            pass

    def on_frame_configure(self):
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"), highlightthickness=0)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # self.on_frame_configure()


class ModuleManager:
    def __init__(self):
        self.module_dir = os.path.join(cwd_path, "bin", "module")
        self.uninstall_gui = self.UninstallMpk
        self.new = self.New
        self.new.module_dir = self.module_dir
        self.uninstall_gui.module_dir = self.module_dir
        self.MshParse.module_dir = self.module_dir

    def get_name(self, id_) -> str:
        name = self.get_info(id_, 'name')
        if name:
            return name
        else:
            return id_

    def get_info(self, id_: str, item: str) -> str:
        info_file = self.module_dir + os.sep + id_ + os.sep + 'info.json'
        if not os.path.exists(info_file):
            return ''
        with open(info_file, 'r', encoding='UTF-8') as f:
            data = json.load(f)
            return data.get(item, '')

    @animation
    def run(self, id_) -> int:
        if not dn.get():
            print(lang.warn1)
            return 1
        if id_:
            value = id_
        else:
            print(lang.warn2)
            return 1

        name = self.get_name(id_)
        script_path = self.module_dir + os.sep + value + os.sep
        file = ''
        with open(os.path.join(script_path, "info.json"), 'r', encoding='UTF-8') as f:
            data = json.load(f)
            for n in data['depend'].split():
                if not os.path.exists(os.path.join(self.module_dir, n)):
                    print(lang.text36 % (name, n, n))
                    return 2
        if os.path.exists(script_path + "main.sh") or os.path.exists(script_path + "main.msh"):
            values = self.Parse(script_path + "main.json", os.path.exists(script_path + "main.msh")) if os.path.exists(
                script_path + "main.json") else None
            if not os.path.exists(temp := os.path.join(cwd_path, "bin", "temp") + os.sep):
                re_folder(temp)
            if not file:
                file = temp + v_code()
                while os.path.exists(file):
                    file = temp + v_code()
            if os.path.exists(script_path + "main.sh"):
                with open(file, "w", encoding='UTF-8', newline="\n") as f:
                    if values:
                        for va in values.gavs.keys():
                            if gva := values.gavs[va].get():
                                f.write(f"export {va}='{gva}'\n")
                        values.gavs.clear()
                    f.write('export tool_bin="{}"\n'.format(
                        tool_bin.replace(
                            '\\',
                            '/')))
                    f.write(f'export version="{settings.version}"\n')
                    f.write(f'export language="{settings.language}"\n')
                    f.write(f'export bin="{script_path.replace(os.sep, "/")}"\n')
                    f.write('export moddir="{}"\n'.format(self.module_dir.replace('\\', '/')))
                    f.write(
                        "export project='{}'\nsource $1".format(
                            rwork().replace('\\', '/')))
            if os.path.exists(script_path + "main.msh"):
                self.MshParse(script_path + "main.msh")
            if os.path.exists(file) and os.path.exists(script_path + "main.sh"):
                shell = 'ash' if os.name == 'posix' else 'bash'
                call(['busybox', shell, file, (script_path + 'main.sh').replace(os.sep, '/')])
                try:
                    os.remove(file)
                except (Exception, BaseException) as e:
                    print(e)
        elif os.path.exists(script_path + "main.py") and imp:
            try:
                module = imp.load_source('module', script_path + "main.py")
                if hasattr(module, 'main'):
                    data = {
                        "win": win,
                        'version': settings.version, "bin": script_path.replace(os.sep, "/"),
                        "project": rwork().replace('\\', '/'), 'moddir': self.module_dir.replace('\\', '/'),
                        'tool_bin': tool_bin.replace(
                            '\\',
                            '/')
                    }
                    module.main(data)
            except Exception as e:
                print(e)
        elif not os.path.exists(self.module_dir + os.sep + value):
            win.message_pop(lang.warn7.format(value))
            list_pls_plugin()
            win.tab7.lift()
        else:
            print(lang.warn8)
        return 0

    def get_installed(self, id_) -> bool:
        return os.path.exists(os.path.join(self.module_dir, id_))

    def install(self, mpk):
        if not mpk or not os.path.exists(mpk) or not zipfile.is_zipfile(mpk):
            print(lang.warn2)
            return
        with zipfile.ZipFile(mpk) as f:
            if 'info' not in f.namelist():
                print(lang.warn2)
                return
        mconf = ConfigParser()
        with zipfile.ZipFile(mpk) as f:
            with f.open('info') as info_file:
                mconf.read_string(info_file.read().decode('utf-8'))
        try:
            supports = mconf.get('module', 'supports').split()
            if sys.platform not in supports:
                return 0
        except (Exception, BaseException):
            ...
        for dep in mconf.get('module', 'depend').split():
            if not os.path.isdir(os.path.join(cwd_path, "bin", "module", dep)):
                print(lang.text36 % (mconf.get('module', 'name'), dep, dep))
                return 0
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

        print(mconf.get('module', 'name'), lang.text39)
        list_pls_plugin()

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
            for i in get_all_file_paths(self.module_dir + os.sep + value):
                arch_name = str(i).replace(self.module_dir + os.sep + value, '')
                if os.path.basename(i) in ['info.json', 'icon']:
                    continue
                print(f"{lang.text1}:{arch_name}")
                try:
                    mpk.write(str(i), arcname=arch_name)
                except Exception as e:
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
            self.identifier = None
            self.dep = None
            self.intro = None
            self.ver = None
            self.aou = None
            self.name = None
            if not hasattr(self, 'module_dir'):
                self.module_dir = os.path.join(cwd_path, "bin", "module")
            self.gui()
            jzxs(self)

        @staticmethod
        def label_entry(master, text, side):
            frame = Frame(master)
            ttk.Label(frame, text=text).pack(padx=5, pady=5, side=LEFT)
            entry = ttk.Entry(frame)
            entry.pack(padx=5, pady=5, side=LEFT)
            frame.pack(padx=5, pady=5, fill=X, side=side)
            return entry

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
            self.name = self.label_entry(f, lang.t20, TOP)
            self.aou = self.label_entry(f, lang.t21, TOP)
            self.ver = self.label_entry(f, lang.t22, TOP)
            self.dep = self.label_entry(f, lang.t23, TOP)
            self.identifier = self.label_entry(f, 'identifier', TOP)
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
            with open(self.module_dir + os.sep + iden + os.sep + "info.json", 'w+', encoding='utf-8',
                      newline='\n') as js:
                js.write(json.dumps(data))
            list_pls_plugin()
            self.editor_(iden)

    class MshParse:
        extra_envs = {}
        grammar_words = {"echo": lambda strings: print(strings),
                         "rmdir": lambda path: rmdir(path.strip()),
                         "run": lambda cmd: call(exe=str(cmd), extra=False),
                         'gettype': lambda file_: gettype(file_),
                         'exist': lambda x: '1' if os.path.exists(x) else '0'}

        def __init__(self, sh):
            if not hasattr(self, 'module_dir'):
                self.module_dir = os.path.join(cwd_path, "bin", "module")
            self.envs = {'version': settings.version, 'tool_bin': tool_bin.replace('\\', '/'),
                         'project': (settings.path + os.sep + dn.get()).replace('\\', '/'),
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

        def sfor(self, vn, vs, do):
            for v in vs.split(',' if ',' in vs else None):
                self.runline(do.replace(f'@{vn}@', v))

        def sh(self, cmd):
            with open(file_ := (os.path.join(cwd_path, "bin", "temp", v_code())), "w",
                      encoding='UTF-8',
                      newline="\n") as f:
                for i in self.envs:
                    f.write(f'export {i}="{self.envs.get(i, "")}"\n')
                f.write("source $1")
            if os.path.exists(file_):
                sh = "ash" if os.name == 'posix' else "bash"
                call(f"busybox {sh} {file_} {cmd.replace(os.sep, '/')}")
                try:
                    os.remove(file_)
                except (Exception, BaseException):
                    ...

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

            def generate_sh():
                temp = os.path.join(cwd_path, "bin", "temp")
                if not os.path.exists(temp):
                    os.mkdir(temp)
                self.destroy()

            def generate_msh():
                for va in self.gavs.keys():
                    if gva := self.gavs[va].get():
                        ModuleManager.MshParse.extra_envs[va] = gva
                        if gva is str and os.path.isabs(gva) and os.name == 'nt':
                            if '\\' in gva:
                                ModuleManager.MshParse.extra_envs[va] = gva.replace("\\", '/')
                self.destroy()
                self.gavs.clear()

            with open(jsons, 'r', encoding='UTF-8') as f:
                try:
                    data = json.load(f)
                except Exception as e:
                    win.message_pop(lang.text133 + str(e))
                    print(lang.text133 + str(e))
                    self.destroy()
                self.title(data['main']['info']['title'])
                # 设置窗口大小和位置
                height = data['main']['info']['height']
                width = data['main']['info']['weight']
                if height != 'none' and width != 'none':
                    self.geometry(f"{width}x{height}")
                resizable = data['main']['info']['resize']
                try:
                    self.attributes('-topmost', 'true')
                except (Exception, BaseException):
                    ...
                self.resizable(True, True) if resizable == '1' else self.resizable(False, False)
                for group_name, group_data in data['main'].items():
                    if group_name != "info":
                        group_frame = ttk.LabelFrame(self, text=group_data['title'])
                        group_frame.pack(padx=10, pady=10)
                        for con in group_data['controls']:
                            if con["type"] == "text":
                                text_label = ttk.Label(group_frame, text=con['text'],
                                                       font=(None, int(con['fontsize'])))
                                text_label.pack(side=con['side'], padx=5, pady=5)
                            elif con["type"] == "button":
                                button_command = con['command']
                                button = ttk.Button(group_frame, text=con['text'],
                                                    command=lambda: print(button_command))
                                button.pack(side='left')
                            elif con["type"] == "filechose":
                                ft = ttk.Frame(group_frame)
                                ft.pack(fill=X)
                                file_var_name = con['set']
                                self.gavs[file_var_name] = StringVar()
                                file_label = ttk.Label(ft, text=con['text'])
                                file_label.pack(side='left', padx=10, pady=10)
                                file_entry = ttk.Entry(ft, textvariable=self.gavs[file_var_name])
                                file_entry.pack(side='left', padx=5, pady=5)
                                file_button = ttk.Button(ft, text=lang.text28,
                                                         command=lambda: self.gavs[file_var_name].set(
                                                             filedialog.askopenfilename()))
                                file_button.pack(side='left', padx=10, pady=10)
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
                                text = 'M.K.C' if 'text' not in con else con['text']
                                ttk.Checkbutton(group_frame, text=text, variable=self.gavs[b_var_name], onvalue=1,
                                                offvalue=0,
                                                style="Switch.TCheckbutton").pack(
                                    padx=5, pady=5, fill=BOTH)
                            else:
                                print(lang.warn14.format(con['type']))
            ttk.Button(self, text=lang.ok, command=lambda: cz(generate_msh if msh else generate_sh)).pack(fill=X,
                                                                                                          side='bottom')
            jzxs(self)
            self.wait_window()

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
                ...
            self.title(lang.t6)
            jzxs(self)
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
            if name:
                print(lang.text29.format(name if not show_name else show_name))
                if os.path.exists(self.module_dir + os.sep + name):
                    try:
                        rmtree(self.module_dir + os.sep + name)
                    except PermissionError as e:
                        print(e)
                if os.path.exists(self.module_dir + os.sep + name):
                    win.message_pop(lang.warn9, 'red')
                else:
                    print(lang.text30)
                    try:
                        list_pls_plugin()
                    except (Exception, BaseException):
                        ...
            else:
                win.message_pop(lang.warn2)


ModuleManager = ModuleManager()

list_pls_plugin = print


class MpkMan(ttk.Frame):
    def __init__(self):
        super().__init__(master=win.tab7)
        self.rmenu2 = None
        self.pls = None
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
                if os.path.exists(os.path.join(self.moduledir, i, 'icon')):
                    self.images_[i] = PhotoImage(open_img(os.path.join(self.moduledir, i, 'icon')).resize((70, 70)))
                else:
                    self.images_[i] = PhotoImage(data=images.none_byte)
                data = JsonEdit(os.path.join(self.moduledir, i, "info.json")).read()
                icon = tk.Label(self.pls.scrollable_frame,
                                image=self.images_[i],
                                compound="center",
                                text=data.get('name'),
                                bg="#4682B4",
                                wraplength=70,
                                justify='center')
                icon.bind('<Double-Button-1>', lambda event, ar=i: cz(ModuleManager.run, ar))
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
        ttk.Button(self, text='Mpk Store', command=lambda: cz(MpkStore)).pack(side="right", padx=10, pady=10)
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
        rmenu.add_command(label=lang.text23, command=lambda: cz(self.refresh))
        rmenu.add_command(label=lang.text115, command=lambda: cz(ModuleManager.new))
        self.rmenu2 = Menu(self.pls, tearoff=False, borderwidth=0)
        self.rmenu2.add_command(label=lang.text20,
                                command=lambda: cz(ModuleManager.uninstall_gui, self.chosen.get()))
        self.rmenu2.add_command(label=lang.text22,
                                command=lambda: cz(ModuleManager.run, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t14, command=lambda: cz(ModuleManager.export, self.chosen.get()))
        self.rmenu2.add_command(label=lang.t17,
                                command=lambda: cz(ModuleManager.new.editor_, ModuleManager, self.chosen.get()))
        self.list_pls()
        lf1.pack(padx=10, pady=10)


class InstallMpk(Toplevel):
    def __init__(self, mpk=None):
        super().__init__()
        self.pyt = None
        self.mconf = ConfigParser()
        self.installable = True
        self.mpk = mpk
        self.title(lang.text31)
        self.icon = None
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
        self.prog = ttk.Progressbar(self, length=200, mode='determinate', orient=HORIZONTAL, maximum=100, value=0)
        self.prog.pack()
        self.state = Label(self, text=lang.text40, font=(None, 12))
        self.state.pack(padx=10, pady=10)
        self.installb = ttk.Button(self, text=lang.text41, style="Accent.TButton", command=lambda: cz(self.install))
        self.installb.pack(padx=10, pady=10, expand=True, fill=X)
        self.load()
        jzxs(self)
        self.wait_window()
        cz(list_pls_plugin)

    def install(self):
        if self.installb.cget('text') == lang.text34:
            self.destroy()
            return 1
        self.installb.config(state=DISABLED)
        try:
            supports = self.mconf.get('module', 'supports').split()
            if sys.platform not in supports:
                self.state['text'] = lang.warn15.format(sys.platform)
                return 0
        except (Exception, BaseException):
            ...
        for dep in self.mconf.get('module', 'depend').split():
            if not os.path.isdir(os.path.join(cwd_path, "bin", "module", dep)):
                self.state['text'] = lang.text36 % (self.mconf.get('module', 'name'), dep, dep)
                self.installb['text'] = lang.text37
                self.installb.config(state='normal')
                return 0
        if os.path.exists(os.path.join(cwd_path, "bin", "module", self.mconf.get('module', 'identifier'))):
            rmtree(os.path.join(cwd_path, "bin", "module", self.mconf.get('module', 'identifier')))
        install_dir = self.mconf.get('module', 'identifier')
        with zipfile.ZipFile(self.mpk, 'r') as myfile:
            with myfile.open(self.mconf.get('module', 'resource'), 'r') as inner_file:
                fz = zipfile.ZipFile(inner_file, 'r')
                uncompress_size = sum((file.file_size for file in fz.infolist()))
                extracted_size = 0
                for file in fz.namelist():
                    try:
                        file = str(file).encode('cp437').decode('gbk')
                    except (Exception, BaseException):
                        file = str(file).encode('utf-8').decode('utf-8')
                    info = fz.getinfo(file)
                    extracted_size += info.file_size
                    self.state['text'] = lang.text38.format(file)
                    fz.extract(file, str(os.path.join(cwd_path, "bin", "module", install_dir)))
                    self.prog['value'] = extracted_size * 100 / uncompress_size
        try:
            depends = self.mconf.get('module', 'depend')
        except (Exception, BaseException):
            depends = ''
        minfo = {}
        for i in self.mconf.items('module'):
            minfo[i[0]] = i[1]
        minfo['depend'] = depends
        with open(os.path.join(cwd_path, "bin", "module", self.mconf.get('module', 'identifier'), "info.json"),
                  'w', encoding='utf-8') as f:
            json.dump(minfo, f, indent=2, ensure_ascii=False)
        if self.icon:
            with open(os.path.join(cwd_path, "bin", "module", self.mconf.get('module', 'identifier'), "icon"),
                      'wb') as f:
                f.write(self.icon)

        self.state['text'] = lang.text39
        self.installb['text'] = lang.text34
        self.installb.config(state='normal')

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
                    except Exception as e:
                        print(e)
                        self.pyt = PhotoImage(data=images.none_byte)
            except (Exception, BaseException):
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


class Debugger(Toplevel):
    def __init__(self):
        super().__init__()
        self.title("MIO-KITCHEN Debugger")
        self.gui()
        jzxs(self)

    def gui(self):
        ttk.Button(self, text='Globals', command=self.loaded_module).grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(self, text='Settings', command=self.settings).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(self, text='Info', command=self.show_info).grid(row=2, column=2, padx=5, pady=5)
        ttk.Button(self, text='Crash it!', command=self.crash).grid(row=2, column=3, padx=5, pady=5)
        ttk.Button(self, text='Hacker panel',
                   command=lambda: openurl('https://vdse.bdstatic.com/192d9a98d782d9c74c96f09db9378d93.mp4')).grid(
            row=2, column=4, padx=5, pady=5)
        texts = """
                解锁BL是用户的权力！反对禁止限制解锁BL!
                Unlocking BL is user's right! 
                We oppose the ban on BL unlocking!
                我们的设备属于我们，我们才是主人！
                Our device is ours! We Are Host!
                反对肆意违反开源协议！
                We also strongly oppose the companies 
                those are violating open source licenses!
                """
        Label(self, text=texts, font=(None, 12)).grid(row=3, column=0, padx=5, pady=5)

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
        jzxs(ck)

    @staticmethod
    def settings():
        def save():
            if f.get():
                settings.set_value(h.get(), f.get())
            else:
                read_value()

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
        jzxs(ck)
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
                            pass
                    elif f.get().split()[0] == 'global':
                        try:
                            globals()[h.get()] = globals()[f.get().split()[1]]
                            read_value()
                        except (Exception, BaseException):
                            pass
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
        jzxs(ck)
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
        ttk.Button(ff, text=lang.text23, command=lambda: cz(self.get_db)).pack(padx=10, pady=10, side=RIGHT)
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
        cz(self.get_db)
        self.label_frame.update_idletasks()
        self.canvas.bind_all("<MouseWheel>",
                             lambda event: self.canvas.yview_scroll(-1 * (int(event.delta / 120)), "units"))
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)
        jzxs(self)

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
            if self.search.get() not in i.get('name'):
                self.app_infos.get(i.get('id')).pack_forget()
            else:
                self.app_infos.get(i.get('id')).pack(padx=5, pady=5, anchor='nw')
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
                            command=lambda a=args: cz(self.download, *a))
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
                pass

    def modify_repo(self):
        (input_var := StringVar()).set(settings.plugin_repo)
        a = Toplevel(width=200)
        a.title(lang.t58)
        ttk.Entry(a, textvariable=input_var, width=60).pack(pady=5, padx=5, fill=BOTH)
        ttk.Button(a, text=lang.ok,
                   command=lambda: settings.set_value('plugin_repo', input_var.get()) == a.destroy()).pack(pady=5,
                                                                                                           padx=5,
                                                                                                           fill=BOTH)
        jzxs(a)
        a.wait_window()
        if settings.plugin_repo != self.repo:
            self.init_repo()
            cz(self.get_db)

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
                for percentage, _, _, _, _ in download_api(self.repo + i,
                                                           os.path.join(cwd_path, "bin",
                                                                        "temp"),
                                                           size_=size):
                    if control and states.mpk_store:
                        control.config(text=f"{percentage} %")
                    else:
                        return False

                cz(ModuleManager.install, os.path.join(cwd_path, "bin", "temp", i), join=True)
                try:
                    os.remove(os.path.join(cwd_path, "bin", "temp", i))
                except (Exception, BaseException) as e:
                    print(e)
        except (ConnectTimeout, HTTPError, BaseException, Exception, TclError) as e:
            print(e)
            return
        control.config(state='normal', text=lang.text21)
        if ModuleManager.get_installed(id_):
            control.config(style="")

    def get_db(self):
        self.clear()
        try:
            url = requests.get(self.repo + 'plugin.json')
            self.data = json.loads(url.text)
        except (Exception, BaseException) as e:
            print(e)
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
class Dbkxyt:
    def __init__(self):
        if not dn.get():
            win.message_pop(lang.warn1)
            return
        if os.path.exists((dir_ := rwork()) + "firmware-update"):
            os.rename(dir_ + "firmware-update", dir_ + "images")
        if not os.path.exists(dir_ + "images"):
            os.makedirs(dir_ + 'images')
        if os.path.exists(os.path.join(rwork(), 'payload.bin')):
            print("Found payload.bin ,Stop!")
            return
        if os.path.exists(dir_ + 'META-INF'):
            rmdir(dir_ + 'META-INF')
        zipfile.ZipFile(cwd_path + os.sep + "bin" + os.sep + "extra_flash.zip").extractall(dir_)
        right_device = input_(lang.t26, 'olive')
        with open(dir_ + "bin" + os.sep + "right_device", 'w', encoding='gbk') as rd:
            rd.write(right_device + "\n")
        with open(
                dir_ + 'META-INF' + os.sep + "com" + os.sep + "google" + os.sep + "android" + os.sep + "update-binary",
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
                call(['zstd', '-5', '--rm', path,'-o', f'{path}.zst'])
            except Exception as e:
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
        (lf1 := ttk.LabelFrame(self, text=lang.text54)).pack(fill=BOTH)
        (lf1_r := ttk.LabelFrame(self, text=lang.attribute)).pack(fill=BOTH)
        (lf2 := ttk.LabelFrame(self, text=lang.settings)).pack(fill=BOTH)
        (lf3 := ttk.LabelFrame(self, text=lang.text55)).pack(fill=BOTH, expand=True)
        self.supersz.set(1)
        # 自动设置
        ttk.Radiobutton(lf1, text="A-only", variable=self.supersz, value=1).pack(side='left', padx=10, pady=10)
        ttk.Radiobutton(lf1, text="Virtual-ab", variable=self.supersz, value=2).pack(side='left', padx=10, pady=10)
        ttk.Radiobutton(lf1, text="A/B", variable=self.supersz, value=3).pack(side='left', padx=10, pady=10)
        ttk.Radiobutton(lf1_r, text="Readonly", variable=self.attrib, value='readonly').pack(side='left', padx=10,
                                                                                             pady=10)
        ttk.Radiobutton(lf1_r, text="None", variable=self.attrib, value='none').pack(side='left', padx=10, pady=10)
        Label(lf2, text=lang.text56).pack(side='left', padx=10, pady=10)
        (sdbfzs := ttk.Combobox(lf2, textvariable=self.sdbfz, values=("qti_dynamic_partitions", "main"))).pack(
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
        self.work = rwork()

        self.tl.pack(padx=10, pady=10, expand=True, fill=BOTH)

        ttk.Checkbutton(self, text=lang.text58, variable=self.ssparse, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=10, pady=10, fill=BOTH)
        t_frame = Frame(self)
        ttk.Checkbutton(t_frame, text=lang.t11, variable=self.scywj, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(side=LEFT,
                                                          padx=10, pady=10, fill=BOTH)
        ttk.Button(t_frame, text=lang.text23, command=self.refresh).pack(side=RIGHT, padx=10, pady=10)
        self.g_b = ttk.Button(t_frame, text=lang.t27, command=lambda: cz(self.generate))
        self.g_b.pack(side=LEFT, padx=10, pady=10, fill=BOTH)
        t_frame.pack(fill=X)
        cz(self.refresh)
        jzxs(self)

        ttk.Button(self, text=lang.cancel, command=self.destroy).pack(side='left', padx=10, pady=10,
                                                                      fill=X,
                                                                      expand=True)
        ttk.Button(self, text=lang.pack, command=lambda: cz(self.start_), style="Accent.TButton").pack(side='left',
                                                                                                       padx=5,
                                                                                                       pady=5, fill=X,
                                                                                                       expand=True)
        self.read_list()

    def start_(self):
        try:
            self.supers.get()
        except (Exception, BaseException):
            self.supers.set(0)
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
                t = 1024 * 1024 * 1024 * i - size
                if t < 0:
                    continue
                if t < diff_size:
                    diff_size = t
                else:
                    size = i * 1024 * 1024 * 1024
                    break
            self.supers.set(int(size))
            return False
        else:
            return True

    def generate(self):
        self.g_b.config(text=lang.t28, state='disabled')
        utils.generate_dynamic_list(dbfz=self.sdbfz.get(), size=self.supers.get(), set_=self.supersz.get(),
                                    lb=self.tl.selected.copy(), work=rwork())
        self.g_b.config(text=lang.text34)
        time.sleep(1)
        self.g_b.config(text=lang.t27, state='normal')

    def refresh(self):
        self.tl.clear()
        for file_name in os.listdir(self.work):
            if file_name.endswith(".img"):
                if (file_type := gettype(self.work + file_name)) in ["ext", "erofs", 'f2fs', 'sparse']:
                    self.tl.insert(f"{file_name[:-4]} [{file_type}]", file_name[:-4])

    def read_list(self):
        if os.path.exists(self.work + "dynamic_partitions_op_list"):
            try:
                data = utils.dynamic_list_reader(self.work + "dynamic_partitions_op_list")
            except (Exception, BaseException):
                return
            if len(data) > 1:
                fir, sec = data
                if fir[:-2] == sec[:-2]:
                    self.sdbfz.set(fir[:-2])
                    self.supersz.set(2)
                    self.supers.set(int(data[fir]['size']))
            else:
                dbfz, = data
                self.sdbfz.set(dbfz)
                self.supers.set(int(data[dbfz]['size']))
                self.supersz.set(1)


@animation
def packsuper(sparse, dbfz, size, set_, lb: list, del_=0, return_cmd=0, attrib='readonly'):
    if not dn.get():
        warn_win(text=lang.warn1)
        return False
    work = rwork()
    lb_c = []
    for part in lb:
        if part.endswith('_b') or part.endswith('_a'):
            part = part.replace('_a', '').replace('_b', '')
        lb_c.append(part)
    lb = lb_c
    for part in lb:
        if not os.path.exists(work + part + '.img') and os.path.exists(work + part + '_a.img'):
            try:
                os.rename(work + part + '_a.img', work + part + '.img')
            except:
                pass
    command = "lpmake --metadata-size 65536 -super-name super -metadata-slots "
    if set_.get() == 1:
        command += f"2 -device super:{size.get()} --group {dbfz.get()}:{size.get()} "
        for part in lb:
            command += f"--partition {part}:{attrib}:{os.path.getsize(work + part + '.img')}:{dbfz.get()} --image {part}={work + part}.img "
    else:
        command += f"3 -device super:{size.get()} --group {dbfz.get()}_a:{size.get()} "
        for part in lb:
            command += f"--partition {part}_a:{attrib}:{os.path.getsize(work + part + '.img')}:{dbfz.get()}_a --image {part}_a={work + part}.img "
        command += f"--group {dbfz.get()}_b:{size.get()} "
        for part in lb:
            command += f"--partition {part}_b:{attrib}:0:{dbfz.get()}_b "
        if set_.get() == 2:
            command += "--virtual-ab "
    if sparse.get() == 1:
        command += "--sparse "
    command += f" --out {work + 'super.img'}"
    if return_cmd == 1:
        return command
    if call(command) == 0:
        if os.access(work + "super.img", os.F_OK):
            print(lang.text59 % (work + "super.img"))
            if del_ == 1:
                for img in lb:
                    if os.path.exists(work + img + ".img"):
                        try:
                            os.remove(work + img + ".img")
                        except Exception as e:
                            print(e)
        else:
            win.message_pop(lang.warn10)
    else:
        win.message_pop(lang.warn10)


class StdoutRedirector:
    def __init__(self, text_widget, error_=False):
        self.text_space = text_widget
        self.error = error_
        self.error_info = ''

    def write(self, string):
        if self.error:
            self.error_info += string
            return
        self.text_space.insert(tk.END, string)
        self.text_space.see('end')

    def flush(self):
        if self.error_info:
            error(1, self.error_info)


def call(exe, extra=True, out=0):
    if isinstance(exe, list):
        cmd = exe
        if extra:
            cmd[0] = f"{tool_bin}{exe[0]}"
        cmd = [i for i in cmd if i]
    else:
        cmd = f'{tool_bin}{exe}' if extra else exe
    if os.name != 'posix':
        conf = subprocess.CREATE_NO_WINDOW
    else:
        conf = 0
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
        states.open_pids.remove(pid)
    except subprocess.CalledProcessError as e:
        for i in iter(e.stdout.readline, b""):
            if out == 0:
                try:
                    out_put = i.decode("utf-8").strip()
                except (Exception, BaseException):
                    out_put = i.decode("gbk").strip()
                print(out_put)
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
            if file_size != 0:
                if int_:
                    percentage = int((bytes_downloaded / file_size) * 100)
                else:
                    percentage = (bytes_downloaded / file_size) * 100
            else:
                percentage = 'None'
            yield percentage, speed, bytes_downloaded, file_size, elapsed


def download_file():
    var1 = IntVar(value=0)
    down = win.get_frame(lang.text61 + os.path.basename(url := input_(title=lang.text60)))
    win.message_pop(lang.text62, "green")
    progressbar = ttk.Progressbar(down, length=200, mode="determinate")
    progressbar.pack(padx=10, pady=10)
    ttk.Label(down, textvariable=(jd := StringVar())).pack(padx=10, pady=10)
    c1 = ttk.Checkbutton(down, text=lang.text63, variable=var1, onvalue=1, offvalue=0)
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
        if var1.get() == 1:
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
    if not (boot := findfile(f"{bn}.img", (work := rwork()))):
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
    if call(['magiskboot', 'unpack', '-h', f'{boot}']) != 0:
        print(f"Unpack {boot} Fail...")
        os.chdir(cwd_path)
        rmtree(work + bn)
        return
    if os.access(work + bn + os.sep + "ramdisk.cpio", os.F_OK):
        comp = gettype(work + bn + os.sep + "ramdisk.cpio")
        print(f"Ramdisk is {comp}")
        with open(work + bn + os.sep + "comp", "w", encoding='utf-8') as f:
            f.write(comp)
        if comp != "unknown":
            os.rename(work + bn + os.sep + "ramdisk.cpio",
                      work + bn + os.sep + "ramdisk.cpio.comp")
            if call(["magiskboot", "decompress", work + bn + os.sep + 'ramdisk.cpio.comp', work + bn + os.sep + 'ramdisk.cpio']) != 0:
                print("Failed to decompress Ramdisk...")
                return
        if not os.path.exists(work + bn + os.sep + "ramdisk"):
            os.mkdir(work + bn + os.sep + "ramdisk")
        os.chdir(work + bn + os.sep)
        print("Unpacking Ramdisk...")
        call(['cpio', '-i', '-d', '-F', 'ramdisk.cpio', '-D', 'ramdisk'])
        os.chdir(cwd_path)
    else:
        print("Unpack Done!")
    os.chdir(cwd_path)


@animation
def dboot(nm: str = 'boot'):
    work = rwork()
    flag = ''
    boot = findfile(f"{nm}.img", work)
    if not os.path.exists(work + nm):
        print(f"Cannot Find {nm}...")
        return
    cpio = findfile("cpio.exe" if os.name != 'posix' else 'cpio',
                    tool_bin).replace(
        '\\', "/")

    if os.path.isdir(work + nm + os.sep + "ramdisk"):
        os.chdir(work + nm + os.sep + "ramdisk")
        call(exe=["busybox", "ash", "-c", f"find | sed 1d | {cpio} -H newc -R 0:0 -o -F ../ramdisk-new.cpio"])
        os.chdir(work + nm + os.sep)
        with open(work + nm + os.sep + "comp", "r", encoding='utf-8') as compf:
            comp = compf.read()
        print(f"Compressing:{comp}")
        if comp != "unknown":
            if call(['magiskboot', f'compress={comp}', 'ramdisk-new.cpio']) != 0:
                print("Failed to pack Ramdisk...")
                os.remove("ramdisk-new.cpio")
            else:
                print("Successfully packed Ramdisk..")
                try:
                    os.remove("ramdisk.cpio")
                except (Exception, BaseException):
                    ...
                os.rename(f"ramdisk-new.cpio.{comp.split('_')[0]}", "ramdisk.cpio")
        else:
            print("Successfully packed Ramdisk..")
            os.remove("ramdisk.cpio")
            os.rename("ramdisk-new.cpio", "ramdisk.cpio")
        if comp == "unknown":
            flag = "-n"
    os.chdir(work + nm + os.sep)
    if call(['magiskboot', 'repack', flag, boot]) != 0:
        print("Failed to Pack boot...")
    else:
        os.remove(work + f"{nm}.img")
        os.rename(work + nm + os.sep + "new-boot.img", work + os.sep + f"{nm}.img")
        os.chdir(cwd_path)
        try:
            rmdir(work + nm)
        except (Exception, BaseException):
            print(lang.warn11.format(nm))
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
        self.ext4_method.trace('w', lambda *x: self.show_modify_size())
        cz(self.show_modify_size)
        #
        Label(lf3, text=lang.text49).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf3, state="readonly", textvariable=self.dbgs, values=("raw", "sparse", "br", "dat")).pack(padx=5,
                                                                                                                pady=5,
                                                                                                                side='left')
        Label(lf2, text=lang.text50).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf2, state="readonly", textvariable=self.edbgs,
                     values=("lz4", "lz4hc", "lzma", "deflate")).pack(side='left', padx=5, pady=5)
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
        ttk.Button(self, text=lang.pack, command=lambda: cz(self.start_), style="Accent.TButton").pack(side='left',
                                                                                                       padx=2, pady=2,
                                                                                                       fill=X,
                                                                                                       expand=True)
        jzxs(self)

    def start_(self):
        try:
            self.destroy()
        except AttributeError:
            pass
        self.packrom()

    def show_modify_size(self):
        if self.ext4_method.get() == lang.t32:
            self.xgdx.pack_forget()
        else:
            self.xgdx.pack(
                side='left', padx=5, pady=5)

    def verify(self):
        parts_dict = JsonEdit(rwork() + "config" + os.sep + "parts_info").read()
        for i in self.lg:
            if i not in parts_dict.keys():
                parts_dict[i] = 'unknown'
            if parts_dict[i] in ['ext', 'erofs', 'f2fs']:
                return True
        return False

    def modify_custom_size(self):
        work = rwork()

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
                    elif os.path.exists(work + "config" + os.sep + dname + "_size.txt"):
                        with open(work + "config" + os.sep + dname + "_size.txt", encoding='utf-8') as size_f:
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
        jzxs(ck)
        ck.wait_window()

    @animation
    def packrom(self) -> bool:
        if not dn.get():
            win.message_pop(lang.warn1)
            return False
        elif not os.path.exists(settings.path + os.sep + dn.get()):
            win.message_pop(lang.warn1, "red")
            return False
        parts_dict = JsonEdit((work := rwork()) + "config" + os.sep + "parts_info").read()
        for i in self.lg:
            dname = os.path.basename(i)
            if dname not in parts_dict.keys():
                parts_dict[dname] = 'unknown'
            if self.spatchvb.get() == 1:
                for j in "vbmeta.img", "vbmeta_system.img", "vbmeta_vendor.img":
                    file = findfile(j, work)
                    if file:
                        if gettype(file) == 'vbmeta':
                            print(lang.text71 % file)
                            utils.Vbpatch(file).disavb()
            if os.access(os.path.join(work + "config", f"{dname}_fs_config"), os.F_OK):
                if os.name == 'nt':
                    try:
                        if folder := findfolder(work, "com.google.android.apps.nbu."):
                            call(['mv', folder, folder.replace('com.google.android.apps.nbu.', 'com.google.android.apps.nbu')])
                    except Exception as e:
                        print(e)
                fspatch.main(work + dname, os.path.join(work + "config", dname + "_fs_config"))
                utils.qc(work + "config" + os.sep + dname + "_fs_config")
                if settings.contextpatch == "1":
                    contextpatch.main(work + dname, work + "config" + os.sep + dname + "_file_contexts")
                utils.qc(work + "config" + os.sep + dname + "_file_contexts")
                if self.fs_conver.get():
                    if parts_dict[dname] == self.origin_fs.get():
                        parts_dict[dname] = self.modify_fs.get()
                if parts_dict[dname] == 'erofs':
                    if mkerofs(dname, str(self.edbgs.get()), work, level=int(self.scale_erofs.get()),
                               old_kernel=self.erofs_old_kernel.get(), UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.delywj.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.dbgs.get() in ["dat", "br", "sparse"]:
                            img2simg(work + dname + ".img")
                            if self.dbgs.get() == 'dat':
                                datbr(work, dname, "dat", int(parts_dict.get('dat_ver', 4)))
                            elif self.dbgs.get() == 'br':
                                datbr(work, dname, self.scale.get(), int(parts_dict.get('dat_ver', 4)))
                            else:
                                print(lang.text3.format(dname))
                elif parts_dict[dname] == 'f2fs':
                    if make_f2fs(dname, work, UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.delywj.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.dbgs.get() in ["dat", "br", "sparse"]:
                            img2simg(work + dname + ".img")
                            if self.dbgs.get() == 'dat':
                                datbr(work, dname, "dat", int(parts_dict.get('dat_ver', 4)))
                            elif self.dbgs.get() == 'br':
                                datbr(work, dname, self.scale.get(), int(parts_dict.get('dat_ver', 4)))
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
                        elif os.path.exists(work + "config" + os.sep + dname + "_size.txt"):
                            with open(work + "config" + os.sep + dname + "_size.txt", encoding='utf-8') as f:
                                try:
                                    ext4_size_value = int(f.read().strip())
                                except ValueError:
                                    ext4_size_value = 0

                    if make_ext4fs(dname, work, "-s" if self.dbgs.get() in ["dat", "br", "sparse"] else '',
                                   ext4_size_value, UTC=self.UTC.get()) if self.dbfs.get() == "make_ext4fs" else mke2fs(
                        dname,
                        work,
                        "y" if self.dbgs.get() in [
                            "dat",
                            "br",
                            "sparse"] else 'n',
                        ext4_size_value,
                        UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                        continue
                    if self.delywj.get() == 1:
                        rdi(work, dname)
                    if self.dbgs.get() == "dat":
                        datbr(work, dname, "dat", int(parts_dict.get('dat_ver', '4')))
                    elif self.dbgs.get() == "br":
                        datbr(work, dname, self.scale.get(), int(parts_dict.get('dat_ver', '4')))
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
        if settings.ai_engine == '1':
            AI_engine.suggest(win.show.get(1.0, tk.END), language='cn' if "Chinese" in settings.language else 'en',
                              ok=lang.ok)


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
        except Exception as e:
            print(lang.text73 % (part_name, e))
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
        if not os.path.exists(path + os.sep + "config"):
            os.makedirs(path + os.sep + "config")
        extra.script2fs_context(findfile("updater-script", path + os.sep + "META-INF"), path + os.sep + "config", path)
        json_ = JsonEdit(os.path.join(path, "config", "parts_info"))
        parts = json_.read()
        for v in os.listdir(path):
            if os.path.exists(path + os.sep + "config" + os.sep + v + "_fs_config"):
                if v not in parts.keys():
                    parts[v] = 'ext'
        json_.write(parts)


@animation
def unpackrom(ifile) -> None:
    print(lang.text77 + (zip_src := ifile), f'Type:[{gettype(ifile)}]')
    if (ftype := gettype(ifile)) == "ozip":
        print(lang.text78 + ifile)
        ozipdecrypt.main(ifile)
        try:
            os.remove(ifile)
        except (PermissionError, IOError) as e:
            win.message_pop(lang.warn11.format(e))
        zip_src = os.path.dirname(ifile) + os.sep + os.path.basename(ifile)[:-4] + "zip"
    elif ftype == 'kdz':
        project_dir = settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0]
        project_dir = os.path.normpath(project_dir)
        if not os.path.exists(project_dir):
            re_folder(project_dir)
        KDZFileTools(ifile, project_dir, extract_all=True)
        for i in os.listdir(project_dir):
            if not os.path.isfile(project_dir + os.sep + i):
                continue
            if i.endswith('.dz') and gettype(project_dir + os.sep + i) == 'dz':
                DZFileTools(project_dir + os.sep + i, project_dir, extract_all=True)
        return
    elif os.path.splitext(ifile)[1] == '.ofp':
        if ask_win(lang.t12) == 1:
            ofp_mtk_decrypt.main(ifile, settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        else:
            ofp_qc_decrypt.main(ifile, settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
            script2fs(settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        unpackg.refs()
        return
    elif os.path.splitext(ifile)[1] == '.ops':
        args = {'decrypt': True,
                "<filename>": ifile,
                'outdir': os.path.join(settings.path, os.path.basename(ifile).split('.')[0])}
        opscrypto.main(args)
        unpackg.refs()
        return
    if gettype(zip_src) == 'zip':
        fz = zipfile.ZipFile(zip_src, 'r')
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
                fz.extract(fi, settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
                if fi != file_:
                    os.rename(os.path.join(settings.path, os.path.splitext(os.path.basename(zip_src))[0], fi),
                              os.path.join(settings.path, os.path.splitext(os.path.basename(zip_src))[0], file_))
            except Exception as e:
                print(lang.text80 % (file_, e))
                win.message_pop(lang.warn4.format(file_))
        print(lang.text81)
        if os.path.isdir(os.path.join(settings.path, os.path.splitext(os.path.basename(zip_src))[0])):
            project_menu.set_project(os.path.splitext(os.path.basename(zip_src))[0])
        script2fs(settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        unpackg.refs()
        fz.close()
        if settings.auto_unpack == '1':
            chose = [i.split('.')[0] for i in os.listdir(rwork())]

            unpack(chose)
        return
    elif ftype != 'unknown':
        folder = os.path.join(settings.path, os.path.splitext(os.path.basename(ifile))[0] + v_code()) if os.path.exists(
            os.path.join(
                settings.path, os.path.splitext(os.path.basename(ifile))[0])) else os.path.join(settings.path,
                                                                                                os.path.splitext(
                                                                                                    os.path.basename(
                                                                                                        ifile))[0])
        try:
            os.mkdir(folder)
        except Exception as e:
            win.message_pop(str(e))
        copy(ifile, str(folder))
        project_menu.listdir()
        dn.set(os.path.basename(folder))
        if settings.auto_unpack == '1':
            chose = [i.split('.')[0] for i in os.listdir(rwork())]

            unpack(chose)
    else:
        print(lang.text82 % ftype)
    unpackg.refs()


def rwork() -> str:
    return os.path.join(settings.path, dn.get()) + os.sep


@animation
def unpack(chose, form: str = '') -> bool:
    if os.name == 'nt':
        if windll.shell32.IsUserAnAdmin():
            try:
                ensure_dir_case_sensitive(rwork())
            except (Exception, BaseException):
                ...
    if not dn.get():
        win.message_pop(lang.warn1)
        return False
    elif not os.path.exists(settings.path + os.sep + dn.get()):
        win.message_pop(lang.warn1, "red")
        return False
    json_ = JsonEdit((work := rwork()) + "config" + os.sep + "parts_info")
    parts = json_.read()
    if not chose:
        return False
    if form == 'payload':
        print(lang.text79 + "payload")
        Dumper(work + "payload.bin", work, diff=False, old='old', images=chose).run()
        if settings.rm_pay == '1':
            try:
                os.remove(work + "payload.bin")
            except Exception as e:
                print(lang.text72 + f" payload.bin:{e}")
                os.remove(work + "payload.bin")
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
                            ...
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
                    pass
                else:
                    logo_dump(i)
            if gettype(work + i + ".img") == 'vbmeta':
                print(f"{lang.text85}AVB:{i}")
                utils.Vbpatch(work + i + ".img").disavb()
            file_type = gettype(work + i + ".img")
            print(lang.text79 + i + f".img ({file_type})")
            if file_type == "sparse":
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
                imgextractor.Extractor().main(work + i + ".img", work + i, work)
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except Exception as e:
                        win.message_pop(lang.warn11.format(i + ".img:" + e))
            if file_type == "erofs":
                if call(exe=['extract.erofs', '-i', os.path.join(settings.path, dn.get(), i + '.img'), '-o', work, '-x'],
                        out=1) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'f2fs':
                if call(exe=['extract.f2fs', '-o', work, os.path.join(settings.path, dn.get(), i + '.img')],
                        out=1) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
    if not os.path.exists(work + "config"):
        os.makedirs(work + "config")
    json_.write(parts)
    parts.clear()
    print(lang.text8)
    return True


def ask_win(text='', ok=None, cancel=None) -> int:
    if not ok:
        ok = lang.ok
    if not cancel:
        cancel = lang.cancel
    value = IntVar()
    ask = ttk.LabelFrame(win)
    ask.place(relx=0.5, rely=0.5, anchor="center")
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20)).pack(side=TOP)
    frame_button = ttk.Frame(frame_inner)
    frame_button.pack(side=TOP)

    ttk.Button(frame_button, text=cancel, command=lambda: close_ask(0)).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                             expand=True)
    ttk.Button(frame_button, text=ok, command=lambda: close_ask(1), style="Accent.TButton").pack(side='left', padx=5,
                                                                                                 pady=5,
                                                                                                 fill=BOTH,
                                                                                                 expand=True)

    def close_ask(value_=1):
        value.set(value_)
        ask.destroy()

    ask.wait_window()
    return value.get()


def ask_win2(text='', ok=lang.ok, cancel=lang.cancel) -> int:
    value = IntVar()
    ask = Toplevel()
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20)).pack(side=TOP)
    frame_button = ttk.Frame(frame_inner)

    ttk.Button(frame_button, text=cancel, command=lambda: close_ask(0)).pack(padx=5, pady=5, fill=X, side='left', expand=True)
    ttk.Button(frame_button, text=ok, command=lambda: close_ask(1), style="Accent.TButton").pack(padx=5,
                                                                                                 pady=5,
                                                                                                 fill=X, side='left',
                                                                                                 expand=True)
    frame_button.pack(fill=X, expand=True, padx=10, pady=5)

    def close_ask(value_=1):
        value.set(value_)
        ask.destroy()

    jzxs(ask)

    ask.wait_window()
    return value.get()


class Dirsize:
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
                pass
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
        except Exception as e:
            print(e)
            os.remove(work + name + ".img")
    if brl == "dat":
        print(lang.text87 % name)
    else:
        print(lang.text88 % (name, 'br'))
        call(['brotli', '-q', str(brl), '-j', '-w', '24', f"{work + name}.new.dat", '-o', f"{work + name}.new.dat.br"])
        if os.access(work + name + ".new.dat", os.F_OK):
            try:
                os.remove(work + name + ".new.dat")
            except Exception as e:
                print(e)
        print(lang.text89 % (name, 'br'))


def mkerofs(name, format_, work, level, old_kernel=0, UTC=None):
    if not UTC:
        UTC = int(time.time())
    print(lang.text90 % (name, format_ + f',{level}', "1.x"))
    extra_ = f'{format_},{level}' if format_ != 'lz4' else format_
    other_ = '-E legacy-compress' if old_kernel else []
    cmd = ['mkfs.erofs', *other_.split(), f'-z{extra_}', '-T', f'{UTC}', f'--mount-point=/{name}',
     f'--product-out={work}',
     f'--fs-config-file={work}config{os.sep}{name}_fs_config',
     f'--file-contexts={work}config{os.sep}{name}_file_contexts',
     f'{work + name}.img', work + name + os.sep]
    return call(cmd, out=1)


@animation
def make_ext4fs(name, work, sparse, size=0, UTC=None):
    print(lang.text91 % name)
    if not UTC:
        UTC = int(time.time())
    if not size:
        size = Dirsize(work + name, 1, 3, work + "dynamic_partitions_op_list").rsize_v
    print(f"{name}:[{size}]")
    return call(['make_ext4fs', '-J', '-T', f'{UTC}', f'{sparse}', '-S', f'{work}config/{name}_file_contexts', '-l', f'{size}', '-C', f'{work}config{os.sep}{name}_fs_config', '-L', f'{name}', '-a', name, f"{work + name}.img", work + name])


@animation
def make_f2fs(name, work, UTC=None):
    print(lang.text91 % name)
    size = Dirsize(work + name, 1, 1).rsize_v
    print(f"{name}:[{size}]")
    size_f2fs = (54 * 1024 * 1024) + size
    size_f2fs = int(size_f2fs * 1.15) + 1
    if not UTC:
        UTC = int(time.time())
    with open(f"{work + name}.img", 'wb') as f:
        f.truncate(size_f2fs)
    if call(['mkfs.f2fs', f"{work + name}.img", '-O', 'extra_attr', '-O', 'inode_checksum', '-O', 'sb_checksum', '-O', 'compression', '-f']) != 0:
        return 1
    # todo:Its A Stupid method, we need a new!
    with open(f'{work}config{os.sep}{name}_file_contexts', 'a+', encoding='utf-8') as f:
        if not [i for i in f.readlines() if f'/{name}/{name} u' in i]:
            f.write(f'/{name}/{name} u:object_r:system_file:s0\n')
    return call(
        ['sload.f2fs', '-f', work+name, '-C', f'{work}config{os.sep}{name}_fs_config', '-T', f'{UTC}', '-s', f'{work}config{os.sep}{name}_file_contexts', '-t', f'/{name}', '-c', f'{work+name}.img'])


def mke2fs(name, work, sparse, size=0, UTC=None):
    print(lang.text91 % name)
    size = Dirsize(work + name, 4096, 3, work + "dynamic_partitions_op_list").rsize_v if not size else size / 4096
    print(f"{name}:[{size}]")
    if not UTC:
        UTC = int(time.time())
    if call(
            ['mke2fs', '-O', '^has_journal,^metadata_csum,extent,huge_file,^flex_bg,^64bit,uninit_bg,dir_nlink,extra_isize', '-L', name, '-I', '256', '-M', f'/{name}', '-m', '0', '-t', 'ext4', '-b', '4096', f'{work+name}_new.img', f'{int(size)}']) != 0:
        rmdir(f'{work + name}_new.img')
        print(lang.text75 % name)
        return 1
    ret = call(
        ['e2fsdroid', '-e', '-T', f'{UTC}', '-S', f'{work}config{os.sep}{name}_file_contexts', '-C', f'{work}config{os.sep}{name}_fs_config', '-a', f'/{name}', '-f', f'{work+name}', f'{work+name}_new.img'])
    if ret != 0:
        rmdir(f'{work + name}_new.img')
        print(lang.text75 % name)
        return 1
    if sparse == "y":
        call(['img2simg', f'{work+name}_new.img', f'{work+name}.img'])
        try:
            os.remove(work + name + "_new.img")
        except (Exception, BaseException):
            ...
    else:
        if os.path.isfile(work + name + ".img"):
            try:
                os.remove(work + name + ".img")
            except (Exception, BaseException):
                ...
        os.rename(work + name + "_new.img", work + name + ".img")
    return 0


@animation
def rmdir(path):
    if not path:
        win.message_pop(lang.warn1)
    else:
        print(lang.text97 + os.path.basename(path))
        try:
            try:
                rmtree(path)
            except (Exception, BaseException):
                call(['busybox', 'rm', '-rf', path])
        except (Exception, BaseException):
            print(lang.warn11.format(path))
        win.message_pop(lang.warn11.format(path)) if os.path.exists(path) else print(lang.text98 + path)


def get_all_file_paths(directory):
    for root, _, files in os.walk(directory):
        for filename in files:
            yield os.path.join(root, filename)


@animation
def pack_zip():
    if ask_win(lang.t53) != 1:
        return
    if not dn.get():
        win.message_pop(lang.warn1)
    else:
        print(lang.text91 % dn.get())
        if ask_win(lang.t25) == 1:
            Dbkxyt()
        with zipfile.ZipFile(relpath := settings.path + os.sep + dn.get() + ".zip", 'w',
                             compression=zipfile.ZIP_DEFLATED) as zip_:
            for file in get_all_file_paths(settings.path + os.sep + dn.get()):
                file = str(file)
                arch_name = file.replace(settings.path + os.sep + dn.get(), '')
                print(f"{lang.text1}:{arch_name}")
                try:
                    zip_.write(file, arcname=arch_name)
                except Exception as e:
                    print(lang.text2.format(file, e))
        if os.path.exists(relpath):
            print(lang.text3.format(relpath))


def dndfile(files):
    for fi in files:
        try:
            fi = fi.decode('gbk')
        except (Exception, BaseException):
            ...
        if os.path.exists(fi):
            if fi.endswith(".mpk"):
                InstallMpk(fi)
            else:
                cz(unpackrom, fi)
        else:
            print(fi + lang.text84)


class ProjectMenuUtils(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text12)
        self.combobox = None
        self.pack(padx=5, pady=5)

    @staticmethod
    def select_print():
        print(lang.text96 + dn.get())

    def gui(self):
        self.combobox = ttk.Combobox(self, textvariable=dn, state='readonly')
        self.combobox.pack(side="top", padx=10, pady=10, fill=X)
        self.combobox.bind('<<ComboboxSelected>>', lambda *x: self.select_print())
        ttk.Button(self, text=lang.text23, command=self.listdir).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text115, command=self.new).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text116, command=lambda: cz(self.remove)).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text117, command=lambda: cz(self.rename)).pack(side="left", padx=10, pady=10)

    def set_project(self, name):
        if not os.path.isdir(os.path.join(settings.path, name)):
            return
        self.listdir()
        dn.set(name)

    def listdir(self):
        array = []
        for f in os.listdir(settings.path + os.sep + "."):
            if os.path.isdir(settings.path + os.sep + f) and f != 'bin' and not f.startswith('.'):
                array.append(f)
        self.combobox["value"] = array
        if not array:
            dn.set('')
            self.combobox.current()
        else:
            self.combobox.current(0)

    def rename(self) -> bool:
        if not dn.get():
            print(lang.warn1)
            return False
        if os.path.exists(settings.path + os.sep + (inputvar := input_(lang.text102 + dn.get(), dn.get()))):
            print(lang.text103)
            return False
        if inputvar != dn.get():
            os.rename(settings.path + os.sep + dn.get(), settings.path + os.sep + inputvar)
            self.listdir()
        else:
            print(lang.text104)
        return True

    def remove(self):
        win.message_pop(lang.warn1) if not dn.get() else rmdir(settings.path + os.sep + dn.get())
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
        ttk.Button(self, text=lang.text122, command=lambda: cz(pack_zip)).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(self, text=lang.text123, command=lambda: cz(PackSuper)).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self, text=lang.text19, command=lambda: win.notepad.select(win.tab7)).grid(row=0, column=2, padx=5,
                                                                                              pady=5)
        ttk.Button(self, text=lang.t13, command=lambda: cz(FormatConversion)).grid(row=0, column=3, padx=5, pady=5)


class UnpackGui(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.t57)
        self.fm = None
        self.lsg = None
        self.menu = None
        self.ch = BooleanVar()

    def gui(self):
        self.pack(padx=5, pady=5)
        self.ch.set(True)
        self.fm = ttk.Combobox(self, state="readonly",
                               values=('new.dat.br', "new.dat", 'img', 'zst', 'payload', 'super', 'update.app'))
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
        ttk.Button(self, text=lang.run, command=lambda: cz(self.close_)).pack(padx=5, pady=5, side='left')
        self.refs()
        self.ch.trace("w", lambda *x: self.hd())

    def show_menu(self, event):
        if len(self.lsg.selected) == 1 and self.fm.get() == 'img':
            self.menu.post(event.x_root, event.y_root)

    def info(self):
        ck_ = Toplevel()
        jzxs(ck_)
        ck_.title(lang.attribute)
        if not self.lsg.selected:
            ck_.destroy()
            return
        f_path = os.path.join(rwork(), self.lsg.selected[0] + ".img")
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

    def refs(self):
        self.lsg.clear()
        if not os.path.exists(work := rwork()):
            win.message_pop(lang.warn1)
            return False
        if self.fm.get() == 'payload':
            if os.path.exists(work + "payload.bin"):
                with open(work + "payload.bin", 'rb') as pay:
                    for i in utils.payload_reader(pay).partitions:
                        self.lsg.insert(f"{i.get('1')}{hum_convert(int(i.get('7').get('1'))):>10}",
                                        i.get('1'))
        elif self.fm.get() == 'super':
            if os.path.exists(work + "super.img"):
                if gettype(work + "super.img") == 'sparse':
                    cz(utils.simg2img, work + "super.img", join=True)
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
        if not os.path.exists(work := rwork()):
            win.message_pop(lang.warn1)
            return False
        parts_dict = JsonEdit(work + "config" + os.sep + "parts_info").read()
        for folder in os.listdir(work):
            if os.path.isdir(work + folder) and folder in parts_dict.keys():
                self.lsg.insert(folder, folder)

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
        except Exception as e:
            print(e)


class FormatConversion(ttk.LabelFrame):
    def __init__(self):
        super().__init__(text=lang.t13)
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.f = Frame(self)
        self.f.pack(pady=5, padx=5, fill=X)
        self.h = ttk.Combobox(self.f, values=("raw", "sparse", 'dat', 'br'), state='readonly')
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
        cz(self.relist)
        t = Frame(self)
        ttk.Button(t, text=lang.cancel, command=self.destroy).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                   expand=True)
        ttk.Button(t, text=lang.ok, command=lambda: cz(self.conversion), style='Accent.TButton').pack(side='left',
                                                                                                      padx=5, pady=5,
                                                                                                      fill=BOTH,
                                                                                                      expand=True)
        t.pack(side=BOTTOM, fill=BOTH)

    def relist(self):
        work = rwork()
        self.list_b.clear()
        if self.h.get() == "br":
            for i in self.refile(".new.dat.br"):
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
        for i in os.listdir(work := rwork()):
            if i.endswith(f) and os.path.isfile(work + i):
                yield i

    @animation
    def conversion(self):
        work = rwork()
        f_get = self.f.get()
        hget = self.h.get()
        selection = self.list_b.selected.copy()
        self.destroy()
        if f_get == hget:
            ...
        else:
            for i in selection:
                print(f'[{hget}->{f_get}]{i}')
                if f_get == 'sparse':
                    basename = os.path.basename(i).split('.')[0]
                    if hget == 'br':
                        if os.access(work + i, os.F_OK):
                            print(lang.text79 + i)
                            call(['brotli', '-dj', work + i])
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
                                        ...
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
                    if hget in ['dat', 'br']:
                        if os.path.exists(work):
                            if hget == 'br':
                                i = i.replace('.br', '')
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
                                        ...
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

                elif f_get == 'br':
                    if hget == 'raw':
                        img2simg(work + i)
                    if hget in ['raw', 'sparse']:
                        datbr(work, os.path.basename(i).split('.')[0], 0)
                    if hget == 'dat':
                        print(lang.text88 % (os.path.basename(i).split('.')[0], 'br'))
                        call(['brotli', '-q', '0',  '-j', '-w', '24', work + i, '-o', f'{work + i}.br'])
                        if os.access(work + i + '.br', os.F_OK):
                            try:
                                os.remove(work + i)
                            except Exception as e:
                                print(e)
        print(lang.text8)


project_menu: ProjectMenuUtils
unpackg: UnpackGui


def init_verify():
    if not os.path.exists(tool_bin):
        error(1, 'Sorry,Not support your device yet.')
    if not settings.path.isprintable():
        ask_win2(lang.warn16 % lang.special_words)


def init():
    if settings.updating in ['1', '2']:
        Updater()
    if int(settings.oobe) < 5:
        Welcome()
    init_verify()
    try:
        win.winfo_exists()
    except TclError:
        return
    if os.name == 'nt' and settings.treff == '1':
        pywinstyles.apply_style(win, 'acrylic')
    win.gui()
    global unpackg
    unpackg = UnpackGui()
    global project_menu
    project_menu = ProjectMenuUtils()
    project_menu.gui()
    unpackg.gui()
    Frame3().gui()
    project_menu.listdir()
    animation.load_gif(open_img(BytesIO(getattr(images, f"loading_{win.list2.get()}_byte"))))
    animation.init()
    print(lang.text108)
    win.update()
    jzxs(win)
    win.get_time()
    print(lang.text134 % (dti() - start))
    do_override_sv_ttk_fonts()
    win.mainloop()


def restart(er=None):
    try:
        if animation.tasks:
            if not ask_win2("Your operation will not be saved."):
                return
    except (TclError, ValueError, AttributeError):
        pass

    def _inner():
        argv = [sys.executable]
        if not pathlib.Path(tool_self).samefile(pathlib.Path(argv[0])):
            # only needed when running within a Python intepreter
            argv.append(tool_self)
        argv.extend(sys.argv[1:])
        p = subprocess.Popen(argv)
        p.wait()
        sys.exit(p.returncode)

    if er:
        er.destroy()
    try:
        for i in win.winfo_children():
            try:
                i.destroy()
            except (TclError, ValueError, AttributeError):
                pass
        win.destroy()
    except (Exception, BaseException):
        pass

    threading.Thread(target=_inner).start()


if __name__ == "__main__":
    init()
