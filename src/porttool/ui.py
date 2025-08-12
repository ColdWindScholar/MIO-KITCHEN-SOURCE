from multiprocessing.dummy import DummyProcess
from tkinter import (
    ttk,
    Toplevel,
    StringVar,
    BooleanVar,
    Canvas, )
from tkinter.filedialog import askopenfilename

from src.core.utils import prog_path
from .configs import *
from .pathlib import Path
from .utils import portutils


class FileChooser(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Please choose boot, system from device and the port rom")

        self.portzip = StringVar()
        self.basesys = StringVar()
        self.baseboot = StringVar()

        basesys = Path("base/system.img")
        baseboot = Path("base/boot.img")
        if basesys.exists():
            self.basesys.set(basesys.absolute())
        if baseboot.exists():
            self.baseboot.set(baseboot.absolute())

        self.frame = []
        self.__setup_widgets()
        self.focus()

    def __setup_widgets(self):
        __match = {
            0: "Port Rom",
            1: "Boot from device",
            2: "System from device",
        }

        def __choose_file(val: StringVar):
            val.set(askopenfilename(initialdir=prog_path))
            self.focus()

        for index, current in enumerate((self.portzip, self.baseboot, self.basesys)):
            frame = ttk.Frame(self)
            self.frame.append([frame, ttk.Label(frame, text=__match.get(index, ''), width=16),
                               ttk.Entry(frame, textvariable=current, width=40),
                               ttk.Button(frame, text="Choose...", command=lambda x=current: __choose_file(x))])
        for i in self.frame:
            for index, widget in enumerate(i):
                if index == 0:  # frame
                    widget.pack(side='top', fill='x', padx=5, pady=5)
                elif index == 2:  # entry
                    widget.pack(side='left', fill='x', padx=5, pady=5)
                else:
                    widget.pack(side='left', padx=5, pady=5)
        bottom_frame = ttk.Frame(self)
        ttk.Button(bottom_frame, text='OK', command=self.destroy).pack(side='right', padx=5, pady=5)
        bottom_frame.pack(side='bottom', fill='x', padx=5, pady=5)

    def get(self) -> list:
        """
        return boot.img, system.img, portzip.zip path
        """
        self.wait_window(self)
        return [
            self.baseboot.get(),
            self.basesys.get(),
            self.portzip.get(),
        ]



class MyUI(ttk.Labelframe):
    def __init__(self, parent):
        super().__init__(parent, text="MTK LowLevel Machines Port Tool")
        self.chipset_select = StringVar(value='mt65')
        self.pack_type = StringVar(value='zip')
        self.item = []
        self.item_box = []  # save Checkbutton

        self.patch_magisk = BooleanVar(value=False)
        self.target_arch = StringVar(value='arm64')
        self.magisk_apk = StringVar(value="magisk.apk")
        self.__setup_widgets()

    def __start_port(self):
        # item check not 0
        if self.item.__len__() == 0:
            print("Error: 移植条目为0，请先加载移植条目！")
            return
        files = boot, system, portzip = FileChooser(self).get()
        for i in boot, system, portzip:
            if not Path(i).exists() or not i:
                print(f"File{i} Not chosen or not exists")
                return
        print(f"Boot from baserom：{boot}\n"
              f"System from baserom：{system}\n"
              f"Port Rom：{portzip}")
        # config items
        newdict = support_chipset_portstep[self.chipset_select.get()]
        for key, tkbool in self.item:
            newdict[key] = tkbool.get()

        # magisk stuff
        newdict['patch_magisk'] = self.patch_magisk.get()
        newdict['magisk_apk'] = self.magisk_apk.get()
        newdict['target_arch'] = self.target_arch.get()

        # start to port
        p = portutils(
            newdict, *files, self.pack_type.get() == 'img',
        ).start
        DummyProcess(target=p).start()

    def __setup_widgets(self):
        def __scroll_event(event):
            actcanvas.yview_scroll(int(-event.delta / 2), 'units')

        def __create_cv_frame():
            self.actcvframe = ttk.Frame(actcanvas)
            actcanvas.create_window(0, 0, window=self.actcvframe, anchor='nw')
            self.actcvframe.bind("<Configure>",
                                 lambda *x: actcanvas.configure(scrollregion=actcanvas.bbox("all"), width=300,
                                                                height=180))
            actcanvas.update()

        def __load_port_item(select):
            # select = self.chipset_select.get()
            print(f"选中移植方案为{select}...")
            item = support_chipset_portstep[select]['flags']
            # Destory last items
            self.item = []
            self.item_box = []
            try:
                self.actcvframe.destroy()
            except (Exception, BaseException):
                ...
            __create_cv_frame()

            for index, current in enumerate(item):
                self.item.append([current, BooleanVar(value=item[current])])  # flagname, flag[True, False]
                self.item_box.append(ttk.Checkbutton(self.actcvframe, text=current, variable=self.item[index][1]))

            for i in self.item_box:
                i.pack(side='top', fill='x', padx=5)

        # label of support devices
        optframe = ttk.Frame(self)
        optlabel = ttk.Label(optframe)

        ttk.Label(optlabel, text="SOC Type", anchor='e').pack(side='left', padx=5, pady=5, expand=False)
        ttk.OptionMenu(optlabel, self.chipset_select, support_chipset[0], *support_chipset,
                       command=__load_port_item).pack(side='left', fill='x', padx=5, pady=5, expand=False)
        optlabel.pack(side='top', fill='x')

        # Frame of support action
        actframe = ttk.Labelframe(optframe, text="Supported port item", height=180)

        actcanvas = Canvas(actframe)
        actscroll = ttk.Scrollbar(actframe, orient='vertical', command=actcanvas.yview)

        actcanvas.configure(yscrollcommand=actscroll.set)
        actcanvas.configure(scrollregion=(0, 0, 300, 180))
        actcanvas.configure(yscrollincrement=1)
        actcanvas.bind("<MouseWheel>", __scroll_event)

        actscroll.pack(side='right', fill='y')
        actcanvas.pack(side='right', fill='x', expand=True, anchor='e')
        actframe.pack(side='top', fill='x', expand=True)
        __create_cv_frame()

        # label of buttons
        buttonlabel = ttk.Label(optframe)
        ttk.Button(optframe, text="Port", command=self.__start_port).pack(side='top', fill='both', padx=5, pady=5,
                                                                              expand=True)
        ttk.Radiobutton(buttonlabel, text="Output to a zip rom", variable=self.pack_type, value='zip',
                        ).grid(column=0, row=0, padx=5, pady=5)
        ttk.Radiobutton(buttonlabel, text="Output to a image", variable=self.pack_type, value='img',
                        ).grid(column=1, row=0, padx=5, pady=5)

        magiskarch = ttk.OptionMenu(buttonlabel, self.target_arch, "arm64-v8a",
                                    *["arm64-v8a", "armeabi-v7a", "x86", "x86_64"])

        magiskapkentry = ttk.Entry(buttonlabel, textvariable=self.magisk_apk)
        magiskapkentry.bind("<Button-1>", lambda x: self.magisk_apk.set(askopenfilename()))

        ttk.Checkbutton(buttonlabel, text="Patch magisk", variable=self.patch_magisk, onvalue=True,
                        offvalue=False, command=lambda: (
                magiskapkentry.grid_forget(),
                magiskarch.grid_forget(),
            ) if not self.patch_magisk.get() else (  # 你在点的时候是函数还是没变的，所以反着来
                magiskapkentry.grid(column=0, row=3, padx=5, pady=5, sticky='nsew', columnspan=2),
                magiskarch.grid(column=0, row=2, padx=5, pady=5, sticky='nsew', columnspan=2)
            )).grid(column=0, row=1, padx=5, pady=5, sticky='w')
        buttonlabel.pack(side='top', padx=5, pady=5, fill='x', expand=True)
        optframe.pack(side='left', padx=5, pady=5, fill='y', expand=False)
        # log label
        __load_port_item(self.chipset_select.get())
