#!/usr/bin/env python3
from tkinter import Toplevel
from .ui import MyUI
from os import name

if name == 'nt':
    import ctypes
    from multiprocessing.dummy import freeze_support

    freeze_support()


class Main(Toplevel):
    def __init__(self):
        super().__init__()
        self.title("MTK Port Tool")
        self.gui()
        self.mainloop()

    def gui(self):
        myapp = MyUI(self)
        myapp.pack(side='top', fill='both', padx=5, pady=5, expand=True)
        # Fix high dpi
        if name == 'nt':
            # Tell system using self dpi adapt
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            # Get screen resize scale factor
            self.tk.call('tk', 'scaling', ctypes.windll.shcore.GetScaleFactorForDevice(0) / 75)
        self.update()

