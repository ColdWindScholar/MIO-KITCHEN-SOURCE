#!/usr/bin/env python3
import os
import json
import re
import shlex
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
from configparser import ConfigParser
import extra
from extra import *
import contextpatch


if os.name == 'nt':
    import windnd
import zipfile
from io import BytesIO, StringIO
from platform import machine
from random import randint, choice
from tkinter import *
from tkinter import filedialog, ttk, messagebox
from shutil import rmtree, copy
import requests
import sv_ttk
from PIL import Image, ImageTk
import fspatch
import img2sdat
import imgextractor
import lpunpack
import mkdtboimg
import ozipdecrypt
import payload_dumper
import sdat2img
import splituapp
import vbpatch
from timeit import default_timer as dti
import qc
import ofp_qc_decrypt
import ofp_mtk_decrypt
import editor

# 欢迎各位大佬提PR
config = ConfigParser()
elocal = os.getcwd()
setfile = elocal + os.sep + "bin" + os.sep + "setting.ini"
modfile = elocal + os.sep + "bin" + os.sep + "module" + os.sep + "module.json"
win = Tk()
start = dti()
win.title('OPEN-MIO-KITCHEN')
dn = StringVar()
theme = StringVar()
language = StringVar()
var1 = IntVar()
car = IntVar()
formats = ([b'PK', "zip"], [b'OPPOENCRYPT!', "ozip"], [b'7z', "7z"], [b'\x53\xef', 'ext', 1080],
           [b'\x3a\xff\x26\xed', "sparse"], [b'\xe2\xe1\xf5\xe0', "erofs", 1024], [b"CrAU", "payload"],
           [b"AVB0", "vbmeta"], [b'\xd7\xb7\xab\x1e', "dtbo"],
           [b'\xd0\x0d\xfe\xed', "dtb"], [b"MZ", "exe"], [b".ELF", 'elf'],
           [b"ANDROID!", "boot"], [b"VNDRBOOT", "vendor_boot"],
           [b'AVBf', "avb_foot"], [b'BZh', "bzip2"],
           [b'CHROMEOS', 'chrome'], [b'\x1f\x8b', "gzip"],
           [b'\x1f\x9e', "gzip"], [b'\x02\x21\x4c\x18', "lz4_legacy"],
           [b'\x03\x21\x4c\x18', 'lz4'], [b'\x04\x22\x4d\x18', 'lz4'],
           [b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\x03', "zopfli"], [b'\xfd7zXZ', 'xz'],
           [b']\x00\x00\x00\x04\xff\xff\xff\xff\xff\xff\xff\xff', 'lzma'], [b'\x02!L\x18', 'lz4_lg'],
           [b'\x89PNG', 'png'])


class ModuleError(Exception):
    pass


class jzxs(object):
    def __init__(self, master):
        self.master = master
        self.sf = self.master.after(20, self.set)

    def set(self):
        self.master.geometry('+{}+{}'.format(int(self.master.winfo_screenwidth() / 2 - self.master.winfo_width() / 2),
                                             int(self.master.winfo_screenheight() / 2 - self.master.winfo_height() / 2)))
        self.master.after_cancel(self.sf)


# 打包设置变量
class lang(object):
    pass


def load(name):
    if not name and not os.path.exists(elocal + os.sep + f'bin/languages/English.json'):
        error(1)
    elif not os.path.exists(elocal + os.sep + f'bin/languages/{name}.json'):
        with open(elocal + os.sep + 'bin/languages/English.json', 'r', encoding='utf-8') as f:
            _lang = json.load(f)
    else:
        with open(f'{elocal}{os.sep}bin/languages/{name}.json', 'r', encoding='utf-8') as f:
            _lang = json.load(f)
    for i in _lang:
        setattr(lang, i, _lang[i])


def error(code, desc="未知错误"):
    if not win:
        er = Tk()
    else:
        er = win
    er.protocol("WM_DELETE_WINDOW", sys.exit)
    er.title("启动错误")
    er.lift()
    er.resizable(False, False)
    jzxs(er)
    Label(er, text="错误代码：%s" % code).pack(padx=10, pady=10)
    te = Text(er)
    te.pack(padx=10, pady=10)
    te.insert('insert', desc)

    ttk.Button(er, text="确定", command=lambda: sys.exit(1)).pack(padx=10, pady=10)
    if not win:
        er.wait_window()
    else:
        er.mainloop()


class welcome(object):
    def __init__(self):
        self.ck = Toplevel()
        self.ck.title(lang.text135)
        self.ck.resizable(False, False)
        self.ck.protocol("WM_DELETE_WINDOW", self.clos)
        self.frame = None
        if oobe == "1":
            self.main()
        elif oobe == '2':
            self.license()
        elif oobe == '3':
            self.private()
        elif oobe == '4':
            self.done()
        else:
            ttk.Label(self.ck, text=lang.text135, font=("宋体", 40)).pack(padx=10, pady=10, fill=BOTH, expand=True)
            ttk.Separator(self.ck, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
            ttk.Label(self.ck, text=lang.text137, font=("宋体", 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)
            ttk.Button(self.ck, text=lang.text136, command=self.main).pack(fill=BOTH)

    def reframe(self):
        if self.frame:
            self.frame.destroy()
        self.frame = ttk.Frame(self.ck)
        self.frame.pack(expand=1, fill=BOTH)

    def main(self):
        setf("oobe", "1")
        for i in self.ck.winfo_children():
            i.destroy()
        self.reframe()
        ttk.Label(self.frame, text=lang.text129, font=("宋体", 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        LB3_ = ttk.Combobox(self.frame, state='readonly', textvariable=language,
                            value=[i.rsplit('.')[0] for i in
                                   os.listdir(elocal + os.sep + "bin" + os.sep + "languages")])
        LB3_.pack(padx=10, pady=10, side='top')
        LB3_.bind('<<ComboboxSelected>>', set_language)
        ttk.Button(self.frame, text=lang.text138, command=self.license).pack(fill=X, side='bottom')

    def license(self):
        setf("oobe", "2")
        lce = StringVar()

        def loadlice(self):
            te.delete(1.0, END)
            with open(elocal + os.sep + "bin" + os.sep + "licenses" + os.sep + lce.get() + ".txt", 'r',
                      encoding='UTF-8') as f:
                te.insert('insert', f.read())

        self.reframe()
        LB = ttk.Combobox(self.frame, state='readonly', textvariable=lce,
                          value=[i.rsplit('.')[0] for i in os.listdir(elocal + os.sep + "bin" + os.sep + "licenses")])
        LB.bind('<<ComboboxSelected>>', loadlice)
        LB.current(0)
        ttk.Label(self.frame, text=lang.text139, font=("宋体", 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                         expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        LB.pack(padx=10, pady=10, side='top', fill=X)
        te = Text(self.frame)
        te.pack(fill=BOTH, side='top')
        loadlice(self)
        ttk.Label(self.frame, text=lang.t1).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.private).pack(fill=BOTH, side='bottom')

    def private(self):
        setf("oobe", "3")
        self.reframe()
        ttk.Label(self.frame, text=lang.t2, font=("宋体", 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                    expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        te = Text(self.frame)
        with open(elocal + os.sep + "bin" + os.sep + "licenses" + os.sep + "private.txt", 'r', encoding='UTF-8') as f:
            te.insert('insert', f.read())
        te.pack(fill=BOTH)
        ttk.Label(self.frame, text=lang.t3).pack()
        ttk.Button(self.frame, text=lang.text138, command=self.done).pack(fill=BOTH, side='bottom')

    def done(self):
        setf("oobe", "4")
        self.reframe()
        ttk.Label(self.frame, text=lang.t4, font=("宋体", 25)).pack(side='top', padx=10, pady=10, fill=BOTH,
                                                                    expand=True)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.t5, font=("宋体", 20)).pack(
            side='top', fill=BOTH, padx=10, pady=10)
        ttk.Button(self.ck, text=lang.text34, command=self.ck.destroy).pack(fill=BOTH, side='bottom')

    def clos(self):
        pass


def upgrade():
    ck = Toplevel()
    ck.title("检查更新")
    data = requests.get(update_url + "update.json").content.decode()
    up = json.loads(data)
    Label(ck, text="MIO-KITCHEN", font=('楷书', 30)).pack(padx=5, pady=5)
    ttk.Separator(ck, orient=HORIZONTAL).pack(padx=30, fill=X)
    if up['version'] != VERSION:
        Label(ck, text="发现新版本：%s" % (up['version']), font=('楷书', 15), fg='green').pack(padx=5, pady=5)
        lf = ttk.LabelFrame(ck, text="更新日志")
        lf.pack(padx=10, pady=10)
        text = Text(lf)
        text.insert("insert", up['uplog'])
        text.pack(fill=BOTH, padx=5, pady=5)
        ttk.Button(ck, text="更新").pack(padx=5, pady=5, fill=X)
    else:
        Label(ck, text="已是最新版本：%s" % VERSION, font=('华文行楷', 15)).pack(padx=5, pady=5)
        ttk.Button(ck, text="确定", command=ck.destroy).pack(padx=5, pady=5, fill=X, side=LEFT, expand=True)
        ttk.Button(ck, text="刷新", command=ck.destroy).pack(padx=5, pady=5, fill=X, side=LEFT, expand=True)


def loadset():
    if os.access(setfile, os.F_OK):
        config.read(setfile)
        sv_ttk.set_theme(config.get('setting', 'theme'))
        theme.set(config.get('setting', 'theme'))
        global local
        local = config.get('setting', 'path')
        if os.path.exists(local):
            if not local:
                local = os.getcwd()
        else:
            local = os.getcwd()
        global update_url
        update_url = config.get('setting', 'update_url')
        global VERSION
        VERSION = config.get('setting', 'version')
        global barlv
        barlv = config.get('setting', 'barlevel')
        if not barlv:
            barlv = '0.9'
        win.attributes("-alpha", barlv)
        global oobe
        oobe = config.get('setting', 'oobe')
        language.set(config.get('setting', 'language'))
        load(language.get())


if os.path.exists(setfile):
    loadset()
else:
    sv_ttk.set_theme("dark")
    error(1, '缺失配置文件，请重新安装此软件')


def messpop(message, color='orange') -> None:
    tsk.config(text=message, bg=color)


def gettime() -> None:
    tsk.config(text=time.strftime("%H:%M:%S"), bg=win.cget('bg'))
    tsk.after(1000, gettime)


def v_code() -> str:
    ret = ""
    for i in range(6):
        num = randint(0, 9)
        # num = chr(random.randint(48,57))#ASCII表示数字
        letter = chr(randint(97, 122))  # 取小写字母
        Letter = chr(randint(65, 90))  # 取大写字母
        s = str(choice([num, letter, Letter]))
        ret += s
    return ret


def refolder(path) -> None:
    if os.path.exists(path):
        rmdir(path)
        os.mkdir(path)
    else:
        os.mkdir(path)


def undtbo(bn: str = 'dtbo') -> any:
    load_car(0)
    work = rwork()
    dtboimg = findfile(f"{bn}.img", work)
    if not dtboimg:
        print(lang.warn3.format(bn))
        car.set(1)
        return False
    refolder(work + f"{bn}")
    refolder(work + f"{bn}" + os.sep + "dtbo")
    refolder(work + f"{bn}" + os.sep + "dts")
    try:
        mkdtboimg.dump_dtbo(dtboimg, work + f"{bn}" + os.sep + "dtbo" + os.sep + "dtbo")
    except Exception as e:
        print(lang.warn4.format(e))
        car.set(1)
        return False
    for dtbo in os.listdir(work + f"{bn}" + os.sep + "dtbo"):
        if dtbo.startswith("dtbo."):
            print(lang.text4.format(dtbo))
            call(exe="dtc -@ -I dtb -O dts %s -o %s" % (work + f"{bn}" + os.sep + "dtbo" + os.sep + dtbo,
                                                        work + f"{bn}" + os.sep + "dts" + os.sep + "dts." +
                                                        os.path.basename(dtbo).rsplit('.', 1)[1]), out=1)
    print(lang.text5)
    os.remove(dtboimg)
    rmdir(work + "dtbo" + os.sep + "dtbo", 1)


def padtbo() -> any:
    work = rwork()
    refolder(work + "dtbo" + os.sep + "dtbo")
    load_car(0)
    if not os.path.exists(work + "dtbo" + os.sep + "dts"):
        print(lang.warn5)
        car.set(1)
        return False
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
    rmdir(work + "dtbo", 1)
    print(lang.text8)
    car.set(1)


class DUMPCFG:
    def __init__(self):
        self.blksz = 0x1 << 0xc
        self.headoff = 0x4000
        self.magic = b"LOGO!!!!"
        self.imgnum = 0
        self.imgblkoffs = []
        self.imgblkszs = []


class BMPHEAD(object):
    def __init__(self, buf: bytes = None):  # Read bytes buf and use this struct to parse
        assert buf is not None, f"buf Should be bytes not {type(buf)}"
        # print(buf)
        self.structstr = "<H6I"
        (
            self.magic,
            self.fsize,
            self.reserved,
            self.hsize,
            self.dib,
            self.width,
            self.height,
        ) = struct.unpack(self.structstr, buf)


class XIAOMI_BLKSTRUCT(object):
    def __init__(self, buf: bytes):
        self.structstr = "2I"
        (
            self.imgoff,
            self.blksz,
        ) = struct.unpack(self.structstr, buf)


class LOGODUMPER(object):
    def __init__(self, img: str, out: str, dir: str = "pic"):
        self.out = out
        self.img = img
        self.dir = dir
        self.structstr = "<8s"
        self.cfg = DUMPCFG()
        self.chkimg(img)

    def chkimg(self, img: str):
        assert os.access(img, os.F_OK), f"{img} does not found!"
        with open(img, 'rb') as f:
            f.seek(self.cfg.headoff, 0)
            self.magic = struct.unpack(
                self.structstr, f.read(struct.calcsize(self.structstr))
            )[0]
            while True:
                m = XIAOMI_BLKSTRUCT(f.read(8))
                if m.imgoff != 0:
                    # print(blksz<<0xc)
                    self.cfg.imgblkszs.append(m.blksz << 0xc)
                    self.cfg.imgblkoffs.append(m.imgoff << 0xc)
                    self.cfg.imgnum += 1
                else:
                    break
        # print(self.magic)
        assert self.magic == b"LOGO!!!!", "File does not match xiaomi logo magic!"
        print("Xiaomi LOGO!!!! format check pass!")

    def unpack(self):
        with open(self.img, 'rb') as f:
            print("Unpack:\n"
                  "BMP\tSize\tWidth\tHeight")
            for i in range(self.cfg.imgnum):
                f.seek(self.cfg.imgblkoffs[i], 0)
                bmph = BMPHEAD(f.read(26))
                f.seek(self.cfg.imgblkoffs[i], 0)
                print("%d\t%d\t%d\t%d" % (i, bmph.fsize, bmph.width, bmph.height))
                with open(os.path.join(self.out, "%d.bmp" % i), 'wb') as o:
                    o.write(f.read(bmph.fsize))
            print("\tDone!")

    def repack(self):
        with open(self.out, 'wb') as o:
            off = 0x5
            for i in range(self.cfg.imgnum):
                print("Write BMP [%d.bmp] at offset 0x%X" % (i, off << 0xc))
                with open(os.path.join(self.dir, "%d.bmp" % i), 'rb') as b:
                    bhead = BMPHEAD(b.read(26))
                    b.seek(0, 0)
                    self.cfg.imgblkszs[i] = (bhead.fsize >> 0xc) + 1
                    self.cfg.imgblkoffs[i] = off

                    o.seek(off << 0xc)
                    o.write(b.read(bhead.fsize))

                    off += self.cfg.imgblkszs[i]
            o.seek(self.cfg.headoff)
            o.write(self.magic)
            for i in range(self.cfg.imgnum):
                o.write(struct.pack("<I", self.cfg.imgblkoffs[i]))
                o.write(struct.pack("<I", self.cfg.imgblkszs[i]))
            print("\tDone!")


def logodump(bn: str = 'logo'):
    work = rwork()
    logo = findfile(f'{bn}.img', work)
    if not logo:
        messpop(lang.warn3.format(bn))
        return False
    refolder(work + f"{bn}")
    LOGODUMPER(logo, work + f"{bn}").unpack()


def logopack() -> int:
    work = rwork()
    orlogo = findfile('logo.img', work)
    logo = work + "logo-new.img"
    dir_ = work + "logo"
    if not os.path.exists(dir_):
        print(lang.warn6)
        return 1
    if not os.path.exists(orlogo):
        print(lang.warn6)
        return 1
    LOGODUMPER(orlogo, logo, dir_).repack()
    os.remove(orlogo)
    os.rename(logo, orlogo)
    rmdir(dir_, 1)


# 绘制界面
subwin2 = ttk.LabelFrame(win, text=lang.text9)
subwin3 = ttk.LabelFrame(win, text=lang.text10)
subwin3.pack(fill=BOTH, side=LEFT, expand=True, padx=5)
subwin2.pack(fill=BOTH, side=LEFT, expand=True, pady=5)
notepad = ttk.Notebook(subwin2)
tab = ttk.Frame(notepad)
tab2 = ttk.Frame(notepad)
tab3 = ttk.Frame(notepad)
tab4 = ttk.Frame(notepad)
tab5 = ttk.Frame(notepad)
tab6 = ttk.Frame(notepad)
notepad.add(tab, text=lang.text11)
notepad.add(tab2, text=lang.text12)
notepad.add(tab3, text=lang.text13)
notepad.add(tab4, text=lang.text14)
notepad.add(tab5, text=lang.text15)
notepad.add(tab6, text=lang.text16)
scrollbar = ttk.Scrollbar(tab5, orient=tk.VERTICAL)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
canvas1 = Canvas(tab5, yscrollcommand=scrollbar.set)
canvas1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
frame_bg = ttk.Frame(canvas1)
canvas1.create_window((0, 0), window=frame_bg, anchor='nw')
canvas1.config(highlightthickness=0)


def upjdt():
    frame_bg.update_idletasks()
    canvas1.config(scrollregion=canvas1.bbox('all'))
    scrollbar.config(command=canvas1.yview)


def getframe(title):
    frame = ttk.LabelFrame(frame_bg, text=title)
    frame.pack(padx=10, pady=10)
    ttk.Button(frame, text=lang.text17, command=frame.destroy).pack(anchor="ne")
    upjdt()
    return frame


# 子进程运行 防卡死
def CallZ(func, *args):
    threading.Thread(target=func, args=args, daemon=True).start()


def subp(com: int = 1, title: str = lang.text18, master: any = None):
    if com == 1:
        subpage = Toplevel()
        subpage.title(title)
        subpage.resizable(False, False)
        jzxs(subpage)
        return subpage
    else:
        master.destroy()


class mpkman(object):

    def __init__(self) -> None:
        if not dn.get():
            messpop(lang.warn1)
            return
        manager = Toplevel()
        manager.title(lang.text19)
        ttk.Label(manager, text=lang.text19, font=("宋体", 40)).pack(padx=10, pady=10, fill=BOTH, expand=True)
        ttk.Separator(manager, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        Label(manager, text=lang.text24).pack(padx=5, pady=5)
        pls = Listbox(manager, activestyle='dotbox', highlightthickness=0)
        lf2 = ttk.LabelFrame(manager)
        ttk.Button(lf2, text=lang.text20, command=lambda: CallZ(unmpk)).pack(padx=5, pady=5, fill=BOTH)
        ttk.Button(lf2, text=lang.text22, command=lambda: CallZ(run)).pack(padx=5, pady=5, fill=BOTH)
        ttk.Button(lf2, text=lang.t14, command=lambda: CallZ(export)).pack(padx=5, pady=5, fill=BOTH)
        ttk.Button(lf2, text=lang.t17, command=lambda: CallZ(editor_)).pack(padx=5, pady=5, fill=BOTH)
        lf1 = Frame(manager)
        pls.pack(padx=5, pady=5, fill=BOTH, side=LEFT, expand=True)
        lf2.pack(padx=5, pady=5, fill=BOTH, side=LEFT, expand=True)
        rmenu = Menu(pls, tearoff=False, borderwidth=0)
        rmenu.add_command(label=lang.text21, command=lambda: CallZ(impk))
        rmenu.add_command(label=lang.text23, command=lambda: CallZ(listpls))
        rmenu.add_command(label=lang.text115, command=lambda: CallZ(new_))

        class new_(Toplevel):
            def __init__(self):
                super().__init__()
                jzxs(self)
                self.resizable(False, False)
                self.title(lang.text115)
                ttk.Label(self, text=lang.t19, font=(None, 25)).pack(fill=BOTH, expand=0, padx=10, pady=10)
                ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
                f1 = ttk.Frame(self)
                ttk.Label(f1, text=lang.t20).pack(side=LEFT, padx=5, pady=5)
                self.name = ttk.Entry(f1)
                self.name.pack(padx=5, pady=5, side=LEFT)
                f1.pack(padx=5, pady=5, fill=X)
                f2 = ttk.Frame(self)
                ttk.Label(f2, text=lang.t21).pack(side=LEFT, padx=5, pady=5)
                self.aou = ttk.Entry(f2)
                self.aou.pack(padx=5, pady=5, side=LEFT)
                f2.pack(padx=5, pady=5, fill=X)
                f3 = ttk.Frame(self)
                ttk.Label(f3, text=lang.t22).pack(side=LEFT, padx=5, pady=5)
                self.ver = ttk.Entry(f3)
                self.ver.pack(padx=5, pady=5, side=LEFT)
                f3.pack(padx=5, pady=5, fill=X)
                f4 = ttk.Frame(self)
                ttk.Label(f4, text=lang.t23).pack(side=LEFT, padx=5, pady=5)
                self.dep = ttk.Entry(f4)
                self.dep.pack(padx=5, pady=5, side=LEFT)
                f4.pack(padx=5, pady=5, fill=X)
                ttk.Label(self, text=lang.t24).pack(padx=5, pady=5, expand=1)
                self.intro = Text(self)
                self.intro.pack(fill=BOTH, padx=5, pady=5, expand=1)
                ttk.Button(self, text=lang.text115, command=self.create).pack(fill=BOTH, side=BOTTOM)

            def create(self):
                iden = v_code()
                data = {
                    "name": self.name.get(),
                    "author": self.aou.get(),
                    "version": self.ver.get(),
                    "identifier": iden,
                    "describe": self.intro.get(1.0, END),
                    "depend": self.dep.get()
                }
                self.destroy()
                if not os.path.exists(moduledir + os.sep + iden):
                    os.mkdir(moduledir + os.sep + iden)
                with open(moduledir + os.sep + iden + os.sep + "info.json", 'w+', encoding='utf-8', newline='\n') as js:
                    js.write(json.dumps(data))
                listpls()
                editor_(iden)

        def editor_(id_=None):
            if not pls.curselection():
                messpop(lang.warn2)
                return 1
            if id_ is None:
                id_ = globals()[pls.get(pls.curselection())]
            if not os.path.exists(moduledir + os.sep + id_ + os.sep + "main.msh") and not os.path.exists(
                    moduledir + os.sep + id_ + os.sep + "main.sh"):
                ask = ask_win(lang.t18, 'SH', 'MSH')
                if ask == 1:
                    s = "main.sh"
                else:
                    s = "main.msh"
                with open(moduledir + os.sep + id_ + os.sep + s, 'w+', encoding='utf-8', newline='\n') as sh:
                    sh.write("echo hello,world")
                editor.main(moduledir + os.sep + id_ + os.sep + s)
            else:
                if os.path.exists(moduledir + os.sep + id_ + os.sep + "main.msh"):
                    editor.main(moduledir + os.sep + id_ + os.sep + "main.msh")
                elif os.path.exists(moduledir + os.sep + id_ + os.sep + "main.sh"):
                    editor.main(moduledir + os.sep + id_ + os.sep + "main.sh")

        def export():
            if not pls.curselection():
                messpop(lang.warn2)
                return 1
            buffer = BytesIO()
            buffer2 = StringIO()
            info_ = ConfigParser()
            value = globals()[pls.get(pls.curselection())]
            with open(moduledir + os.sep + value + os.sep + "info.json", 'r', encoding='UTF-8') as f:
                data = json.load(f)
                if "describe" in data:
                    des = data["describe"]
                else:
                    des = ''
                info_['module'] = {
                    'name': f'{data["name"]}',
                    'version': f'{data["version"]}',
                    'author': f'{data["author"]}',
                    'describe': f'{des}',
                    'resource': 'main.zip',
                    'identifier': f'{value}',
                    'depend': f'{data["depend"]}'
                }
                info_.write(buffer2)
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk:
                os.chdir(moduledir + os.sep + value + os.sep)
                for i in get_all_file_paths("."):
                    print(f"{lang.text1}:%s" % i.rsplit(".\\")[1])
                    try:
                        mpk.write(i)
                    except Exception as e:
                        print(lang.text2.format(i, e))
                os.chdir(elocal)
            with zipfile.ZipFile(local + os.sep + pls.get(pls.curselection()) + ".mpk", 'w',
                                 compression=zipfile.ZIP_DEFLATED, allowZip64=True) as mpk2:
                mpk2.writestr('main.zip', buffer.getvalue())
                mpk2.writestr('info', buffer2.getvalue())
            if os.path.exists(local + os.sep + pls.get(pls.curselection()) + ".mpk"):
                print(lang.t15 % (local + os.sep + pls.get(pls.curselection()) + ".mpk"))
            else:
                print(lang.t16 % (local + os.sep + pls.get(pls.curselection()) + ".mpk"))

        def relf2(self):
            try:
                lf2.config(text=pls.get(pls.curselection()))
            except Exception as e:
                if e:
                    lf2.config(text="Null")

        def popup(event):
            rmenu.post(event.x_root, event.y_root)  # post在指定的位置显示弹出菜单

        pls.bind("<<ListboxSelect>>", relf2)
        pls.bind("<Button-3>", popup)
        moduledir = elocal + os.sep + "bin" + os.sep + "module"
        manager.resizable(False, False)
        file = StringVar()

        def listpls():
            pls.delete(0, "end")
            for i in os.listdir(moduledir):
                if os.path.isdir(moduledir + os.sep + i):
                    with open(moduledir + os.sep + i + os.sep + "info.json", 'r', encoding='UTF-8') as f:
                        data = json.load(f)
                        pls.insert('end', data['name'])
                        globals()[data['name']] = data['identifier']
            try:
                pls.selection_set(0)
                relf2(self)
            except:
                pass

        listpls()

        def impk() -> Exception:
            installmpk(filedialog.askopenfilename(title=lang.text25, filetypes=((lang.text26, "*.mpk"),)))
            manager.lift()
            try:
                listpls()
            except Exception as e:
                listpls()
                return e

        class msh_parse(object):
            envs = {'version': VERSION,
                    'tool_bin': (elocal + os.sep + 'bin' + os.sep + os.name + '_' + machine() + os.sep).replace('\\',
                                                                                                                '/'),
                    'project': (local + os.sep + dn.get()).replace('\\', '/'),
                    'moddir': moduledir.replace('\\', '/')}

            def __init__(self, sh):
                self.envs['bin'] = os.path.dirname(sh.replace('\\', '/'))
                with open(sh, 'r+', encoding='utf-8', newline='\n') as shell:
                    for i in shell.readlines():
                        for key, value in self.envs.items():
                            i = i.replace('@{}@'.format(key), value)
                        try:
                            if i[:1] != "#":
                                if i.split()[0] == "if":
                                    self.sif(i.split()[1], i.split()[2], shlex.split(i)[3])
                                elif i.split()[0] == "for":
                                    self.sfor(i.split()[1], shlex.split(i)[3], shlex.split(i)[4])
                                else:
                                    getattr(self, i.split()[0])(i[i.index(" ") + 1:])
                        except AttributeError as e:
                            print("未知的参数或命令：%s\n错误：%s" % (i, str(e).replace("msh_parse", 'MSH解释器')))
                        except ModuleError as e:
                            print("异常:%s" % e)
                            return
                        except Exception as e:
                            print("运行错误:%s\n错误：%s" % (i, e))
                        except:
                            print("运行错误:%s" % i)

            def set(self, cmd):
                try:
                    vn, va = cmd.split()
                except Exception as e:
                    print("赋值异常：%s\n语句：%s" % (e, cmd))
                    return 1
                self.envs[vn] = va

            def run_ex(self, cmd):
                try:
                    vn, va = shlex.split(cmd)
                except Exception as e:
                    print("运行异常:%s\n语句:run_ma %s" % (e, cmd))
                    return 1
                try:
                    getattr(extra, vn)(va.split())
                except:
                    print("调用失败! %s " % va)

            @staticmethod
            def echo(cmd):
                print(cmd)

            @staticmethod
            def gettype(file_):
                gettype(file_)

            def sfor(self, vn, vs, do):
                if ',' in vs:
                    fgf = ','
                else:
                    fgf = None
                for v in vs.split(fgf):
                    do_ = do.replace(f'@{vn}@', v)
                    getattr(self, do_.split()[0])(do_[do_.index(' ') + 1:])

            @staticmethod
            def rmdir(path):
                rmdir(path, up=1)

            @staticmethod
            def run(cmd):
                call(exe=str(cmd), kz='N', shstate=True)

            @staticmethod
            def packsuper(cmd):
                supers = IntVar()
                ssparse = IntVar()
                supersz = IntVar()
                sdbfz = StringVar()
                try:
                    sparse, dbfz, size, set_, lb = shlex.split(cmd)
                except:
                    raise ModuleError("SUPER数据异常")
                supers.set(int(size))
                ssparse.set(int(sparse))
                supersz.set(int(set_))
                sdbfz.set(dbfz)
                packsuper(sparse=ssparse, dbfz=sdbfz, size=supers, set_=supersz, lb=lb)

            def sh(self, cmd):
                temp = elocal + os.sep + "bin" + os.sep + "temp" + os.sep
                file_ = temp + v_code()
                with open(file_, "w", encoding='UTF-8', newline="\n") as f:
                    for i in self.envs:
                        f.write(f'export {i}={self.envs[i]}\n')
                    f.write("source $1")
                if os.path.exists(file_):
                    if os.name == 'posix':
                        sh = "ash"
                    else:
                        sh = "bash"
                    load_car(0)
                    call("busybox {} {} {}".format(sh, file_, cmd.replace('\\', '/')))
                    try:
                        os.remove(file_)
                    except:
                        pass

            @staticmethod
            def msh(cmd):
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
                        msh_parse(argv)
                        print("执行完成：%s" % os.path.basename(argv))
                elif cmd_ == "show":
                    print("----------\nMSH解释器\n----------")
                    if argv == 'all':
                        print('版本：1.0\n作者：米欧科技')
                    elif argv == 'version':
                        print("版本：1.0")
                    elif argv == 'author':
                        print("作者：米欧科技")
                else:
                    print('-------\nMSH解释器\n-------\n用法：\nmsh run [script]\nmsh show [all,version,author]')

            @staticmethod
            def exit(value):
                raise ModuleError(value)

            def sif(self, mode, var_, other):
                modes = {
                    'exist': lambda var: os.path.exists(var),
                    '!exist': lambda var: not os.path.exists(var),
                    'equ': lambda var: var.split('--')[0] == var.split('--')[1],
                    '!equ': lambda var: var.split('--')[0] != var.split('--')[1],
                    'gettype': lambda var: gettype(var.split('--')[0]) == var.split('--')[1],
                    '!gettype': lambda var: gettype(var.split('--')[0]) != var.split('--')[1]
                }

                if modes[mode](var_):
                    getattr(self, other.split()[0])(other[other.index(' ') + 1:])

        class parse(Toplevel):
            gavs = {}

            def __init__(self, jsons, msh=False):
                super().__init__()
                self.value = []

                def callcmd(cmd):
                    if cmd.split()[0] == "msg":
                        messagebox.showinfo(cmd.split()[1], cmd.split()[2])
                    elif cmd.split()[0] == "start":
                        CallZ(call(cmd[cmd.index(' ') + 1:], 'N'))
                    elif cmd.split()[0] == "exec":
                        exec(cmd[cmd.index(' ') + 1:])
                    else:
                        print(lang.text27)

                def generate_sh():
                    sh_content = ""
                    for va in self.value:
                        if self.gavs[va].get():
                            if os.path.isabs(self.gavs[va].get()) and os.name == 'nt':
                                if "\\" in self.gavs[va].get():
                                    gva = self.gavs[va].get().replace('\\', '/')
                                else:
                                    gva = self.gavs[va].get()
                            else:
                                gva = self.gavs[va].get()
                            sh_content += f"export {va}={gva}\n"
                    temp = elocal + os.sep + "bin" + os.sep + "temp" + os.sep
                    if not os.path.exists(temp):
                        refolder(temp)
                    file.set(temp + v_code())
                    with open(file.get(), "w", encoding='UTF-8', newline="\n") as f:
                        f.write(sh_content)
                        f.write('export version={}\n'.format(VERSION))
                        f.write('export tool_bin={}\n'.format(
                            (elocal + os.sep + 'bin' + os.sep + os.name + '_' + machine() + os.sep).replace('\\', '/')))
                        f.write("export project={}\nsource $1".format((local + os.sep + dn.get()).replace('\\', '/')))
                    self.destroy()
                    self.gavs.clear()

                def generate_msh():
                    for va in self.value:
                        if self.gavs[va].get():
                            if os.path.isabs(self.gavs[va].get()) and os.name == 'nt':
                                if '\\' in self.gavs[va].get():
                                    msh_parse.envs[va] = self.gavs[va].get().replace("\\", '/')
                                else:
                                    msh_parse.envs[va] = self.gavs[va].get()
                            else:
                                msh_parse.envs[va] = self.gavs[va].get()
                    self.destroy()
                    self.gavs.clear()

                with open(jsons, 'r', encoding='UTF-8') as f:
                    try:
                        data = json.load(f)
                    except Exception as e:
                        messpop(lang.text133 + str(e))
                        print(lang.text133 + str(e))
                        self.destroy()
                    self.title(data['main']['info']['title'])
                    # 设置窗口大小和位置
                    height = data['main']['info']['height']
                    width = data['main']['info']['weight']
                    if height != 'none' and width != 'none':
                        self.geometry(f"{width}x{height}")
                    resizable = data['main']['info']['resize']
                    if resizable == '1':
                        self.resizable(True, True)
                    else:
                        self.resizable(False, False)
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
                                    input_var_name = con['set']
                                    self.gavs[input_var_name] = StringVar()
                                    ttk.Entry(group_frame, textvariable=self.gavs[input_var_name]).pack(pady=5, padx=5,
                                                                                                        fill=BOTH)
                                elif con['type'] == 'checkbutton':
                                    b_var_name = con['set']
                                    self.gavs[b_var_name] = IntVar()
                                    if not 'text' in con:
                                        text = 'M.K.C'
                                    else:
                                        text = con['text']
                                    ttk.Checkbutton(group_frame, text=text, variable=self.gavs[b_var_name], onvalue=1,
                                                    offvalue=0,
                                                    style="Switch.TCheckbutton").pack(
                                        padx=5, pady=5, fill=BOTH)
                                else:
                                    print(lang.warn14.format(con['type']))
                    if msh:
                        ttk.Button(self, text=lang.ok, command=lambda: CallZ(generate_msh)).pack(fill=X, side='bottom')
                    else:
                        ttk.Button(self, text=lang.ok, command=lambda: CallZ(generate_sh)).pack(fill=X, side='bottom')

                jzxs(self)
                self.wait_window()

        def run():
            if pls.curselection():
                value = globals()[pls.get(pls.curselection())]
            else:
                value = ""
            if value:
                if os.path.exists(moduledir + os.sep + value + os.sep + "main.sh") or os.path.exists(
                        moduledir + os.sep + value + os.sep + "main.msh"):
                    if os.path.exists(moduledir + os.sep + value + os.sep + "main.json"):
                        parse(moduledir + os.sep + value + os.sep + "main.json",
                              (os.path.exists(moduledir + os.sep + value + os.sep + "main.msh")))
                        if os.path.exists(moduledir + os.sep + value + os.sep + "main.sh"):
                            if os.path.exists(file.get()):
                                if os.name == 'posix':
                                    sh = "ash"
                                else:
                                    sh = "bash"
                                load_car(0)
                                call("busybox {} {} {}".format(sh, file.get(),
                                                               (
                                                                       moduledir + os.sep + value + os.sep + "main.sh").replace(
                                                                   '\\',
                                                                   '/')))
                                car.set(1)
                                os.remove(file.get())
                        elif os.path.exists(moduledir + os.sep + value + os.sep + "main.msh"):
                            msh_parse(moduledir + os.sep + value + os.sep + "main.msh")


                    # 生成TMP
                    else:
                        if os.path.exists(moduledir + os.sep + value + os.sep + "main.sh"):
                            temp = elocal + os.sep + "bin" + os.sep + "temp" + os.sep
                            if not os.path.exists(temp):
                                refolder(temp)
                            if not file.get():
                                file.set(temp + os.sep + v_code())
                            with open(file.get(), "w", encoding='UTF-8', newline="\n") as f:
                                f.write('export tool_bin={}\n'.format(
                                    (elocal + os.sep + 'bin' + os.sep + os.name + '_' + machine() + os.sep).replace(
                                        '\\',
                                        '/')))
                                f.write('export version={}\n'.format(VERSION))
                                f.write(
                                    "export project={}\nsource $1".format(
                                        (local + os.sep + dn.get()).replace('\\', '/')))
                            if os.path.exists(file.get()):
                                if os.name == 'posix':
                                    sh = "ash"
                                else:
                                    sh = "bash"
                                load_car(0)
                                call("busybox {} {} {}".format(sh, file.get(),
                                                               (
                                                                       moduledir + os.sep + value + os.sep + "main.sh").replace(
                                                                   '\\',
                                                                   '/')))
                                car.set(1)
                                os.remove(file.get())
                        elif os.path.exists(moduledir + os.sep + value + os.sep + "main.msh"):
                            msh_parse(moduledir + os.sep + value + os.sep + "main.msh")
                else:
                    if not os.path.exists(moduledir + os.sep + value):
                        messpop(lang.warn7.format(value))
                        listpls()
                        manager.lift()
                    else:
                        print(lang.warn8)
            else:
                print(lang.warn2)

        class unmpk:

            def __init__(self):
                self.arr = []
                self.arr2 = []
                if pls.curselection():
                    self.value = globals()[pls.get(pls.curselection())]
                    self.value2 = pls.get(pls.curselection())
                    self.lfdep()
                    self.ask()
                else:
                    messpop(lang.warn2)

            def ask(self):
                self.ck = Toplevel()
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
                    with open(moduledir + os.sep + i + os.sep + "info.json", 'r', encoding='UTF-8') as f:
                        data = json.load(f)
                        for n in data['depend'].split():
                            if name == n:
                                self.arr.append(i)
                                self.lfdep(i)
                                self.arr2.append(data['name'])
                                break

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
                        rmtree(moduledir + os.sep + name)
                    if os.path.exists(moduledir + os.sep + name):
                        messpop(lang.warn9, 'red')
                    else:
                        print(lang.text30)
                        try:
                            listpls()
                        except:
                            pass
                else:
                    messpop(lang.warn2)

        try:
            listpls()
        except:
            pass
        lf1.pack(padx=10, pady=10)
        jzxs(manager)


class installmpk(Toplevel):
    def __init__(self, mpk):
        super().__init__()
        self.mconf = ConfigParser()
        if not mpk:
            messpop(lang.warn2)
            self.destroy()
            return
        self.title(lang.text31)
        self.resizable(False, False)
        with zipfile.ZipFile(mpk, 'r') as myfile:
            with myfile.open('info') as info_file:
                self.mconf.read_string(info_file.read().decode('utf-8'))
            try:
                with myfile.open('icon') as myfi:
                    try:
                        pyt = ImageTk.PhotoImage(Image.open(BytesIO(myfi.read())))
                    except Exception as e:
                        print(e)
                        pyt = ImageTk.PhotoImage(Image.open(elocal + os.sep + "images" + os.sep + "none"))
            except:
                pyt = ImageTk.PhotoImage(Image.open(elocal + os.sep + "bin" + os.sep + "images" + os.sep + "none"))
            with myfile.open('%s' % (self.mconf.get('module', 'resource')), 'r') as inner_file:
                self.inner_zipdata = inner_file.read()
                self.inner_filenames = zipfile.ZipFile(BytesIO(self.inner_zipdata)).namelist()
        Label(self, image=pyt).pack(padx=10, pady=10)
        Label(self, text="%s" % (self.mconf.get('module', 'name')), font=('黑体', 14)).pack(padx=10, pady=10)
        Label(self, text=lang.text32.format((self.mconf.get('module', 'version'))), font=('黑体', 12)).pack(padx=10,
                                                                                                            pady=10)
        Label(self, text=lang.text33.format((self.mconf.get('module', 'author'))), font=('黑体', 12)).pack(padx=10,
                                                                                                           pady=10)
        text = Text(self)
        text.insert("insert", "%s" % (self.mconf.get('module', 'describe')))
        text.pack(padx=10, pady=10)
        self.prog = ttk.Progressbar(self, length=200, mode='determinate', orient=HORIZONTAL, maximum=100, value=0)
        self.prog.pack()
        self.state = Label(self, text=lang.text40, font=('黑体', 12))
        self.state.pack(padx=10, pady=10)
        self.installb = ttk.Button(self, text=lang.text41, command=lambda: CallZ(self.install))
        self.installb.pack(padx=10, pady=10, expand=True, fill=X)
        jzxs(self)
        self.wait_window()

    def install(self):
        if self.installb.cget('text') == lang.text34:
            self.destroy()
            return True
        self.installb.config(state=DISABLED)
        for dep in self.mconf.get('module', 'depend').split():
            if not os.path.isdir(elocal + os.sep + "bin" + os.sep + "module" + os.sep + dep):
                self.state['text'] = lang.text36 % (self.mconf.get('module', 'name'), dep, dep)
                self.installb['text'] = lang.text37
                self.installb.config(state='normal')
                return False
        if os.path.exists(
                elocal + os.sep + "bin" + os.sep + "module" + os.sep + self.mconf.get('module', 'identifier')):
            rmtree(elocal + os.sep + "bin" + os.sep + "module" + os.sep + self.mconf.get('module', 'identifier'))
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
            fz.extract(file,
                       elocal + os.sep + "bin" + os.sep + "module" + os.sep + self.mconf.get('module', 'identifier'))
            self.prog['value'] = extracted_size * 100 / uncompress_size
        try:
            depends = self.mconf.get('module', 'depend')
        except:
            depends = ''
        minfo = {"name": "%s" % (self.mconf.get('module', 'name')),
                 "author": "%s" % (self.mconf.get('module', 'author')),
                 "version": "%s" % (self.mconf.get('module', 'version')),
                 "identifier": "%s" % (self.mconf.get('module', 'identifier')),
                 "describe": "%s" % (self.mconf.get('module', 'describe')),
                 "depend": "%s" % depends}
        with open(elocal + os.sep + "bin" + os.sep + "module" + os.sep + self.mconf.get('module',
                                                                                        'identifier') + os.sep + "info.json",
                  'w') as f:
            json.dump(minfo, f, indent=2)
        self.state['text'] = lang.text39
        self.installb['text'] = lang.text34
        self.installb.config(state='normal')


class packxx(object):
    def __init__(self):
        self.dbfs = StringVar()
        self.dbgs = StringVar()
        self.edbgs = StringVar()
        self.scale = IntVar()
        self.spatchvb = IntVar()
        self.delywj = IntVar()
        self.ck = subp(com=1, title=lang.text42)
        lf1 = ttk.LabelFrame(self.ck, text=lang.text43)
        lf1.pack(fill=BOTH, padx=5, pady=5)
        lf2 = ttk.LabelFrame(self.ck, text=lang.text44)

        lf2.pack(fill=BOTH, padx=5, pady=5)
        lf3 = ttk.LabelFrame(self.ck, text=lang.text45)
        lf3.pack(fill=BOTH, padx=5, pady=5)
        lf4 = ttk.LabelFrame(self.ck, text=lang.text46)
        lf4.pack(fill=BOTH, pady=5, padx=5)
        sf1 = Frame(lf3)
        sf1.pack(fill=X, padx=5, pady=5, side=TOP)
        self.scale.set(0)
        Label(lf1, text=lang.text48).pack(side='left', padx=5, pady=5)
        dbfss = ttk.Combobox(lf1, state="readonly", textvariable=self.dbfs)
        dbfss.pack(side='left', padx=5, pady=5)
        dbfss['value'] = ("make_ext4fs", "mke2fs+e2fsdroid")
        Label(lf3, text=lang.text49).pack(side='left', padx=5, pady=5)
        dbgss = ttk.Combobox(lf3, state="readonly", textvariable=self.dbgs, values=("raw", "sparse", "br", "dat"))
        dbgss.pack(padx=5, pady=5, side='left')
        Label(lf2, text=lang.text50).pack(side='left', padx=5, pady=5)
        edbgss = ttk.Combobox(lf2, state="readonly", textvariable=self.edbgs)
        edbgss.pack(side='left', padx=5, pady=5)
        edbgss['value'] = ("lz4", "lz4hc", "lzma", "deflate")
        Label(lf2, text=lang.text51).pack(side='left', padx=5, pady=5)
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
        self.lsg = Listbox(lf4, activestyle='dotbox', selectmode=MULTIPLE, highlightthickness=0)
        self.lsg.pack(fill=BOTH, padx=5, pady=5)
        dbfss.current(0)
        dbgss.current(0)
        edbgss.current(0)
        ttk.Button(self.ck, text=lang.pack, command=lambda: CallZ(self.start_)).pack(side='left', padx=2, pady=2,
                                                                                     fill=X,
                                                                                     expand=True)
        ttk.Button(self.ck, text=lang.cancel, command=lambda: subp(com=0, master=self.ck)).pack(side='left', padx=2,
                                                                                                pady=2,
                                                                                                fill=X,
                                                                                                expand=True)
        self.refs()

    def refs(self):
        work = rwork()
        self.lsg.delete(0, END)
        if not os.path.exists(work):
            messpop(lang.warn1)
            return False
        for i in os.listdir(work):
            if os.path.isdir(work + i):
                if os.access(work + "config" + os.sep + "%s_file_contexts" % i, os.F_OK):
                    self.lsg.insert(END, i)

    def update_label(self, value):
        self.label.config(text=lang.text47.format(int(float(value))))

    def start_(self):
        lg = [self.lsg.get(index) for index in self.lsg.curselection()]
        subp(com=0, master=self.ck)
        packrom(self.edbgs, self.dbgs, self.dbfs, self.scale, lg, self.spatchvb, self.delywj.get())


class packss:
    def __init__(self):
        ck = subp(com=1, title=lang.text53)
        supers = IntVar()
        ssparse = IntVar()
        supersz = IntVar()
        sdbfz = StringVar()
        lf1 = ttk.LabelFrame(ck, text=lang.text54)
        lf1.pack(fill=BOTH)
        lf2 = ttk.LabelFrame(ck, text=lang.settings)
        lf2.pack(fill=BOTH)
        lf3 = ttk.LabelFrame(ck, text=lang.text55)
        lf3.pack(fill=BOTH)

        # 自动设置
        ttk.Radiobutton(lf1, text="A-only", variable=supersz, value=1).pack(side='left', padx=10, pady=10)
        ttk.Radiobutton(lf1, text="Virtual-ab", variable=supersz, value=2).pack(side='left', padx=10, pady=10)
        ttk.Radiobutton(lf1, text="A/B", variable=supersz, value=3).pack(side='left', padx=10, pady=10)
        Label(lf2, text=lang.text56).pack(side='left', padx=10, pady=10)
        sdbfzs = ttk.Combobox(lf2, textvariable=sdbfz)
        sdbfzs.pack(side='left', padx=10, pady=10, fill='both')
        sdbfzs['value'] = ("qti_dynamic_partitions", "main")
        sdbfzs.current(0)
        Label(lf2, text=lang.text57).pack(side='left', padx=10, pady=10)
        supers.set(9126805504)
        ent = ttk.Entry(lf2, textvariable=supers)
        ent.pack(side='left', padx=10, pady=10)

        tl = Listbox(lf3, selectmode=MULTIPLE, activestyle='dotbox')
        tl.config(highlightthickness=0)
        work = rwork()
        for file_name in os.listdir(work):
            if file_name.endswith(".img"):
                if gettype(work + file_name) == "ext" or gettype(work + file_name) == "erofs":
                    tl.insert(END, file_name[:-4])
        tl.pack(padx=10, pady=10, fill=BOTH)

        ttk.Checkbutton(ck, text=lang.text58, variable=ssparse, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=10, pady=10, fill=BOTH)

        def versize():
            size = 0
            for i in [tl.get(index) for index in tl.curselection()]:
                size += os.path.getsize(work + i + ".img")
            if size > supers.get() + 409600:
                supers.set(size + 4096000)
                return False
            else:
                return True

        def start_():
            try:
                supers.get()
            except:
                supers.set(0)
            if not versize():
                ask_win(lang.t10)
                return False
            lbs = [tl.get(index) for index in tl.curselection()]
            subp(com=0, master=ck)
            packsuper(sparse=ssparse, dbfz=sdbfz, size=supers, set_=supersz, lb=lbs)

        ttk.Button(ck, text=lang.pack, command=lambda: CallZ(start_)).pack(side='left',
                                                                           padx=5,
                                                                           pady=5, fill=X, expand=True)
        ttk.Button(ck, text=lang.cancel, command=lambda: subp(com=0, master=ck)).pack(side='left', padx=10, pady=10,
                                                                                      fill=X,
                                                                                      expand=True)


def packsuper(sparse, dbfz, size, set_, lb):
    if not dn.get():
        messpop(lang.warn1)
        return False
    load_car(0)
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
    call(command)
    if os.access(work + "super.img", os.F_OK):
        print(lang.text59 % (work + "super.img"))
    else:
        messpop(lang.warn10)
    car.set(1)


def returnoutput(cmd, kz=1):
    if kz == 1:
        comd = elocal + os.sep + "bin" + os.sep + os.name + '_' + machine() + os.sep + cmd
    else:
        comd = cmd
    if os.name == 'posix':
        comd = comd.split()
    else:
        comd = cmd
    try:
        ret = subprocess.check_output(comd, shell=False, stderr=subprocess.STDOUT)
        return ret.decode()
    except subprocess.CalledProcessError as e:
        return e.decode()


class StdoutRedirector(object):
    def __init__(self, text_widget):
        self.text_space = text_widget

    def write(self, string):
        self.text_space.insert(END, string)
        self.text_space.yview('end')

    @staticmethod
    def flush() -> str:
        return "MIO-KITCHEN"


def call(exe, kz='Y', out=0, shstate=False, sp=0):
    if kz == "Y":
        cmd = f'{elocal}{os.sep}bin{os.sep}{os.name}_{machine()}{os.sep}{exe}'
    else:
        cmd = exe
    if os.name != 'posix':
        conf = subprocess.CREATE_NO_WINDOW
    else:
        if sp == 0:
            cmd = cmd.split()
        conf = 0
    try:
        ret = subprocess.Popen(cmd, shell=shstate, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=conf)
        for i in iter(ret.stdout.readline, b""):
            if out == 0:
                print(i.decode("utf-8", "ignore").strip())
    except subprocess.CalledProcessError as e:
        for i in iter(e.stdout.readline, b""):
            if out == 0:
                print(e.decode("utf-8", "ignore").strip())
    ret.wait()
    return ret.returncode


def DownloadFile():
    url = input_(title=lang.text60)
    down = getframe(lang.text61 + os.path.basename(url))
    messpop(lang.text62, "green")
    progressbar = tk.ttk.Progressbar(down, length=200, mode="determinate")
    progressbar.pack(padx=10, pady=10)
    jd = StringVar()
    var1.set(0)
    ttk.Label(down, textvariable=jd).pack(padx=10, pady=10)
    c1 = ttk.Checkbutton(down, text=lang.text63, variable=var1, onvalue=1, offvalue=0)
    c1.pack(padx=10, pady=10)
    start_time = time.time()
    try:
        response = requests.Session().head(url)
        file_size = int(response.headers.get("Content-Length", 0))
        response = requests.Session().get(url, stream=True, verify=False)
        with open(local + os.sep + os.path.basename(url), "wb") as f:
            chunk_size = 2048576
            bytes_downloaded = 0
            for data in response.iter_content(chunk_size=chunk_size):
                f.write(data)
                bytes_downloaded += len(data)
                elapsed = time.time() - start_time
                speed = bytes_downloaded / (1024 * elapsed)
                percentage = int(bytes_downloaded * 100 / file_size)
                progressbar["value"] = percentage
                jd.set(lang.text64.format(str(percentage), str(speed), str(bytes_downloaded), str(file_size)))
                progressbar.update()
        progressbar["value"] = 0
        print(lang.text65.format(os.path.basename(url), str(elapsed)))
        down.destroy()
        if var1.get() == 1:
            unpackrom(local + os.sep + os.path.basename(url))
            os.remove(local + os.sep + os.path.basename(url))
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
                    messpop("%s" % e)
                messpop(lang.text68, "red")


def jboot(bn: str = 'boot'):
    work = rwork()
    boot = findfile(f"{bn}.img", work)
    if not boot:
        print(lang.warn3.format(bn))
        car.set(1)
        return False
    if not os.path.exists(boot):
        messpop(lang.warn3.format(bn))
        car.set(1)
        return False
    if os.path.exists(work + f"{bn}"):
        if rmdir((work + f"{bn}")) != 0:
            print(lang.text69)
            car.set(1)
            return False
    refolder(work + f"{bn}")
    os.chdir(work + f"{bn}")
    if call("magiskboot unpack -h %s" % boot) != 0:
        print("Unpack %s Fail..." % boot)
        os.chdir(elocal)
        rmtree((work + f"{bn}"))
        car.set(1)
        return False
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
                car.set(1)
                return False
        if not os.path.exists(work + f"{bn}" + os.sep + "ramdisk"):
            os.mkdir(work + f"{bn}" + os.sep + "ramdisk")
        os.chdir(work + f"{bn}" + os.sep)
        if not os.name == 'nt':
            cpio = findfile("cpio", elocal + os.sep + "bin" + os.sep + os.name + "_" + machine())
        else:
            cpio = findfile("cpio.exe", elocal + os.sep + "bin" + os.sep + os.name + "_" + machine())
        print("Unpacking Ramdisk...")
        call("%s -d --no-absolute-filenames -F %s -i -D %s" % (
            cpio, "ramdisk.cpio", "ramdisk"), kz='N')
        os.chdir(elocal)

    else:
        print("Unpack Done!")
    os.chdir(elocal)


def dboot():
    work = rwork()
    flag = ''
    boot = findfile("boot.img", work)
    load_car(0)
    if not os.path.exists(work + "boot"):
        print("Cannot Find Boot...")
        car.set(1)
        return False
    try:
        os.chdir(work + "boot" + os.sep + "ramdisk")
    except Exception as e:
        print("Ramdisk Not Found.. %s" % e)
        car.set(1)
        return False
    if os.name != 'posix':
        cpio = findfile("cpio.exe", elocal + os.sep + "bin" + os.sep).replace('\\', "/")
    else:
        cpio = findfile("cpio", elocal + os.sep + "bin" + os.sep + os.name + "_" + machine())
    call(exe="busybox ash -c \"find . | %s -H newc -R 0:0 -o -F ../ramdisk-new.cpio\"" % cpio, sp=1, shstate=True)
    os.chdir(work + "boot" + os.sep)
    with open(work + "boot" + os.sep + "comp", "r", encoding='utf-8') as compf:
        comp = compf.read()
    print("Compressing:%s" % comp)
    if comp != "unknow":
        if call("magiskboot compress=%s ramdisk-new.cpio") != 0:
            print("Pack Ramdisk Fail...")
            os.remove("ramdisk-new.cpio")
            car.set(1)
            return False
        else:
            print("Pack Ramdisk Successful..")
            os.remove("ramdisk.cpio")
            os.rename("ramdisk-new.cpio", "ramdisk.cpio")
    else:
        print("Pack Ramdisk Successful..")
        os.remove("ramdisk.cpio")
        os.rename("ramdisk-new.cpio", "ramdisk.cpio")
    if comp == "cpio": flag = "-n"
    if call("magiskboot repack %s %s" % (flag, boot)) != 0:
        print("Pack boot Fail...")
        car.set(1)
        return False
    else:
        os.remove(work + "boot.img")
        os.rename(work + "boot" + os.sep + "new-boot.img", work + "boot.img")
        os.chdir(elocal)
        if rmdir((work + "boot")) != 0:
            print(lang.warn11.format("boot"))
        print("Pack Successful...")
        car.set(1)


def findfile(file, dir_) -> str:
    for root, dirs, files in os.walk(dir_, topdown=True):
        if file in files:
            print(lang.text70 % root + os.sep + file)
            if os.name == 'nt':
                return (root + os.sep + file).replace("\\", '/')
            else:
                return root + os.sep + file
        else:
            pass


def findfolder(dir__, folder_name):
    for root, dirnames, filenames in os.walk(dir__):
        for dirname in dirnames:
            if dirname == folder_name:
                return os.path.join(root, dirname).replace("\\", '/')
    return None


def packrom(edbgs, dbgs, dbfs, scale, parts, spatch, dely=0) -> any:
    if not dn.get():
        messpop(lang.warn1)
        return False
    else:
        if not os.path.exists(local + os.sep + dn.get()):
            messpop(lang.warn1, "red")
            return False
    load_car(0)
    work = rwork()

    for i in parts:
        print(i)
        dname = os.path.basename(i)
        if spatch == 1:
            for j in "vbmeta.img", "vbmeta_system.img", "vbmeta_vendor.img":
                file = str(findfile(j, work))
                if file:
                    if vbpatch.checkmagic(file):
                        print(lang.text71 % file)
                        vbpatch.disavb(file)
        if os.access(work + "config" + os.sep + "%s_fs_config" % dname, os.F_OK):
            try:
                folder = findfolder(work, "com.google.android.apps.nbu.")
                if folder:
                    call("mv {} {}".format(folder, folder.replace("com.google.android.apps.nbu.",
                                                                  "com.google.android.apps.nbu")))
                    rmdir(findfolder(work, "com.google.android.apps.nbu"))
                fspatch.main(work + dname, work + "config" + os.sep + dname + "_fs_config")
                qc.handle(work + "config" + os.sep + dname + "_fs_config")
                contextpatch.main(work + dname, work + "config" + os.sep + dname + "_file_contexts")
                qc.handle(work + "config" + os.sep + dname + "_file_contexts")
            except Exception as e:
                print(e)
            if os.access(work + "config" + os.sep + "%s_erofs" % dname, os.F_OK):
                mkerofs(dname, "%s" % (edbgs.get()), work)
                if dely == 1:
                    rdi(work, dname)
                print(lang.text3.format(dname))
                if dbgs.get() == "dat" or dbgs.get() == "br" or dbgs.get() == "sparse":
                    call('img2simg {}.img {}.simg'.format(work + dname, work + dname))
                    if os.path.exists(work + dname + ".simg"):
                        os.remove(work + dname + ".img")
                        os.rename(work + dname + ".simg", work + dname + ".img")
                    if dbgs.get() == 'dat':
                        datbr(work, dname, "dat")
                    elif dbgs.get() == 'br':
                        datbr(work, dname, scale.get())
                    else:
                        print(lang.text3.format(dname))
            else:

                if dbgs.get() == "dat" or dbgs.get() == "br" or dbgs.get() == "sparse":
                    if dbfs.get() == "make_ext4fs":
                        make_ext4fs(dname, work, "-s")
                    else:
                        mke2fs(dname, work, "y")
                    if dely == 1:
                        rdi(work, dname)
                    if dbgs.get() == "dat":
                        datbr(work, dname, "dat")
                    elif dbgs.get() == "br":
                        datbr(work, dname, scale.get())
                    else:
                        print(lang.text3.format(dname))
                else:
                    if dbfs.get() == "make_ext4fs":
                        make_ext4fs(dname, work, "")
                    else:
                        mke2fs(dname, work, "n")
                    if dely == 1:
                        rdi(work, dname)
    car.set(1)


def rdi(work, dname) -> any:
    if not os.listdir(work + "config"):
        rmtree(work + "config")
        return False
    if os.access(work + dname + ".img", os.F_OK):
        print(lang.text72 % dname)
        try:
            rmdir(work + dname, 1)
            if os.access(work + "config" + os.sep + "%s_erofs", os.F_OK):
                os.remove(work + "config" + os.sep + "%s_erofs" % dname)
            if os.access(work + "config" + os.sep + "%s_size.txt" % dname, os.F_OK):
                os.remove(work + "config" + os.sep + "%s_size.txt" % dname)
            os.remove(work + "config" + os.sep + "%s_file_contexts" % dname)
            os.remove(work + "config" + os.sep + "%s_fs_config" % dname)
        except Exception as e:
            print(lang.text73 % (dname, e))
        print(lang.text3.format(dname))
    else:
        messpop(lang.text75 % dname, "red")


def input_(title: str = lang.text76, text: str = "") -> str:
    inputvar = StringVar()
    inputvar.set(text)
    input__ = Toplevel()
    input__.geometry("300x180")
    input__.resizable(False, False)
    input__.title(title)
    ttk.Entry(input__, textvariable=inputvar).pack(pady=5, padx=5, fill=BOTH)
    ttk.Button(input__, text=lang.ok, command=input__.destroy).pack(padx=5, pady=5, fill=BOTH, side='bottom')
    jzxs(input__)
    input__.wait_window()
    return inputvar.get()


def unpackrom(ifile) -> int:
    zip_src = ifile
    print(lang.text77 + zip_src)
    ftype = gettype(ifile)
    load_car(0)
    if ftype == "ozip":
        print(lang.text78 + ifile)
        ozipdecrypt.main(ifile)
        try:
            os.remove(ifile)
        except Exception as e:
            messpop(lang.warn11.format(e))
        zip_src = os.path.dirname(ifile) + os.sep + os.path.basename(ifile)[:-4] + "zip"
    elif os.path.splitext(ifile)[1] == '.ofp':
        if ask_win(lang.t12) == 1:
            ofp_mtk_decrypt.main(ifile, local + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        else:
            ofp_qc_decrypt.main(ifile, local + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
        car.set(1)
        return 0
    if zipfile.is_zipfile(zip_src):
        fz = zipfile.ZipFile(zip_src, 'r')
        for fi in fz.namelist():
            try:
                file = fi.encode('cp437').decode('gbk')
            except:
                try:
                    file = fi.encode('cp437').decode('utf-8')
                except:
                    pass
            print(lang.text79 + file)
            try:
                fz.extract(file, local + os.sep + os.path.splitext(os.path.basename(zip_src))[0])
            except Exception as e:
                print(lang.text80 % (file, e))
                messpop(lang.warn4.format(file))
            finally:
                pass
        print(lang.text81)
        if os.path.exists(local + os.sep + os.path.splitext(os.path.basename(zip_src))[0]):
            listdir()
            dn.set(os.path.splitext(os.path.basename(zip_src))[0])
        else:
            listdir()
    else:
        if ftype != 'unknow':
            if os.path.exists(local + os.sep + os.path.splitext(os.path.basename(ifile))[0]):
                folder = local + os.sep + os.path.splitext(os.path.basename(ifile))[0] + v_code()
            else:
                folder = local + os.sep + os.path.splitext(os.path.basename(ifile))[0]
            try:
                os.mkdir(folder)
            except Exception as e:
                messpop(e)
            copy(ifile, folder)
            listdir()
            dn.set(os.path.basename(folder))
        else:
            print(lang.text82 % ftype)
    car.set(1)


def gettype(file) -> str:
    if not os.path.exists(file):
        return "fne"

    def compare(header: bytes, number: int = 0) -> int:
        with open(file, 'rb') as f:
            f.seek(number)
            return f.read(len(header)) == header

    def is_super(fil) -> any:
        with open(fil, 'rb') as file_:
            buf = bytearray(file_.read(4))
            if len(buf) < 4:
                return False
            file_.seek(0, 0)

            while buf[0] == 0x00:
                buf = bytearray(file_.read(1))
            try:
                file_.seek(-1, 1)
            except:
                return False
            buf += bytearray(file_.read(4))
        return buf[1:] == b'\x67\x44\x6c\x61'

    if is_super(file):
        return "super"
    for f_ in formats:
        if len(f_) == 2:
            if compare(f_[0]):
                return f_[1]
        elif len(f_) == 3:
            if compare(f_[0], f_[2]):
                return f_[1]
    return "unknow"


def rwork() -> str:
    return local + os.sep + dn.get() + os.sep


def unpack(chose, form: any = None):
    if not dn.get():
        messpop(lang.warn1)
        return False
    else:
        if not os.path.exists(local + os.sep + dn.get()):
            messpop(lang.warn1, "red")
            return False
    load_car(0)
    work = rwork()
    for fd in [f for f in os.listdir(work) if re.search(r'\.new\.dat\.\d+', f)]:
        with open(work + os.path.basename(fd).rsplit('.', 1)[0], 'ab') as ofd:
            for fd1 in sorted(
                    [f for f in os.listdir(work) if f.startswith(os.path.basename(fd).rsplit('.', 1)[0] + ".")],
                    key=lambda x: int(x.rsplit('.')[3])):
                print(lang.text83 % (fd1, os.path.basename(fd).rsplit('.', 1)[0]))
                with open(work + fd1, 'rb') as nfd:
                    ofd.write(nfd.read())
                os.remove(work + fd1)
    if os.access(work + "UPDATE.APP", os.F_OK):
        print(lang.text79 + "UPDATE.APP")
        splituapp.extract(work + "UPDATE.APP", "")
    if not chose:
        car.set(1)
        return 1
    if form == 'payload':
        print(lang.text79 + "payload")
        pay = open(work + "payload.bin", 'rb')
        payload_dumper.ota_payload_dumper( pay, work, 'store_true', 'old', chose)
        pay.close()
        if ask_win(lang.t9.format("payload.bin")) == 1:
            try:
                os.remove(work + "payload.bin")
            except Exception as e:
                print(lang.text72 + " payload.bin:%s" % e)
                os.remove(work + "payload.bin")
        car.set(1)
        return 1

    for i in chose:
        dname = os.path.basename(i).split('.')[0]
        if os.access(work + dname + ".new.dat.br", os.F_OK):
            print(lang.text79 + dname + ".new.dat.br")
            call("brotli -dj " + work + dname + ".new.dat.br")
        if os.access(work + dname + ".new.dat", os.F_OK):
            print(lang.text79 + work + dname + ".new.dat")
            if os.path.getsize(work + dname + ".new.dat") != 0:
                transferpath = os.path.abspath(os.path.dirname(work)) + os.sep + dname + ".transfer.list"
                if os.access(transferpath, os.F_OK):
                    sdat2img.main(transferpath, work + dname + ".new.dat", work + dname + ".img")
                    if os.access(work + dname + ".img", os.F_OK):
                        os.remove(work + dname + ".new.dat")
                        os.remove(transferpath)
                        try:
                            os.remove(work + dname + '.patch.dat')
                        except:
                            pass
                    else:
                        print("transferpath" + lang.text84)
        if os.access(work + dname + ".img", os.F_OK):
            if gettype(work + dname + ".img") == 'dtbo':
                undtbo(dname)
            if gettype(work + dname + ".img") == 'boot' or gettype(work + dname + ".img") == 'vendor_boot':
                jboot(dname)
            if dname == 'logo':
                logodump(dname)
            if gettype(work + dname + ".img") == 'vbmeta':
                print(f"{lang.text85}AVB:{dname}")
                vbpatch.disavb(work + dname + ".img")
            ftype = gettype(work + dname + ".img")
            if ftype == "sparse":
                print(lang.text79 + dname + ".img [%s]" % ftype)
                call("simg2img " + work + dname + ".img " + work + dname + ".rimg")
                try:
                    os.remove(work + dname + ".img")
                    os.rename(work + dname + ".rimg", work + dname + ".img")
                except:
                    messpop(lang.warn11.format(dname + ".img"))
            if gettype(work + dname + ".img") == 'super':
                print(lang.text79 + dname + ".img")
                if gettype(work + dname + ".img") == "sparse":
                    call("simg2img " + work + dname + ".img " + work + dname + ".rimg")
                    try:
                        os.remove(work + dname + ".img")
                        os.rename(work + dname + ".rimg", work + dname + ".img")
                    except:
                        messpop(lang.warn11.format(dname))
                lpunpack.unpack(work + dname + ".img", work)
                #
                if os.access(work + "system_a.img", os.F_OK):
                    # start
                    for wjm in os.listdir(work):
                        if wjm.endswith('_a.img'):
                            os.rename(work + wjm, work + wjm.replace('_a', ''))
                        if wjm.endswith('_b.img'):
                            if os.path.getsize(work + wjm) == 0:
                                os.remove(work + wjm)
                    # end
                    # supersz :2
                else:
                    # supersz :1
                    pass
            ftype = gettype(work + dname + ".img")
            if ftype == "ext":
                print(lang.text79 + dname + ".img [%s]" % ftype)
                try:
                    imgextractor.Extractor().main(work + dname + ".img", work + dname, work)
                except Exception as e:
                    print(f"Unpack Fail..{e}")
                    car.set(1)
                    return 0
                if os.path.exists(work + dname):
                    try:
                        os.remove(work + dname + ".img")
                    except Exception as e:
                        messpop(lang.warn11.format(dname + ".img:" + e))
            if ftype == "erofs":
                print(lang.text79 + dname + ".img [%s]" % ftype)
                call(exe="extract.erofs -i " + local + os.sep + dn.get() + os.sep + dname + ".img -o " + work + " -x",
                     out=1)
                with open(work + "config" + os.sep + dname + "_erofs", 'w') as f:
                    f.write("erofs")
                if os.access(work + "config" + os.sep + dname + "_fs_config", os.F_OK):
                    with open(work + "config" + os.sep + dname + "_fs_config", 'a', encoding='utf-8',
                              newline='\n') as fs:
                        fs.write("/lost+found 0 0 0777\r\n")
                if os.path.exists(work + dname):
                    try:
                        os.remove(work + dname + ".img")
                    except:
                        messpop(lang.warn11.format(dname + ".img"))

    car.set(1)
    print(lang.text8)


def ask_win(text='', ok=lang.ok, cancel=lang.cancel) -> int:
    value = IntVar()
    ask = Toplevel()
    ask.resizable(False, False)
    ttk.Label(ask, text=text, font=(None, 20)).pack()
    ttk.Button(ask, text=ok, command=lambda: close_ask(1)).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                expand=True)
    ttk.Button(ask, text=cancel, command=lambda: close_ask(0)).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                    expand=True)

    def close_ask(value_=1):
        value.set(value_)
        ask.destroy()

    jzxs(ask)
    ask.wait_window()
    return value.get()


class dirsize(object):
    # get-command
    # 1 - retun True value of dir size
    # 2 - return Rsize value of dir size
    # 3 - return Rsize value of dir size and modify dynampic_partition_list
    def __init__(self, dir: str, num: int = 1, get=2, list_f: str = None):
        self.rsize_v: int
        self.num = num
        self.get = get
        self.list_f = list_f
        self.dname = os.path.basename(dir)
        self.size = 0
        for root, dirs, files in os.walk(dir):
            self.size += sum([os.path.getsize(os.path.join(root, name)) for name in files if
                              not os.path.islink(os.path.join(root, name))])
        if self.get == 1:
            self.rsize_v = self.size
        elif self.get == 2 or self.get == 3:
            self.rsize(self.size, self.num)
        else:
            self.rsize_v = self.size

    def rsize(self, size: int, num: int):
        if size <= 1048576:
            size = 2097152
            bs = 1
        else:
            size = int(size + 10086)
            if size > 2684354560:
                bs = 1.0658
            elif size <= 2684354560:
                bs = 1.1158
            elif size <= 1073741824:
                bs = 1.1258
            elif size <= 536870912:
                bs = 1.1558
            elif size <= 104857600:
                bs = 1.4058
            else:
                bs = 1.258
        if self.get == 3:
            self.rsizelist(self.dname, int(size * bs), self.list_f)
        self.rsize_v = int(size * bs / num)

    @staticmethod
    def rsizelist(dname, size, file):
        if os.access(file, os.F_OK):
            print(lang.text74 % (dname, size))
            with open(file, 'r') as f:
                content = f.read()
            with open(file, 'w', encoding='utf-8', newline='\n') as ff:
                content = re.sub("resize {} \d+".format(dname),
                                 "resize {} {}".format(dname, size), content)
                content = re.sub("resize {}_a \d+".format(dname),
                                 "resize {}_a {}".format(dname, size), content)
                content = re.sub("# Grow partition {} from 0 to \d+".format(dname),
                                 "# Grow partition {} from 0 to {}".format(dname, size),
                                 content)
                content = re.sub("# Grow partition {}_a from 0 to \d+".format(dname),
                                 "# Grow partition {}_a from 0 to {}".format(dname, size), content)
                ff.write(content)


def datbr(work, name, brl):
    print(lang.text86 % (name, name))
    img2sdat.main(work + name + ".img", work, 4, name)
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


def mkerofs(name, level, work):
    print(lang.text90 % (name, level, "1.6"))
    call(
        f"mkfs.erofs -z{level} -T {int(time.time())} --mount-point=/{name} --product-out={work} --fs-config-file={work}config{os.sep}{name}_fs_config --file-contexts={work}config{os.sep}{name}_file_contexts {work + name}.img {work + name + os.sep}")


def make_ext4fs(name, work, sparse):
    print(lang.text91 % name)
    size = dirsize(work + name, 1, 3, work + "dynamic_partitions_op_list").rsize_v
    call(
        f"make_ext4fs -J -T {int(time.time())} {sparse} -S {work}config{os.sep}{name}_file_contexts -l {size} -C {work}config{os.sep}{name}_fs_config -L {name} -a {name} {work + name}.img {work + name}")


def mke2fs(name, work, sparse):
    print(lang.text91 % name)
    size = dirsize(work + name, 4096, 3, work + "dynamic_partitions_op_list").rsize_v
    if call(
            f"mke2fs -O ^has_journal -L {name} -I 256 -M /{name} -m 0 -t ext4 -b 4096 {work + name}_new.img {size}") != 0:
        rmdir(f'{work + name}_new.img', 1)
        print(lang.text75 % name)
        return False
    if call(
            f"e2fsdroid -e -T {int(time.time())} -S {work}config{os.sep}{name}_file_contexts -C {work}config{os.sep}{name}_fs_config -a /{name} -f {work + name} {work + name}_new.img") != 0:
        rmdir(f'{work + name}_new.img', 1)
        print(lang.text75 % name)
        return False
    if sparse == "y":
        call(f"img2simg {work + name}_new.img {work + name}.img")
        try:
            os.remove(work + name + "_new.img")
        except:
            pass
    else:
        os.rename(work + name + "_new.img", work + name + ".img")


class handle_log:
    @staticmethod
    def uploadlog():
        da = {'JXK_Myname': 'MKC',
              'JXK_Content': "%s" % (show.get(1.0, 'end-1c').encode('UTF-8'))
              }
        ret = requests.post('http://xzz.web3v.vip/bugreport/book/List.asp?Action=save', data=da)
        print(lang.text92 + str(ret.status_code))
        if ret.status_code != 200:
            messpop(lang.text93)
        else:
            print(lang.text94)

    @staticmethod
    def putlog():
        log = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        with open(local + os.sep + log + v_code() + '.txt', 'w', encoding='utf-8', newline='\n') as f:
            f.write(show.get(1.0, END))
        show.delete(1.0, END)
        print(lang.text95 + local + os.sep + log + v_code() + ".txt")


def selectp(self):
    print(lang.text96 + dn.get())


def listdir():
    array = []
    for f in os.listdir(local + os.sep + "."):
        if os.path.isdir(local + os.sep + f) and f != 'bin':
            array.append(f)
    if not array:
        dn.set("")
        LB1["value"] = array
        LB1.current()
    else:
        LB1["value"] = array
        LB1.current(0)


def delwork():
    if not dn.get():
        messpop(lang.warn1)
    else:
        rmdir(local + os.sep + dn.get())
    listdir()


def rmdir(path, up=0):
    if up == 0:
        load_car(0)
    if not path:
        messpop(lang.warn1)
    else:
        print(lang.text97 + f'{os.path.basename(path)}')
        try:
            try:
                rmtree(f'{path}')
            except:
                call(f'busybox rm -rf {path}')
        except:
            print(lang.warn11.format(path))
        if os.path.exists(path):
            messpop(lang.warn11.format(path))
        else:
            print(lang.text98 + path)
    if up == 0:
        car.set(1)


def newp():
    inputvar = input_()
    if not inputvar:
        messpop(lang.warn12)
    else:
        print(lang.text99 % inputvar)
        os.mkdir(local + os.sep + "%s" % inputvar)
    listdir()


def get_all_file_paths(directory) -> Ellipsis:
    # 初始化文件路径列表
    file_paths = []
    for root, directories, files in os.walk(directory):
        for filename in files:
            # 连接字符串形成完整的路径
            file_paths.append(os.path.join(root, filename))

    # 返回所有文件路径
    return file_paths


def setf(n, w):
    config.read(setfile)
    config.set("setting", "%s" % n, "%s" % w)
    with open(setfile, 'w') as fil:
        config.write(fil)


def set_theme(self):
    print(lang.text100 + theme.get())
    try:
        setf("theme", theme.get())
        sv_ttk.set_theme(theme.get())
        gif = Image.open("bin/images/loading_{}.gif".format(LB2.get()))
        loadgif(gif)
        gifl.configure(image=frames[1])
    except Exception as e:
        messpop(lang.text101 % (theme.get(), e))


def set_language(self):
    print(lang.text129 + language.get())
    try:
        setf("language", language.get())
        load(language.get())
    except Exception as e:
        print(lang.t130, e)


class zip_file(object):
    def __init__(self, file, dst_dir):

        relpath = os.path.abspath(file)
        os.chdir(dst_dir)
        file_paths_ = get_all_file_paths('.')
        with zipfile.ZipFile(relpath, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zip_:
            # 遍历写入文件
            for file in file_paths_:
                print(f"{lang.text1}:%s" % file)
                try:
                    zip_.write(file)
                except Exception as e:
                    print(lang.text2.format(file, e))
        if os.path.exists(relpath):
            print(lang.text3.format(relpath))
        os.chdir(elocal)


def packzip():
    if not dn.get():
        messpop(lang.warn1)
    else:
        load_car(0)
        print(lang.text91 % dn.get())
        zip_file(dn.get() + ".zip", local + os.sep + dn.get() + os.sep)
        car.set(1)


def modpath():
    folder = filedialog.askdirectory()
    if not folder:
        return False
    setf("path", folder)
    slocal.set(folder)
    loadset()


def cmm():
    if not dn.get():
        print(lang.warn1)
        return
    inputvar = input_(lang.text102 + dn.get(), dn.get())
    if os.path.exists(local + os.sep + inputvar):
        print(lang.text103)
        return False
    if inputvar != dn.get():
        os.rename(local + os.sep + dn.get(), local + os.sep + inputvar)
        listdir()
    else:
        print(lang.text104)


def dndfile(files):
    for fi in files:
        try:
            fi = fi.decode('gbk')
        except:
            fi = fi

        if os.path.exists(fi):
            if os.path.basename(fi).endswith(".mpk"):
                installmpk(fi)
            else:
                CallZ(unpackrom, fi)
        else:
            print(fi + lang.text84)


def sdxz(other):
    dndfile(filedialog.askopenfilename().split())


notepad.pack(fill=BOTH)
rzf = ttk.Frame(subwin3)
tsk = Label(subwin3, text="MIO-KITCHEN", font=('楷书', 15))
tsk.bind('<Button-1>')
tsk.pack(padx=10, pady=10, side='top')
tr = ttk.LabelFrame(subwin3, text=lang.text131)
Label(tr, text=lang.text132).pack(padx=10, pady=10, side='bottom')
tr.bind('<Button-1>', sdxz)
tr.pack(padx=5, pady=5, side='top', expand=True, fill=BOTH)
if os.name == 'nt':
    windnd.hook_dropfiles(tr, func=dndfile)
show = Text(rzf)
show.pack(side=LEFT, fill=BOTH, expand=True)
ttk.Button(rzf, text=lang.text105, command=lambda: show.delete(1.0, END)).pack(side='bottom', padx=10, pady=5,
                                                                               expand=True)
ttk.Button(rzf, text=lang.text106, command=handle_log().putlog).pack(side='bottom', padx=10, pady=5, expand=True)
ttk.Button(rzf, text=lang.text107, command=lambda: CallZ(handle_log().uploadlog)).pack(side='bottom', padx=10, pady=5,
                                                                                       expand=True)
rzf.pack(padx=5, pady=5, fill=BOTH, side='bottom')
# 项目列表的控件
sys.stdout = StdoutRedirector(show)
zyf1 = ttk.LabelFrame(tab, text=lang.text9)
zyf1.pack(padx=10, pady=10)
ttk.Button(zyf1, text=lang.text16, command=lambda: notepad.select(tab6)).pack(side='left',
                                                                              padx=10,
                                                                              pady=10)
ttk.Button(zyf1, text=lang.text114, command=lambda: CallZ(DownloadFile)).pack(side='left', padx=10, pady=10)
xmcd = ttk.LabelFrame(tab2, text=lang.text12)
info = ttk.LabelFrame(tab2, text="Rom信息")
frame1 = ttk.LabelFrame(tab2, text=lang.unpack)
frame2 = ttk.LabelFrame(tab2, text=lang.pack)
frame3 = ttk.LabelFrame(tab2, text=lang.text112)
LB1 = ttk.Combobox(xmcd, textvariable=dn, state='readonly')
LB1.pack(side="top", padx=10, pady=10, fill=X)
LB1.bind('<<ComboboxSelected>>', selectp)
ttk.Button(xmcd, text=lang.text23, command=listdir).pack(side="left", padx=10, pady=10)
ttk.Button(xmcd, text=lang.text115, command=newp).pack(side="left", padx=10, pady=10)
ttk.Button(xmcd, text=lang.text116, command=lambda: CallZ(delwork)).pack(side="left", padx=10, pady=10)
ttk.Button(xmcd, text=lang.text117, command=lambda: CallZ(cmm)).pack(side="left", padx=10, pady=10)


class unpackg(object):
    def __init__(self):
        ck = frame1
        self.fm = ttk.Combobox(ck, state="readonly", values=("dat", 'br', 'img', 'payload'))
        self.lsg = Listbox(ck, activestyle='dotbox', selectmode=MULTIPLE, highlightthickness=0)
        self.fm.current(0)
        self.fm.bind("<<ComboboxSelected>>", self.refs)

        self.lsg.pack(padx=5, pady=5, fill=X, side='top')
        ttk.Separator(ck, orient=HORIZONTAL).pack(padx=50, fill=X)
        self.fm.pack(padx=5, pady=5, fill=Y, side='left')
        ttk.Button(ck, text=lang.unpack, command=lambda: CallZ(self.close_)).pack(padx=5, pady=5, side='left')
        self.refs()

    def refs(self, N=None):
        work = rwork()
        self.lsg.delete(0, END)
        if not os.path.exists(work):
            messpop(lang.warn1)
            return False
        if self.fm.get() != 'payload' and self.fm.get() != 'super':
            for file_name in os.listdir(work):
                if file_name.endswith(self.fm.get()):
                    self.lsg.insert(END, file_name.rsplit('.')[0])
        else:
            if self.fm.get() == 'payload':
                if os.path.exists(work + "payload.bin"):
                    with open(work + "payload.bin", 'rb') as pay:
                        for i in payload_dumper.ota_payload_dumper(pay, work, 'store_true', 'old', '',
                                                                   0):
                            self.lsg.insert(END, i.partition_name)

    def close_(self):
        lbs = [self.lsg.get(index) for index in self.lsg.curselection()]
        self.refs()
        unpack(lbs, self.fm.get())


unpackg()
ttk.Button(frame2, text=lang.text118, command=lambda: CallZ(packxx)).pack(side="left", padx=10, pady=10)
ttk.Button(frame2, text=lang.text119, command=lambda: CallZ(dboot)).pack(side="left", padx=10, pady=10)
ttk.Button(frame2, text=lang.text120, command=lambda: CallZ(padtbo)).pack(side="left", padx=10, pady=10)
ttk.Button(frame2, text=lang.text121, command=lambda: CallZ(logopack)).pack(side="left", padx=10, pady=10)
ttk.Button(frame3, text=lang.text122, command=lambda: CallZ(packzip)).pack(side="left", padx=10, pady=10)
ttk.Button(frame3, text=lang.text123, command=lambda: CallZ(packss)).pack(side="left", padx=10, pady=10)
ttk.Button(frame3, text=lang.text19, command=lambda: CallZ(mpkman)).pack(side="left", padx=10, pady=10)
ttk.Button(frame3, text=lang.t13, command=lambda: CallZ(format_conversion)).pack(side="left", padx=10, pady=10)
xmcd.pack(padx=5, pady=5)
frame1.pack(padx=5, pady=5)
frame2.pack(padx=5, pady=5)
frame3.pack(padx=5, pady=5)
listdir()
# 设置的控件
slocal = StringVar()
slocal.set(local)
sf1 = ttk.Frame(tab3)
sf2 = ttk.Frame(tab3)
sf3 = ttk.Frame(tab3)
ttk.Label(sf1, text=lang.text124).pack(side='left', padx=10, pady=10)
LB2 = ttk.Combobox(sf1, textvariable=theme, state='readonly')
LB2["value"] = ["light", "dark"]
LB2.pack(padx=10, pady=10, side='left')
LB2.bind('<<ComboboxSelected>>', set_theme)


def startwjjj(self):
    if os.name == 'nt':
        os.startfile(slocal.get())


ttk.Label(sf3, text=lang.text125).pack(side='left', padx=10, pady=10)
slo = ttk.Label(sf3, textvariable=slocal)
slo.bind('<Button-1>', startwjjj)
slo.pack(padx=10, pady=10, side='left')
ttk.Button(sf3, text=lang.text126, command=modpath).pack(side="left", padx=10, pady=10)

ttk.Label(sf2, text=lang.lang).pack(side='left', padx=10, pady=10)
LB3 = ttk.Combobox(sf2, state='readonly', textvariable=language,
                   value=[i.rsplit('.')[0] for i in os.listdir(elocal + os.sep + "bin" + os.sep + "languages")])
LB3.pack(padx=10, pady=10, side='left')
LB3.bind('<<ComboboxSelected>>', set_language)
sf1.pack(padx=10, pady=10, fill='both')
sf2.pack(padx=10, pady=10, fill='both')
sf3.pack(padx=10, pady=10, fill='both')
# 关于我们
Label(tab4, text="MIO-KITCHEN", font=('楷书', 30)).pack(padx=20, pady=10)
Label(tab4, text=lang.text111, font=('楷书', 15), fg='#00BFFF').pack(padx=10, pady=10)
ttk.Separator(tab4, orient=HORIZONTAL).pack(padx=100, fill=X)
Label(tab4,
      text=lang.text128.format(VERSION, sys.version[:6], os.name, machine()),
      font=('楷书', 11), fg='#00aaff').pack(padx=10, pady=10)
ttk.Separator(tab4, orient=HORIZONTAL).pack(padx=100, fill=X)
Label(tab4,
      text=lang.text127,
      font=('楷书', 12), fg='#ff8800').pack(padx=10, pady=10)
ttk.Separator(tab4, orient=HORIZONTAL).pack(padx=100, fill=X)
tab4_1 = ttk.LabelFrame(tab4, text=lang.text9)
Label(tab4, text=lang.text110, font=('楷书', 10)).pack(padx=10, pady=10, side='bottom')
# ttk.Button(tab4_1, text="检查更新", command=lambda: CallZ(upgrade())).pack(padx=10, pady=10)
tab4_1.pack(padx=10, pady=10)
# tab4_2.pack(padx=10, pady=10)
# 捐赠
Label(tab6,
      text=f"Wechat Pay/微信支付",
      font=('楷书', 20), fg='#008000').pack(padx=10, pady=10)
photo = ImageTk.PhotoImage(Image.open('bin/images/wechat.gif'))
Label(tab6, image=photo).pack(padx=5, pady=5)
Label(tab6, text=lang.text109, font=('楷书', 12), fg='#00aafA').pack(padx=10, pady=10, side='bottom')


class format_conversion(Toplevel):
    def __init__(self):
        super().__init__()
        self.resizable(False, False)
        self.title(lang.t13)
        self.f = Frame(self)
        self.f.pack(pady=5, padx=5, fill=X)
        self.h = ttk.Combobox(self.f, values=("raw", "sparse", 'dat', 'br'), state='readonly')
        self.h.current(0)
        self.h.bind("<<ComboboxSelected>>", self.relist)
        self.h.pack(side='left', padx=5)
        Label(self.f, text='==》').pack(side='left', padx=5)
        self.f = ttk.Combobox(self.f, values=("raw", "sparse", 'dat', 'br'), state='readonly')
        self.f.current(0)
        self.f.pack(side='left', padx=5)
        self.list_b = Listbox(self, highlightthickness=0, activestyle='dotbox', selectmode=MULTIPLE)
        self.list_b.pack(padx=5, pady=5, fill=BOTH)
        self.relist()
        ttk.Button(self, text=lang.ok, command=lambda: CallZ(self.conversion)).pack(side=BOTTOM, fill=BOTH)
        jzxs(self)

    def relist(self, *other):
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
                    if gettype(work + i) == 'ext' or gettype(work + i) == 'erofs' or gettype(work + i) == 'super':
                        self.list_b.insert('end', i)

    @staticmethod
    def refile(f):
        work = rwork()
        a = []
        for i in os.listdir(work):
            if i.endswith(f):
                if os.path.isfile(work + i):
                    a.append(i)
        return a

    def conversion(self):
        work = rwork()
        fget = self.f.get()
        hget = self.h.get()
        selection = [self.list_b.get(index) for index in self.list_b.curselection()]
        self.destroy()
        load_car(0)
        if fget == hget:
            pass
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
                                sdat2img.main(transferpath, work + i, work + dname + ".img")
                                if os.access(work + dname + ".img", os.F_OK):
                                    os.remove(work + i)
                                    os.remove(transferpath)
                                    try:
                                        os.remove(work + dname + '.patch.dat')
                                    except:
                                        pass
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
                if hget == 'dat' or hget == 'br':
                    if os.path.exists(work):
                        if hget == 'br':
                            i = i.replace('.br', '')
                        print(lang.text79 + work + i)
                        if os.path.getsize(work + i) != 0:
                            transferpath = os.path.abspath(os.path.dirname(work)) + os.sep + dname + ".transfer.list"
                            if os.access(transferpath, os.F_OK):
                                sdat2img.main(transferpath, work + i, work + dname + ".img")
                                if os.access(work + dname + ".img", os.F_OK):
                                    try:
                                        os.remove(work + i)
                                        os.remove(transferpath)
                                        os.remove(work + dname + '.patch.dat')
                                    except:
                                        pass
                            else:
                                print("transferpath" + lang.text84)
                if hget == 'sparse':
                    call('simg2img {} {}'.format(work + i, work + i + 'r'))
                    if os.path.exists(work + i + 'r'):
                        try:
                            os.remove(work + i)
                            os.rename(work + i + 'r', work + i)
                        except Exception as e:
                            print(e)
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
                if hget == 'raw' or hget == 'sparse':
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
                if hget == 'raw' or hget == 'sparse':
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
        car.set(1)
        print(lang.text8)


def loadgif(gif):
    global frames
    frames = []
    try:
        while True:
            frames.append(ImageTk.PhotoImage(gif.copy()))
            gif.seek(len(frames))
    except EOFError:
        pass


loadgif(Image.open("bin/images/loading_%s.gif" % (LB2.get())))


class load_car(object):
    def __init__(self, ind: int = 0):
        frame = frames[ind]
        ind += 1
        if ind == len(frames):
            ind = 0
        gifl.configure(image=frame)
        self.gifs = gifl.after(30, load_car, ind)
        if car.get() == 1:
            self.endupdate()

    def endupdate(self):
        gifl.after_cancel(self.gifs)
        gifl.configure(image=frames[1])
        car.set(0)


gifl = Label(rzf)
gifl.pack(padx=10, pady=10)
load_car(0)
car.set(1)
print(lang.text108)
if os.name == "posix":
    if os.geteuid() != 0:
        print(lang.warn13)
else:
    win.iconphoto(True, tk.PhotoImage(file=elocal + os.sep + "bin" + os.sep + "images" + os.sep + "icon.png"))
jzxs(win)
CallZ(gettime)
if int(oobe) < 4:
    welcome()
print(lang.text134 % (dti() - start))
win.update()
win.mainloop(0)
