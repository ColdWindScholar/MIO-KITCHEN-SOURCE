#!/usr/bin/env python3
import mmap
import platform
import subprocess
from functools import wraps
import ext4
if not platform.system() == 'Darwin':
    try:
        import load_window
    except ModuleNotFoundError:
        ...
import json
import os.path
import shlex
import sys
import time
import tkinter as tk
from configparser import ConfigParser
from webbrowser import open as openurl
import contextpatch
import extra
import utils
from extra import *
from utils import cz, jzxs, v_code, gettype, findfile, findfolder, sdat2img

if os.name == 'nt':
    import windnd
    from tkinter import filedialog
elif os.name == "posix":
    import mkc_filedialog as filedialog
import zipfile
from io import BytesIO, StringIO
from platform import machine
from tkinter import *
from tkinter import ttk, messagebox
from shutil import rmtree, copy, move
import requests
import sv_ttk

if sys.version_info.major == 3 and sys.version_info.minor > 12:
    print(f"Not Support [{sys.version}] yet\nSorry for any inconvenience caused")
    input()
    sys.exit(1)
from PIL import Image, ImageTk
import fspatch
import imgextractor
import lpunpack
import mkdtboimg
import ozipdecrypt
import payload_dumper
import splituapp
from timeit import default_timer as dti
import ofp_qc_decrypt
import ofp_mtk_decrypt
import editor
import yaml
import opscrypto
import images


class json_edit:
    def __init__(self, j_f):
        self.file = j_f

    def read(self):
        if not os.path.exists(self.file):
            return {}
        with open(self.file, 'r+', encoding='utf-8') as pf:
            try:
                return json.loads(pf.read())
            except BaseException or Exception:
                return {}

    def write(self, data):
        with open(self.file, 'w+', encoding='utf-8') as pf:
            json.dump(data, pf, indent=4)

    def edit(self, name, value):
        data = self.read()
        data[name] = value
        self.write(data)


class load_car:
    gifs = []

    def __init__(self, *args):
        self.frame = None

    def run(self, ind: int = 0):
        self.hide_gifl = False
        if not self.hide_gifl:
            win.gifl.pack(padx=10, pady=10)
        self.frame = self.frames[ind]
        ind += 1
        if ind == len(self.frames):
            ind = 0
        win.gifl.configure(image=self.frame)
        self.gifs.append(win.gifl.after(30, self.run, ind))

    def endupdate(self):
        for i in self.gifs:
            try:
                win.gifl.after_cancel(i)
            except:
                ...
        win.gifl.pack_forget()
        self.hide_gifl = True

    def init(self):
        self.run()
        self.endupdate()

    def loadgif(self, gif):
        self.frames = []
        try:
            while True:
                self.frames.append(ImageTk.PhotoImage(gif.copy()))
                gif.seek(len(self.frames))
        except EOFError:
            ...

    def __call__(self, func):
        @wraps(func)
        def call_func(*args, **kwargs):
            cz(self.run())
            try:
                func(*args, **kwargs)
            except Exception as e:
                error(e.args[0], e.__repr__())
            self.endupdate()

        return call_func


cartoon = load_car()


class dev_null:
    def __init__(self):
        ...

    def write(self, string):
        ...

    @staticmethod
    def flush():
        ...


class Tool(Tk):
    def __init__(self):
        super().__init__()
        self.rzf = None
        self.tsk = None
        self.gifl = None
        self.photo = None
        self.slocal = None
        self.LB2 = None
        self.notepad = None
        self.title('MIO-KITCHEN')
        if os.name != "posix":
            self.iconphoto(True,
                           PhotoImage(
                               data=images.icon_byte))
        sys.stdout = dev_null()

    def putlog(self):
        log_ = settings.path + os.sep + v_code() + '.txt'
        with open(log_, 'w', encoding='utf-8', newline='\n') as f:
            f.write(self.show.get(1.0, END))
            self.show.delete(1.0, END)
        print(lang.text95 + log_)

    def get_time(self):
        self.tsk.config(text=time.strftime("%H:%M:%S"), bg=win.cget('bg'))
        self.after(1000, self.get_time)

    def messpop(self, message, color='orange') -> None:
        self.tsk.config(text=message, bg=color)

    def getframe(self, title):
        frame = ttk.LabelFrame(self.frame_bg, text=title)
        frame.pack(padx=10, pady=10)
        ttk.Button(frame, text=lang.text17, command=frame.destroy).pack(anchor="ne")
        self.upjdt()
        return frame

    def gui(self):
        if os.name == 'posix' and os.geteuid() != 0:
            print(lang.warn13)
        self.subwin2 = ttk.LabelFrame(self, text=lang.text9)
        self.subwin3 = ttk.LabelFrame(self, text=lang.text10)
        self.subwin3.pack(fill=BOTH, side=LEFT, expand=True, padx=5)
        self.subwin2.pack(fill=BOTH, side=LEFT, expand=True, pady=5)
        self.notepad = ttk.Notebook(self.subwin2)
        self.tab = ttk.Frame(self.notepad)
        self.tab2 = ttk.Frame(self.notepad)
        self.tab3 = ttk.Frame(self.notepad)
        self.tab4 = ttk.Frame(self.notepad)
        self.tab5 = ttk.Frame(self.notepad)
        self.tab7 = ttk.Frame(self.notepad)
        self.notepad.add(self.tab, text=lang.text11)
        self.notepad.add(self.tab2, text=lang.text12)
        self.notepad.add(self.tab7, text=lang.text19)
        self.notepad.add(self.tab3, text=lang.text13)
        self.notepad.add(self.tab4, text=lang.text14)
        self.notepad.add(self.tab5, text=lang.text15)
        self.scrollbar = ttk.Scrollbar(self.tab5, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas1 = Canvas(self.tab5, yscrollcommand=self.scrollbar.set)
        self.canvas1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.frame_bg = ttk.Frame(self.canvas1)
        self.canvas1.create_window((0, 0), window=self.frame_bg, anchor='nw')
        self.canvas1.config(highlightthickness=0)
        self.tab4_n()
        self.setting_tab()
        self.notepad.pack(fill=BOTH)
        self.rzf = ttk.Frame(self.subwin3)
        self.tsk = Label(self.subwin3, text="MIO-KITCHEN", font=('楷书', 15))
        self.tsk.bind('<Button-1>')
        self.tsk.pack(padx=10, pady=10, side='top')
        tr = ttk.LabelFrame(self.subwin3, text=lang.text131)
        Label(tr, text=lang.text132).pack(padx=10, pady=10, side='bottom')
        tr.bind('<Button-1>', lambda *x: dndfile([filedialog.askopenfilename()]))
        tr.pack(padx=5, pady=5, side='top', expand=True, fill=BOTH)
        if os.name == 'nt':
            windnd.hook_dropfiles(tr, func=dndfile)
        self.scroll = ttk.Scrollbar(self.rzf)
        self.show = Text(self.rzf)
        self.show.pack(side=LEFT, fill=BOTH, expand=True)
        self.scroll.pack(side=LEFT, fill=BOTH)
        self.scroll.config(command=self.show.yview)
        self.show.config(yscrollcommand=self.scroll.set)
        ttk.Button(self.rzf, text=lang.text105, command=lambda: self.show.delete(1.0, END)).pack(side='bottom', padx=10,
                                                                                                 pady=5,
                                                                                                 expand=True)
        ttk.Button(self.rzf, text=lang.text106, command=lambda: self.putlog()).pack(side='bottom', padx=10, pady=5,
                                                                                    expand=True)
        self.rzf.pack(padx=5, pady=5, fill=BOTH, side='bottom')
        sys.stdout = StdoutRedirector(self.show)
        sys.stderr = StdoutRedirector(self.show)
        zyf1 = ttk.LabelFrame(self.tab, text=lang.text9)
        zyf1.pack(padx=10, pady=10)
        ttk.Button(zyf1, text=lang.text114, command=lambda: cz(download_file)).pack(side='left', padx=10, pady=10)
        Label(self.tab,
              text='解锁BL是用户的权力！反对禁止解锁BL!\nUnlocking BL is the user right! Oppose the ban on unlocking BL!',
              font=(None, 10)).pack(
            padx=5, pady=5)
        Label(self.tab,
              text='反对肆意违反开源协议！\nOppose wanton violation of open source agreements!',
              font=(None, 10)).pack(
            padx=5, pady=5)
        self.tab6_n()
        mpkman()
        self.gifl = Label(self.rzf)
        self.gifl.pack(padx=10, pady=10)
        self.get_time()

    def upjdt(self):
        self.frame_bg.update_idletasks()
        self.canvas1.config(scrollregion=self.canvas1.bbox('all'))
        self.scrollbar.config(command=self.canvas1.yview)

    def tab4_n(self):
        Label(self.tab4, text="MIO-KITCHEN", font=('楷书', 30)).pack(padx=20, pady=10)
        Label(self.tab4, text=lang.text111, font=('楷书', 15), fg='#00BFFF').pack(padx=10, pady=10)
        Label(self.tab4,
              text=lang.text128.format(settings.version, sys.version[:6], platform.system(), machine()),
              font=('楷书', 11), fg='#00aaff').pack(padx=10, pady=10)
        Label(self.tab4,
              text=lang.text127,
              font=('楷书', 12), fg='#ff8800').pack(padx=10, pady=10)
        Label(self.tab4, text=lang.text110, font=('楷书', 10)).pack(padx=10, pady=10, side='bottom')
        # ttk.Button(self.tab4, text="检查更新", command=lambda: cz(upgrade())).pack(padx=10, pady=10)
        link = ttk.Label(self.tab4, text="Github: MIO-KITCHEN-SOURCE", cursor="hand2",
                         style="Link.TLabel")
        link.bind("<Button-1>", lambda *x: openurl("https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE"))
        link.pack()

    def tab6_n(self):
        tab = ttk.LabelFrame(self.tab, text=lang.text16)
        Label(tab,
              text=f"Wechat Pay/微信支付",
              font=('楷书', 20), fg='#008000').pack(padx=10, pady=10)
        self.photo = ImageTk.PhotoImage(data=images.wechat_byte)
        Label(tab, image=self.photo).pack(padx=5, pady=5)
        Label(tab, text=lang.text109, font=('楷书', 12), fg='#00aafA').pack(padx=10, pady=10, side='bottom')
        tab.pack()

    def setting_tab(self):
        self.slocal = StringVar()
        self.slocal.set(settings.path)
        sf1 = ttk.Frame(self.tab3)
        sf2 = ttk.Frame(self.tab3)
        sf3 = ttk.Frame(self.tab3)
        ttk.Label(sf1, text=lang.text124).pack(side='left', padx=10, pady=10)
        self.LB2 = ttk.Combobox(sf1, textvariable=theme, state='readonly', values=["light", "dark"])
        self.LB2.pack(padx=10, pady=10, side='left')
        self.LB2.bind('<<ComboboxSelected>>', lambda *x: settings.set_theme())

        def startwjjj():
            if os.name == 'nt':
                os.startfile(self.slocal.get())

        ttk.Label(sf3, text=lang.text125).pack(side='left', padx=10, pady=10)
        slo = ttk.Label(sf3, textvariable=self.slocal)
        slo.bind('<Button-1>', lambda *x: startwjjj())
        slo.pack(padx=10, pady=10, side='left')
        ttk.Button(sf3, text=lang.text126, command=settings.modpath).pack(side="left", padx=10, pady=10)

        ttk.Label(sf2, text=lang.lang).pack(side='left', padx=10, pady=10)
        lb3 = ttk.Combobox(sf2, state='readonly', textvariable=language,
                           value=[str(i.rsplit('.', 1)[0]) for i in
                                  os.listdir(elocal + os.sep + "bin" + os.sep + "languages")])
        lb3.pack(padx=10, pady=10, side='left')
        lb3.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())
        sf1.pack(padx=10, pady=10, fill='both')
        sf2.pack(padx=10, pady=10, fill='both')
        sf3.pack(padx=10, pady=10, fill='both')


win = Tool()
start = dti()
setfile = os.path.join((elocal := utils.elocal), "bin", "setting.ini")
dn = utils.dn = StringVar()
theme = StringVar()
language = StringVar()
tool_bin = os.path.join(elocal, 'bin', platform.system(), platform.machine()) + os.sep


class ModuleError(Exception):
    ...


class lang:
    ...


def load(name):
    global _lang
    lang_file = f'bin/languages/{name}.json'
    if not name and not os.path.exists(elocal + os.sep + 'bin/languages/English.json'):
        error(1)
    elif not os.path.exists(elocal + os.sep + lang_file):
        _lang = json_edit(elocal + os.sep + 'bin/languages/English.json').read()
    else:
        _lang = json_edit(f'{elocal}{os.sep}{lang_file}').read()
    [setattr(lang, i, _lang[i]) for i in _lang]


def error(code, desc="未知错误"):
    win.withdraw()
    sv_ttk.use_dark_theme()
    er = Toplevel()
    img = Image.open(BytesIO(images.error_logo_byte)).resize((100, 100))
    pyt = ImageTk.PhotoImage(img)
    Label(er, image=pyt).pack(padx=10, pady=10)
    er.protocol("WM_DELETE_WINDOW", win.destroy)
    er.title("Error")
    er.lift()
    er.resizable(False, False)
    jzxs(er)
    Label(er, text="Error:0x%d" % code, font=(None, 20), fg='red').pack(padx=10, pady=10)
    te = Text(er)
    te.pack(padx=10, pady=10)
    te.insert('insert', desc)
    ttk.Button(er, text="Report",
               command=lambda: openurl("https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/issues")).pack(side=LEFT,
                                                                                                             padx=10,
                                                                                                             pady=10)
    ttk.Button(er, text="Exit", command=lambda: win.destroy()).pack(side=LEFT, padx=10, pady=10)
    er.wait_window()
    sys.exit()


if not os.path.exists(f'{elocal}{os.sep}bin{os.sep}{platform.system()}{os.sep}{platform.machine()}'):
    error(1, '暂不支持您的设备\nSorry,Not support your device yet.')


class welcome(Toplevel):
    def __init__(self):
        super().__init__()
        self.title(lang.text135)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: print())
        self.frame = None
        oobe = settings.oobe
        if oobe == "1":
            self.main()
        elif oobe == '2':
            self.license()
        elif oobe == '3':
            self.private()
        elif oobe == '4':
            self.done()
        else:
            ttk.Label(self, text=lang.text135, font=("宋体", 40)).pack(padx=10, pady=10, fill=BOTH, expand=True)
            ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
            ttk.Label(self, text=lang.text137, font=("宋体", 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)
            ttk.Button(self, text=lang.text136, command=self.main).pack(fill=BOTH)
        win.withdraw()
        self.wait_window()
        win.deiconify()

    def reframe(self):
        if self.frame:
            self.frame.destroy()
        self.frame = ttk.Frame(self)
        self.frame.pack(expand=1, fill=BOTH)

    def main(self):
        settings.setf("oobe", "1")
        for i in self.winfo_children():
            i.destroy()
        self.reframe()
        ttk.Label(self.frame, text=lang.text129, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb3_ = ttk.Combobox(self.frame, state='readonly', textvariable=language,
                            value=[i.rsplit('.', 1)[0] for i in
                                   os.listdir(elocal + os.sep + "bin" + os.sep + "languages")])
        lb3_.pack(padx=10, pady=10, side='top')
        lb3_.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())
        ttk.Button(self.frame, text=lang.text138, command=self.license).pack(fill=X, side='bottom')

    def license(self):
        settings.setf("oobe", "2")
        lce = StringVar()

        def loadlice():
            te.delete(1.0, END)
            with open(os.path.join(elocal, "bin", "licenses", lce.get() + ".txt"), 'r',
                      encoding='UTF-8') as f:
                te.insert('insert', f.read())

        self.reframe()
        lb = ttk.Combobox(self.frame, state='readonly', textvariable=lce,
                          value=[i.rsplit('.')[0] for i in os.listdir(elocal + os.sep + "bin" + os.sep + "licenses")])
        lb.bind('<<ComboboxSelected>>', lambda *x: loadlice())
        lb.current(0)
        ttk.Label(self.frame, text=lang.text139, font=("宋体", 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                         expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb.pack(padx=10, pady=10, side='top', fill=X)
        te = Text(self.frame)
        te.pack(fill=BOTH, side='top')
        loadlice()
        ttk.Label(self.frame, text=lang.t1).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.private).pack(fill=BOTH, side='bottom')

    def private(self):
        settings.setf("oobe", "3")
        self.reframe()
        ttk.Label(self.frame, text=lang.t2, font=("宋体", 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                    expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        with open(os.path.join(elocal, "bin", "licenses", "private.txt"), 'r',
                  encoding='UTF-8') as f:
            (te := Text(self.frame)).insert('insert', f.read())
        te.pack(fill=BOTH)
        ttk.Label(self.frame, text=lang.t3).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.done).pack(fill=BOTH, side='bottom')

    def done(self):
        settings.setf("oobe", "4")
        self.reframe()
        ttk.Label(self.frame, text=lang.t4, font=("宋体", 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                    expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.t5, font=("宋体", 20)).pack(
            side='top', fill=BOTH, padx=10, pady=10)
        ttk.Button(self, text=lang.text34, command=self.destroy).pack(fill=BOTH, side='bottom')


class set_utils:
    def __init__(self, set_ini):
        self.path = None
        self.barlevel = '0.9'
        self.set_file = set_ini
        self.config = ConfigParser()
        if os.access(self.set_file, os.F_OK):
            self.load()
        else:
            sv_ttk.set_theme("dark")
            error(1, '缺失配置文件，请重新安装此软件')

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
        load(language.get())
        theme.set(self.theme)
        sv_ttk.set_theme(self.theme)
        win.attributes("-alpha", self.barlevel)

    def setf(self, name, value):
        self.config.read(setfile)
        self.config.set("setting", name, value)
        with open(self.set_file, 'w') as fil:
            self.config.write(fil)
        self.load()

    def set_theme(self):
        print(lang.text100 + theme.get())
        try:
            self.setf("theme", theme.get())
            sv_ttk.set_theme(theme.get())
            gif = Image.open(BytesIO(getattr(images, "loading_{}_byte".format(win.LB2.get()))))
            cartoon.loadgif(gif)
        except Exception as e:
            win.messpop(lang.text101 % (theme.get(), e))

    def set_language(self):
        print(lang.text129 + language.get())
        try:
            self.setf("language", language.get())
            load(language.get())
        except Exception as e:
            print(lang.t130, e)

    def modpath(self):
        if not (folder := filedialog.askdirectory()):
            return False
        self.setf("path", folder)
        win.slocal.set(folder)
        self.load()


settings = set_utils(setfile)
settings.load()


def re_folder(path) -> None:
    if os.path.exists(path):
        rmdir(path)
        os.mkdir(path)
    else:
        os.mkdir(path)


@cartoon
def un_dtbo(bn: str = 'dtbo') -> any:
    if not (dtboimg := findfile(f"{bn}.img", work := rwork())):
        print(lang.warn3.format(bn))
        return False
    re_folder(work + f"{bn}")
    re_folder(work + f"{bn}" + os.sep + "dtbo")
    re_folder(work + f"{bn}" + os.sep + "dts")
    try:
        mkdtboimg.dump_dtbo(dtboimg, work + f"{bn}" + os.sep + "dtbo" + os.sep + "dtbo")
    except Exception as e:
        print(lang.warn4.format(e))
        return False
    for dtbo in os.listdir(work + f"{bn}" + os.sep + "dtbo"):
        if dtbo.startswith("dtbo."):
            print(lang.text4.format(dtbo))
            call(exe="dtc -@ -I dtb -O dts %s -o %s" % (work + f"{bn}" + os.sep + "dtbo" + os.sep + dtbo,
                                                        os.path.join(work, f"{bn}", "dts", "dts." +
                                                                     os.path.basename(dtbo).rsplit('.', 1)[1])), out=1)
    print(lang.text5)
    try:
        os.remove(dtboimg)
    except:
        ...
    rmdir(work + "dtbo" + os.sep + "dtbo")


@cartoon
def padtbo() -> any:
    work = rwork()
    if not os.path.exists(work + "dtbo" + os.sep + "dts") or not os.path.exists(work + "dtbo"):
        print(lang.warn5)
        return False
    re_folder(work + "dtbo" + os.sep + "dtbo")
    for dts in os.listdir(work + "dtbo" + os.sep + "dts"):
        if dts.startswith("dts."):
            print(f"{lang.text6}:%s" % dts)
            call(exe="dtc -@ -I dts -O dtb %s -o %s" % (work + "dtbo" + os.sep + "dts" + os.sep + dts,
                                                        work + "dtbo" + os.sep + "dtbo" + os.sep + "dtbo." +
                                                        os.path.basename(dts).rsplit('.', 1)[1]), out=1)
    print(f"{lang.text7}:dtbo.img")
    list_ = []
    for f in os.listdir(work + "dtbo" + os.sep + "dtbo"):
        if f.startswith("dtbo."):
            list_.append(work + "dtbo" + os.sep + "dtbo" + os.sep + f)
    list_ = sorted(list_, key=lambda x: int(x.rsplit('.')[1]))
    mkdtboimg.create_dtbo(work + "dtbo.img", list_, 4096)
    rmdir(work + "dtbo")
    print(lang.text8)


@cartoon
def logodump(bn: str = 'logo'):
    if not (logo := findfile(f'{bn}.img', work := rwork())):
        win.messpop(lang.warn3.format(bn))
        return False
    re_folder(work + f"{bn}")
    utils.LOGODUMPER(logo, work + f"{bn}").unpack()


@cartoon
def logopack() -> int:
    orlogo = findfile('logo.img', work := rwork())
    logo = work + "logo-new.img"
    if not os.path.exists(dir_ := work + "logo"):
        print(lang.warn6)
        return 1
    if not os.path.exists(orlogo):
        print(lang.warn6)
        return 1
    utils.LOGODUMPER(orlogo, logo, dir_).repack()
    os.remove(orlogo)
    os.rename(logo, orlogo)
    rmdir(dir_)


class Process(Toplevel):
    def __init__(self, mps):
        super().__init__()
        self.prc = None
        self.dir = os.path.join(elocal + os.sep + 'bin' + os.sep + 'temp', v_code(10))
        self.project = os.path.join(self.dir, v_code())
        self.mps = mps
        self.in_process = False
        self.error = 1
        dn.set(os.path.basename(self.project))
        self.gavs = {
            'bin': self.dir,
            'tool_bin': tool_bin.replace('\\', '/'),
            'mkc_env': os.path.join(self.dir, v_code(10)),
            'project': self.project.replace('\\', '/')
        }
        self.value = self.gavs.keys()
        self.value = list(self.value)
        self.control = []
        self.able = True
        self.protocol("WM_DELETE_WINDOW", self.exit)
        try:
            win.withdraw()
        finally:
            ...
        self.notice = Label(self, text='Preparing...', font=(None, 15))
        self.notice.pack(padx=10, pady=10)
        self.title("Preparing...")
        self.start = ttk.Button(self, text='Preparing', state='disabled', command=lambda: cz(self.run))
        self.start.pack(side=BOTTOM, padx=30, pady=30)
        self.progbar = ttk.Progressbar(self, orient=HORIZONTAL, length=200, mode='indeterminate')
        self.progbar.pack(side=TOP, fill=X)
        self.prepare()

    def prepare(self):
        zipfile.ZipFile(self.mps).extractall(self.dir)
        jzxs(self)
        with open(self.dir + os.sep + "main.yml", 'r', encoding='utf-8') as yml:
            self.prc = yaml.load(yml.read(), Loader=yaml.FullLoader)
        self.title(self.prc['name'])
        if "system" in self.prc['support']:
            if sys.platform not in self.prc['support']['system']:
                self.notice.configure(text="未满足系统要求", fg='red')
                self.able = False
        if "version" in self.prc['support']:
            if settings.version not in self.prc['support']['version']:
                self.notice.configure(text="未满足版本要求", fg='red')
                self.able = False
        self.start.configure(state='normal')
        if not self.able:
            self.start.configure(text="退出")
        else:
            self.controls()
            self.notice.configure(text="准备就绪", fg='green')
            self.start.configure(text="运行")

    def controls(self):
        for key in self.prc['inputs']:
            con = self.prc['inputs'][key]
            self.value.append(key)
            if con["type"] == "radio":
                radio_var_name = key
                self.gavs[radio_var_name] = StringVar()
                options = con['opins'].split()
                pft1 = ttk.LabelFrame(self, text=con['text']) if 'text' in con else ttk.Frame(self)
                self.control.append(pft1)
                pft1.pack(padx=10, pady=10)
                for option in options:
                    text, value = option.split('|')
                    self.gavs[radio_var_name].set(value)
                    ttk.Radiobutton(pft1, text=text, variable=self.gavs[radio_var_name],
                                    value=value).pack(side=LEFT, padx=5, pady=5)
            elif con["type"] in ['entry', 'Entry']:
                input_frame = Frame(self)
                input_frame.pack(padx=10, pady=10)
                self.control.append(input_frame)
                input_var_name = key
                self.gavs[input_var_name] = StringVar()
                if 'text' in con:
                    ttk.Label(input_frame, text=con['text']).pack(side=LEFT, padx=5, pady=5, fill=X)
                ttk.Entry(input_frame, textvariable=self.gavs[input_var_name]).pack(side=LEFT, pady=5,
                                                                                    padx=5,
                                                                                    fill=X)
            elif con['type'] == 'checkbutton':
                b_var_name = key
                self.gavs[b_var_name] = IntVar()
                text = 'M.K.C' if 'text' not in con else con['text']
                self.control.append(cb := ttk.Checkbutton(self, text=text, variable=self.gavs[b_var_name], onvalue=1,
                                                          offvalue=0,
                                                          style="Switch.TCheckbutton"))
                cb.pack(
                    padx=5, pady=5, fill=BOTH)
            else:
                print(lang.warn14.format(con['type']))

    def run(self):
        if not self.able:
            self.exit()
            return
        for c in self.control:
            c.destroy()
        self.in_process = True
        process = Text(self)
        process.pack(fill=BOTH)
        sys.stdout = StdoutRedirector(process)
        sys.stderr = StdoutRedirector(process)
        self.start.configure(text="正在运行", state='disabled')
        with open(engine := self.dir + os.sep + v_code() + "_engine", 'w', encoding='utf-8') as en:
            for u in self.value:
                if 'get' in dir(self.gavs[u]):
                    var = self.gavs[u].get()
                else:
                    var = self.gavs[u]
                en.write(f"export {u}={var}\n")
            en.write("source $1")
        self.progbar.start()
        for step in self.prc['steps']:
            self.notice.configure(text=step['name'])
            if 'run' in step:
                with open(sh_tmp_file := self.dir + os.sep + v_code(), 'w', encoding='utf-8') as sh_tmp:
                    sh_tmp.writelines(step['run'])
                sh = "ash" if os.name == 'posix' else 'bash'
                self.error = call("busybox {} {} {}".format(sh, engine, sh_tmp_file))
            elif "use" in step:
                try:
                    self.use(step)
                except Exception as e:
                    print(e)
                    self.error = 0
                    self.stop()
                    break
            else:
                print(f"Unsupported {step}")
        self.progbar.stop()
        self.able = False
        self.in_process = False
        self.start.configure(text="退出", state='normal')

    def use(self, step):
        def download(url):
            try:
                for percentage, speed, bytes_downloaded, file_size, elapsed in download_api(url, self.project):
                    print(lang.text64.format(str(percentage), str(speed), str(bytes_downloaded), str(file_size)))
            except BaseException or Exception:
                self.error = 0
            else:
                self.error = 1

        def unzip(file, folder):
            print(f"Unzipping {file}...")
            with zipfile.ZipFile(file) as zip_:
                for file_ in zip_.namelist():
                    try:
                        file = str(file_).encode('cp437').decode('gbk')
                    except:
                        file = str(file_).encode('utf-8').decode('utf-8')
                    print(lang.text38.format(file_))
                    zip_.extract(file, folder)

        actions = {
            'download': lambda url: download(url['url']),
            'unzip': lambda cmd: unzip(os.path.abspath(cmd['src']), os.path.abspath(cmd['dst']))
        }
        actions[step['use']](step)

    def stop(self):
        self.in_process = False
        self.able = False
        self.progbar.stop()
        self.notice.configure(text="错误！", fg='red')
        self.start.configure(text="退出", state='normal')

    def exit(self):
        if self.in_process:
            return
        settings.load()
        sys.stdout = StdoutRedirector(win.show)
        sys.stderr = StdoutRedirector(win.show)
        xmcd_.listdir()
        rmdir(self.dir)
        self.destroy()
        win.deiconify()


class IconGrid(tk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.icons = []
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

    def add_icon(self, icon, num=4):
        self.icons.append(icon)
        row = (len(self.icons) - 1) // num
        col = (len(self.icons) - 1) % num
        icon.grid(row=row, column=col, padx=10, pady=10)

    def clean(self):
        for i in self.icons:
            i.destroy()
        self.icons.clear()

    def on_frame_configure(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


def mpkman() -> None:
    chosed = tk.StringVar()
    chosed.set('')

    def impk():
        Installmpk(filedialog.askopenfilename(title=lang.text25, filetypes=((lang.text26, "*.mpk"),)))
        list_pls()

    class new_(Toplevel):
        def __init__(self):
            super().__init__()
            jzxs(self)
            self.title(lang.text115)
            self.gui()

        @staticmethod
        def labelEntry(master, text, side):
            frame = Frame(master)
            ttk.Label(frame, text=text).pack(padx=5, pady=5, side=LEFT)
            entry = ttk.Entry(frame)
            entry.pack(padx=5, pady=5, side=LEFT)
            frame.pack(padx=5, pady=5, fill=X, side=side)
            return entry

        def gui(self):
            ttk.Label(self, text=lang.t19, font=(None, 25)).pack(fill=BOTH, expand=0, padx=10, pady=10)
            ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
            #
            self.name = self.labelEntry(self, lang.t20, TOP)
            #
            self.aou = self.labelEntry(self, lang.t21, TOP)
            #
            self.ver = self.labelEntry(self, lang.t22, TOP)
            #
            self.dep = self.labelEntry(self, lang.t23, TOP)
            #
            ttk.Label(self, text=lang.t24).pack(padx=5, pady=5, expand=1)
            self.intro = Text(self)
            self.intro.pack(fill=BOTH, padx=5, pady=5, expand=1)
            ttk.Button(self, text=lang.text115, command=self.create).pack(fill=BOTH, side=BOTTOM)

        def create(self):
            data = {
                "name": self.name.get(),
                "author": self.aou.get(),
                "version": self.ver.get(),
                "identifier": (iden := v_code()),
                "describe": self.intro.get(1.0, END),
                "depend": self.dep.get()
            }
            self.destroy()
            if not os.path.exists(moduledir + os.sep + iden):
                os.makedirs(moduledir + os.sep + iden)
            with open(moduledir + os.sep + iden + os.sep + "info.json", 'w+', encoding='utf-8', newline='\n') as js:
                js.write(json.dumps(data))
            list_pls()
            editor_(iden)

    def editor_(id_=None):
        if not chosed.get():
            win.messpop(lang.warn2)
            return 1
        if id_ is None:
            id_ = globals()[chosed.get()]
        path = os.path.join(moduledir, id_) + os.sep
        if not os.path.exists(path + "main.msh") and not os.path.exists(path + 'main.sh'):
            s = "main.sh" if ask_win(lang.t18, 'SH', 'MSH') == 1 else "main.msh"
            with open(path + s, 'w+', encoding='utf-8', newline='\n') as sh:
                sh.write("echo MIO-KITCHEN")
            editor.main(path + s)
        else:
            if os.path.exists(path + "main.msh"):
                editor.main(path + "main.msh")
            elif os.path.exists(path + 'main.sh'):
                editor.main(path + 'main.sh')

    class mpkrun:
        def __init__(self, name):
            self.name = name

        def popup(self, event):
            chosed.set(self.name)
            rmenu2.post(event.x_root, event.y_root)

        def run(self):
            chosed.set(self.name)
            run()

    @cartoon
    def export():
        if not chosed.get():
            win.messpop(lang.warn2)
            return 1
        with open(os.path.join(moduledir, (value := globals()[chosed.get()]), "info.json"), 'r', encoding='UTF-8') as f:
            data = json.load(f)
            if "describe" in data:
                des = data["describe"]
            else:
                des = ''
            (info_ := ConfigParser())['module'] = {
                'name': f'{data["name"]}',
                'version': f'{data["version"]}',
                'author': f'{data["author"]}',
                'describe': f'{des}',
                'resource': 'main.zip',
                'identifier': f'{value}',
                'depend': f'{data["depend"]}'
            }
            info_.write((buffer2 := StringIO()))
        with zipfile.ZipFile((buffer := BytesIO()), 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk:
            os.chdir(moduledir + os.sep + value)
            for i in get_all_file_paths("."):
                print(f"{lang.text1}:%s" % i.rsplit(".\\")[1])
                try:
                    mpk.write(i)
                except Exception as e:
                    print(lang.text2.format(i, e))
            os.chdir(elocal)
        with zipfile.ZipFile(os.path.join(settings.path, str(chosed.get()) + ".mpk"), 'w',
                             compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk2:
            mpk2.writestr('main.zip', buffer.getvalue())
            mpk2.writestr('info', buffer2.getvalue())
            del buffer2, buffer
        print(lang.t15 % (settings.path + os.sep + chosed.get() + ".mpk")) if os.path.exists(
            settings.path + os.sep + chosed.get() + ".mpk") else print(
            lang.t16 % (settings.path + os.sep + chosed.get() + ".mpk"))

    def popup(event):
        rmenu.post(event.x_root, event.y_root)  # post在指定的位置显示弹出菜单

    moduledir = os.path.join(elocal, "bin", "module")
    if not os.path.exists(moduledir):
        os.makedirs(moduledir)
    file = StringVar()
    images_ = {}

    def list_pls():
        pls.clean()
        for i in os.listdir(moduledir):
            if os.path.isdir(moduledir + os.sep + i):
                if os.path.exists(os.path.join(moduledir, i, 'icon')):
                    images_[i] = ImageTk.PhotoImage(Image.open(os.path.join(moduledir, i, 'icon')).resize((70, 70)))
                else:
                    images_[i] = ImageTk.PhotoImage(data=images.none_byte)
                data = json_edit(os.path.join(moduledir, i, "info.json")).read()
                icon = tk.Label(pls.scrollable_frame,
                                image=images_[i],
                                compound="center",
                                text=data['name']
                                , bg="#4682B4",
                                wraplength=70,
                                justify='center')
                icon.bind('<Double-Button-1>', lambda *x: mpkrun(data['name']).run())
                icon.bind('<Button-3>', mpkrun(data['name']).popup)
                pls.add_icon(icon)
                globals()[data['name']] = data['identifier']

    class msh_parse:
        envs = {'version': settings.version,
                'tool_bin': tool_bin.replace('\\', '/'),
                'project': (settings.path + os.sep + dn.get()).replace('\\', '/'),
                'moddir': moduledir.replace('\\', '/')}
        grammar_words = {"echo": lambda strings: print(strings),
                         "rmdir": lambda path: rmdir(path.strip()),
                         "run": lambda cmd: call(exe=str(cmd), kz='N', shstate=True),
                         'gettype': lambda file_: gettype(file_),
                         'exist': lambda x: '1' if os.path.exists(x) else '0'}

        def __init__(self, sh):
            self.envs['bin'] = os.path.dirname(sh.replace('\\', '/'))
            with open(sh, 'r+', encoding='utf-8', newline='\n') as shell:
                for i in shell.readlines():
                    try:
                        self.runline(i)
                    except AttributeError as e:
                        print("未知的参数或命令：%s\n错误：%s" % (i, str(e).replace("msh_parse", 'MSH解释器')))
                    except ModuleError as e:
                        print("异常:%s" % e)
                        return
                    except Exception as e:
                        print("运行错误:%s\n错误：%s" % (i, e))
                    except:
                        print("运行错误:%s" % i)
            self.envs.clear()

        def set(self, cmd):
            try:
                vn, va = cmd.split()
            except Exception as e:
                print("赋值异常：%s\n语句：%s" % (e, cmd))
                return 1
            if not self.envs[vn] == str(va):
                self.envs[vn] = str(va)

        def runline(self, i):
            for key, value in self.envs.items():
                i = i.replace(f'@{key}@', value).strip()
            if i[:1] not in ["#"] and i not in ["", '\n', "\r\n"]:
                if i[:1] == "@":
                    i = i[1:]
                if i.split()[0] == "if":
                    self.sif(i.split()[1], i.split()[2], shlex.split(i)[3])
                elif i.split()[0] == "for":
                    self.sfor(i.split()[1], shlex.split(i)[3], shlex.split(i)[4])
                else:
                    if i.split()[0] in self.grammar_words.keys():
                        self.envs["result"] = self.grammar_words[i.split()[0]](i[i.index(" ") + 1:])
                    else:
                        self.envs["result"] = getattr(self, i.split()[0])(i[i.index(" ") + 1:])
                    if not self.envs['result']:
                        self.envs['result'] = ""

        def sfor(self, vn, vs, do):
            for v in vs.split(',' if ',' in vs else None):
                self.runline(do.replace(f'@{vn}@', v))

        def sh(self, cmd):
            with open(file_ := (os.path.join(elocal, "bin", "temp", v_code())), "w",
                      encoding='UTF-8',
                      newline="\n") as f:
                for i in self.envs:
                    f.write(f'export {i}="{self.envs[i]}"\n')
                f.write("source $1")
            if os.path.exists(file_):
                sh = "ash" if os.name == 'posix' else "bash"
                call("busybox {} {} {}".format(sh, file_, cmd.replace('\\', '/')))
                try:
                    os.remove(file_)
                except:
                    ...

        def msh(self, cmd):
            try:
                cmd_, argv = cmd.split()
            except Exception:
                raise ModuleError("MSH解释器: 不支持的命令 %s" % cmd)
            if cmd_ == 'run':
                if not os.path.exists(argv.replace("\\", '/')):
                    print("脚本不存在：%s" % argv)
                    return 1
                else:
                    print("开始执行:%s" % os.path.basename(argv))
                    self.__init__(argv)
                    print("执行完成：%s" % os.path.basename(argv))
            else:
                print('-------\nMSH解释器\n-------\n用法：\nmsh run [script]')

        @staticmethod
        def exit(value):
            raise ModuleError(value)

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

    class parse(Toplevel):
        gavs = {}

        def __init__(self, jsons, msh=False):
            super().__init__()
            self.value = []

            def callcmd(cmd):
                if cmd.split()[0] == "msg":
                    messagebox.showinfo(cmd.split()[1], cmd.split()[2])
                elif cmd.split()[0] == "start":
                    cz(call(cmd[cmd.index(' ') + 1:], 'N'))
                elif cmd.split()[0] == "exec":
                    exec(cmd[cmd.index(' ') + 1:])
                else:
                    print(lang.text27, cmd)

            def generate_sh():
                temp = os.path.join(elocal, "bin", "temp")
                if not os.path.exists(temp):
                    re_folder(temp)
                file.set(os.path.join(temp, v_code()))
                with open(file.get(), "w", encoding='UTF-8', newline="\n") as _f_:
                    for va in self.value:
                        if gva := self.gavs[va].get():
                            if gva is str and os.path.isabs(gva) and os.name == 'nt':
                                if os.sep in gva:
                                    gva = gva.replace(os.sep, '/')
                            _f_.write(f"export {va}='{gva}'\n")
                        else:
                            continue
                    _f_.write('export version="{}"\n'.format(settings.version))
                    _f_.write('export tool_bin="{}"\n'.format(tool_bin.replace('\\', '/')))
                    _f_.write('export moddir="{}"\n'.format(moduledir.replace('\\', '/')))
                    _f_.write(
                        "export project='{}'\nsource $1".format((settings.path + os.sep + dn.get()).replace('\\', '/')))
                self.destroy()
                self.gavs.clear()
                self.value.clear()

            def generate_msh():
                for va in self.value:
                    if gva := self.gavs[va].get():
                        msh_parse.envs[va] = gva
                        if gva is str and os.path.isabs(gva) and os.name == 'nt':
                            if '\\' in gva:
                                msh_parse.envs[va] = gva.replace("\\", '/')
                self.destroy()
                self.gavs.clear()
                self.value.clear()

            with open(jsons, 'r', encoding='UTF-8') as f:
                try:
                    data = json.load(f)
                except Exception as e:
                    win.messpop(lang.text133 + str(e))
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
                except:
                    ...
                self.resizable(True, True) if resizable == '1' else self.resizable(False, False)
                for group_name, group_data in data['main'].items():
                    if group_name != "info":
                        group_frame = ttk.LabelFrame(self, text=group_data['title'])
                        group_frame.pack(padx=10, pady=10)
                        for con in group_data['controls']:
                            if 'set' in con:
                                self.value.append(con['set'])
                            if con["type"] == "text":
                                text_label = ttk.Label(group_frame, text=con['text'],
                                                       font=(None, int(con['fontsize'])))
                                text_label.pack(side=con['side'], padx=5, pady=5)
                            elif con["type"] == "button":
                                button_command = con['command']
                                button = ttk.Button(group_frame, text=con['text'],
                                                    command=lambda: callcmd(button_command))
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
                if msh:
                    ttk.Button(self, text=lang.ok, command=lambda: cz(generate_msh)).pack(fill=X, side='bottom')
                else:
                    ttk.Button(self, text=lang.ok, command=lambda: cz(generate_sh)).pack(fill=X, side='bottom')

            jzxs(self)
            self.wait_window()

    @cartoon
    def run():
        if not dn.get():
            print(lang.warn1)
            return
        if chosed.get():
            value = globals()[chosed.get()]
        else:
            print(lang.warn2)
            return
        script_path = moduledir + os.sep + value + os.sep
        sh = "ash" if os.name == 'posix' else 'bash'
        if os.path.exists(script_path + "main.sh") or os.path.exists(script_path + "main.msh"):
            if os.path.exists(script_path + "main.json"):
                parse(script_path + "main.json", os.path.exists(script_path + "main.msh"))
                if os.path.exists(script_path + "main.sh") and file.get():
                    call("busybox {} {} {}".format(sh, file.get(),
                                                   (script_path + "main.sh").replace(
                                                       '\\',
                                                       '/')))
                    os.remove(file.get())
                elif os.path.exists(os.path.join(moduledir, value, "main.msh")):
                    msh_parse(os.path.join(moduledir, value, "main.msh"))
            else:
                if os.path.exists(os.path.join(moduledir, value, "main.sh")):
                    if not os.path.exists(temp := os.path.join(elocal, "bin", "temp") + os.sep):
                        re_folder(temp)
                    if not file.get():
                        file.set(temp + v_code())
                    with open(file.get(), "w", encoding='UTF-8', newline="\n") as f:
                        f.write('export tool_bin={}\n'.format(
                            tool_bin.replace(
                                '\\',
                                '/')))
                        f.write('export version={}\n'.format(settings.version))
                        f.write('export moddir={}\n'.format(moduledir.replace('\\', '/')))
                        f.write(
                            "export project={}\nsource $1".format(
                                (settings.path + os.sep + dn.get()).replace('\\', '/')))
                    if os.path.exists(file.get()):
                        call("busybox {} {} {}".format(sh, file.get(), (script_path + "main.sh").replace('\\', '/')))
                        os.remove(file.get())
                elif os.path.exists(msh_tmp := script_path + "main.msh"):
                    msh_parse(msh_tmp)
        else:
            if not os.path.exists(moduledir + os.sep + value):
                win.messpop(lang.warn7.format(value))
                list_pls()
                win.tab7.lift()
            else:
                print(lang.warn8)

    class unmpk:

        def __init__(self):
            self.ck = None
            self.arr = []
            self.arr2 = []
            if chosed.get():
                self.value = globals()[chosed.get()]
                self.value2 = chosed.get()
                self.lfdep()
                self.ask()
            else:
                win.messpop(lang.warn2)

        def ask(self):
            self.ck = Toplevel()
            try:
                self.ck.attributes('-topmost', 'true')
            except:
                ...
            self.ck.title(lang.t6)
            jzxs(self.ck)
            ttk.Label(self.ck, text=lang.t7 % self.value2, font=(None, 30)).pack(padx=10, pady=10, fill=BOTH,
                                                                                 expand=True)
            if self.arr2:
                ttk.Separator(self.ck, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
                ttk.Label(self.ck, text=lang.t8, font=(None, 15)).pack(padx=10, pady=10, fill=BOTH,
                                                                       expand=True)
                te = Listbox(self.ck, highlightthickness=0, activestyle='dotbox')
                for i in self.arr2:
                    te.insert("end", i)
                te.pack(fill=BOTH, padx=10, pady=10)
            ttk.Button(self.ck, text=lang.ok, command=self.unloop).pack(fill=X, expand=True, side=LEFT, pady=10,
                                                                        padx=10)
            ttk.Button(self.ck, text=lang.cancel, command=self.ck.destroy).pack(fill=X, expand=True, side=LEFT,
                                                                                pady=10,
                                                                                padx=10)

        def lfdep(self, name=None):
            if not name:
                name = self.value
            for i in [i for i in os.listdir(moduledir) if os.path.isdir(moduledir + os.sep + i)]:
                with open(os.path.join(moduledir, i, "info.json"), 'r', encoding='UTF-8') as f:
                    data = json.load(f)
                    for n in data['depend'].split():
                        if name == n:
                            self.arr.append(i)
                            self.arr2.append(data['name'])
                            self.lfdep(i)
                            break
                    self.arr = sorted(set(self.arr), key=self.arr.index)
                    self.arr2 = sorted(set(self.arr2), key=self.arr2.index)

        def unloop(self):
            self.ck.destroy()
            for i in self.arr:
                self.umpk(i)
            self.umpk(self.value)

        @staticmethod
        def umpk(name=None) -> None:
            if name:
                print(lang.text29.format(name))
                if os.path.exists(moduledir + os.sep + name):
                    try:
                        rmtree(moduledir + os.sep + name)
                    except PermissionError as e:
                        print(e)
                if os.path.exists(moduledir + os.sep + name):
                    win.messpop(lang.warn9, 'red')
                else:
                    print(lang.text30)
                    try:
                        list_pls()
                    except:
                        ...
            else:
                win.messpop(lang.warn2)

    ttk.Label(win.tab7, text=lang.text19, font=("宋体", 20)).pack(padx=10, pady=10, fill=BOTH)
    ttk.Separator(win.tab7, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
    Label(win.tab7, text=lang.text24).pack(padx=5, pady=5)
    pls = IconGrid(win.tab7)
    lf1 = Frame(win.tab7)
    pls.pack(padx=5, pady=5, fill=BOTH, side=LEFT, expand=True)
    pls.canvas.bind('<Button-3>', popup)
    pls.bind('<Button-3>', popup)
    rmenu = Menu(pls, tearoff=False, borderwidth=0)
    rmenu.add_command(label=lang.text21, command=lambda: cz(impk))
    rmenu.add_command(label=lang.text23, command=lambda: cz(list_pls))
    rmenu.add_command(label=lang.text115, command=lambda: cz(new_))
    rmenu2 = Menu(pls, tearoff=False, borderwidth=0)
    rmenu2.add_command(label=lang.text20, command=lambda: cz(unmpk))
    rmenu2.add_command(label=lang.text22, command=lambda: cz(run))
    rmenu2.add_command(label=lang.t14, command=lambda: cz(export))
    rmenu2.add_command(label=lang.t17, command=lambda: cz(editor_))
    try:
        list_pls()
    except:
        ...
    lf1.pack(padx=10, pady=10)


class Installmpk(Toplevel):
    def __init__(self, mpk):
        super().__init__()
        self.mconf = ConfigParser()
        if not mpk:
            win.messpop(lang.warn2)
            self.destroy()
            return
        self.title(lang.text31)
        self.icon = None
        self.resizable(False, False)
        with zipfile.ZipFile(mpk, 'r') as myfile:
            with myfile.open('info') as info_file:
                self.mconf.read_string(info_file.read().decode('utf-8'))
            try:
                with myfile.open('icon') as myfi:
                    self.icon = myfi.read()
                    try:
                        pyt = ImageTk.PhotoImage(Image.open(BytesIO(self.icon)))
                    except Exception as e:
                        print(e)
                        pyt = ImageTk.PhotoImage(data=images.none_byte)
            except:
                pyt = ImageTk.PhotoImage(data=images.none_byte)
            with myfile.open('%s' % (self.mconf.get('module', 'resource')), 'r') as inner_file:
                self.inner_zipdata = inner_file.read()
                self.inner_filenames = zipfile.ZipFile(BytesIO(self.inner_zipdata)).namelist()
        Label(self, image=pyt).pack(padx=10, pady=10)
        Label(self, text=self.mconf.get('module', 'name'), font=('黑体', 14)).pack(padx=10, pady=10)
        Label(self, text=lang.text32.format((self.mconf.get('module', 'version'))), font=('黑体', 12)).pack(padx=10,
                                                                                                            pady=10)
        Label(self, text=lang.text33.format((self.mconf.get('module', 'author'))), font=('黑体', 12)).pack(padx=10,
                                                                                                           pady=10)
        text = Text(self)
        text.insert("insert", self.mconf.get('module', 'describe'))
        text.pack(padx=10, pady=10)
        self.prog = ttk.Progressbar(self, length=200, mode='determinate', orient=HORIZONTAL, maximum=100, value=0)
        self.prog.pack()
        self.state = Label(self, text=lang.text40, font=('黑体', 12))
        self.state.pack(padx=10, pady=10)
        self.installb = ttk.Button(self, text=lang.text41, command=lambda: cz(self.install))
        self.installb.pack(padx=10, pady=10, expand=True, fill=X)
        jzxs(self)
        self.wait_window()

    def install(self):
        if self.installb.cget('text') == lang.text34:
            self.destroy()
            return 1
        self.installb.config(state=DISABLED)
        try:
            supports = self.mconf.get('module', 'supports').split()
        except:
            supports = [sys.platform]
        if sys.platform not in supports:
            self.state['text'] = lang.warn15.format(sys.platform)
            return 0
        for dep in self.mconf.get('module', 'depend').split():
            if not os.path.isdir(os.path.join(elocal, "bin", "module", dep)):
                self.state['text'] = lang.text36 % (self.mconf.get('module', 'name'), dep, dep)
                self.installb['text'] = lang.text37
                self.installb.config(state='normal')
                return 0
        if os.path.exists(os.path.join(elocal, "bin", "module", self.mconf.get('module', 'identifier'))):
            rmtree(os.path.join(elocal, "bin", "module", self.mconf.get('module', 'identifier')))
        fz = zipfile.ZipFile(BytesIO(self.inner_zipdata), 'r')
        uncompress_size = sum((file.file_size for file in fz.infolist()))
        extracted_size = 0
        for file in self.inner_filenames:
            try:
                file = str(file).encode('cp437').decode('gbk')
            except:
                file = str(file).encode('utf-8').decode('utf-8')
            info = fz.getinfo(file)
            extracted_size += info.file_size
            self.state['text'] = lang.text38.format(file)
            fz.extract(file, os.path.join(elocal, "bin", "module", self.mconf.get('module', 'identifier')))
            self.prog['value'] = extracted_size * 100 / uncompress_size
        try:
            depends = self.mconf.get('module', 'depend')
        except:
            depends = ''
        minfo = {}
        for i in self.mconf.items('module'):
            minfo[i[0]] = i[1]
        minfo['depend'] = depends
        with open(os.path.join(elocal, "bin", "module", self.mconf.get('module', 'identifier'), "info.json"),
                  'w') as f:
            json.dump(minfo, f, indent=2)
        if self.icon:
            with open(os.path.join(elocal, "bin", "module", self.mconf.get('module', 'identifier'), "icon"),
                      'wb') as f:
                f.write(self.icon)

        self.state['text'] = lang.text39
        self.installb['text'] = lang.text34
        self.installb.config(state='normal')


class packxx(Toplevel):
    def __init__(self, list_):
        if not list_:
            return
        super().__init__()
        self.title(lang.text42)
        self.dbfs = StringVar()
        self.dbgs = StringVar()
        self.edbgs = StringVar()
        self.scale = IntVar()
        self.scale_erofs = IntVar()
        self.spatchvb = IntVar()
        self.delywj = IntVar()
        self.ext4_method = StringVar()
        self.lg = list_
        self.erofsext4 = IntVar()
        lf1 = ttk.LabelFrame(self, text=lang.text43)
        lf1.pack(fill=BOTH, padx=5, pady=5)
        lf2 = ttk.LabelFrame(self, text=lang.text44)
        lf2.pack(fill=BOTH, padx=5, pady=5)
        lf3 = ttk.LabelFrame(self, text=lang.text45)
        lf3.pack(fill=BOTH, padx=5, pady=5)
        lf4 = ttk.LabelFrame(self, text=lang.text46)
        lf4.pack(fill=BOTH, pady=5, padx=5)
        (sf1 := Frame(lf3)).pack(fill=X, padx=5, pady=5, side=TOP)
        self.scale.set(0)
        # EXT4 Settings
        Label(lf1, text=lang.text48).pack(side='left', padx=5, pady=5)
        dbfss = ttk.Combobox(lf1, state="readonly", values=("make_ext4fs", "mke2fs+e2fsdroid"), textvariable=self.dbfs)
        dbfss.pack(side='left', padx=5, pady=5)
        Label(lf1, text=lang.t31).pack(side='left', padx=5, pady=5)
        (t := ttk.Combobox(lf1, state="readonly", values=(lang.t32, lang.t33), textvariable=self.ext4_method)).pack(
            side='left', padx=5, pady=5)
        t.current(0)
        #
        Label(lf3, text=lang.text49).pack(side='left', padx=5, pady=5)
        dbgss = ttk.Combobox(lf3, state="readonly", textvariable=self.dbgs, values=("raw", "sparse", "br", "dat"))
        dbgss.pack(padx=5, pady=5, side='left')
        Label(lf2, text=lang.text50).pack(side='left', padx=5, pady=5)
        edbgss = ttk.Combobox(lf2, state="readonly", textvariable=self.edbgs)
        edbgss.pack(side='left', padx=5, pady=5)
        edbgss['value'] = ("lz4", "lz4hc", "lzma", "deflate")
        # --
        scales_erofs = ttk.Scale(lf2, from_=0, to=9, orient="horizontal", command=self.update_label_erofs,
                                 variable=self.scale_erofs)
        self.label_e = tk.Label(lf2, text=lang.t30.format(int(scales_erofs.get())))
        self.label_e.pack(side='left', padx=5, pady=5)
        scales_erofs.pack(fill="x", padx=5, pady=5)
        # --
        scales = ttk.Scale(sf1, from_=0, to=9, orient="horizontal", command=self.update_label, variable=self.scale)
        self.label = tk.Label(sf1, text=lang.text47.format(int(scales.get())))
        self.label.pack(side='left', padx=5, pady=5)
        scales.pack(fill="x", padx=5, pady=5)
        ttk.Checkbutton(lf3, text=lang.text52, variable=self.spatchvb, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)
        ttk.Checkbutton(lf3, text=lang.t11, variable=self.delywj, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)
        ttk.Checkbutton(lf3, text=lang.t34, variable=self.erofsext4, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)
        dbfss.current(0)
        dbgss.current(0)
        edbgss.current(0)
        ttk.Button(self, text=lang.pack, command=lambda: cz(self.start_)).pack(side='left', padx=2, pady=2,
                                                                               fill=X,
                                                                               expand=True)
        ttk.Button(self, text=lang.cancel, command=lambda: self.destroy()).pack(side='left', padx=2,
                                                                                pady=2,
                                                                                fill=X,
                                                                                expand=True)
        jzxs(self)

    def update_label(self, value):
        self.label.config(text=lang.text47.format(int(float(value))))

    def update_label_erofs(self, value):
        self.label_e.config(text=lang.t30.format(int(float(value))))

    def start_(self):
        lg = self.lg
        self.destroy()
        packrom(self.edbgs, self.dbgs, self.dbfs, self.scale, lg, self.spatchvb, self.delywj.get(),
                int(self.scale_erofs.get()), self.ext4_method.get(), self.erofsext4.get())


@cartoon
class dbkxyt:
    def __init__(self):
        if not dn.get():
            win.messpop(lang.warn1)
            return
        if os.path.exists((dir_ := rwork()) + "firmware-update"):
            os.rename(dir_ + "firmware-update", dir_ + "images")
        if not os.path.exists(dir_ + "images"):
            os.makedirs(dir_ + 'images')
        if os.path.exists(dir_ + 'META-INF'):
            rmdir(dir_ + 'META-INF')
        zipfile.ZipFile(elocal + os.sep + "bin" + os.sep + "extra_flash.zip").extractall(dir_)
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
                    print("Add Flash method {} to update-binary".format(t))
                    if os.path.getsize(os.path.join(dir_ + 'images', t)) > 209715200:
                        self.zstd_compress(os.path.join(dir_ + 'images', t))
                        lines.insert(add_line,
                                     'package_extract_zstd "images/{}.zst" "/dev/block/by-name/{}"\n'.format(t, t[:-4]))
                    else:
                        lines.insert(add_line,
                                     'package_extract_file "images/{}" "/dev/block/by-name/{}"\n'.format(t, t[:-4]))
            for t in os.listdir(dir_):
                if not t.startswith("preloader_") and not os.path.isdir(dir_ + t) and t.endswith('.img'):
                    print("Add Flash method {} to update-binary".format(t))
                    if os.path.getsize(dir_ + t) > 209715200:
                        self.zstd_compress(dir_ + t)
                        move(os.path.join(dir_, t + ".zst"), os.path.join(dir_ + "images", t + ".zst"))
                        lines.insert(add_line,
                                     'package_extract_zstd "images/{}.zst" "/dev/block/by-name/{}"\n'.format(t, t[:-4]))
                    else:
                        lines.insert(add_line,
                                     'package_extract_file "images/{}" "/dev/block/by-name/{}"\n'.format(t, t[:-4]))
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
                call("zstd -5 --rm {} -o {}".format(path, path + ".zst"))
            except Exception as e:
                print(f"[Fail] Compress {os.path.basename(path)} Fail:{e}")


class packss(Toplevel):
    def __init__(self):
        super().__init__()
        self.title(lang.text53)
        supers = IntVar()
        ssparse = IntVar()
        supersz = IntVar()
        sdbfz = StringVar()
        scywj = IntVar()
        (lf1 := ttk.LabelFrame(self, text=lang.text54)).pack(fill=BOTH)
        (lf2 := ttk.LabelFrame(self, text=lang.settings)).pack(fill=BOTH)
        (lf3 := ttk.LabelFrame(self, text=lang.text55)).pack(fill=BOTH)
        supersz.set(1)
        # 自动设置
        ttk.Radiobutton(lf1, text="A-only", variable=supersz, value=1).pack(side='left', padx=10, pady=10)
        ttk.Radiobutton(lf1, text="Virtual-ab", variable=supersz, value=2).pack(side='left', padx=10, pady=10)
        ttk.Radiobutton(lf1, text="A/B", variable=supersz, value=3).pack(side='left', padx=10, pady=10)
        Label(lf2, text=lang.text56).pack(side='left', padx=10, pady=10)
        (sdbfzs := ttk.Combobox(lf2, textvariable=sdbfz)).pack(side='left', padx=10, pady=10, fill='both')
        sdbfzs['value'] = ("qti_dynamic_partitions", "main")
        sdbfzs.current(0)
        Label(lf2, text=lang.text57).pack(side='left', padx=10, pady=10)
        supers.set(9126805504)
        (ttk.Entry(lf2, textvariable=supers)).pack(side='left', padx=10, pady=10)

        (tl := Listbox(lf3, selectmode=MULTIPLE, activestyle='dotbox')).config(highlightthickness=0)
        work = rwork()
        for file_name in os.listdir(work):
            if file_name.endswith(".img"):
                if gettype(work + file_name) in ["ext", "erofs"]:
                    tl.insert(END, file_name[:-4])
        tl.pack(padx=10, pady=10, fill=BOTH)

        ttk.Checkbutton(self, text=lang.text58, variable=ssparse, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=10, pady=10, fill=BOTH)
        t_frame = Frame(self)
        ttk.Checkbutton(t_frame, text=lang.t11, variable=scywj, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(side=LEFT,
                                                          padx=10, pady=10, fill=BOTH)
        g_b = ttk.Button(t_frame, text=lang.t27, command=lambda: cz(generate))
        g_b.pack(side=LEFT, padx=10, pady=10, fill=BOTH)
        t_frame.pack(fill=X)
        jzxs(self)

        def read_list():
            if os.path.exists(work + "dynamic_partitions_op_list"):
                try:
                    data = utils.dynamic_list_reader(work + "dynamic_partitions_op_list")
                except:
                    return
                if len(data) > 1:
                    fir, sec = data
                    if fir[:-2] == sec[:-2]:
                        sdbfz.set(fir[:-2])
                        supersz.set(2)
                        supers.set(int(data[fir]['size']))
                else:
                    dbfz, = data
                    sdbfz.set(dbfz)
                    supers.set(int(data[dbfz]['size']))
                    supersz.set(1)

        def versize():
            size = sum(
                [os.path.getsize(work + i + ".img") for i in [tl.get(index) for index in tl.curselection()]]) + 409600
            diff_size = size
            if size > supers.get():
                for i in range(20):
                    if not i:
                        continue
                    i = i - 0.5
                    t = 1024 * 1024 * 1024 * i - size
                    if t < 0:
                        continue
                    if t < diff_size:
                        diff_size = t
                    else:
                        size = i * 1024 * 1024 * 1024
                        break
                supers.set(int(size))
                return False
            else:
                return True

        def generate():
            g_b.config(text=lang.t28, state='disabled')
            utils.generate_dynamic_list(dbfz=sdbfz.get(), size=supers.get(), set_=supersz.get(),
                                        lb=[tl.get(index) for index in tl.curselection()], work=rwork())
            g_b.config(text=lang.text34)
            time.sleep(1)
            g_b.config(text=lang.t27, state='normal')

        def start_():
            try:
                supers.get()
            except:
                supers.set(0)
            if not versize():
                ask_win(lang.t10)
                return False
            lbs = [tl.get(index) for index in tl.curselection()]
            sc = scywj.get()
            self.destroy()
            packsuper(sparse=ssparse, dbfz=sdbfz, size=supers, set_=supersz, lb=lbs, del_=sc)

        ttk.Button(self, text=lang.pack, command=lambda: cz(start_)).pack(side='left',
                                                                          padx=5,
                                                                          pady=5, fill=X, expand=True)
        ttk.Button(self, text=lang.cancel, command=lambda: self.destroy()).pack(side='left', padx=10, pady=10,
                                                                                fill=X,
                                                                                expand=True)
        read_list()


@cartoon
def packsuper(sparse, dbfz, size, set_, lb, del_=0, return_cmd=0):
    if not dn.get():
        win.messpop(lang.warn1)
        return False
    work = rwork()
    command = "lpmake --metadata-size 65536 -super-name super -metadata-slots "
    if set_.get() == 1:
        command += "2 -device super:%s --group %s:%s " % (size.get(), dbfz.get(), size.get())
        for part in lb:
            command += "--partition %s:readonly:%s:%s --image %s=%s.img " % (
                part, os.path.getsize(work + part + ".img"), dbfz.get(), part, work + part)
    else:
        command += "3 -device super:%s --group %s_a:%s " % (size.get(), dbfz.get(), size.get())
        for part in lb:
            command += "--partition %s_a:readonly:%s:%s_a --image %s_a=%s.img " % (
                part, os.path.getsize(work + part + ".img"), dbfz.get(), part, work + part)
        command += "--group %s_b:%s " % (dbfz.get(), size.get())
        for part in lb:
            command += "--partition %s_b:readonly:0:%s_b " % (part, dbfz.get())
        if set_.get() == 2:
            command += "--virtual-ab "
    if sparse.get() == 1:
        command += "--sparse "
    command += " --out %s" % (work + "super.img")
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
            win.messpop(lang.warn10)
    else:
        win.messpop(lang.warn10)


class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_space = text_widget

    def write(self, string):
        self.text_space.insert(END, string)
        self.text_space.yview('end')

    def flush(self):
        ...


def call(exe, kz='Y', out=0, shstate=False, sp=0):
    cmd = f'{tool_bin}{exe}' if kz == "Y" else exe
    if os.name != 'posix':
        conf = subprocess.CREATE_NO_WINDOW
    else:
        if sp == 0:
            cmd = shlex.split(cmd)
        conf = 0
    try:
        ret = subprocess.Popen(cmd, shell=shstate, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=conf)
        for i in iter(ret.stdout.readline, b""):
            if out == 0:
                try:
                    out_put = i.decode("utf-8").strip()
                except:
                    out_put = i.decode("gbk").strip()
                print(out_put)
    except subprocess.CalledProcessError as e:
        ret = lambda: print(f"Error!{exe}")
        ret.returncode = 114514
        for i in iter(e.stdout.readline, b""):
            if out == 0:
                try:
                    out_put = i.decode("utf-8").strip()
                except:
                    out_put = i.decode("gbk").strip()
                print(out_put)
    ret.wait()
    return ret.returncode


def download_api(url, path=None):
    start_time = time.time()
    response = requests.Session().head(url)
    file_size = int(response.headers.get("Content-Length", 0))
    response = requests.Session().get(url, stream=True, verify=False)
    with open((settings.path if path is None else path) + os.sep + os.path.basename(url), "wb") as f:
        chunk_size = 2048576
        bytes_downloaded = 0
        for data in response.iter_content(chunk_size=chunk_size):
            f.write(data)
            bytes_downloaded += len(data)
            elapsed = time.time() - start_time
            speed = bytes_downloaded / (1024 * elapsed)
            percentage = int(bytes_downloaded * 100 / file_size)
            yield percentage, speed, bytes_downloaded, file_size, elapsed


def download_file():
    var1 = IntVar()
    down = win.getframe(lang.text61 + os.path.basename(url := input_(title=lang.text60)))
    win.messpop(lang.text62, "green")
    progressbar = tk.ttk.Progressbar(down, length=200, mode="determinate")
    progressbar.pack(padx=10, pady=10)
    var1.set(0)
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
        except:
            if os.access(os.path.basename(url), os.F_OK):
                print(lang.text67 + os.path.basename(url))
            else:
                try:
                    down.destroy()
                except Exception as e:
                    win.messpop("%s" % e)
                win.messpop(lang.text68, "red")


@cartoon
def jboot(bn: str = 'boot'):
    if not (boot := findfile(f"{bn}.img", (work := rwork()))):
        print(lang.warn3.format(bn))
        return
    if not os.path.exists(boot):
        win.messpop(lang.warn3.format(bn))
        return
    if os.path.exists(work + f"{bn}"):
        if rmdir(work + f"{bn}") != 0:
            print(lang.text69)
            return
    re_folder(work + f"{bn}")
    os.chdir(work + f"{bn}")
    if call("magiskboot unpack -h %s" % boot) != 0:
        print("Unpack %s Fail..." % boot)
        os.chdir(elocal)
        rmtree((work + f"{bn}"))
        return
    if os.access(work + f"{bn}" + os.sep + "ramdisk.cpio", os.F_OK):
        comp = gettype(work + f"{bn}" + os.sep + "ramdisk.cpio")
        print("Ramdisk is %s" % comp)
        with open(work + f"{bn}" + os.sep + "comp", "w") as f:
            f.write(comp)
        if comp != "unknow":
            os.rename(work + f"{bn}" + os.sep + "ramdisk.cpio",
                      work + f"{bn}" + os.sep + "ramdisk.cpio.comp")
            if call("magiskboot decompress %s %s" % (
                    work + f"{bn}" + os.sep + "ramdisk.cpio.comp",
                    work + f"{bn}" + os.sep + "ramdisk.cpio")) != 0:
                print("Decompress Ramdisk Fail...")
                return
        if not os.path.exists(work + f"{bn}" + os.sep + "ramdisk"):
            os.mkdir(work + f"{bn}" + os.sep + "ramdisk")
        os.chdir(work + f"{bn}" + os.sep)
        print("Unpacking Ramdisk...")
        call("cpio -i -d -F %s -D %s" % ("ramdisk.cpio", "ramdisk"))
        os.chdir(elocal)
    else:
        print("Unpack Done!")
    os.chdir(elocal)


@cartoon
def dboot(nm: str = 'boot'):
    work = rwork()
    flag = ''
    boot = findfile(f"{nm}.img", work)
    if not os.path.exists(work + f"{nm}"):
        print(f"Cannot Find {nm}...")
        return
    cpio = findfile("cpio.exe" if os.name != 'posix' else 'cpio',
                    f'{elocal}{os.sep}bin{os.sep}{platform.system()}{os.sep}{platform.machine()}{os.sep}').replace(
        '\\', "/")

    if os.path.isdir(work + f"{nm}" + os.sep + "ramdisk"):
        os.chdir(work + f"{nm}" + os.sep + "ramdisk")
        call(exe="busybox ash -c \"find | sed 1d | %s -H newc -R 0:0 -o -F ../ramdisk-new.cpio\"" % cpio, sp=1,
             shstate=True)
        os.chdir(work + f"{nm}" + os.sep)
        with open(work + f"{nm}" + os.sep + "comp", "r", encoding='utf-8') as compf:
            comp = compf.read()
        print("Compressing:%s" % comp)
        if comp != "unknow":
            if call("magiskboot compress=%s ramdisk-new.cpio" % comp) != 0:
                print("Pack Ramdisk Fail...")
                os.remove("ramdisk-new.cpio")
                return
            else:
                print("Pack Ramdisk Successful..")
                try:
                    os.remove("ramdisk.cpio")
                except:
                    ...
                os.rename("ramdisk-new.cpio.%s" % comp.split('_')[0], "ramdisk.cpio")
        else:
            print("Pack Ramdisk Successful..")
            os.remove("ramdisk.cpio")
            os.rename("ramdisk-new.cpio", "ramdisk.cpio")
        if comp == "cpio":
            flag = "-n"
        ramdisk = True
    else:
        ramdisk = False
    if call("magiskboot repack %s %s" % (flag, boot)) != 0:
        print("Pack boot Fail...")
        return
    else:
        if ramdisk:
            os.remove(work + f"{nm}.img")
            os.rename(work + f"{nm}" + os.sep + "new-boot.img", work + f"{nm}.img")
        os.chdir(elocal)
        try:
            rmdir(work + f"{nm}")
        except:
            print(lang.warn11.format(nm))
        print("Pack Successful...")


@cartoon
def packrom(edbgs, dbgs, dbfs, scale, parts, spatch, *others) -> any:
    dely, erofs_level, ext4_size, erofsext4 = others
    if not dn.get():
        win.messpop(lang.warn1)
        return False
    elif not os.path.exists(settings.path + os.sep + dn.get()):
        win.messpop(lang.warn1, "red")
        return False
    parts_dict = json_edit((work := rwork()) + "config" + os.sep + "parts_info").read()
    for i in parts:
        dname = os.path.basename(i)
        if dname not in parts_dict.keys():
            parts_dict[dname] = 'unknow'
        if spatch == 1:
            for j in "vbmeta.img", "vbmeta_system.img", "vbmeta_vendor.img":
                file = findfile(j, work)
                if file:
                    if gettype(file) == 'vbmeta':
                        print(lang.text71 % file)
                        utils.vbpatch(file).disavb()
        if os.access(os.path.join(work + "config", "%s_fs_config" % dname), os.F_OK):
            if os.name == 'nt':
                try:
                    if folder := findfolder(work, "com.google.android.apps.nbu."):
                        call("mv {} {}".format(folder, folder.replace("com.google.android.apps.nbu.",
                                                                      "com.google.android.apps.nbu")))
                except Exception as e:
                    print(e)
            fspatch.main(work + dname, os.path.join(work + "config", dname + "_fs_config"))
            utils.qc(work + "config" + os.sep + dname + "_fs_config")
            contextpatch.main(work + dname, work + "config" + os.sep + dname + "_file_contexts")
            utils.qc(work + "config" + os.sep + dname + "_file_contexts")
            if erofsext4:
                if parts_dict[dname] == 'erofs':
                    parts_dict[dname] = 'ext'
                elif parts_dict[dname] == 'ext':
                    parts_dict[dname] = 'erofs'
            if parts_dict[dname] == 'erofs':
                mkerofs(dname, "%s" % (edbgs.get()), work, erofs_level)
                if dely == 1:
                    rdi(work, dname)
                print(lang.text3.format(dname))
                if dbgs.get() in ["dat", "br", "sparse"]:
                    call('img2simg {}.img {}.simg'.format(work + dname, work + dname))
                    if os.path.exists(work + dname + ".simg"):
                        os.remove(work + dname + ".img")
                        os.rename(work + dname + ".simg", work + dname + ".img")
                    if dbgs.get() == 'dat':
                        datbr(work, dname, "dat", int(parts_dict['dat_ver']))
                    elif dbgs.get() == 'br':
                        datbr(work, dname, scale.get(), int(parts_dict['dat_ver']))
                    else:
                        print(lang.text3.format(dname))
            else:
                ext4_size_value = 0
                if ext4_size == lang.t33:
                    if os.path.exists(work + "config" + os.sep + dname + "_size.txt"):
                        with open(work + "config" + os.sep + dname + "_size.txt", encoding='utf-8') as f:
                            ext4_size_value = int(f.read().strip())
                if dbgs.get() in ["dat", "br", "sparse"]:
                    make_ext4fs(dname, work, "-s", ext4_size_value) if dbfs.get() == "make_ext4fs" else mke2fs(dname,
                                                                                                               work,
                                                                                                               "y",
                                                                                                               ext4_size_value)
                    if dely == 1:
                        rdi(work, dname)
                    if not parts_dict.get('dat_ver'):
                        parts_dict['dat_ver'] = '4'
                    if dbgs.get() == "dat":
                        datbr(work, dname, "dat", int(parts_dict.get('dat_ver')))
                    elif dbgs.get() == "br":
                        datbr(work, dname, scale.get(), int(parts_dict.get('dat_ver')))
                    else:
                        print(lang.text3.format(dname))
                else:
                    make_ext4fs(dname, work, "", ext4_size_value) if dbfs.get() == "make_ext4fs" else mke2fs(dname,
                                                                                                             work, "n",
                                                                                                             ext4_size_value)
                    if dely == 1:
                        rdi(work, dname)
        elif parts_dict[i] in ['boot', 'vendor_boot']:
            dboot(i)
        elif parts_dict[i] == 'dtbo':
            padtbo()
        elif parts_dict[i] == 'logo':
            logopack()
        else:
            print(f"Unsupport {i}:{parts_dict[i]}")


def rdi(work, dname) -> any:
    if not os.listdir(work + "config"):
        rmtree(work + "config")
        return False
    if os.access(work + dname + ".img", os.F_OK):
        print(lang.text72 % dname)
        try:
            rmdir(work + dname)
            if os.access(work + "config" + os.sep + "%s_size.txt" % dname, os.F_OK):
                os.remove(work + "config" + os.sep + "%s_size.txt" % dname)
            os.remove(work + "config" + os.sep + "%s_file_contexts" % dname)
            os.remove(work + "config" + os.sep + "%s_fs_config" % dname)
        except Exception as e:
            print(lang.text73 % (dname, e))
        print(lang.text3.format(dname))
    else:
        win.messpop(lang.text75 % dname, "red")


def input_(title: str = lang.text76, text: str = "") -> str:
    (inputvar := StringVar()).set(text)
    input__ = Toplevel()
    input__.attributes('-topmost', 'true')
    input__.geometry("300x180")
    input__.resizable(False, False)
    input__.title(title)
    ttk.Entry(input__, textvariable=inputvar).pack(pady=5, padx=5, fill=BOTH)
    ttk.Button(input__, text=lang.ok, command=input__.destroy).pack(padx=5, pady=5, fill=BOTH, side='bottom')
    jzxs(input__)
    input__.wait_window()
    return inputvar.get()


def script2fs(path):
    if os.path.exists(os.path.join(path, "system", "app")):
        if not os.path.exists(path + os.sep + "config"):
            os.makedirs(path + os.sep + "config")
        extra.script2fs_context(findfile("updater-script", path + os.sep + "META-INF"), path + os.sep + "config", path)
        json_ = json_edit(os.path.join(path, "config", "parts_info"))
        parts = json_.read()
        for v in os.listdir(path):
            if os.path.exists(path + os.sep + "config" + os.sep + v + "_fs_config"):
                if v not in parts.keys():
                    parts[v] = 'ext'
        json_.write(parts)


@cartoon
def unpackrom(ifile) -> None:
    print(lang.text77 + (zip_src := ifile))
    if (ftype := gettype(ifile)) == "ozip":
        print(lang.text78 + ifile)
        ozipdecrypt.main(ifile)
        try:
            os.remove(ifile)
        except Exception as e:
            win.messpop(lang.warn11.format(e))
        zip_src = os.path.dirname(ifile) + os.sep + os.path.basename(ifile)[:-4] + "zip"
    elif os.path.splitext(ifile)[1] == '.ofp':
        if ask_win(lang.t12) == 1:
            ofp_mtk_decrypt.main(ifile, settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        else:
            ofp_qc_decrypt.main(ifile, settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
            script2fs(settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        try:
            unpackg.refs()
        except:
            ...
        return
    elif os.path.splitext(ifile)[1] == '.ops':
        args = {'decrypt': True,
                "<filename>": ifile,
                'outdir': os.path.join(settings.path, os.path.basename(ifile).split('.')[0])}
        opscrypto.main(args)
        try:
            unpackg.refs()
        except:
            ...
        return
    if gettype(zip_src) == 'zip':
        fz = zipfile.ZipFile(zip_src, 'r')
        for fi in fz.namelist():
            try:
                file_ = fi.encode('cp437').decode('gbk')
            except:
                try:
                    file_ = fi.encode('cp437').decode('utf-8')
                except:
                    file_ = fi
            print(lang.text79 + file_)
            try:
                fz.extract(fi, settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
                if fi != file_:
                    os.rename(os.path.join(settings.path, os.path.splitext(os.path.basename(zip_src))[0], fi),
                              os.path.join(settings.path, os.path.splitext(os.path.basename(zip_src))[0], file_))
            except Exception as e:
                print(lang.text80 % (file_, e))
                win.messpop(lang.warn4.format(file_))
            finally:
                ...
        print(lang.text81)
        if os.path.exists(os.path.join(settings.path, os.path.splitext(os.path.basename(zip_src))[0])):
            xmcd_.listdir()
            dn.set(os.path.splitext(os.path.basename(zip_src))[0])
        else:
            xmcd_.listdir()
        script2fs(settings.path + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        try:
            unpackg.refs()
        except:
            ...
        fz.close()
        return
    elif ftype != 'unknow':
        folder = os.path.join(settings.path, os.path.splitext(os.path.basename(ifile))[0] + v_code()) if os.path.exists(
            os.path.join(
                settings.path, os.path.splitext(os.path.basename(ifile))[0])) else os.path.join(settings.path,
                                                                                                os.path.splitext(
                                                                                                    os.path.basename(
                                                                                                        ifile))[0])
        try:
            os.mkdir(folder)
        except Exception as e:
            win.messpop(e)
        copy(ifile, str(folder))
        xmcd_.listdir()
        dn.set(os.path.basename(folder))
    else:
        print(lang.text82 % ftype)
    try:
        unpackg.refs()
    except:
        ...


def rwork() -> str:
    return os.path.join(settings.path, dn.get()) + os.sep


@cartoon
def unpack(chose, form: any = None):
    if not dn.get():
        win.messpop(lang.warn1)
        return False
    elif not os.path.exists(settings.path + os.sep + dn.get()):
        win.messpop(lang.warn1, "red")
        return False
    json_ = json_edit((work := rwork()) + "config" + os.sep + "parts_info")
    parts = json_.read()
    if os.access(work + "UPDATE.APP", os.F_OK):
        print(lang.text79 + "UPDATE.APP")
        splituapp.extract(work + "UPDATE.APP", "")
    if not chose:
        return 1
    if form == 'payload':
        print(lang.text79 + "payload")
        with open(work + "payload.bin", 'rb') as pay:
            try:
                mmap.mmap(pay.fileno(), 0, access=mmap.ACCESS_READ).close()
            except ValueError as e:
                print(e, "Use Old Method")
                payload_dumper.ota_payload_dumper(pay, work, 'old', chose)
            else:
                payload_dumper.ota_payload_dumper(mmap.mmap(pay.fileno(), 0, access=mmap.ACCESS_READ), work, 'old',
                                                  chose)
        if ask_win(lang.t9.format("payload.bin")) == 1:
            try:
                os.remove(work + "payload.bin")
            except Exception as e:
                print(lang.text72 + " payload.bin:%s" % e)
                os.remove(work + "payload.bin")
        return 1
    elif form == 'super':
        print(lang.text79 + f"Super")
        ftype = gettype(work + "super.img")
        if ftype == "sparse":
            print(lang.text79 + "super.img [%s]" % ftype)
            try:
                utils.simg2img(work + "super.img")
            except:
                win.messpop(lang.warn11.format("super.img"))
        if gettype(work + "super.img") == 'super':
            lpunpack.unpack(os.path.join(work, "super.img"), work, chose)
        return 1
    for i in chose:
        if os.access(work + i + ".zstd", os.F_OK):
            print(lang.text79 + i + ".zstd")
            call('zstd --rm -d ' + work + i + '.zstd')
            return
        if os.access(work + i + ".new.dat.br", os.F_OK):
            print(lang.text79 + i + ".new.dat.br")
            call("brotli -dj " + work + i + ".new.dat.br")
        if os.access(work + i + ".new.dat.1", os.F_OK):
            with open(work + i + ".new.dat", 'ab') as ofd:
                for n in range(100):
                    if os.access(work + i + f".new.dat.{n}", os.F_OK):
                        print(lang.text83 % (i + f".new.dat.{n}", i + f".new.dat"))
                        with open(work + i + f".new.dat.{n}", 'rb') as fd:
                            ofd.write(fd.read())
                        os.remove(work + i + f".new.dat.{n}")
        if os.access(work + i + ".new.dat", os.F_OK):
            print(lang.text79 + work + i + ".new.dat")
            if os.path.getsize(work + i + ".new.dat") != 0:
                transferpath = os.path.abspath(os.path.dirname(work)) + os.sep + i + ".transfer.list"
                if os.access(transferpath, os.F_OK):
                    parts['dat_ver'] = sdat2img(transferpath, work + i + ".new.dat", work + i + ".img").version
                    if os.access(work + i + ".img", os.F_OK):
                        os.remove(work + i + ".new.dat")
                        os.remove(transferpath)
                        try:
                            os.remove(work + i + '.patch.dat')
                        except:
                            ...
                    else:
                        print("transferpath" + lang.text84)
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
                logodump(i)
            if gettype(work + i + ".img") == 'vbmeta':
                print(f"{lang.text85}AVB:{i}")
                utils.vbpatch(work + i + ".img").disavb()
            ftype = gettype(work + i + ".img")
            if ftype == "sparse":
                print(lang.text79 + i + ".img [%s]" % ftype)
                try:
                    utils.simg2img(work + i + ".img")
                except:
                    win.messpop(lang.warn11.format(i + ".img"))
            if i not in parts.keys():
                parts[i] = gettype(work + i + ".img")
            if gettype(work + i + ".img") == 'super':
                print(lang.text79 + i + ".img")
                if gettype(work + i + ".img") == "sparse":
                    try:
                        utils.simg2img(work + i + ".img")
                    except:
                        win.messpop(lang.warn11.format(i))
                lpunpack.unpack(work + i + ".img", work)
                if os.access(work + "system_a.img", os.F_OK):
                    for wjm in os.listdir(work):
                        if wjm.endswith('_a.img'):
                            os.rename(work + wjm, work + wjm.replace('_a', ''))
                        if wjm.endswith('_b.img'):
                            if os.path.getsize(work + wjm) == 0:
                                os.remove(work + wjm)
            if (ftype := gettype(work + i + ".img")) == "ext":
                print(lang.text79 + i + ".img [%s]" % ftype)
                try:
                    imgextractor.Extractor().main(work + i + ".img", work + i, work)
                except Exception as e:
                    print(f"Unpack Fail..{e}")
                    continue
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except Exception as e:
                        win.messpop(lang.warn11.format(i + ".img:" + e))
            if ftype == "erofs":
                print(lang.text79 + i + ".img [%s]" % ftype)
                if call(exe="extract.erofs -i " + settings.path + os.sep + dn.get() + os.sep + i + ".img -o " + work + " -x",
                        out=1) != 0:
                    print(f'Unpack Fail...')
                    continue
                if os.path.exists(work + i):
                    try:
                        os.remove(work + i + ".img")
                    except:
                        win.messpop(lang.warn11.format(i + ".img"))
    if not os.path.exists(work + "config"):
        os.makedirs(work + "config")
    json_.write(parts)
    parts.clear()
    print(lang.text8)


def ask_win(text='', ok=lang.ok, cancel=lang.cancel) -> int:
    value = IntVar()
    ask = Toplevel()
    ask.resizable(False, False)
    ask.attributes('-topmost', 'true')
    ttk.Label(ask, text=text, font=(None, 20)).pack()
    ttk.Button(ask, text=ok, command=lambda: close_ask(1)).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                expand=True)
    ttk.Button(ask, text=cancel, command=lambda: close_ask(0)).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                    expand=True)

    def close_ask(value_=1):
        value.set(value_)
        ask.destroy()

    jzxs(ask)
    ask.lift()
    ask.wait_window()
    return value.get()


class dirsize:
    # get-command
    # 1 - retun True value of dir size
    # 2 - return Rsize value of dir size
    # 3 - return Rsize value of dir size and modify dynampic_partition_list
    def __init__(self, dir_: str, num: int = 1, get: int = 2, list_f: str = None):
        self.rsize_v: int
        self.num = num
        self.get = get
        self.list_f = list_f
        self.dname = os.path.basename(dir_)
        self.size = 0
        for root, dirs, files in os.walk(dir_):
            self.size += sum([os.path.getsize(os.path.join(root, name)) for name in files if
                              not os.path.islink(os.path.join(root, name))])
        if self.get == 1:
            self.rsize_v = self.size
        elif self.get in [2, 3]:
            self.rsize(self.size, self.num)
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
            if size_ <= 2684354560:
                bs = 1.0758
            if size_ <= 1073741824:
                bs = 1.0858
            if size_ <= 536870912:
                bs = 1.0958
            if size_ <= 104857600:
                bs = 1.1158
            else:
                bs = 1.1258
        print(f"Multiple:{bs}")
        if self.get == 3:
            self.rsizelist(self.dname, int(size_ * bs), self.list_f)
        self.rsize_v = int(size_ * bs / num)

    @staticmethod
    def rsizelist(dname, size, file):
        if os.access(file, os.F_OK):
            print(lang.text74 % (dname, size))
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(file, 'w', encoding='utf-8', newline='\n') as ff:
                content = re.sub("resize {} \\d+".format(dname),
                                 "resize {} {}".format(dname, size), content)
                content = re.sub("resize {}_a \\d+".format(dname),
                                 "resize {}_a {}".format(dname, size), content)
                content = re.sub("# Grow partition {} from 0 to \\d+".format(dname),
                                 "# Grow partition {} from 0 to {}".format(dname, size),
                                 content)
                content = re.sub("# Grow partition {}_a from 0 to \\d+".format(dname),
                                 "# Grow partition {}_a from 0 to {}".format(dname, size), content)
                ff.write(content)


@cartoon
def datbr(work, name, brl: any, dat_ver=None):
    if not dat_ver:
        dat_ver = 4
    print(lang.text86 % (name, name))
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
        print(lang.text88 % name)
        call("brotli -q {} -j -w 24 {} -o {}".format(brl, work + name + ".new.dat", work + name + ".new.dat.br"))
        if os.access(work + name + ".new.dat", os.F_OK):
            try:
                os.remove(work + name + ".new.dat")
            except Exception as e:
                print(e)
        print(lang.text89 % name)


def mkerofs(name, format_, work, level):
    print(lang.text90 % (name, format_ + f',{level}', "1.x"))
    extra_ = f'{format_},{level}' if format_ != 'lz4' else f'{format_}'
    cmd = f"mkfs.erofs -z{extra_} -T {int(time.time())} --mount-point=/{name} --product-out={work} --fs-config-file={work}config{os.sep}{name}_fs_config --file-contexts={work}config{os.sep}{name}_file_contexts {work + name}.img {work + name + os.sep}"
    call(cmd)


@cartoon
def make_ext4fs(name, work, sparse, size=0):
    print(lang.text91 % name)
    if not size:
        size = dirsize(work + name, 1, 3, work + "dynamic_partitions_op_list").rsize_v
    call(
        f"make_ext4fs -J -T {int(time.time())} {sparse} -S {work}config{os.sep}{name}_file_contexts -l {size} -C {work}config{os.sep}{name}_fs_config -L {name} -a {name} {work + name}.img {work + name}")


def mke2fs(name, work, sparse, size=0):
    print(lang.text91 % name)
    size = dirsize(work + name, 4096, 3, work + "dynamic_partitions_op_list").rsize_v if not size else size / 4096
    if call(
            f"mke2fs -O ^has_journal -L {name} -I 256 -M /{name} -m 0 -t ext4 -b 4096 {work + name}_new.img {int(size)}") != 0:
        rmdir(f'{work + name}_new.img')
        print(lang.text75 % name)
        return False
    if call(
            f"e2fsdroid -e -T {int(time.time())} -S {work}config{os.sep}{name}_file_contexts -C {work}config{os.sep}{name}_fs_config -a /{name} -f {work + name} {work + name}_new.img") != 0:
        rmdir(f'{work + name}_new.img')
        print(lang.text75 % name)
        return False
    if sparse == "y":
        call(f"img2simg {work + name}_new.img {work + name}.img")
        try:
            os.remove(work + name + "_new.img")
        except:
            ...
    else:
        if os.path.isfile(work + name + ".img"):
            try:
                os.remove(work + name + ".img")
            except:
                ...
        os.rename(work + name + "_new.img", work + name + ".img")


@cartoon
def rmdir(path):
    if not path:
        win.messpop(lang.warn1)
    else:
        print(lang.text97 + f'{os.path.basename(path)}')
        try:
            try:
                rmtree(f'{path}')
            except:
                call(f'busybox rm -rf {path}')
        except:
            print(lang.warn11.format(path))
        win.messpop(lang.warn11.format(path)) if os.path.exists(path) else print(lang.text98 + path)


def get_all_file_paths(directory) -> Ellipsis:
    for root, directories, files in os.walk(directory):
        for filename in files:
            yield os.path.join(root, filename)


@cartoon
class zip_file:
    def __init__(self, file, dst_dir, path=None):
        if not path:
            path = settings.path + os.sep
        os.chdir(dst_dir)
        with zipfile.ZipFile(relpath := path + file, 'w', compression=zipfile.ZIP_DEFLATED) as zip_:
            # 遍历写入文件
            for file in get_all_file_paths('.'):
                print(f"{lang.text1}:%s" % file)
                try:
                    zip_.write(file)
                except Exception as e:
                    print(lang.text2.format(file, e))
        if os.path.exists(relpath):
            print(lang.text3.format(relpath))
        os.chdir(elocal)


@cartoon
def packzip():
    if not dn.get():
        win.messpop(lang.warn1)
    else:
        print(lang.text91 % dn.get())
        if ask_win(lang.t25) == 1:
            dbkxyt()
        zip_file(dn.get() + ".zip", settings.path + os.sep + dn.get())


def dndfile(files):
    for fi in files:
        try:
            fi = fi.decode('gbk')
        except:
            fi = fi
        if os.path.exists(fi):
            if os.path.basename(fi).endswith(".mpk"):
                Installmpk(fi)
            elif os.path.basename(fi).endswith(".mps"):
                Process(fi)
            else:
                cz(unpackrom, fi)
        else:
            print(fi + lang.text84)


class xmcd(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text12)
        self.pack(padx=5, pady=5)

    @staticmethod
    def selectp():
        print(lang.text96 + dn.get())
        if ' ' in dn.get():
            print(lang.t29 + dn.get())

    def gui(self):
        self.LB1 = ttk.Combobox(self, textvariable=dn, state='readonly')
        self.LB1.pack(side="top", padx=10, pady=10, fill=X)
        self.LB1.bind('<<ComboboxSelected>>', lambda *x: self.selectp())
        ttk.Button(self, text=lang.text23, command=self.listdir).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text115, command=self.newp).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text116, command=lambda: cz(self.delwork)).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text117, command=lambda: cz(self.cmm)).pack(side="left", padx=10, pady=10)

    def listdir(self):
        array = []
        for f in os.listdir(settings.path + os.sep + "."):
            if os.path.isdir(settings.path + os.sep + f) and f != 'bin' and not f.startswith('.'):
                array.append(f)
        if not array:
            dn.set("")
            self.LB1["value"] = array
            self.LB1.current()
        else:
            self.LB1["value"] = array
            self.LB1.current(0)

    def cmm(self):
        if not dn.get():
            print(lang.warn1)
            return
        if os.path.exists(settings.path + os.sep + (inputvar := input_(lang.text102 + dn.get(), dn.get()))):
            print(lang.text103)
            return False
        if inputvar != dn.get():
            os.rename(settings.path + os.sep + dn.get(), settings.path + os.sep + inputvar)
            self.listdir()
        else:
            print(lang.text104)

    def delwork(self):
        win.messpop(lang.warn1) if not dn.get() else rmdir(settings.path + os.sep + dn.get())
        self.listdir()

    def newp(self):
        if not (inputvar := input_()):
            win.messpop(lang.warn12)
        else:
            print(lang.text99 % inputvar)
            os.mkdir(settings.path + os.sep + inputvar)
        self.listdir()


class frame3(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text112)
        self.pack(padx=5, pady=5)

    def gui(self):
        ttk.Button(self, text=lang.text122, command=lambda: cz(packzip)).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text123, command=lambda: cz(packss)).pack(side="left", padx=10, pady=10)
        ttk.Button(self, text=lang.text19, command=lambda: win.notepad.select(win.tab7)).pack(side="left", padx=10,
                                                                                              pady=10)
        ttk.Button(self, text=lang.t13, command=lambda: cz(format_conversion)).pack(side="left", padx=10, pady=10)


class unpack_gui(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text9)

    def gui(self):
        self.pack(padx=5, pady=5)
        self.ch = IntVar()
        self.ch.set(1)
        self.fm = ttk.Combobox(self, state="readonly",
                               values=('new.dat.br', "new.dat", 'img', 'zstd', 'payload', 'super'))
        self.lsg = Listbox(self, activestyle='dotbox', selectmode=MULTIPLE, highlightthickness=0)
        self.menu = Menu(self.lsg, tearoff=False, borderwidth=0)
        self.menu.add_command(label="属性" , command=self.info)
        self.lsg.bind('<Button-3>', self.show_menu)
        self.fm.current(0)
        self.fm.bind("<<ComboboxSelected>>", self.refs)

        self.lsg.pack(padx=5, pady=5, fill=X, side='top')
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=50, fill=X)
        ff1 = ttk.Frame(self)
        ttk.Radiobutton(ff1, text=lang.unpack, variable=self.ch,
                        value=1).pack(padx=5, pady=5, side='left')
        ttk.Radiobutton(ff1, text=lang.pack, variable=self.ch,
                        value=0).pack(padx=5, pady=5, side='left')
        ff1.pack(padx=5, pady=5, fill=X)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=50, fill=X)
        self.fm.pack(padx=5, pady=5, fill=Y, side='left')
        ttk.Button(self, text=lang.run, command=lambda: cz(self.close_)).pack(padx=5, pady=5, side='left')
        self.refs()
        self.ch.trace("w", lambda *x: self.hd())

    def show_menu(self, event):
        if self.lsg.curselection().__len__() == 1 and self.fm.get() == 'img':
            self.menu.post(event.x_root, event.y_root)

    def info(self):
        ck_ = Toplevel()
        jzxs(ck_)
        ck_.title("属性")
        f_path = os.path.join(rwork(), [self.lsg.get(index) for index in self.lsg.curselection()][0]+".img")
        if not os.path.exists(f_path):
            print("文件不存在")
            ck_.destroy()
        f_type = gettype(f_path)
        if f_type == 'ext':
            info = [["路径" , f_path], ['类型', f_type,]]
            with open(f_path, 'rb') as e:
                t = ext4.Volume(e)
                data = t.get_info_list
            for i in data:
                info.append(i)
        else:
            info = [["路径" , f_path], ['类型', f_type,]]
        scroll = ttk.Scrollbar(ck_, orient=VERTICAL)
        columns = ['信息', '参数']
        table = ttk.Treeview(master=ck_,height=10,columns=columns,show='headings',yscrollcommand=scroll.set)
        for column in columns:
            table.heading(column=column, text=column, anchor=CENTER)
            table.column(column=column, anchor=CENTER, )
        scroll.config(command=table.yview)
        scroll.pack(side=RIGHT, fill=Y)
        table.pack(fill=BOTH, expand=True)
        for index, data in enumerate(info):
            table.insert('', END, values=data)
        ttk.Button(ck_, text="确定",command=ck_.destroy).pack(padx=5, pady=5)

    def hd(self):
        if self.ch.get() == 1:
            self.fm.configure(state='readonly')
            self.refs(None)
        else:
            self.fm.configure(state="disabled")
            self.refs2()

    def refs(self, N=None):
        self.lsg.delete(0, END)
        if not os.path.exists(work := rwork()):
            win.messpop(lang.warn1)
            return False
        if not self.fm.get() in ['payload', 'super']:
            for file_name in os.listdir(work):
                if file_name.endswith(self.fm.get()):
                    self.lsg.insert(END, file_name.split("." + self.fm.get())[0])
        elif self.fm.get() == 'payload':
            if os.path.exists(work + "payload.bin"):
                with open(work + "payload.bin", 'rb') as pay:
                    for i in payload_dumper.ota_payload_dumper(pay, work, 'old', '',
                                                               0):
                        self.lsg.insert(END, i.partition_name)
        elif self.fm.get() == 'super':
            if os.path.exists(work + "super.img"):
                data = lpunpack.get_parts(work + "super.img")
                if len(data):
                    for i in data:
                        self.lsg.insert(END, i)

    def refs2(self):
        self.lsg.delete(0, END)
        if not os.path.exists(work := rwork()):
            win.messpop(lang.warn1)
            return False
        parts_dict = json_edit(work + "config" + os.sep + "parts_info").read()
        for folder in os.listdir(work):
            if os.path.isdir(work + folder) and folder in parts_dict.keys():
                self.lsg.insert(END, folder)

    def close_(self):
        lbs = [self.lsg.get(index) for index in self.lsg.curselection()]
        self.hd()
        if self.ch.get() == 1:
            unpack(lbs, self.fm.get())
            self.refs()
        else:
            packxx(lbs)


if int(settings.oobe) < 4:
    welcome()
win.gui()
unpackg = unpack_gui()
xmcd_ = xmcd()
xmcd_.gui()
unpackg.gui()
frame3().gui()
xmcd_.listdir()


class format_conversion(Toplevel):
    def __init__(self):
        super().__init__()
        self.resizable(False, False)
        self.title(lang.t13)
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
        self.list_b = Listbox(self, highlightthickness=0, activestyle='dotbox', selectmode=MULTIPLE)
        self.list_b.pack(padx=5, pady=5, fill=BOTH)
        self.relist()
        ttk.Button(self, text=lang.ok, command=lambda: cz(self.conversion)).pack(side=BOTTOM, fill=BOTH)
        jzxs(self)

    def relist(self):
        work = rwork()
        self.list_b.delete(0, "end")
        if self.h.get() == "br":
            for i in self.refile(".new.dat.br"):
                self.list_b.insert('end', i)
        elif self.h.get() == 'dat':
            for i in self.refile(".new.dat"):
                self.list_b.insert('end', i)
        elif self.h.get() == 'sparse':
            for i in os.listdir(work):
                if os.path.isfile(work + i) and gettype(work + i) == 'sparse':
                    self.list_b.insert('end', i)
        elif self.h.get() == 'raw':
            for i in os.listdir(work):
                if os.path.isfile(work + i):
                    if gettype(work + i) in ['ext', 'erofs', 'super']:
                        self.list_b.insert('end', i)

    @staticmethod
    def refile(f):
        for i in os.listdir(work := rwork()):
            if i.endswith(f):
                if os.path.isfile(work + i):
                    yield i

    @cartoon
    def conversion(self):
        work = rwork()
        fget = self.f.get()
        hget = self.h.get()
        selection = [self.list_b.get(index) for index in self.list_b.curselection()]
        self.destroy()
        if fget == hget:
            ...
        elif fget == 'sparse':
            for i in selection:
                print(f'[{hget}->{fget}]{i}')
                dname = os.path.basename(i).split('.')[0]
                if hget == 'br':
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + i)
                        call("brotli -dj " + work + i)
                if hget == 'dat':
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + work + i)
                        if os.path.getsize(work + i) != 0:
                            transferpath = os.path.abspath(os.path.dirname(work)) + os.sep + dname + ".transfer.list"
                            if os.access(transferpath, os.F_OK):
                                sdat2img(transferpath, work + i, work + dname + ".img")
                                if os.access(work + dname + ".img", os.F_OK):
                                    os.remove(work + i)
                                    os.remove(transferpath)
                                    try:
                                        os.remove(work + dname + '.patch.dat')
                                    except:
                                        ...
                            else:
                                print("transferpath" + lang.text84)
                    if os.path.exists(work + dname + '.img'):
                        call('img2simg {} {}'.format(work + i, work + i + 's'))
                        if os.path.exists(work + i + 's'):
                            try:
                                os.remove(work + i)
                                os.rename(work + i + 's', work + i)
                            except Exception as e:
                                print(e)
        elif fget == 'raw':
            for i in selection:
                print(f'[{hget}->{fget}]{i}')
                dname = os.path.basename(i).split('.')[0]
                if hget == 'br':
                    if os.access(work + i, os.F_OK):
                        print(lang.text79 + i)
                        call("brotli -dj " + work + i)
                if hget in ['dat', 'br']:
                    if os.path.exists(work):
                        if hget == 'br':
                            i = i.replace('.br', '')
                        print(lang.text79 + work + i)
                        if os.path.getsize(work + i) != 0:
                            transferpath = os.path.abspath(os.path.dirname(work)) + os.sep + dname + ".transfer.list"
                            if os.access(transferpath, os.F_OK):
                                sdat2img(transferpath, work + i, work + dname + ".img")
                                if os.access(work + dname + ".img", os.F_OK):
                                    try:
                                        os.remove(work + i)
                                        os.remove(transferpath)
                                        os.remove(work + dname + '.patch.dat')
                                    except:
                                        ...
                            else:
                                print("transferpath" + lang.text84)
                if hget == 'sparse':
                    utils.simg2img(work + i)
        elif fget == 'dat':
            for i in selection:
                print(f'[{hget}->{fget}]{i}')
                if hget == 'raw':
                    call('img2simg {} {}'.format(work + i, work + i + 's'))
                    if os.path.exists(work + i + 's'):
                        try:
                            os.remove(work + i)
                            os.rename(work + i + 's', work + i)
                        except Exception as e:
                            print(e)
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], "dat")
                if hget == 'br':
                    print(lang.text79 + i)
                    call("brotli -dj " + work + i)

        elif fget == 'br':
            for i in selection:
                print(f'[{hget}->{fget}]{i}')
                if hget == 'raw':
                    call('img2simg {} {}'.format(work + i, work + i + 's'))
                    if os.path.exists(work + i + 's'):
                        try:
                            os.remove(work + i)
                            os.rename(work + i + 's', work + i)
                        except Exception as e:
                            print(e)
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], 0)
                if hget == 'dat':
                    print(lang.text88 % os.path.basename(i).split('.')[0])
                    call("brotli -q {} -j -w 24 {} -o {}".format(0, work + i,
                                                                 work + i + ".br"))
                    if os.access(work + i + '.br', os.F_OK):
                        try:
                            os.remove(work + i)
                        except Exception as e:
                            print(e)
        print(lang.text8)


cartoon.loadgif(Image.open(BytesIO(getattr(images, "loading_%s_byte" % (win.LB2.get())))))
cartoon.init()
print(lang.text108)
win.update()
jzxs(win)
print(lang.text134 % (dti() - start))
win.mainloop()
