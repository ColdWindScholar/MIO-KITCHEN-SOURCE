# File Choose Extra Module For MIO-KITCHEN
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
import os
from tkinter import Toplevel, Listbox, X, BOTH, LEFT, END, StringVar
from tkinter.ttk import Button, Entry, Frame, Combobox

from .utils import lang, create_thread, jzxs


def askopenfilename(title="Choose File", filetypes=(("*", "*.*"),)):
    return askopenfilenames(title=title, filetypes=filetypes).file


def askdirectory(title="Choose File"):
    return askdirectorys(title=title).file


class askopenfilenames(Toplevel):
    file = ""

    def __init__(self, title="Choose File", filetypes=(("*", "*.*"),)):
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.filetypes = filetypes
        self.type = Combobox(self, state='readonly', values=[i[1] for i in self.filetypes])
        try:
            self.type.current(0)
        finally:
            pass
        self.type.pack(fill=X, padx=5, pady=5)
        self.path = StringVar()
        self.paths = Entry(self, textvariable=self.path)
        self.paths.bind("<Return>", lambda x:self.p_bind())
        self.path.set(os.path.abspath("/"))
        self.paths.pack(fill=X, padx=5, pady=5)
        self.show = Listbox(self, activestyle='dotbox', highlightthickness=0)
        self.show.bind("<Double-Button-1>", lambda x:self.p_bind())
        self.show.pack(fill=BOTH, padx=5, pady=5)
        ff = Frame(self)
        Button(ff, text=lang.t56, command=self.return_var).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text=lang.text23, command=self.refs).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text=lang.cancel, command=self.cancel).pack(fill=X, side=LEFT, padx=5, pady=5)
        ff.pack(padx=5, pady=5, fill=X)
        create_thread(self.refs)
        jzxs(self)
        self.wait_window()

    def p_bind(self):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        var = os.path.abspath(os.path.join(self.path.get(), file))
        if os.path.isdir(var):
            self.path.set(var)
            create_thread(self.refs)
        elif os.path.isfile(var):
            self.return_var()

    def refs(self):
        self.show.delete(0, END)
        if not self.path.get():
            self.path.set(os.path.abspath("/"))
        f, e = self.type.get().replace("*", "").split(".")
        for f in os.listdir(self.path.get()):
            if f.startswith(f) and f.endswith(e):
                self.show.insert(END, f)

    def return_var(self):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        var = os.path.join(self.path.get(), file)
        if os.path.isfile(var):
            self.file = var
            self.destroy()

    def cancel(self):
        self.destroy()


class askdirectorys(Toplevel):
    file = ""

    def __init__(self, title="Choose File"):
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.path = StringVar()
        self.paths = Entry(self, textvariable=self.path)
        self.paths.bind("<Return>", self.p_bind)
        self.path.set(os.path.abspath("/"))
        self.paths.pack(fill=X, padx=5, pady=5)
        self.show = Listbox(self, activestyle='dotbox', highlightthickness=0)
        self.show.bind("<Double-Button-1>", self.p_bind)
        self.show.pack(fill=BOTH, padx=5, pady=5)
        ff = Frame(self)
        Button(ff, text=lang.t56, command=self.return_var).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text=lang.text23, command=self.refs).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text=lang.cancel, command=self.cancel).pack(fill=X, side=LEFT, padx=5, pady=5)
        ff.pack(padx=5, pady=5, fill=X)
        create_thread(self.refs)
        jzxs(self)
        self.wait_window()

    def p_bind(self, event):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        var = os.path.abspath(os.path.join(self.path.get(), file))
        if os.path.isdir(var):
            self.path.set(var)
            create_thread(self.refs)
        elif os.path.isfile(var):
            self.return_var()

    def refs(self):
        self.show.delete(0, END)
        if not self.path.get():
            self.path.set(os.path.abspath("/"))
        for f in os.listdir(self.path.get()):
            if os.path.isdir(os.path.join(self.path.get(), f)):
                self.show.insert(END, f)

    def return_var(self):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        self.file = os.path.join(self.path.get(), file)
        self.destroy()

    def cancel(self):
        self.destroy()
