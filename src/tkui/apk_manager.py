import os
import tkinter as tk
from tkinter import ttk

import logging
from androguard.core.apk import APK
from loguru import logger
from src.core.utils import hum_convert
# Remove the default logger console handler completely
logger.remove()


class ApkManagerContent:

    def __init__(self, root):
        self.root = root
        self.root.geometry("1000x550")
        self.apk_data_list = {}
        self.create_widgets()
        style = ttk.Style()

        style.map("Treeview",
                  background=[("selected", "#0078D4")],  # Custom Windows-like blue on select
                  foreground=[("selected", "#ffffff")],  # White text on select
                  )

    def create_widgets(self):
        self.lbl_status = tk.Label(
            self.root,
            text="Loaded 0 APK's",
            fg="#a0aec0",
            bg="#212b36",
            anchor="w",
            padx=10,
        )
        self.lbl_status.pack(fill=tk.X, pady=5)

        # 2. 中部核心表格
        columns = (
            "filename",
            "package",
            "internal_name",
            "size",
            "partition",
            "version",
            "target_sdk",
        )
        self.tree = ttk.Treeview(
            self.root,
            columns=columns,
            show="headings",
        )

        headers = {
            "filename": "Filename",
            "package": "Package",
            "internal_name": "Internal Name",
            "size": "Size",
            "partition": "Partition",
            "version": "Version",
            "target_sdk": "Target SDK",
        }
        for col, text in headers.items():
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=130, anchor="w")

        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_item_selected)

        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)

        left_pane = tk.Frame(bottom_frame)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        search_frame = tk.Frame(left_pane)
        search_frame.pack(fill=tk.X, pady=5)



        self.search_entry = tk.Entry(
            search_frame, fg="white", insertbackground="white"
        )
        self.search_entry.insert(0, "search...")
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.meta_labels = {}
        meta_keys = [
            "Version",
            "Min. SDK Version",
            "Target SDK Version",
            "Screen Sizes",
            "Screen Densities",
        ]
        for key in meta_keys:
            f = tk.Frame(left_pane)
            f.pack(fill=tk.X, pady=2)
            tk.Label(
                f, text=f"{key}:", fg="#a0aec0", width=18, anchor="w"
            ).pack(side=tk.LEFT)
            lbl_val = tk.Label(
                f, text="<none>", fg="white", anchor="w"
            )
            lbl_val.pack(side=tk.LEFT, fill=tk.X)
            self.meta_labels[key] = lbl_val

        right_pane = tk.Frame(bottom_frame)
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH)

        p_frame = tk.Frame(right_pane)
        p_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(p_frame, text="Permissions").pack(
            anchor="w"
        )
        self.list_perms = tk.Listbox(
            p_frame,
            width=25,
            height=6,
            bg="#1a202c",
            fg="white",
            selectbackground="#0078D4",
        )
        self.list_perms.pack()

        f_frame = tk.Frame(right_pane)
        f_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(f_frame, text="Features").pack(
            anchor="w"
        )
        self.list_features = tk.Listbox(
            f_frame,
            width=25,
            height=6,
            bg="#1a202c",
            fg="white",
            selectbackground="#0078D4",
        )
        self.list_features.pack()


    def parse_single_apk(self, full_path):
        f_size = hum_convert(os.path.getsize(full_path))
        apk = APK(full_path)
        return {
                "success": True,
                "filename": os.path.basename(full_path),
                "package": apk.get_package(),
                "internal_name": apk.get_app_name() or "<Unknown>",
                "size": f_size,
                "partition": os.path.dirname(os.path.dirname(full_path)).split("/")[-1:],
                "version": apk.get_androidversion_name(),
                "target_sdk": apk.get_target_sdk_version(),
                "min_sdk": apk.get_min_sdk_version(),
                "permissions": apk.get_permissions(),
                "features": apk.get_features(),
            }


    def start_parallel_parse(self, dir_path):
        count = 0
        self.lbl_status.config(
            text=f"Loading...")
        for dirpath, dirnames, filenames in os.walk(dir_path):
            for filename in filenames:
                if filename.endswith(".apk"):
                    self.lbl_status.config(
                        text=f"[{count}]Loading {filename}")
                    try:
                        res = self.parse_single_apk(os.path.join(dirpath, filename))
                    except Exception as e:
                        logging.exception(e)
                        continue
                    if res and res["success"]:
                        self.insert_tree_item(res)
                        count += 1
        self.lbl_status.config(
                text=f"Loaded {count} APK's")



    def insert_tree_item(self, info):
        item_id = self.tree.insert(
            "",
            tk.END,
            values=(
                info["filename"],
                info["package"],
                info["internal_name"],
                info["size"],
                info["partition"],
                info["version"],
                info["target_sdk"],
            ),
        )
        self.apk_data_list[item_id] = info

    def on_item_selected(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        item_id = selected_items[0]
        info = self.apk_data_list.get(item_id)
        if not info:
            return

        self.meta_labels["Version"].config(text=info["version"])
        self.meta_labels["Min. SDK Version"].config(text=info["min_sdk"])
        self.meta_labels["Target SDK Version"].config(text=info["target_sdk"])
        self.meta_labels["Screen Sizes"].config(text="Dynamic")
        self.meta_labels["Screen Densities"].config(text="Dynamic")

        self.list_perms.delete(0, tk.END)
        for perm in info["permissions"]:
            self.list_perms.insert(tk.END, perm.split(".")[-1])

        self.list_features.delete(0, tk.END)
        for feat in info["features"]:
            self.list_features.insert(tk.END, feat)



