import os
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from tkinter import filedialog, ttk

import sv_ttk
from PIL import Image, ImageTk
from androguard.core.apk import APK
from loguru import logger

from src.core.utils import hum_convert, lang

logger.remove()

class ApkCard(tk.Frame):
    def __init__(self, parent, info, on_click, on_toggle):
        sv_ttk.use_dark_theme()
        super().__init__(parent, highlightthickness=1, highlightbackground="#2d3748")
        self.info = info
        self.on_toggle = on_toggle
        self.configure(width=280, height=80)
        self.pack_propagate(False)

        self.chk_var = tk.BooleanVar(value=info.get("selected", False))
        self.chk = ttk.Checkbutton(
            self, variable=self.chk_var, command=self._toggle_handler
        )
        self.chk.pack(side=tk.LEFT, padx=(10, 0))

        lbl_img = tk.Label(self, image=info["icon_img"])
        lbl_img.pack(side=tk.LEFT, padx=10)

        f_txt = tk.Frame(self)
        f_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=8)

        tk.Label(f_txt, text=info["internal_name"], font=("Segoe UI", 10, "bold"), fg="white",
                 anchor="w").pack(fill=tk.X)
        tk.Label(f_txt, text=info["package"], font=("Segoe UI", 8), fg="#a0aec0", anchor="w").pack(
            fill=tk.X)
        tk.Label(f_txt, text=f"{info['size']} • SDK {info['target_sdk']}", font=("Segoe UI", 8), fg="#718096"
                , anchor="w").pack(fill=tk.X)

        for w in (self, lbl_img, f_txt):
            w.bind("<Button-1>", lambda e: on_click(self.info, self))

    def _toggle_handler(self):
        self.on_toggle(self.info, self.chk_var.get())

    def update_checkbox(self, value):
        self.chk_var.set(value)

    def mark_selected(self, sel):
        self.configure(highlightbackground="#0078D4" if sel else "#2d3748", highlightthickness=2 if sel else 1)


class ApkManagerContent:
    def __init__(self, root):
        sv_ttk.use_dark_theme()
        self.root = root
        self.root.geometry("1300x600")
        self.root.configure()
        self.apk_data = []
        self.active_card = None
        self.icon_cache = []
        self.card_widgets = {}

        img = Image.new("RGBA", (48, 48), "#2d3748")
        self.default_icon = ImageTk.PhotoImage(img)
        self.icon_cache.append(self.default_icon)
        self.create_widgets()

    def create_widgets(self):
        top = ttk.Frame(self.root, height=40)
        top.pack(fill=tk.X)
        top.pack_propagate(False)

        self.lbl_status = tk.Label(top, text="Loaded 0 APK's", fg="#a0aec0",  font=("Segoe UI", 9, "bold"),
                                   padx=15)
        self.lbl_status.pack(side=tk.LEFT, fill=tk.Y)

        # Search Entry Bar
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_cards())
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, font=("Segoe UI", 9), width=30)
        self.search_entry.pack(side=tk.RIGHT, padx=15, pady=8)
        self.search_entry.bind("<FocusIn>", lambda e: self.search_entry.delete(0,
                                                                               tk.END) if self.search_var.get() == "search..." else None)


        ttk.Button(top, text=lang.import_debloat_list, command=self.import_debloat_list).pack(side=tk.RIGHT, padx=5, pady=3)
        ttk.Button(top, text=lang.export_debloat_list, command=self.export_debloat_list).pack(side=tk.RIGHT, padx=5, pady=3)


        ws = tk.Frame(self.root)
        ws.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        g_con = tk.Frame(ws)
        g_con.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(g_con, bd=0, highlightthickness=0)
        sb = ttk.Scrollbar(g_con, orient="vertical", command=self.canvas.yview)
        self.grid_frame = tk.Frame(self.canvas)
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        rp = tk.Frame(ws, width=340, highlightthickness=1, highlightbackground="#2d3748")
        rp.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        rp.pack_propagate(False)

        self.ins_icon = tk.Label(rp, image=self.default_icon)
        self.ins_icon.pack(pady=(20, 5))
        self.ins_name = tk.Label(rp, text=lang.select_an_apk, font=("Segoe UI", 12, "bold"), fg="white")
        self.ins_name.pack()

        self.meta_labels = {}
        for key in ["Version", "Min. SDK Version", "Target SDK Version"]:
            f = tk.Frame(rp)
            f.pack(fill=tk.X, padx=20, pady=4)
            tk.Label(f, text=f"{key}:", font=("Segoe UI", 9), fg="#a0aec0", width=15, anchor="w").pack(
                side=tk.LEFT)
            lbl = tk.Label(f, text="<none>", font=("Segoe UI", 9, "bold"), fg="white", anchor="w")
            lbl.pack(side=tk.LEFT, fill=tk.X)
            self.meta_labels[key] = lbl

        tk.Label(rp, text=lang.permissions, font=("Segoe UI", 9, "bold"), fg="#a0aec0").pack(anchor="w",
                                                                                                        padx=20,
                                                                                                        pady=(15, 2))
        self.list_perms = tk.Listbox(rp, fg="white", bd=0, highlightthickness=1,
                                     highlightbackground="#2d3748", font=("Consolas", 9))
        self.list_perms.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

    def export_debloat_list(self):
        f = filedialog.asksaveasfile(filetypes=[("Debloat List", ".txt")], title="Save debloat list", defaultextension=".txt")
        if f:
            for info in self.get_selected_apps_info():
                f.write(f"{info['package']}\n")

    def import_debloat_list(self):
        f = filedialog.askopenfilename(filetypes=[("Debloat List", "*.txt")])
        if f:
            with open(f, "r") as f:
                for line in f.readlines():
                    line = line.strip()
                    self.select_by_package(line)
    def select_dir(self, d):
        if d:
            for w in self.grid_frame.winfo_children(): w.destroy()
            self.apk_data.clear()
            self.card_widgets.clear()
            self.search_var.set("")
            self.active_card = None
            self.parse_dir(d)

    def parse_single_apk(self, path):
        try:
            apk = APK(path)
            size = hum_convert(os.path.getsize(path))

            icon_tk = self.default_icon
            icon_path = apk.get_app_icon(max_dpi=480)
            if icon_path:
                icon_data = apk.get_file(icon_path)
                if icon_data:
                    img = Image.open(BytesIO(icon_data))
                    img = img.resize((48, 48), Image.Resampling.LANCZOS)
                    icon_tk = ImageTk.PhotoImage(img)

            return {
                "success": True, "filename": os.path.basename(path), "package": apk.get_package() or "Unknown",
                "internal_name": apk.get_app_name() or os.path.basename(path), "size": size,
                "version": apk.get_androidversion_name() or "1.0", "target_sdk": apk.get_target_sdk_version() or "?",
                "min_sdk": apk.get_min_sdk_version() or "?", "permissions": apk.get_permissions() or [],
                "icon_img": icon_tk,
                "selected": False
            }
        except:
            return {"success": False}

    def parse_dir(self, d):
        self.lbl_status.config(text="Scanning...")
        files = [os.path.join(dp, f) for dp, _, fn in os.walk(d) for f in fn if f.lower().endswith(".apk")]

        count = 0
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as ex:
            for res in ex.map(self.parse_single_apk, files):
                if res.get("success"):
                    count += 1
                    self.add_card(res, count)
        self.lbl_status.config(text=f"Loaded {count} APK's completely.")

    def add_card(self, info, count):
        self.apk_data.append(info)
        self.icon_cache.append(info["icon_img"])
        self.lbl_status.config(text=f"[{count}] Parsing: {info['filename']}")
        card = ApkCard(self.grid_frame, info, self.on_click, self.on_toggle)
        self.card_widgets[info["package"]] = card
        self.filter_cards()

    def filter_cards(self):
        query = self.search_var.get().strip().lower()
        visible_idx = 0
        for info in self.apk_data:
            card = self.card_widgets.get(info["package"])
            if not card: continue
            if query:
                match = (query in info["package"].lower() or
                     query in info["filename"].lower() or
                     query in info["internal_name"].lower())
            else:
                match = 1

            if match:
                card.grid(row=visible_idx // 3, column=visible_idx % 3, padx=10, pady=10, sticky="nsew")
                visible_idx += 1
            else:
                card.grid_forget()

    def on_click(self, info, widget):
        if self.active_card:
            self.active_card.mark_selected(False)
        self.active_card = widget
        self.active_card.mark_selected(True)

        self.ins_icon.config(image=info["icon_img"])
        self.ins_name.config(text=info["internal_name"])
        self.meta_labels["Version"].config(text=info["version"])
        self.meta_labels["Min. SDK Version"].config(text=info["min_sdk"])
        self.meta_labels["Target SDK Version"].config(text=info["target_sdk"])

        self.list_perms.delete(0, tk.END)
        for p in info["permissions"]: self.list_perms.insert(tk.END, p.split(".")[-1])

    def on_toggle(self, info, is_checked):
        info["selected"] = is_checked

    def select_by_package(self, package_name, state=True):
        for info in self.apk_data:
            if info["package"] == package_name:
                info["selected"] = state
                if package_name in self.card_widgets:
                    self.card_widgets[package_name].update_checkbox(state)
                break

    def get_selected_apps_info(self):
        return [info for info in self.apk_data if info.get("selected")]

if __name__ == "__main__":
    root = tk.Tk()
    ttk.Style(root).theme_use("clam")
    app = ApkManagerContent(root)
    root.mainloop()