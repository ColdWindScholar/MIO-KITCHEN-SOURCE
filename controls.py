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
from tkinter.ttk import Frame, Scrollbar, Checkbutton, Separator
from tkinter import Canvas, Tk, X, BooleanVar, HORIZONTAL, TclError


class ListBox(Frame):
    def __init__(self, master, text=''):
        super().__init__(master=master)
        self.var = None
        self.set_all = None
        self.label_frame = None
        self.canvas = None
        self.selected: list = []
        self.vars = []
        self.controls = []

    def __on_mouse(self, event):
        self.canvas.yview_scroll(-1 * (int(event.delta / 120)), "units")

    def clear(self):
        self.selected.clear()
        for i in self.controls:
            try:
                i.destroy()
            except (TclError, AttributeError, ValueError):
                pass

    def gui(self):
        self.var = BooleanVar(value=False)
        scrollbar = Scrollbar(self, orient='vertical')
        scrollbar.pack(side='right', fill='y', padx=10, pady=10)
        self.canvas = Canvas(self, yscrollcommand=scrollbar.set, width=300, height=150)
        self.canvas.pack_propagate(False)
        self.canvas.pack(fill='both', expand=True)
        scrollbar.config(command=self.canvas.yview)
        self.label_frame = Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.label_frame, anchor='nw')
        self.canvas.bind_all("<MouseWheel>",
                             lambda event: self.__on_mouse(event))
        Separator(self, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        self.set_all = Checkbutton(self, text='全选', variable=self.var, onvalue=True, offvalue=False,
                                   command=lambda *x, var_=self.var: [i.set(True) for i in
                                                                      self.vars] if var_.get() else [i.set(False) for i
                                                                                                     in self.vars])
        self.set_all.pack(padx=5, pady=5, anchor='nw')
        self.update_ui()

    def update_ui(self):
        self.label_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

    def __set_value(self, var, value):
        if var.get():
            if value not in self.selected:
                self.selected.append(value)
        else:
            if value in self.selected:
                self.selected.remove(value)
        self.var.set(True if all(i.get() for i in self.vars) else False)

    def insert(self, text: str = '', value: str = ''):
        var = BooleanVar(value=False)
        c = Checkbutton(self.label_frame, text=text, variable=var, onvalue=True, offvalue=False)
        self.vars.append(var)
        args = (var, value)
        var.trace('w',
                  lambda *x, arg=args: self.__set_value(*arg))
        self.controls.append(c)
        c.pack(anchor='nw', fill='y', padx=5, pady=3)
        self.update_ui()


if __name__ == '__main__':
    a = Tk()
    b = ListBox(a, '测试')
    b.gui()
    b.insert('nb', 'n')
    b.insert('nb', 'n')
    b.insert('nb', 'n')
    b.insert('nb', 'n')
    b.insert('nb', 'n')
    b.pack(expand=True, fill='both')
    a.mainloop()
    print(b.selected)
