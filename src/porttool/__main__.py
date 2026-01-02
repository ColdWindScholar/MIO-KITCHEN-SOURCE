#!/usr/bin/env python3
from tkinter import Toplevel
from .ui import MyUI
from os import name

if name == 'nt':
    from multiprocessing.dummy import freeze_support

    freeze_support()


class Main(Toplevel):
    def __init__(self):
        super().__init__()
        self.title("MTK Port Tool")
        self.resizable(False, False)
        self.gui()
        self.mainloop()

    def gui(self):
        myapp = MyUI(self)
        myapp.pack(side='top', fill='both', padx=5, pady=5, expand=True)
        self.update()

