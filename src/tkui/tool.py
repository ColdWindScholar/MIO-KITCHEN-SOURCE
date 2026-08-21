#!/usr/bin/env python3
# pylint: disable=line-too-long, missing-class-docstring, missing-function-docstring
# Copyright (C) 2022-2026 The MIO-KITCHEN-SOURCE Project
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
import gzip
import json
import platform
import shutil
import subprocess
import threading
import uuid
from contextlib import suppress
from functools import wraps
from tkinter.ttk import Scrollbar
from typing import Optional, Any

from qt_layer.widgets import TkinterEmbeddedPanel
from src.core import merge_sparse
from src.core import tarsafe
from src.core.Magisk import Magisk_patch
from src.core.addon_register import loader, Entry
from src.core.avb_disabler import process_fstab
from src.tkui.apk_manager import ApkManagerContent

try:
    from cpb_file import extract as extract_cpb
except ModuleNotFoundError:
    pass
from src.core.encryption_disabler import process_fstab_for_encryption
from src.core.ntpiutils import extractor as ntpiextractor
from src.core.ntpiutils import parser as ntpiparser
from src.core.pygpt.gpt_reader import GPTReader
from src.core.qsb_imger import process_by_xml
from src.core.romfs_parse import RomfsParse
from src.core.rsceutil import unpack as rsceutil_unpack, repack as rsceutil_repack
from src.core.splash_editor.main import splash_repack
from src.core.splash_editor.src.logo_gen_decoder import process_splashimg
from src.core.unkdz import KDZFileTools
from src.porttool.ui import MyUI
from ..core.payload_extract import extract_partitions_from_payload
from ..core.xtc_recovery_helper import decrypt as decrypt_xtc

pyi_splash_available = False
if platform.system() != 'Darwin':
    try:
        import pyi_splash

        pyi_splash.update_text('Loading ...')
        pyi_splash_available = True
    except ModuleNotFoundError:
        ...
import os.path
import pathlib
import sys
import time
from webbrowser import open as openurl
import tkinter as tk
from tkinter import ttk
from timeit import default_timer as dti

start = dti()
import zipfile
from src.core.aml_image import main as aml_main
from src.core.cpio import extract as cpio_extract, repack as cpio_repack
from io import BytesIO, StringIO
from tkinter import (BOTH, LEFT, RIGHT, Canvas, Text, X, Y, BOTTOM, StringVar, IntVar, TOP, Toplevel,
                     HORIZONTAL, TclError, Frame, Label, DISABLED, Menu, BooleanVar, CENTER)
from shutil import rmtree, copy, move
import pygments.lexers
import requests
from requests import ConnectTimeout, HTTPError
import sv_ttk
from PIL.Image import open as open_img
from PIL.ImageTk import PhotoImage
from src.core.utils import lang, LogoDumper, terminate_process, calculate_md5_file, calculate_sha256_file, \
    JsonEdit, ModuleErrorCodes, hum_convert, GuoKeLogo, img2simg, prog_path, GetFolderSize
from tkinter import filedialog

if os.name == 'nt':
    from ctypes import windll
    from multiprocessing.dummy import freeze_support

    freeze_support()
from src.core import imgextractor
from src.core import lpunpack
from src.core import mkdtboimg
from src.core import ozipdecrypt
from src.core import splituapp
from src.core import ofp_qc_decrypt
from src.core import ofp_mtk_decrypt
from . import editor
from src.core import opscrypto
from src.core import images
from src.core import extra
from src.core import ext4
from src.core.config_parser import ConfigParser
from src.core import utils
from src.core.unpac import MODE as PACMODE, unpac
from multiprocessing import cpu_count

from src.core.extra import fspatch, re, contextpatch
from src.core.utils import create_thread, move_center, v_code, gettype, is_empty_img, findfile, findfolder, Sdat2img, \
    Unxz
from .widgets import ListBox, input_
from src.core.undz import DZFileTools
from src.core.selinux_audit_allow import main as selinux_audit_allow
import logging

is_pro = False
try:
    from src.pro.sn import v as verify

    is_pro = True
except ImportError:
    verify = None
    is_pro = False
if is_pro:
    from src.pro.active_ui import Active

try:
    from src.core import imp
except ImportError:
    imp = None
try:
    from src.core.pycase import ensure_dir_case_sensitive
except ImportError:
    ensure_dir_case_sensitive = lambda *x: print(f'Cannot sensitive {x}, Not Supported')

cwd_path = utils.prog_path


class LoadAnim:
    """Manages animated loading indicators for background tasks.

    Attributes:
        gifs (list): Track active animation frames to prevent memory leaks
        tasks (dict): Map task IDs to their animation states
        task_num_index (int): Cyclic counter for task identification

    Methods handle animation lifecycle including start/stop operations
    with thread-safe task tracking.
    """
    gifs = []

    def __init__(self, master=None):
        """Initializes the LoadAnim instance.

        Args:
            master: The parent Tkinter widget (optional).
        """
        self.master = master  # The parent widget where the GIF label will be displayed.
        self.frames = []  # Stores individual frames of the GIF.
        self.hide_gif = False  # Flag to control GIF visibility.
        self.frame = None  # The current GIF frame being displayed.
        self.tasks = {}  # Dictionary to keep track of running tasks associated with the animation.
        self.task_num_index = 0  # Index for assigning unique task numbers.
        self.task_num_max = cpu_count()  # Maximum number of concurrent tasks (for task_num_index cycling).

    def run(self, ind: int = 0):
        """Cycles through GIF frames to create the animation.

        This method is called recursively using `after` to display the next frame.

        Args:
            ind: The index of the current frame to display.
        """
        self.hide_gif = False
        if not self.master or not hasattr(self.master, 'gif_label'):
            logging.warning('Master\'s not set! Skip Animation init.')
            return 1
        if not self.hide_gif:
            try:
                self.master.gif_label.pack(padx=10, pady=10)
            except RuntimeError:
                return 1
        self.frame = self.frames[ind]
        ind = (ind + 1) % len(self.frames)
        self.master.gif_label.configure(image=self.frame)
        self.gifs.append(self.master.gif_label.after(30, self.run, ind))
        return 0

    def get_task_num(self):
        """Generates a unique task number for tracking.

        Returns:
            An integer representing the task number.
        """
        self.task_num_index = (self.task_num_index + 1) % self.task_num_max
        return self.task_num_index

    def stop(self):
        """Stops the animation and hides the GIF.

        Cancels all scheduled frame updates and hides the label.
        """
        for i in self.gifs:
            try:
                self.master.gif_label.after_cancel(i)
            except (Exception, BaseException):
                # Log any exceptions during cancellation, as it might indicate a minor issue.
                logging.exception('Error stopping GIF animation')
        if hasattr(self.master, 'gif_label'):
            self.master.gif_label.pack_forget()
        self.hide_gif = True

    def init(self):
        """Initializes and immediately stops the animation.

        Used for pre-loading or setup purposes if needed,
        though its current implementation just runs and stops.
        """
        self.run()
        self.stop()

    def load_gif(self, gif):
        """Loads frames from a GIF image.

        Args:
            gif: An opened PIL.Image object representing the GIF.
        """
        self.frames.clear()
        while True:
            # Append each frame of the GIF to the internal list.
            self.frames.append(PhotoImage(gif))
            try:
                gif.seek(len(self.frames))  # Move to the next frame.
            except EOFError:
                break  # Reached the end of the GIF.

    def __call__(self, func):
        """Makes the LoadAnim instance callable, acting as a decorator.

        Allows wrapping functions to automatically show the loading
        animation while the function executes in a separate thread.

        Args:
            func: The function to be decorated.

        Returns:
            The wrapper function.
        """

        @wraps(func)
        def call_func(*args, **kwargs):
            return_value = None

            def wrapper():
                nonlocal return_value
                return_value = func(*args, **kwargs)

            """The wrapper function that manages the animation and task execution."""
            # Start the animation in a new thread to avoid blocking the UI.
            if len(self.tasks) >= self.task_num_max or utils.threads >= self.task_num_max:
                return lambda *a, **k: print("Cannot create new thread.The thread pool has been filled.")
            self.run()
            task_num = self.get_task_num()
            # The actual function execution also happens in a separate thread.
            task_real = create_thread(wrapper, join=True)
            info = [func.__name__, args, task_real]
            if task_num in self.tasks:
                return lambda *a, **k: print(
                    f"Error: Task number {task_num} is being used by {task_real} for {info[0]}.")
            self.tasks[task_num] = info
            if task_num in self.tasks:
                del self.tasks[task_num]
            # 'info' or 'task_num' go out of scope automatically.

            # If no other tasks are running, stop the animation.
            if not self.tasks:
                self.stop()
            return return_value

        return call_func


def warn_win(text: str = '', color: str = 'red', title: str | None = None,
             master: Optional[tk.Toplevel] = None) -> None:
    """
    Displays a modal warning/error window that stays until the user closes it.

    This function creates a modal dialog that remains on top of its parent
    window. It is designed for displaying critical errors or warnings that
    require user acknowledgment. The window is automatically centered.

    Args:
        text: The message to be displayed in the window.
        color: The color of the message text. Defaults to 'red' for errors.
        title: The title of the dialog window.
        master: The parent widget for this dialog. If None, the main application
                window (`win`) is used as the parent.
    """
    # Determine the parent window; default to the main app window if not specified.
    parent = master or win.tk_root
    if not title:
        title = lang.warning

    popup_window = Toplevel()  # Use the custom Toplevel for theme consistency.
    popup_window.title(title)

    # 1. Make the window "transient" to its parent. This ensures it always
    #    stays on top of the parent window.
    popup_window.transient(parent)

    # 2. Set a "grab". This makes the window modal, preventing any interaction
    #    with the parent window until this dialog is closed.
    popup_window.grab_set()

    ask_frame = ttk.Frame(popup_window, padding=(20, 10))
    ask_frame.pack(expand=True, fill=BOTH)

    msg_label = ttk.Label(ask_frame, text=text, font=(None, 14), foreground=color, wraplength=350,
                          justify='center')
    msg_label.pack(pady=(10, 20), expand=True, fill='x')

    def close_popup() -> None:
        """Releases the modal grab and destroys the popup window."""
        popup_window.grab_release()
        popup_window.destroy()

    # Add an "OK" button that the user must click to close the window.
    ok_text = lang.ok  # Use localized text for the button.
    ok_button = ttk.Button(ask_frame, text=ok_text, command=close_popup, style="Accent.TButton")
    ok_button.pack(pady=(0, 10), padx=20, fill=X, ipady=4)  # ipady adds vertical padding inside the button.

    popup_window.update_idletasks()
    move_center(popup_window)  # Center the dialog on the screen.

    # This crucial line pauses the execution of the calling code until the
    # popup_window is destroyed, enforcing the modal behavior.
    parent.wait_window(popup_window)


class CustomWidgets:
    """Provides static methods for creating common custom UI control groups.

    Encapsulates the creation of frequently used compound widgets,
    like a label, entry, and button for file selection, to reduce
    boilerplate code in the main UI construction.
    """

    def __init__(self):
        """Initializes the CustomControls instance.

        This class currently only contains static methods, so the constructor is empty.
        """
        pass

    @staticmethod
    def filechose(master, textvariable: tk.Variable, text: str, is_folder: bool = False):
        """Creates a file/folder selection widget group.

        This group consists of a label, an entry to display the path,
        and a button to open a file/folder dialog.

        Args:
            master: The parent Tkinter widget.
            textvariable: A tk.Variable to store the selected path.
            text: The text for the label.
            is_folder: If True, opens a directory chooser; otherwise, a file chooser.
        """
        ft = ttk.Frame(master)
        ft.pack(fill=X)
        ttk.Label(ft, text=text, width=15, font=(None, 12)).pack(side='left', padx=10, pady=10)
        ttk.Entry(ft, textvariable=textvariable).pack(side='left', padx=5, pady=5)
        # Use a lambda to decide whether to ask for a file or directory.
        ttk.Button(ft, text=lang.text28,  # Assuming lang.text28 is 'Browse' or similar
                   command=lambda: textvariable.set(
                       filedialog.askopenfilename() if not is_folder else filedialog.askdirectory())).pack(side='left',
                                                                                                           padx=10,
                                                                                                           pady=10)

    @staticmethod
    def combobox(master, textvariable: tk.Variable, values: list | tuple[str, ...], text: str, state: str = 'normal'):
        """Creates a labeled combobox widget group.

        This group consists of a label and a combobox.

        Args:
            master: The parent Tkinter widget.
            textvariable: A tk.Variable to store the selected value.
            values: A list of values for the combobox dropdown.
            text: The text for the label.
            state: The state of the combobox (e.g., 'normal', 'readonly').
        """
        ft = ttk.Frame(master)
        ft.pack(fill=X)
        ttk.Label(ft, text=text, width=15, font=(None, 12)).pack(side='left', padx=10, pady=10)
        ttk.Combobox(ft, textvariable=textvariable, values=values, state=state).pack(side='left', padx=5, pady=5)


c_widgets = CustomWidgets()


class ToolBox(ttk.Frame):
    """A ttk.Frame subclass serving as a container for various tool buttons.

    Designed to group utility functions, each launched by a button,
    within a scrollable area. Each tool often opens its own Toplevel window for interaction.
    """

    def __init__(self, master):
        """Initializes the ToolBox frame.

        Args:
            master: The parent Tkinter widget.
        """
        super().__init__(master=master)
        # Use a lambda for the mouse wheel scroll event for conciseness.
        self.__on_mouse = lambda event: self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

    def pack_basic(self):
        """Sets up the basic scrollable canvas structure for the toolbox.

        Creates a Canvas with a vertical Scrollbar and a Frame inside the Canvas
        to hold the actual content (buttons).
        """
        scrollbar = Scrollbar(self, orient='vertical')
        scrollbar.pack(side='right', fill='y', padx=10, pady=10)
        self.canvas = Canvas(self, yscrollcommand=scrollbar.set)
        self.canvas.pack_propagate(False)  # Prevents the canvas from shrinking to fit its content.
        self.canvas.pack(fill='both', expand=True)
        scrollbar.config(command=self.canvas.yview)
        self.label_frame = Frame(self.canvas)  # This frame will contain the tool buttons.
        self.canvas.create_window((0, 0), window=self.label_frame, anchor='nw')
        # Bind the mouse wheel event to the canvas for scrolling.
        self.canvas.bind_all("<MouseWheel>",
                             lambda event: self.__on_mouse(event))

    def gui(self):
        """Populates the toolbox with buttons for different tools.

        Defines a list of tool names (from `lang` for localization) and their
        corresponding callback functions, then arranges them in a grid.
        """
        self.pack_basic()
        functions = [
            (lang.t59, self.GetFileInfo),  # Get File Info
            (lang.t60, self.FileBytes),  # File Bytes Operations
            (lang.audit_allow, self.SelinuxAuditAllow),  # Selinux Audit Allow
            (lang.disable_avb, self.DisableAVB),
            (lang.disable_encryption, self.DisableEncryption),
            (lang.trim_image, self.TrimImage),  # Trim Image
            (lang.magisk_patch, self.MagiskPatcher),  # Magisk Patcher
            (lang.mergequalcommimage, self.MergequalcommimageOld),  # Merge Qualcomm Image (Legacy)
            (lang.merge_file_segments, self.MergeSparseImage),
            (lang.decrypt_xtc_xml, self.DecryptXtcXml),
            (lang.mtk_port_tool, self.MtkPortTool),
        ]
        width_controls = 3  # Number of buttons per row.
        index_row = 0
        index_column = 0
        for text, func in functions:
            ttk.Button(self.label_frame, text=text, command=func, width=17).grid(row=index_row, column=index_column,
                                                                                 padx=5, pady=5)
            index_column = (index_column + 1) % width_controls
            if not index_column:  # Move to the next row if the current one is full.
                index_row += 1
        self.update_ui()  # Adjusts the scroll region after adding buttons.

    def update_ui(self):
        """Updates the canvas scroll region to fit its content.

        I call this after adding or removing widgets from `label_frame`
        to ensure the scrollbar behaves correctly.
        """
        self.label_frame.update_idletasks()  # Ensure all pending geometry changes are processed.
        self.canvas.config(scrollregion=self.canvas.bbox('all'), highlightthickness=0)

    class MtkPortTool(Toplevel):
        def __init__(self):
            super().__init__()
            self.title("MTK Port Tool")
            self.gui()

        def gui(self):
            myapp = MyUI(self)
            myapp.pack(side='top', fill='both', padx=5, pady=5, expand=True)
            move_center(self)
            self.update()

    class DecryptXtcXml(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.decrypt_xtc_xml)
            self.path = StringVar()
            self.gui()
            move_center(self)

        def gui(self):
            c_widgets.filechose(self, self.path, lang.path, is_folder=True)
            ttk.Button(self, text=lang.run, command=lambda: create_thread(self.run)).pack(padx=5, pady=5, fill='both')

        def run(self):
            if not self.path.get() or not os.path.exists(self.path.get()):
                warn_win('Please choose a path.')
                return
            self.destroy()
            for root, _, files in os.walk(self.path.get(), topdown=True):
                for f in files:
                    if f.endswith('.xml'):
                        print(f"Decrypting {f}")
                        decrypt_xtc(os.path.join(root, f))

    class MergequalcommimageOld(Toplevel):
        """A Toplevel window for merging Qualcomm sparse images using rawprogram.xml (Legacy version).

        I created this to provide a UI for an older method of merging Qualcomm firmware images.
        It takes a rawprogram.xml, partition name, and output path.
        """

        def __init__(self):
            """Initializes the MergeQualcommImage_old window."""
            super().__init__()
            self.title(lang.mergequalcommimage)
            self.rawprogram_xml = StringVar()  # Path to the rawprogram.xml file.
            self.partition_name = StringVar()  # Name of the partition to merge (e.g., 'system').
            self.output_path = StringVar()  # Directory to save the merged image.
            self.gui()
            move_center(self)  # Centers the window on the screen.

        def gui(self):
            """Creates the GUI elements for the MergeQualcommImage_old window."""
            c_widgets.filechose(self, self.rawprogram_xml, 'RawProgram Xml：')
            c_widgets.combobox(self, self.partition_name, ('system', 'userdata', 'cache'), lang.partition_name)
            c_widgets.filechose(self, self.output_path, lang.output_path, is_folder=True)
            ttk.Button(self, text=lang.run, command=lambda: create_thread(self.run)).pack(padx=5, pady=5, fill='both')

        def run(self):
            """Executes the image merging process in a separate thread."""
            rawprogram_xml = self.rawprogram_xml.get()
            if not os.path.exists(rawprogram_xml):
                # I inform the user if the XML file is not found.
                print(f'Raw Program XML not found: {rawprogram_xml}')
                warn_win(f'Raw Program XML not found: {rawprogram_xml}')
                return 1
            partition_name = self.partition_name.get()
            output_path = self.output_path.get()
            if not output_path:
                # I inform the user if the output path is not selected.
                print('Output path not selected.')
                warn_win('Please choose an output path.')
                return 1
            if not os.path.exists(output_path):
                os.makedirs(output_path, exist_ok=True)

            self.destroy()  # I close the dialog before starting the potentially long process.
            try:
                process_by_xml(rawprogram_xml, partition_name, output_path)
                # I inform the user of success.
                info_win('Image merging completed successfully!')
            except Exception as e:
                # I log the error and inform the user of failure.
                print(f'Merge failed: {e}')
                logging.exception('MergeQC RAWPROGRAM error')
                warn_win(f'Image merging failed: {str(e)}')  # Displaying the error message to the user.
            # No explicit return None needed here as the function naturally returns None if no other return is hit.

    class MagiskPatcher(Toplevel):
        """A Toplevel window for patching boot images with Magisk.

        I designed this to provide a user interface for selecting a boot image,
        a Magisk APK, and various patching options, then initiating the patch process.
        """

        def __init__(self):
            """Initializes the MagiskPatcher window."""
            super().__init__()
            # I initialize StringVars for APK and boot file paths here for clarity,
            # even if they are fully defined in gui().
            self.magisk_apk = StringVar()  # Stores the path to the selected Magisk APK.
            self.boot_file = StringVar()  # Stores the path to the selected boot image file.
            self.title(lang.magisk_patch)
            self.gui()
            move_center(self)

        def get_arch(self, apk_path=None) -> list:
            """Retrieves supported architectures from a Magisk APK.

            Args:
                apk_path: Path to the Magisk APK. If None, uses self.magisk_apk.get().

            Returns:
                A list of supported architectures (e.g., ["arm64-v8a"]), or a default if APK is invalid.
            """
            if not apk_path:
                apk_path = self.magisk_apk.get()  # Use the instance's Magisk APK path if none provided.
            if not apk_path or not os.path.exists(apk_path):
                # I return a default architecture if the APK path is invalid or doesn't exist.
                return ["arm64-v8a"]
            try:
                # I use the Magisk_patch utility to extract architecture information.
                with Magisk_patch(None, None, None, None, MAGISAPK=apk_path) as m:
                    return m.get_arch()
            except Exception as e:
                # I log the error and return a default if Magisk_patch fails, also warning the user.
                logging.error(f"Failed to get arch from Magisk APK {apk_path}: {e}")
                warn_win(f"Could not read architectures from {os.path.basename(apk_path)}.")
                return ["arm64-v8a"]

        def chose_file_refresh(self):
            """Handles Magisk APK file selection and refreshes the architecture combobox.
            I open a file dialog for the user to select an APK, then update the UI.
            """
            file_path = filedialog.askopenfilename(title="Select Magisk APK",
                                                   filetypes=(("APK files", "*.apk"), ("All files", "*.*")))
            if file_path:  # I only proceed if a file was actually selected by the user.
                self.magisk_apk.set(file_path)
                # I update the architectures combobox based on the newly selected APK.
                self.archs.configure(value=self.get_arch(file_path))
            self.lift()  # I ensure the window remains on top after the dialog closes.
            self.focus_force()  # And give it focus.

        def patch(self):
            """Performs the Magisk patching operation in a separate thread.
            I disable the patch button, prepare paths, validate inputs, and then run the patcher.
            """
            self.patch_bu.configure(state="disabled", text=lang.running)  # I disable the button during patching.
            local_path = str(os.path.join(temp, v_code()))  # Generate a unique temporary working directory.
            re_folder(local_path)  # I ensure the temporary folder is clean or created.

            boot_file_path = self.boot_file.get()
            magisk_apk_path = self.magisk_apk.get()

            # Input validation before proceeding with patching.
            if not boot_file_path or not os.path.exists(boot_file_path):
                warn_win("Boot image not selected or not found.")
                self.patch_bu.configure(state="normal", text=lang.patch)  # Re-enable button.
                return

            if not magisk_apk_path or not os.path.exists(magisk_apk_path):
                warn_win("Magisk APK not selected or not found.")
                self.patch_bu.configure(state="normal", text=lang.patch)  # Re-enable button.
                return

            try:
                # I pass all necessary parameters to the Magisk_patch utility.
                with Magisk_patch(boot_file_path, None, f"{settings.tool_bin}/magiskboot", local_path,
                                  self.IS64BIT.get(),
                                  self.KEEPVERITY.get(), self.KEEPFORCEENCRYPT.get(),
                                  self.RECOVERYMODE.get(), magisk_apk_path, self.magisk_arch.get()
                                  ) as m:
                    m.auto_patch()  # Perform the automated patching process.
                    if m.output:
                        # I construct a unique output file name to avoid overwriting existing files.
                        base_name = os.path.basename(boot_file_path)
                        # Handle common image extensions like .img and .bin for name stripping.
                        name_part = base_name
                        for ext in ('.img', '.bin'):  # I check for common extensions.
                            if base_name.lower().endswith(ext):
                                name_part = base_name[:-len(ext)]
                                break
                        output_file = os.path.join(cwd_path,
                                                   f"{name_part}_magisk_patched.img")
                        if os.path.exists(output_file):
                            # If the default patched name exists, I add a unique code to the new one.
                            output_file = os.path.join(cwd_path,
                                                       f"{name_part}_{v_code()}_magisk_patched.img")
                        os.rename(m.output, output_file)  # Move the patched file to the final destination.
                        print(f"Done! Patched Boot: {output_file}")
                        info_win(f"Patched Boot:\n{output_file}")  # Inform the user of success.
                    else:
                        warn_win("Magisk patching process did not produce an output file.")
            except Exception as e:
                # I log any exceptions during patching and inform the user.
                logging.exception("Magisk patching error")
                warn_win(f"Magisk patching failed: {str(e)}")
            finally:
                # I always re-enable the patch button, regardless of success or failure.
                self.patch_bu.configure(state="normal", text=lang.patch)

        def gui(self):
            """Creates the GUI elements for the MagiskPatcher window.
            I set up labels, entries, buttons, and checkboxes for user interaction.
            """
            ttk.Label(self, text=lang.magisk_patch).pack(pady=(5, 10))  # Add some padding to the title label.

            # Boot file selection section
            ft_boot = ttk.Frame(self)
            ft_boot.pack(fill='x', padx=5, pady=2)
            ttk.Label(ft_boot, text=lang.boot_file, width=12).pack(side='left', padx=(0, 5),
                                                                   pady=5)  # Standardized label width.
            ttk.Entry(ft_boot, textvariable=self.boot_file).pack(side='left', padx=5, pady=5, expand=True, fill='x')
            ttk.Button(ft_boot, text=lang.text28,  # Assuming lang.text28 is 'Browse' or similar.
                       command=lambda: self.boot_file.set(
                           filedialog.askopenfilename(title="Select Boot Image",
                                                      filetypes=(("Image files", "*.img *.bin"),
                                                                 ("All files", "*.*"))))).pack(side='left', padx=(5, 0),
                                                                                               pady=5)

            # Magisk APK selection section
            ft_apk = ttk.Frame(self)
            ft_apk.pack(fill=X, padx=5, pady=2)
            ttk.Label(ft_apk, text=lang.magisk_apk, width=12).pack(side='left', padx=(0, 5),
                                                                   pady=5)  # Standardized label width.
            ttk.Entry(ft_apk, textvariable=self.magisk_apk).pack(side='left', padx=5, pady=5, expand=True, fill=X)
            ttk.Button(ft_apk, text=lang.text28,  # Assuming lang.text28 is 'Browse'.
                       command=self.chose_file_refresh).pack(side='left', padx=(5, 0), pady=5)  # No lambda needed here.

            # Architecture selection section
            ft_arch = ttk.Frame(self)
            ft_arch.pack(fill=X, padx=5, pady=2)
            self.magisk_arch = StringVar(value='arm64-v8a')  # Default architecture.
            ttk.Label(ft_arch, text=lang.arch, width=12).pack(side='left', padx=(0, 5),
                                                              pady=5)  # Standardized label width.
            self.archs = ttk.Combobox(ft_arch, state='readonly', textvariable=self.magisk_arch,
                                      values=self.get_arch())  # Initialize with current APK's archs if available, or default.
            self.archs.pack(side='left', padx=5, pady=5, expand=True, fill=X)
            # I removed the refresh button for architectures as it's automatically updated when a new APK is selected.
            # I also removed the commented out options as they are not used.

            # Patching options checkboxes
            # I group these BooleanVars together for better readability and logical grouping in the UI.
            self.IS64BIT = BooleanVar(value=True)
            self.KEEPVERITY = BooleanVar(value=False)
            self.KEEPFORCEENCRYPT = BooleanVar(value=False)
            self.RECOVERYMODE = BooleanVar(value=False)

            # I use two frames to better organize the checkboxes if there are many.
            ft_options_row1 = ttk.Frame(self)
            ft_options_row1.pack(fill=X, padx=5, pady=2)
            ttk.Checkbutton(ft_options_row1, onvalue=True, offvalue=False, text='IS64BIT', variable=self.IS64BIT).pack(
                padx=5, pady=2, side=LEFT)
            ttk.Checkbutton(ft_options_row1, onvalue=True, offvalue=False, text='KEEPVERITY',
                            variable=self.KEEPVERITY).pack(padx=5, pady=2, side=LEFT)

            ft_options_row2 = ttk.Frame(self)  # Renamed for clarity
            ft_options_row2.pack(fill=X, padx=5, pady=2)
            ttk.Checkbutton(ft_options_row2, onvalue=True, offvalue=False, text='KEEPFORCEENCRYPT',
                            variable=self.KEEPFORCEENCRYPT).pack(padx=5, pady=2, side=LEFT)
            ttk.Checkbutton(ft_options_row2, onvalue=True, offvalue=False, text='RECOVERYMODE',
                            variable=self.RECOVERYMODE).pack(
                padx=5, pady=2, side=LEFT)

            # Patch button, styled for emphasis.
            self.patch_bu = ttk.Button(self, text=lang.patch, style='Accent.TButton',
                                       command=lambda: create_thread(self.patch))
            self.patch_bu.pack(fill=X, padx=5, pady=(10, 5))  # Added more vertical padding for better spacing.

    class SelinuxAuditAllow(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.audit_allow)
            self.gui()
            move_center(self)

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
            self.button = ttk.Button(self, text=lang.text22, command=self.run, style='Accent.TButton')
            self.button.pack(padx=5, pady=5, fill=X)

        def run(self):
            if self.button.cget('text') == lang.done:
                self.destroy()
            else:
                self.button.configure(text=lang.running, state='disabled')
                create_thread(selinux_audit_allow, self.choose_file.get(), self.output_dir.get())
                self.button.configure(text=lang.done, state='normal', style='')

    class FileBytes(Toplevel):
        def __init__(self):
            super().__init__()
            self.units = {
                "B": 1,  # Using 1 instead of 2**0 for simplicity
                "KB": 1024,
                "MB": 1024 ** 2,
                "GB": 1024 ** 3,
                "TB": 1024 ** 4,
                "PB": 1024 ** 5  # Added PB for completeness
            }
            self.title(lang.t60)  # lang.t60 = 'Byte Calculator' (example)
            self._is_calculating = False  # Flag to prevent recursion
            self.origin_size_var = tk.StringVar()  # Separate StringVars for the Entry widgets
            self.result_size_var = tk.StringVar()
            self.gui()
            move_center(self)  # Assumes move_center is defined and available

        def gui(self):
            self.f_main = Frame(self)  # Main frame for widgets
            self.f_main.pack(pady=5, padx=5, fill=X, expand=True)

            # Left input field
            self.origin_size = ttk.Entry(self.f_main, textvariable=self.origin_size_var)
            self.origin_size.bind("<KeyRelease>", self.calc_forward)  # Binding for the left field
            self.origin_size.pack(side='left', padx=5, expand=True, fill=X)

            # Left combobox
            self.h = ttk.Combobox(self.f_main, values=list(self.units.keys()), state='readonly', width=4)
            self.h.current(0)
            self.h.bind("<<ComboboxSelected>>", self.calc_forward)  # Binding for the left combobox
            self.h.pack(side='left', padx=5)

            # Equals sign label
            Label(self.f_main, text='=').pack(side='left', padx=5)

            # Right input field
            self.result_size = ttk.Entry(self.f_main, textvariable=self.result_size_var)
            self.result_size.bind("<KeyRelease>", self.calc_reverse)  # Binding for the right field
            self.result_size.pack(side='left', padx=5, expand=True, fill=X)

            # Right combobox
            self.f_ = ttk.Combobox(self.f_main, values=list(self.units.keys()), state='readonly', width=4)
            self.f_.current(0)
            self.f_.bind("<<ComboboxSelected>>", self.calc_reverse)  # Binding for the right combobox
            self.f_.pack(side='left', padx=5)

            # Close button
            ttk.Button(self, text=lang.text17, command=self.destroy).pack(fill=X, padx=5,
                                                                          pady=5)  # lang.text17 = 'Close' (example)

        def calc_forward(self, event=None):
            """Calculates the value from left to right (from the left field to the right field)."""
            if self._is_calculating:
                return  # Prevent recursion

            self._is_calculating = True
            try:
                origin_unit = self.h.get()
                target_unit = self.f_.get()
                origin_value_str = self.origin_size_var.get()

                result_value_str = self.__calc(origin_unit, target_unit, origin_value_str)

                # Update only if the value differs, to avoid redundant events
                if self.result_size_var.get() != result_value_str:
                    self.result_size_var.set(result_value_str)
            finally:
                self._is_calculating = False  # Reset the flag

        def calc_reverse(self, event=None):
            """Calculates the value from right to left (from the right field to the left field)."""
            if self._is_calculating:
                return  # Prevent recursion

            self._is_calculating = True
            try:
                # Units are swapped for calculation
                origin_unit = self.f_.get()  # Get the unit from the right combobox
                target_unit = self.h.get()  # Target unit is from the left combobox
                origin_value_str = self.result_size_var.get()  # Value from the right field

                result_value_str = self.__calc(origin_unit, target_unit, origin_value_str)

                # Update only if the value differs
                if self.origin_size_var.get() != result_value_str:
                    self.origin_size_var.set(result_value_str)
            finally:
                self._is_calculating = False  # Reset the flag

        def __calc(self, origin_unit: str, target_unit: str, size_str: str) -> str:
            """Performs the value conversion between units."""
            # Remove whitespace
            size_str = size_str.strip()

            # Handle empty input
            if not size_str:
                return ""  # Return an empty string if input is empty

            try:
                # Try to convert to float
                size = float(size_str)
            except ValueError:
                # If not a float, check if it's a partially entered number
                if size_str == '.' or size_str == '-' or size_str == '-.' or \
                        (size_str.startswith('-') and size_str.count('.') <= 1 and all(
                            c.isdigit() or c == '.' for c in size_str[1:])) or \
                        (size_str.count('.') <= 1 and all(c.isdigit() or c == '.' for c in size_str)):
                    # If it looks like a number being typed, don't return anything yet.
                    # Return an empty string to avoid interfering with input.
                    return ""
                else:
                    # If it's definitely not a number, return "Invalid".
                    return "Invalid"

            # If units are the same
            if origin_unit == target_unit:
                # Return the number as a string, removing .0 for integers.
                return str(int(size)) if size.is_integer() else str(size)

            # Perform the calculation
            result = size * self.units[origin_unit] / self.units[target_unit]

            # Format the result: remove .0 for integers, limit precision.
            if result.is_integer():
                return str(int(result))
            else:
                # Limit the number of decimal places for readability.
                return f"{result:.6f}".rstrip('0').rstrip('.')

    class GetFileInfo(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.t59)
            self.controls = []
            self.gui()
            self.geometry("400x450")
            # self.resizable(False, False)
            self.dnd = lambda file_list: create_thread(self.__dnd, file_list)
            move_center(self)

        def gui(self):
            a = ttk.LabelFrame(self, text=lang.drop)
            (tl := ttk.Label(a, text=lang.text132_e)).pack(fill=BOTH, padx=5, pady=5)
            tl.bind('<Button-1>', lambda *x: self.dnd([filedialog.askopenfilename()]))
            a.pack(side=TOP, padx=5, pady=5, fill=BOTH)

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
                    logging.exception('Bugs')

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

    class TrimImage(Toplevel):
        def __init__(self):
            super().__init__()
            self.title(lang.trim_image)
            self.gui()
            move_center(self)
            # self.resizable(False, False)

        def gui(self):
            ttk.Label(self, text=lang.help_trim_image).pack(padx=5, pady=5)
            f = Frame(self)
            self.choose_file = StringVar(value='')
            ttk.Label(f, text=lang.text77).pack(side=LEFT, fill=X, padx=5, pady=5)
            self.path_edit = ttk.Entry(f, textvariable=self.choose_file)
            self.path_edit.pack(side=LEFT, fill=X, padx=5, pady=5, expand=True)
            self.choose_button = ttk.Button(f, text=lang.choose, command=lambda: self.choose_file.set(
                filedialog.askopenfilename(title=lang.text25)) == self.lift())
            self.choose_button.pack(side=LEFT, fill=X, padx=5, pady=5)
            f.pack(padx=5, pady=5, anchor='nw', fill=X)
            self.button = ttk.Button(self, text=lang.text22, command=self.run, style='Accent.TButton')
            self.button.pack(padx=5, pady=5, fill=X)

        def do_trim(self, buff_size: int = 8192):
            orig_size = file_size = os.path.getsize(self.choose_file.get())
            zeros_ = bytearray(buff_size)
            with open(self.choose_file.get(), 'rb') as f:
                self.button.configure(text=lang.running + ' - 0%')
                update_ui = 3000
                while file_size:
                    n = min(file_size, buff_size)
                    file_size_ = file_size - n
                    f.seek(file_size_)
                    buf = f.read(n)
                    assert len(buf) == n
                    if n != len(zeros_):
                        zeros_ = bytearray(n)
                    if buf != zeros_:
                        for i, b in enumerate(reversed(buf)):
                            if b != 0: break
                        file_size -= i
                        break
                    file_size = file_size_

                    update_ui -= 1
                    if update_ui == 0:
                        update_ui = 3000
                        percentage = 100 - file_size * 100 // orig_size
                        self.button.configure(text=lang.running + f' - {percentage}%')
                        self.update_idletasks()
            os.truncate(self.choose_file.get(), file_size)
            c = orig_size - file_size
            info_win(lang.trim_image_summary % (c, hum_convert(c)))

        def run(self):
            if self.button.cget('text') == lang.done:
                self.destroy()
                return
            if not os.path.isfile(self.choose_file.get()):
                return
            self.button.configure(text=lang.running, state='disabled')
            self.path_edit.configure(state='disabled')
            self.choose_button.configure(state='disabled')
            self.do_trim()
            self.button.configure(text=lang.done, state='normal', style='')

    class DisableAVB(Toplevel):
        """A Toplevel window for disabling AVB by patching fstab files in the current project."""

        def __init__(self):
            super().__init__()
            self.title(lang.disable_avb)
            self.minsize(450, 350)
            # A dictionary to store {partition_name: [list_of_fstab_paths]}
            self.partitions_with_fstab = {}
            self.gui()
            move_center(self)
            create_thread(self.scan_partitions)

        def gui(self):
            """Creates the graphical user interface for the window."""
            info_frame = ttk.Frame(self)
            info_frame.pack(padx=10, pady=(10, 5), fill=X)
            ttk.Label(info_frame, text=lang.disable_avb_info, wraplength=400).pack(fill=X)

            main_frame = ttk.LabelFrame(self, text=lang.available_partitions)
            main_frame.pack(padx=10, pady=5, fill=BOTH, expand=True)

            self.list_box = ListBox(main_frame)
            self.list_box.gui()
            self.list_box.pack(padx=5, pady=5, fill=BOTH, expand=True)

            button_frame = ttk.Frame(self)
            button_frame.pack(padx=10, pady=(5, 10), fill=X, side=BOTTOM)

            ttk.Button(button_frame, text=lang.refresh, command=self.scan_partitions).pack(side=LEFT, padx=(0, 5))

            self.run_button = ttk.Button(button_frame, text=lang.run, style="Accent.TButton",
                                         command=self.run_disable_avb)
            self.run_button.pack(side=RIGHT, fill=X, expand=True)

        def scan_partitions(self):
            """Scans the project for partitions containing fstab files and displays them."""
            self.list_box.clear()
            self.partitions_with_fstab.clear()

            if not project_manger.exist():
                print(lang.project_not_selected)
                self.run_button.config(state='disabled')
                return

            work_path = project_manger.current_work_path()
            parts_info_path = os.path.join(work_path, 'config', 'parts_info')
            parts_dict = {}
            if os.path.exists(parts_info_path):
                parts_dict = JsonEdit(parts_info_path).read()

            # Scan and group fstab files by their parent partition
            for item_name in sorted(os.listdir(work_path)):
                item_path = os.path.join(work_path, item_name)
                if os.path.isdir(item_path):
                    for root, _, files in os.walk(item_path):
                        for file in files:
                            if 'fstab' in file.lower():
                                if item_name not in self.partitions_with_fstab:
                                    self.partitions_with_fstab[item_name] = []
                                self.partitions_with_fstab[item_name].append(os.path.join(root, file))

            # Populate the ListBox with unique partitions
            if not self.partitions_with_fstab:
                print(lang.no_fstab_partitions_found)
                self.run_button.config(state='disabled')
            else:
                for partition_name in self.partitions_with_fstab.keys():
                    fs_type = parts_dict.get(partition_name, 'unknown')
                    display_text = f"{partition_name} [{fs_type}]"
                    self.list_box.insert(display_text, partition_name)
                self.run_button.config(state='normal')

        def run_disable_avb(self):
            """Starts the process to disable AVB."""
            selected_partitions = self.list_box.selected
            if not selected_partitions:
                warn_win(lang.select_partition_to_disable_avb)
                return

            self.run_button.config(state='disabled', text=lang.running)
            create_thread(self._process_in_thread, selected_partitions)

        def _process_in_thread(self, selected_partitions):
            """Background thread for processing."""
            processed_count = 0
            for partition_name in selected_partitions:
                if partition_name in self.partitions_with_fstab:
                    print(f"--- {lang.processing_partition.format(partition=partition_name)} ---")
                    # Process all fstab files found in this partition
                    for fstab_path in self.partitions_with_fstab[partition_name]:
                        process_fstab(fstab_path)  # Call the AVB patcher
                    processed_count += 1

            def final_actions():
                """Safely update the GUI from the main thread."""
                if self.winfo_exists():
                    self.run_button.config(state='normal', text=lang.run)
                    info_win(lang.disable_avb_completed.format(processed_count=processed_count))
                    self.destroy()

            self.after(0, final_actions)

    class DisableEncryption(Toplevel):
        """A Toplevel window for disabling forced encryption by patching fstab files."""

        def __init__(self):
            super().__init__()
            self.title(lang.disable_encryption)
            self.minsize(450, 350)
            self.partitions_with_fstab = {}
            self.gui()
            move_center(self)
            create_thread(self.scan_partitions)

        def gui(self):
            """Creates the graphical user interface for the window."""
            info_frame = ttk.Frame(self)
            info_frame.pack(padx=10, pady=(10, 5), fill=X)
            ttk.Label(info_frame, text=lang.disable_encryption_info, wraplength=400).pack(fill=X)

            main_frame = ttk.LabelFrame(self, text=lang.available_partitions)
            main_frame.pack(padx=10, pady=5, fill=BOTH, expand=True)

            self.list_box = ListBox(main_frame)
            self.list_box.gui()
            self.list_box.pack(padx=5, pady=5, fill=BOTH, expand=True)

            button_frame = ttk.Frame(self)
            button_frame.pack(padx=10, pady=(5, 10), fill=X, side=BOTTOM)

            ttk.Button(button_frame, text=lang.refresh, command=self.scan_partitions).pack(side=LEFT, padx=(0, 5))

            self.run_button = ttk.Button(button_frame, text=lang.run, style="Accent.TButton",
                                         command=self.run_disable_encryption)
            self.run_button.pack(side=RIGHT, fill=X, expand=True)

        def scan_partitions(self):
            """Scans the current project for all partitions containing fstab files."""
            self.list_box.clear()
            self.partitions_with_fstab.clear()

            if not project_manger.exist():
                print(lang.project_not_selected)
                self.run_button.config(state='disabled')
                return

            work_path = project_manger.current_work_path()
            parts_info_path = os.path.join(work_path, 'config', 'parts_info')
            parts_dict = {}
            if os.path.exists(parts_info_path):
                parts_dict = JsonEdit(parts_info_path).read()

            for item_name in sorted(os.listdir(work_path)):
                item_path = os.path.join(work_path, item_name)
                if os.path.isdir(item_path):
                    for root, _, files in os.walk(item_path):
                        for file in files:
                            if 'fstab' in file.lower():
                                if item_name not in self.partitions_with_fstab:
                                    self.partitions_with_fstab[item_name] = []
                                self.partitions_with_fstab[item_name].append(os.path.join(root, file))

            if not self.partitions_with_fstab:
                print(lang.no_fstab_partitions_found)
                self.run_button.config(state='disabled')
            else:
                for partition_name in self.partitions_with_fstab.keys():
                    fs_type = parts_dict.get(partition_name, 'unknown')
                    display_text = f"{partition_name} [{fs_type}]"
                    self.list_box.insert(display_text, partition_name)
                self.run_button.config(state='normal')

        def run_disable_encryption(self):
            """Starts the process to disable encryption for selected partitions."""
            selected_partitions = self.list_box.selected
            if not selected_partitions:
                warn_win(lang.select_partition_to_disable_avb)
                return

            self.run_button.config(state='disabled', text=lang.running)
            create_thread(self._process_in_thread, selected_partitions)

        def _process_in_thread(self, selected_partitions):
            """Internal method for execution in a separate thread."""
            modified_count = 0
            for partition_name in selected_partitions:
                if partition_name in self.partitions_with_fstab:
                    print(f"--- {lang.processing_partition.format(partition=partition_name)} ---")
                    for fstab_path in self.partitions_with_fstab[partition_name]:
                        process_fstab_for_encryption(fstab_path)
                    modified_count += 1

            def final_actions():
                """This function is executed in the main GUI thread for safe UI updates."""
                if not self.winfo_exists():
                    return

                self.run_button.config(state='normal', text=lang.run)
                info_win(lang.disable_encryption_completed.format(modified_count=modified_count))
                self.destroy()

            self.after(0, final_actions)

    class MergeSparseImage(Toplevel):
        """
        A Toplevel window for merging segmented Android sparse image files.

        This class provides a user-friendly interface for finding, combining, and
        processing sparse image chunks (e.g., `super.img.0`, `super.img.1`)
        into a single, complete raw image file. It features real-time progress
        reporting and options for managing source files.
        """

        def __init__(self) -> None:
            """
            Initializes the MergeSparseImage window and its state variables.
            """
            super().__init__()
            self.title(lang.merge_segments_title)
            self.minsize(420, 240)

            # --- State Variables ---
            # Holds the desired name for the final output image file.
            self.output_filename: StringVar = StringVar(value="super.img")
            # Determines whether to delete the source chunks after a successful merge.
            self.delete_source: BooleanVar = BooleanVar(value=False)

            # --- Widget References ---
            # These will be initialized in the `gui` method.
            self.run_button: Optional[ttk.Button] = None
            self.progressbar: Optional[ttk.Progressbar] = None
            self.progress_label: Optional[ttk.Label] = None

            self.gui()
            move_center(self)

        def gui(self) -> None:
            """
            Builds and lays out the graphical user interface for the window.
            """
            main_frame = ttk.Frame(self, padding=10)
            main_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

            # Informational label explaining the tool's purpose.
            ttk.Label(main_frame, text=lang.merge_segments_info, wraplength=400, justify=LEFT).pack(pady=(0, 10),
                                                                                                    fill=X)

            # Display the current project path or a message if none is selected.
            is_project_selected = project_manger.exist()
            if is_project_selected:
                project_path_text = f"{lang.project_path_label} {project_manger.current_work_path()}"
            else:
                project_path_text = lang.no_project_selected_label

            ttk.Label(main_frame, text=project_path_text, foreground="gray", wraplength=380, justify=LEFT).pack(
                pady=(0, 10), fill=X, anchor='w')

            # --- Output Filename Configuration ---
            output_frame = ttk.Frame(main_frame)
            output_frame.pack(fill=X, pady=5)
            ttk.Label(output_frame, text=lang.output_filename_label, width=22).pack(side=LEFT)
            ttk.Entry(output_frame, textvariable=self.output_filename).pack(side=LEFT, expand=True, fill=X)

            # --- Options ---
            options_frame = ttk.Frame(main_frame)
            options_frame.pack(fill=X, pady=5)
            ttk.Checkbutton(options_frame, text=lang.delete_source_segments_checkbox, variable=self.delete_source,
                            style="Switch.TCheckbutton").pack(side=LEFT, pady=5)

            # --- Action Button ---
            self.run_button = ttk.Button(main_frame, text=lang.create_super_image_button, style="Accent.TButton",
                                         command=self.start_merge)
            self.run_button.pack(fill=X, pady=(10, 5), ipady=4)

            # --- Progress Reporting Widgets (initially hidden) ---
            self.progress_label = ttk.Label(main_frame, text="")
            self.progressbar = ttk.Progressbar(main_frame, mode='determinate', maximum=100)

            # Disable the run button if no project is active.
            if not is_project_selected:
                self.run_button.config(state='disabled')
                ttk.Label(main_frame, text=lang.select_project_to_enable, foreground="orange").pack(pady=(5, 0))

        def start_merge(self) -> None:
            """
            Initiates the merge process.

            This method validates that a project is selected, displays the progress
            widgets, and spawns a new thread to handle the heavy lifting, keeping
            the GUI responsive.
            """
            if not project_manger.exist():
                warn_win(lang.project_not_selected)
                return

            # Make the progress bar and label visible before starting the task.
            self.progress_label.pack(pady=(5, 0))
            self.progressbar.pack(fill=X, pady=(2, 0), expand=True)
            self.update_progress(0)

            # Retrieve user-configured settings from the GUI.
            project_path = project_manger.current_work_path()
            output_name = self.output_filename.get()
            delete_source_files = self.delete_source.get()

            # Offload the main work to a background thread.
            create_thread(self._process_in_thread, project_path, output_name, delete_source_files)

        def update_progress(self, percentage: int) -> None:
            """
            Updates the progress bar and status text based on the merge progress.
            This method is designed to be called safely from the main GUI thread.

            Args:
                percentage: The current progress, from 0 to 100. A value of -1
                            indicates that the merge has failed.
            """
            # Gracefully do nothing if the window has been closed.
            if not self.winfo_exists():
                return

            self.run_button.config(state='disabled')

            if percentage == -1:
                # Handle the failure case.
                self.run_button.config(text=lang.merge_failed_label)
                self.progressbar['value'] = 0
                # Schedule the UI to be reset after a short delay.
                self.after(2000, self.finish_merge)
                return

            # Update the progress bar and button text for normal progress.
            self.progressbar['value'] = percentage
            button_text = f"{lang.running} {percentage}%"
            self.run_button.config(text=button_text)

        def _process_in_thread(self, project_path: str, output_name: str, delete_source: bool) -> None:
            """
            The core logic that runs in a background thread to prevent GUI freezes.
            It calls the main merging function and handles the results.

            Args:
                project_path: The absolute path to the project directory.
                output_name: The desired name for the merged output file.
                delete_source: A boolean indicating if source files should be deleted.
            """
            try:
                # This flag helps determine if the merge process actually started
                # or if it exited early (e.g., no segments found).
                result_status = "PENDING"

                def progress_callback(percentage: int) -> None:
                    """A callback function passed to the merge logic to report progress."""
                    nonlocal result_status
                    if self.winfo_exists():
                        # Once we get a progress update > 0, we know the work has begun.
                        if percentage > 0 and result_status == "PENDING":
                            result_status = "PROCESSING"
                        # Schedule the GUI update on the main thread.
                        self.after(0, self.update_progress, percentage)

                # Call the main merging function from the `merge_sparse` module,
                # injecting all necessary dependencies.
                merge_sparse.main(
                    project_path=project_path,
                    output_name=output_name,
                    delete_source=delete_source,
                    progress_callback=progress_callback,
                    # --- Injected Dependencies ---
                    lang=lang,
                    tool_bin_path=settings.tool_bin,
                    call_func=utils.call,
                    info_func=info_win,
                    warn_func=warn_win
                )

                if result_status == "PENDING":
                    # If the status is still pending, it means the merge function
                    # finished without processing any files (e.g., no segments found).
                    if self.winfo_exists():
                        self.after(0, lambda: info_win(lang.no_segments_to_merge_in_project))

            except Exception as e:
                logging.exception("Error in MergeSparseImage thread")
                error_msg = getattr(lang, 'unexpected_merge_error',
                                    'An unexpected error occurred during merge: {error}').format(error=e)
                if self.winfo_exists():
                    self.after(0, lambda: warn_win(error_msg))
            finally:
                # Always schedule the final UI cleanup.
                if self.winfo_exists():
                    # Wait a moment so the user can see the final status (e.g., 100% or "Failed").
                    self.after(1500, self.finish_merge)

        def finish_merge(self) -> None:
            """
            Resets the GUI to its initial state after the merge process is
            complete or has failed.
            """
            if self.winfo_exists():
                # Hide the progress widgets and re-enable the run button.
                self.progressbar.pack_forget()
                self.progress_label.pack_forget()
                self.run_button.config(state='normal', text=lang.create_super_image_button)


class Tool(TkinterEmbeddedPanel):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("tool")
        self.rotate_angle = 0  # Moved from tab4_content as it's a window state

        # Attempt to get the current alpha value before the "shake".
        # This is important if user settings already include transparency by default.
        self.loops = []
        self.message_pop = warn_win
        init_tk(self)

    def start_loops(self):
        for i in self.loops:
            create_thread(i)

    def gui(self):
        if os.name == 'posix' and os.geteuid() != 0:
            print(lang.warn13)
        if platform.machine() == 'loongarch64':
            print(lang.warnloongarch)
        self.sub_win2 = ttk.Frame(self.tk_root)
        self.sub_win3 = ttk.Frame(self.tk_root)
        self.sub_win2.pack(fill=BOTH, side=RIGHT, expand=True)
        self.sub_win3.pack(fill=BOTH, side=RIGHT, expand=True)
        self.notepad = ttk.Notebook(self.sub_win2)

        self.tab2 = ttk.Frame(self.notepad)
        self.tab5 = ttk.Frame(self.notepad)
        self.tab6 = ttk.Frame(self.notepad)
        self.tab7 = ttk.Frame(self.notepad)

        self.notepad.add(self.tab2, text=lang.text12)
        self.notepad.add(self.tab7, text=lang.text19)
        self.notepad.add(self.tab5, text=lang.text15)
        self.notepad.add(self.tab6, text=lang.toolbox)
        self.scrollbar = ttk.Scrollbar(self.tab5, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas1 = Canvas(self.tab5, yscrollcommand=self.scrollbar.set)
        self.canvas1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.frame_bg = ttk.Frame(self.canvas1)
        self.canvas1.create_window((0, 0), window=self.frame_bg, anchor='nw')
        self.canvas1.config(highlightthickness=0)
        self.tab6_content()
        self.notepad.pack(fill=BOTH, expand=True)
        self.gif_label = Label(self.tk_root)
        self.gif_label.pack(padx=10, pady=10, side=TOP)

    def tab6_content(self):
        ttk.Label(self.tab6, text=lang.toolbox, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH)
        ttk.Separator(self.tab6, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        tool_box = ToolBox(self.tab6)
        tool_box.gui()
        tool_box.pack(fill=BOTH, expand=True)


animation = LoadAnim()

tool_self = os.path.normpath(os.path.abspath(sys.argv[0]))
temp = os.path.join(cwd_path, "bin", "temp").replace(os.sep, '/')
tool_log = f'{temp}/{time.strftime("%Y%m%d_%H-%M-%S", time.localtime())}_{v_code()}.log'
context_rule_file = os.path.join(cwd_path, 'bin', "context_rules.json")
from src.core.utils import states, call



def check_upgrade() -> bool:
    update_url = settings.update_url or 'https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest'
    try:
        url = requests.get(update_url)
    except (Exception, BaseException) as e:
        return False
    try:
        json_ = json.loads(url.text)
    except (Exception, BaseException):
        return False
    new_version = json_.get('name')

    if new_version is None:
        return False

    if not new_version.endswith(settings.version):
        print(lang.t48 % new_version)
        Updater()
        return True
    else:
        print(lang.t49)
        return False


class Updater(Toplevel):

    def __init__(self):
        if states.update_window:
            self.destroy()
        super().__init__()
        self.title(lang.t38)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.tool_name = "tool"
        if os.name != "posix":
            self.tool_name += ".exe"
        states.update_window = True
        self.update_url = settings.update_url or 'https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest'
        self.package_head = ''
        self.update_download_url = ''
        self.update_size = 0
        self.update_zip = ''
        self.download_count = '0'
        self.update_assets = []
        f = ttk.Frame(self)
        ttk.Label(f, text='MIO-KITCHEN', font=(None, 20)).pack(side=LEFT, padx=5, pady=2)
        ttk.Label(f, text=settings.version, foreground='gray').pack(side=LEFT, padx=2, pady=2)
        f.pack(padx=5, pady=5, side=TOP)
        f2 = ttk.LabelFrame(self, text=lang.t39)
        self.notice = ttk.Label(f2, text=lang.t42)
        self.notice.pack(padx=5, pady=5)
        if states.run_source:
            if not shutil.which('git'):
                ttk.Label(self, text=lang.git_not_installed, foreground='orange', font=(None, 12)).pack(padx=5, pady=5)

                move_center(self)
                return
        self.change_log = Text(f2, width=50, height=15)
        self.change_log.pack(padx=5, pady=5)
        f2.pack(fill=BOTH, padx=5, pady=5)
        self.progressbar = ttk.Progressbar(self, length=200, mode='determinate', orient='horizontal', maximum=100
                                           )
        self.progressbar.pack(padx=5, pady=10)
        f3 = ttk.Frame(self)
        self.update_button = ttk.Button(f3, text=lang.t38, style='Accent.TButton',
                                        command=lambda: create_thread(self.get_update))
        ttk.Button(f3, text=lang.cancel, command=self.close).pack(fill=X, expand=True, side=LEFT,
                                                                  pady=10,
                                                                  padx=10)
        self.update_button.pack(fill=X, expand=True, side=LEFT,
                                pady=10,
                                padx=10)
        f3.pack(padx=5, pady=5, fill=X)
        self.resizable(width=False, height=False)
        move_center(self)
        if settings.updating == 'true':
            try:
                self.update_process()
            except (Exception, BaseException) as e:
                logging.exception("Updating failed")
                self.change_log.insert('insert', e)
                self.notice.configure(text=lang.t41, foreground='red')
                settings.set_value('updating', "false")
                if settings.version_old:
                    settings.set_value('version', settings.version_old)
        else:
            create_thread(self.get_update)

    def get_update(self):
        if self.update_button.cget('text') == lang.t40:
            self.update_button.configure(state='disabled', text=lang.t43)
            if not states.run_source:
                try:
                    self.download()
                    self.update_process()
                except (Exception, BaseException):
                    self.notice.configure(text=lang.t44, foreground='red')
                    self.update_button.configure(state='normal', text=lang.text37)
                    self.progressbar.stop()
                    logging.exception("Upgrade")
                    return
            elif shutil.which('git'):
                os.chdir(cwd_path)
                self.progressbar.configure(mode='indeterminate')
                self.progressbar.start()
                call(['git', 'pull'], extra_path=False)
                self.update_button.configure(state='normal', text=lang.t38)
                self.progressbar.stop()
            else:
                self.notice.configure(text=lang.t44, foreground='red')
                self.update_button.configure(state='normal', text=lang.text37)
                self.progressbar['value'] = 0
                self.progressbar.stop()
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
        new_version = json_.get('name')

        if new_version is None:
            self.notice.configure(text=lang.t46, foreground='red')
            self.update_button.configure(state='normal', text=lang.text37)
            self.change_log.insert('insert', url.text)
            return

        if not new_version.endswith(settings.version):
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
        package = self.package_head
        if platform.system() == 'Windows':
            package += '-win.zip'
        elif platform.system() == 'Linux':
            package += '-linux.zip'
        elif platform.system() == 'Darwin':
            package += '-macos-intel.zip' if platform.machine() == 'x86_64' else '-macos.zip'
        for i in self.update_assets:
            if i.get('name') == package:
                if platform.machine() in ['AMD64', 'X86_64', 'x86_64']:
                    self.update_download_url = i.get('browser_download_url')
                    self.update_size = i.get('size')
                    self.download_count = i.get('download_count')
                    return
                else:
                    break
        self.notice.configure(text=lang.t50, foreground='red')

    def download(self):
        if not os.path.exists(temp):
            os.makedirs(temp)
        mode = True
        self.progressbar.configure(mode='indeterminate')
        self.progressbar.start()
        self.update_zip = os.path.normpath(
            os.path.join(temp, os.path.basename(self.update_download_url)))
        for percentage, _, _, _, _ in download_api(self.update_download_url, temp,
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
        win.withdraw()
        self.notice.configure(text=lang.t51, foreground='orange')
        self.update_button.configure(state='disabled', text=lang.t43)
        self.progressbar.configure(mode='indeterminate')
        self.progressbar.start()
        if os.path.basename(sys.argv[0]).startswith('tool') and hasattr(settings, 'update_done'):
            self.__update_progress3()
        elif os.path.basename(sys.argv[0]) == 'updater.exe':
            self.__update_process2()
        else:
            self.__update_process()

    def __update_process(self):
        [terminate_process(i) for i in states.open_pids]
        update_files = []
        with zipfile.ZipFile(self.update_zip, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if file != self.tool_name:
                    try:
                        zip_ref.extract(file, cwd_path)
                    except PermissionError:
                        zip_ref.extract(file, temp)
                        update_files.append(file)
                else:
                    zip_ref.extract(file, os.path.join(cwd_path, "bin"))
        states.open_pids.append(os.getpid())
        update_dict = {
            'updating': 'true',
            'language': settings.language,
            'oobe': settings.oobe,
            'new_tool': os.path.join(cwd_path, "bin", self.tool_name),
            "version_old": settings.version,
            "update_files": ' '.join(update_files),
            "wait_pids": " ".join([str(i) for i in states.open_pids]),
        }
        for i in update_dict.keys():
            settings.set_value(i, update_dict.get(i, ''))
        updater_path = os.path.normpath(os.path.join(cwd_path, "updater.exe"))
        shutil.copy(tool_self, updater_path)
        subprocess.Popen([updater_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        win.destroy()

    def __update_process2(self):
        if hasattr(settings, 'wait_pids'):
            for i in settings.wait_pids.split(' '):
                try:
                    terminate_process(int(i))
                except ProcessLookupError:
                    continue
        if hasattr(settings, 'update_files'):
            for i in settings.update_files.split(' '):
                try:
                    real = i
                    path = os.path.join(temp, real)
                except (KeyError, ValueError):
                    continue
                if os.path.samefile(path, os.path.join(cwd_path, real)):
                    continue
                if os.path.exists(path):
                    if os.path.exists(os.path.join(cwd_path, real)):
                        try:
                            os.remove(os.path.join(cwd_path, real))
                        except PermissionError:
                            logging.warning(os.path.join(cwd_path, real))
                            continue
                    os.rename(path, os.path.join(cwd_path, real))
                else:
                    logging.warning(path)
        if settings.new_tool and os.path.exists(settings.new_tool):
            shutil.copyfile(settings.new_tool,
                            os.path.normpath(os.path.join(cwd_path, self.tool_name)))
            settings.set_value('wait_pids', str(os.getpid()))
            settings.set_value("update_done", 'true')
            subprocess.Popen([os.path.normpath(os.path.join(cwd_path, self.tool_name))],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        else:
            self.notice.configure(text=lang.t41, foreground='red')
            self.update_button.configure(state='normal', text=lang.text37)
            settings.set_value('version', settings.version_old)
            settings.set_value('updating', "false")

    def __update_progress3(self):
        if hasattr(settings, 'wait_pids'):
            for i in settings.wait_pids.split(' '):
                try:
                    terminate_process(int(i))
                except ProcessLookupError:
                    continue
        updater_path = os.path.normpath(os.path.join(cwd_path, "updater.exe"))
        remove_list = [updater_path]
        if settings.new_tool:
            remove_list.append(settings.new_tool)
        while True:
            try:
                for i in remove_list:
                    if os.path.exists(i):
                        os.remove(i)
            except (Exception, BaseException):
                continue
            else:
                break
        settings.set_value('updating', "false")
        settings.set_value('new_tool', '')
        settings.set_value('update_files', '')
        print(lang.upgrade_complete.format(settings.version_old, settings.version))
        win.wm_deiconify()
        self.close()

    def close(self):
        states.update_window = False
        self.destroy()


def error(code, desc="unknown error"):
    sv_ttk.use_dark_theme()
    er: Toplevel = Toplevel()
    er.protocol("WM_DELETE_WINDOW", win.destroy)
    er.title(f"Program crashed! [{settings.version}]")
    er.lift()
    ttk.Label(er, text=f"Error:0x{code}", font=(None, 20), foreground='red').pack(padx=10, pady=10)
    ttk.Label(er, text="Seems something went wrong.\nJust report it to us.Thank you.",
              font=(None, 20), foreground="#FFC0CB").pack(
        padx=10, pady=10)
    scroll = ttk.Scrollbar(er)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    te = Text(er, height=20, width=60)
    scroll.config(command=te.yview)
    te.pack(padx=10, pady=10, fill=BOTH)
    te.insert('insert', desc)
    te.config(yscrollcommand=scroll.set)
    ttk.Label(er, text=f"The Log File Is: {tool_log}", font=(None, 10)).pack(padx=10, pady=10)
    ttk.Button(er, text="Report",
               command=lambda: openurl("https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE/issues"),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Generate Bug Report",
               command=lambda: create_thread(generate_bug_report),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Restart",
               command=lambda: restart(er),
               style="Accent.TButton").pack(side=LEFT,
                                            padx=10,
                                            pady=10, expand=True, fill=BOTH)
    ttk.Button(er, text="Exit", command=win.destroy).pack(side=LEFT, padx=10, pady=10, expand=True, fill=BOTH)
    move_center(er)
    er.wait_window()
    sys.exit()


class Welcome(ttk.Frame):
    def __init__(self):
        # master=win specifies that Welcome will be a child widget of the main window 'win'.

        if not win:
            # This is a critical situation if Welcome expects 'win' to be its master.
            logging.critical(
                "Welcome.__init__: Main application window 'win' is not available or not a Tk instance.")
            error(1, 'Missing Main Window.')

        super().__init__(master=win.tk_root)  # Explicitly pass master.
        self.pack(fill=BOTH, expand=True)  # Welcome frame fills its master (win).

        _settings_obj = settings
        _states_obj = states
        _lang_obj = lang

        if not (_settings_obj and _states_obj and _lang_obj):
            logging.error("Welcome.__init__: Global objects (settings, states, lang) not fully available.")
            # Handle missing globals if necessary, e.g., by disabling functionality or using defaults.

        self.oobe = 0  # Default value.
        if _settings_obj:
            try:
                self.oobe = int(_settings_obj.oobe)
            except (ValueError, TypeError):
                if 'logging' in globals():
                    logging.warning(
                        f"Welcome.__init__: Invalid value for settings.oobe ('{_settings_obj.oobe}'). Defaulting to 0.")
                self.oobe = 0

        if _states_obj:
            _states_obj.in_oobe = True

        self.frames = {
            0: self.hello,
            1: self.main,
            2: self.set_workdir,
            3: self.license,
            4: self.private,
            5: self.done
        }
        self.frame = ttk.Frame(self)  # This is the inner frame that holds the content of each page.
        self.frame.pack(expand=True, fill=BOTH, padx=10, pady=10)  # Added padding for aesthetics.

        self.button_frame = ttk.Frame(self)

        back_text = lang.previous_step
        next_text = "Next"
        if _lang_obj:
            lang_next = lang.text138
            if isinstance(lang_next, str) and lang_next.strip().lower() != "none":
                next_text = lang_next

        self.back = ttk.Button(self.button_frame, text=back_text, command=lambda: self.change_page(self.oobe - 1))
        self.back.pack(fill=X, padx=5, pady=5, side='left', expand=True)  # expand=True
        self.next = ttk.Button(self.button_frame, text=next_text, command=lambda: self.change_page(self.oobe + 1))
        self.next.pack(fill=X, padx=5, pady=5, side='right', expand=True)  # expand=True

        self.button_frame.pack(expand=False, fill=X, padx=5, pady=5, side='bottom')  # expand=False for button_frame.

        self.change_page(self.oobe)  # Initial page load.

        # Centering the main window 'win' after the Welcome frame is packed and the first page is loaded.
        if win.tk_root and move_center and callable(move_center):
            try:
                # Ensure the Welcome frame itself and its content are updated before centering the master window.
                self.update_idletasks()
                win.tk_root.update_idletasks()  # Ensure the master (win) knows its new size with Welcome packed.
                move_center(win.tk_root)
            except Exception as e_mc:
                logging.error(f"Welcome.__init__: Error centering main window: {e_mc}")

        self.wait_window()  # This makes the Welcome sequence modal relative to 'win'.

        if _states_obj:
            _states_obj.in_oobe = False

    def change_page(self, step: int = 0):  # Default step to 0 if None
        _main_app_window = win
        _settings_obj = settings
        _lang_obj = lang
        _move_center_func = move_center

        if not isinstance(step, int) or step not in self.frames:
            step = 0  # Default to the first page if step is invalid

        self.oobe = step
        if settings:
            try:
                settings.set_value('oobe', str(step))  # Ensure value is string for set_value
            except Exception as e_set_oobe:
                logging.error(
                    f"Welcome.change_page: Failed to save OOBE step {step}: {e_set_oobe}")

        # Clear previous page content from the inner frame
        for widget in self.frame.winfo_children():
            widget.destroy()

        # Load the new page content
        self.frames[step]()  # This populates self.frame with new widgets

        # Update the inner frame to get its new size based on content
        self.frame.update_idletasks()
        # Update the Welcome frame itself (which contains self.frame and button_frame)
        self.update_idletasks()

        # Center the main application window ('win') after page content has changed
        if _main_app_window and _move_center_func and callable(_move_center_func):
            try:
                _main_app_window.update_idletasks()  # Ensure 'win' knows its size with the new Welcome content
                _move_center_func(_main_app_window)
            except Exception as e_mc:
                if 'logging' in globals(): logging.error(f"Welcome.change_page: Error centering main window: {e_mc}")

        # Update button states and text
        finish_text = "Finish"
        if _lang_obj:
            lang_finish = lang.text34
            if isinstance(lang_finish, str) and lang_finish.strip().lower() != "none":
                finish_text = lang_finish

        next_text = "Next"  # Default, defined in __init__
        if _lang_obj:
            lang_next = lang.text138
            if isinstance(lang_next, str) and lang_next.strip().lower() != "none":
                next_text = lang_next

        if step == min(self.frames.keys()):
            self.back.config(state='disabled')
        else:
            self.back.config(state='normal')

        if step == max(self.frames.keys()):
            self.next.config(text=finish_text, command=self.destroy_welcome)  # Use a new method to destroy
        else:
            # Ensure 'Next' button is correctly configured if not on the last page
            current_next_text = self.next.cget('text')
            if current_next_text != next_text or self.next.cget('command') == str(
                    self.destroy_welcome):  # Compare command carefully
                self.next.config(text=next_text, command=lambda: self.change_page(self.oobe + 1))

    def destroy_welcome(self):
        """ Safely destroys the Welcome frame. """
        _states_obj = states
        if _states_obj:
            _states_obj.in_oobe = False  # Set this before destroying, so mainloop doesn't get stuck

        if self.winfo_exists():
            self.destroy()

    def hello(self):
        ttk.Label(self.frame, text=lang.text135, font=(None, 40)).pack(padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.text137, font=(None, 20)).pack(padx=10, pady=10, fill=BOTH, expand=True)

    def main(self):
        ttk.Label(self.frame, text=lang.text129, font=(None, 20)).pack(padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb3_ = ttk.Combobox(self.frame, state='readonly', textvariable=language,
                            values=[i.rsplit('.', 1)[0] for i in
                                    os.listdir(f"{cwd_path}/bin/languages")])
        lb3_.pack(padx=10, pady=10, side='top', fill=BOTH)
        lb3_.bind('<<ComboboxSelected>>', lambda *x: settings.set_language())

    def set_workdir(self):
        def modpath():
            if not (folder := filedialog.askdirectory()):
                return
            settings.set_value("path", folder)
            show_local.set(folder)

        show_local = StringVar()
        show_local.set(settings.path)
        ttk.Label(self.frame, text=lang.text125, font=(None, 20)).pack(padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        slo = ttk.Label(self.frame, textvariable=show_local, wraplength=200)
        slo.bind('<Button-1>', lambda *x: windll.shell32.ShellExecuteW(None, "open", show_local.get(), None, None,
                                                                       1) if os.name == 'nt' else ...)
        slo.pack(padx=10, pady=10, side='left')
        ttk.Button(self.frame, text=lang.text126, command=modpath).pack(side="left", padx=10, pady=10)

    def license(self):
        lce = StringVar()

        def load_license():
            te.delete(1.0, tk.END)
            with open(f"{cwd_path}/bin/licenses/{lce.get()}.txt", 'r',
                      encoding='UTF-8') as f:
                te.insert('insert', f.read())

        lb = ttk.Combobox(self.frame, state='readonly', textvariable=lce,
                          values=[i.rsplit('.')[0] for i in os.listdir(f"{cwd_path}/bin/licenses") if
                                  i != 'private.txt'])
        lb.bind('<<ComboboxSelected>>', lambda *x: load_license())
        lb.current(0)
        ttk.Label(self.frame, text=lang.text139, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        lb.pack(padx=10, pady=10, side='top', fill=X)
        f = Frame(self.frame)
        scrollbar = ttk.Scrollbar(f, orient='vertical')
        te = Text(f, height=10)
        te.pack(fill=BOTH, side=LEFT, expand=True)
        scrollbar.config(command=te.yview)
        scrollbar.pack(fill=BOTH, side='right', expand=True)
        te.config(yscrollcommand=scrollbar.set)
        f.pack(fill=BOTH, side='top', expand=True)
        load_license()
        ttk.Label(self.frame, text=lang.t1).pack()

    def private(self):
        ttk.Label(self.frame, text=lang.t2, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        with open(os.path.join(cwd_path, "bin", "licenses", "private.txt"), 'r',
                  encoding='UTF-8') as f:
            (te := Text(self.frame, height=10)).insert('insert', f.read())
        te.pack(fill=BOTH, expand=True)
        ttk.Label(self.frame, text=lang.t3).pack()

    def done(self):
        ttk.Label(self.frame, text=lang.t4, font=(None, 25)).pack(side='top', padx=10, pady=10, fill=X)
        ttk.Separator(self.frame, orient=HORIZONTAL).pack(padx=10, pady=10, fill=X)
        ttk.Label(self.frame, text=lang.t5, font=(None, 20)).pack(
            side='top', fill=BOTH, padx=10, pady=10, expand=True)


from src.qt_layer.settings import cfg


class SetUtils:
    def __init__(self, set_ini: str | None = None, load=True):
        self.project_struct = 'single'
        self.auto_unpack = str(cfg.autoUnpack.value)
        self.set_file = set_ini or os.path.join(cwd_path, "bin", "setting.ini")
        self.plugin_repo = None
        self.contextpatch = '0'
        self.oobe = '0'
        self.path = None
        self.bar_level = '0.9'
        self.ai_engine = '0'
        self.version = 'basic'
        self.check_upgrade = '0'
        self.cpio_impl = 'native'
        self.version_old = 'unknown'
        self.language = 'English'
        self.boot_skip_ramdisk = '0'
        self.magisk_not_decompress = '0'
        self.updating = ''
        self.new_tool = ''
        self.cmd_exit = '0'
        self.cmd_invisible = '0'
        self.debug_mode = 'No'
        self.theme = 'dark'
        self.update_url = 'https://api.github.com/repos/ColdWindScholar/MIO-KITCHEN-SOURCE/releases/latest'
        self.config = ConfigParser()
        if os.access(self.set_file, os.F_OK):
            if load:
                self.load()
        else:
            sv_ttk.set_theme("dark")
            error(1,
                  'Some necessary files were lost, please reinstall this software to fix the problem!')

        self.tool_bin = os.path.join(cwd_path, 'bin', platform.system(), platform.machine()) + os.sep

    def load(self):
        self.config.read(self.set_file)
        for i in self.config.items('setting'):
            setattr(self, i[0], i[1])
        if os.path.exists(self.path):
            if not self.path:
                self.path = os.getcwd()
        else:
            self.path = utils.prog_path
        language.set(self.language)
        self.load_language(language.get())
        theme.set(self.theme)
        sv_ttk.set_theme(self.theme)
        if is_pro:
            if 'active_code' not in dir(self):
                self.active_code = 'None'
            verify.verify(self.active_code)

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
        [setattr(lang, n, v) for n, v in _lang.items()]

    def set_value(self, name, value):
        self.config.read(self.set_file)
        self.config.set("setting", name, value)
        with open(self.set_file, 'w', encoding='utf-8') as fil:
            self.config.write(fil)
        setattr(self, name, value)
        if name in ['treff', 'barlevel', 'theme']:
            self.load()


settings = SetUtils(load=False)


def re_folder(path, quiet=False):
    if os.path.exists(path):
        rmdir(path, quiet)
    os.makedirs(path, exist_ok=True)


@animation
def un_dtbo(bn: str = 'dtbo') -> None:
    if not (dtboimg := findfile(f"{bn}.img", work := project_manger.current_work_path())):
        print(lang.warn3.format(bn))
        return
    re_folder(f"{work}/{bn}")
    re_folder(f"{work}/{bn}/dtbo")
    re_folder(f"{work}/{bn}/dts")
    try:
        mkdtboimg.dump_dtbo(dtboimg, f"{work}/{bn}/dtbo/dtbo")
    except Exception as e:
        logging.exception("Bugs")
        print(lang.warn4.format(e))
        return
    for dtbo in os.listdir(f"{work}/{bn}/dtbo"):
        if dtbo.startswith("dtbo."):
            print(lang.text4.format(dtbo))
            call(
                exe=['dtc', '-@', '-I', 'dtb', '-O', 'dts', f'{work}/{bn}/dtbo/{dtbo}', '-o',
                     os.path.join(work, bn, 'dts', 'dts.' + os.path.basename(dtbo).rsplit('.', 1)[1])],
                out=False)
    print(lang.text5)
    try:
        os.remove(dtboimg)
    except (Exception, BaseException):
        logging.exception('Bugs')
    rmdir(f"{work}/dtbo/dtbo")


@animation
def pack_dtbo() -> bool:
    work = project_manger.current_work_path()
    if not os.path.exists(f"{work}/dtbo/dts") or not os.path.exists(f"{work}/dtbo"):
        print(lang.warn5)
        return False
    re_folder(f"{work}/dtbo/dtbo")
    for dts in os.listdir(f"{work}/dtbo/dts"):
        if dts.startswith("dts."):
            print(f"{lang.text6}:{dts}")
            call(
                exe=['dtc', '-@', '-I', 'dts', '-O', 'dtb', os.path.join(work, 'dtbo', 'dts', dts), '-o',
                     os.path.join(work, 'dtbo', 'dtbo', 'dtbo.' + os.path.basename(dts).rsplit('.', 1)[1])],
                out=False)
    print(f"{lang.text7}:dtbo.img")
    list_ = [os.path.join(work, "dtbo", "dtbo", f) for f in os.listdir(f"{work}/dtbo/dtbo") if
             f.startswith("dtbo.")]
    mkdtboimg.create_dtbo(project_manger.current_work_output_path() + "dtbo.img",
                          sorted(list_, key=lambda x: int(x.rsplit('.')[1])), 4096)
    rmdir(f"{work}/dtbo")
    print(lang.text8)
    return True


@animation
def logo_dump(file_path, output: str = None, output_name: str = "logo"):
    if output is None:
        output = project_manger.current_work_path()
    if not os.path.exists(file_path):
        win.message_pop(lang.warn3.format(output_name))
        return False
    re_folder(output + output_name)
    LogoDumper(file_path, output + output_name).unpack()


@animation
def logo_pack(origin_logo=None) -> int:
    work = project_manger.current_work_path()
    if not origin_logo:
        origin_logo = findfile('logo.img', work)
    logo = f"{work}/logo-new.img"
    if not os.path.exists(dir_ := f"{work}/logo") or not os.path.exists(origin_logo):
        print(lang.warn6)
        return 1
    LogoDumper(origin_logo, logo, dir_).repack()
    os.remove(origin_logo)
    os.rename(logo, origin_logo)
    rmdir(dir_)
    return 1


class MpkStore(Toplevel):
    """A Toplevel window for managing and installing MPK (MIO Package) files.

    Provides a user interface for browsing, selecting, downloading, and installing
    custom packages or modules (plugins) from a remote repository or local source.
    Handles listing available MPKs, showing their details, managing their state (installed/uninstalled),
    and triggering the installation/uninstallation process.
    """

    def __init__(self):
        """Initializes the MpkStore window.

        Ensures only one instance of MpkStore is active. Sets up the UI,
        initializes data structures for managing plugins, and loads the plugin database.
        """
        # Ensure only one instance of MpkStore is active.
        # If an instance already exists, bring it to front and focus.
        if hasattr(states, 'active_mpk_store_instance') and \
                states.active_mpk_store_instance and \
                states.active_mpk_store_instance.winfo_exists():
            states.active_mpk_store_instance.lift()
            states.active_mpk_store_instance.focus_force()
            return

        super().__init__()
        if hasattr(states, 'mpk_store'):  # Global state flag for MpkStore presence.
            states.mpk_store = True

        states.active_mpk_store_instance = self  # Register this instance as active.

        self.title('Mpk Store')  # Window title.
        self.minsize(500, 400)  # Minimum window size.

        self.data = []  # Holds raw data for plugins from the repository.
        self.tasks = []  # Potentially for managing download/install tasks (currently unused based on snippet).
        self.apps = []  # Potentially for storing app/plugin objects (currently unused based on snippet).
        self.app_infos = {}  # Dictionary to store UI frames associated with plugin IDs.
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)  # Handle window close event.
        self.repo = ''  # URL of the plugin repository.
        self.local_db_path = os.path.join(prog_path, 'bin', 'plugin_db.json')
        self.init_repo()  # Initialize repository URL from settings or defaults.

        # --- UI Setup --- 
        header_frame = ttk.Frame(self)
        ttk.Label(header_frame, text="Mpk Store", font=(None, 20)).pack(padx=10, pady=10, side=LEFT)
        ttk.Button(header_frame, text=lang.t58, command=self.modify_repo).pack(padx=10, pady=10,
                                                                               side=RIGHT)  # Button to modify repository URL.
        ttk.Button(header_frame, text=lang.refresh, command=lambda: create_thread(self.get_db)).pack(padx=10, pady=10,
                                                                                                     side=RIGHT)  # Button to refresh plugin database.
        header_frame.pack(padx=10, pady=10, fill=X)

        ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=5, fill=X)

        self.search = ttk.Entry(self)  # Search bar for plugins.
        self.search.pack(fill=X, padx=10, pady=5)
        self.search.bind("<Return>", lambda *x: self.search_apps())  # Trigger search on Enter key.

        ttk.Separator(self, orient=HORIZONTAL).pack(padx=10, pady=5, fill=X)

        self.logo = PhotoImage(data=images.none_byte)  # Placeholder for plugin icons.
        self.control = {}  # Dictionary to store install/uninstall buttons for each plugin ID.

        # Scrollable area for plugin listings.
        scrollable_area_frame = tk.Frame(self)
        scrollable_area_frame.pack(fill='both', padx=10, pady=(0, 10), expand=True)

        self.scrollbar = ttk.Scrollbar(scrollable_area_frame, orient='vertical')

        self.canvas = tk.Canvas(scrollable_area_frame, yscrollcommand=self.scrollbar.set, highlightthickness=0, bd=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.config(command=self.canvas.yview)

        self.label_frame = ttk.Frame(self.canvas)  # Frame inside canvas to hold plugin UI elements.
        self.label_frame_id = self.canvas.create_window((0, 0), window=self.label_frame, anchor='nw')

        # Bind events for dynamic resizing and scrolling.
        self.label_frame.bind("<Configure>", self._on_label_frame_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel_canvas)  # For Windows/macOS mouse wheel.
        self.canvas.bind("<Button-4>", self._on_mousewheel_canvas)  # For Linux mouse wheel (scroll up).
        self.canvas.bind("<Button-5>", self._on_mousewheel_canvas)  # For Linux mouse wheel (scroll down).

        create_thread(self.get_db)  # Load plugin database in a background thread.
        move_center(self)  # Center the window on screen.

    def _on_mousewheel_canvas(self, event):
        """Handles mouse wheel scrolling for the plugin list canvas.

        Args:
            event: The mouse wheel event.
        """
        if not self.canvas.winfo_exists(): return
        # Handle Linux mouse wheel events (Button-4 and Button-5)
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        # Handle Windows/macOS mouse wheel events (delta)
        elif event.delta != 0:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_label_frame_configure(self, event=None):
        """Adjusts the scrollregion of the canvas and visibility of the scrollbar
        when the content frame (label_frame) inside the canvas is reconfigured (e.g., resized).

        Args:
            event: The configure event (optional).
        """
        if not (self.canvas.winfo_exists() and self.label_frame.winfo_exists()): return

        self.canvas.config(scrollregion=self.canvas.bbox("all"))  # Update scrollable region to encompass all content.
        self.label_frame.update_idletasks()  # Ensure dimensions are up-to-date.

        canvas_height = self.canvas.winfo_height()
        content_height = self.label_frame.winfo_reqheight()

        # Show scrollbar only if content height exceeds canvas height.
        if content_height > canvas_height:
            if not self.scrollbar.winfo_ismapped():  # Check if scrollbar is not already visible.
                self.scrollbar.pack(side="right", fill="y", pady=(0, 0), padx=(0, 0))
        else:
            if self.scrollbar.winfo_ismapped():  # Check if scrollbar is currently visible.
                self.scrollbar.pack_forget()

    def _on_canvas_configure(self, event):
        """Adjusts the width of the content frame (label_frame) to match the canvas width
        when the canvas itself is reconfigured (e.g., resized).

        Args:
            event: The configure event, providing the new width.
        """
        if not (self.canvas.winfo_exists() and self.label_frame.winfo_exists() and hasattr(self,
                                                                                           'label_frame_id')): return

        canvas_width = event.width
        # Set the width of the window item within the canvas (which is the label_frame).
        self.canvas.itemconfig(self.label_frame_id, width=canvas_width)
        if self.label_frame.winfo_exists():
            # Also configure the label_frame's width directly to ensure consistency.
            self.label_frame.config(width=canvas_width)
            self.label_frame.update_idletasks()

        # After adjusting width, re-evaluate scrollbar visibility.
        self._on_label_frame_configure()

    def _on_close_window(self):
        """Handles the window close event.

        Cleans up global state references and unbinds events before destroying the window.
        """
        # Clear global references to this MpkStore instance.
        if hasattr(states, 'active_mpk_store_instance') and states.active_mpk_store_instance == self:
            states.active_mpk_store_instance = None
        if hasattr(states, 'mpk_store'):  # Global state flag for MpkStore presence.
            states.mpk_store = False

        # Unbind mouse wheel events from the canvas to prevent errors after destruction.
        if hasattr(self, 'canvas') and self.canvas.winfo_exists():
            self.canvas.unbind("<MouseWheel>")
            self.canvas.unbind("<Button-4>")
            self.canvas.unbind("<Button-5>")

        self.destroy()  # Destroy the Toplevel window.

    def update_plugin_state(self, plugin_id: str):
        """Updates the install/uninstall button states for a given plugin ID.

        Reflects whether the plugin is currently installed by enabling/disabling
        and styling the respective buttons.

        Args:
            plugin_id: The unique identifier of the plugin whose UI state needs updating.
        """
        logging.debug(f"MpkStore.update_plugin_state called for plugin_id: {plugin_id}")
        if not self.winfo_exists():  # Ensure window still exists before UI operations.
            logging.warning(
                f"MpkStore.update_plugin_state: MpkStore window no longer exists. Aborting update for {plugin_id}.")
            return

        if plugin_id in self.control:  # Check if UI controls exist for this plugin.
            install_button, uninstall_button = self.control[plugin_id]

            buttons_valid = True
            # Verify that button widgets still exist.
            if not (install_button and install_button.winfo_exists()):
                logging.warning(f"MpkStore.update_plugin_state: Install button for '{plugin_id}' does not exist.")
                buttons_valid = False
            if not (uninstall_button and uninstall_button.winfo_exists()):
                logging.warning(f"MpkStore.update_plugin_state: Uninstall button for '{plugin_id}' does not exist.")
                buttons_valid = False

            if not buttons_valid:
                return

            is_installed = module_manager.is_installed(plugin_id)  # Check installation status.
            logging.debug(f"MpkStore.update_plugin_state: Plugin '{plugin_id}' is_installed: {is_installed}")

            # Configure buttons based on installation status.
            if not is_installed:
                install_button.config(text=lang.text21, state='normal',
                                      style="Accent.TButton")  # Install button active.
                uninstall_button.config(text=lang.text20, state='disabled', style="")  # Uninstall button inactive.
            else:
                install_button.config(text=getattr(lang, 'plugin_installed_button', lang.text21), state='disabled',
                                      style="")  # Install button inactive (already installed).
                uninstall_button.config(text=lang.text20, state='normal',
                                        style="Accent.TButton")  # Uninstall button active.
        else:
            logging.debug(
                f"MpkStore.update_plugin_state: plugin_id '{plugin_id}' not found in self.control. No UI elements to update for this ID.")

    def init_repo(self):
        """Initializes the plugin repository URL.
        
        Reads the repository URL from settings. If not found or empty,
        it defaults to a predefined URL.
        """
        if not settings.plugin_repo:
            # Default repository URL if not configured in settings.
            self.repo = "https://raw.githubusercontent.com/ColdWindScholar/MPK_Plugins/main/"
        else:
            self.repo = settings.plugin_repo
        logging.info(f"MpkStore: Repository initialized to: {self.repo}")

    def search_apps(self):
        """Filters the displayed plugin list based on the search term entered by the user.
        
        Hides or shows plugin frames in the UI according to whether their names match
        the search term (case-insensitive).
        """
        if not self.winfo_exists(): return  # Ensure window exists.
        search_term = self.search.get().lower()  # Get search term from entry widget.

        # Iterate through all plugin UI frames.
        for plugin_id_key in self.app_infos:
            app_frame = self.app_infos[plugin_id_key]
            if not app_frame.winfo_exists(): continue  # Skip if frame is destroyed.

            # Find the corresponding plugin data to get its name.
            plugin_data_entry = next((item for item in self.data if item.get('id') == plugin_id_key), None)
            plugin_name_lower = plugin_data_entry.get('name', '').lower() if plugin_data_entry else ""

            # Determine visibility based on search term.
            should_be_visible = not search_term or search_term in plugin_name_lower

            if should_be_visible:
                if not app_frame.winfo_ismapped():  # Show if not already visible.
                    app_frame.pack(padx=5, pady=5, fill=X, expand=True)
            else:
                if app_frame.winfo_ismapped():  # Hide if currently visible and doesn't match.
                    app_frame.pack_forget()

        # Update layout and scroll position after filtering.
        if self.label_frame.winfo_exists(): self.label_frame.update_idletasks()
        if self.canvas.winfo_exists():
            self.canvas.yview_moveto(0.0)  # Scroll to top.
            self._on_label_frame_configure()  # Re-evaluate scrollbar.

    def add_app(self, app_dict=None):
        """Dynamically creates and adds UI elements for each plugin to the scrollable list.

        For each plugin in `app_dict`, if a UI representation doesn't already exist,
        this method constructs a LabelFrame containing plugin information (icon, name, author,
        version, size, description) and action buttons (install/uninstall).

        Args:
            app_dict (list, optional): A list of dictionaries, where each dictionary
                                       contains metadata for a plugin. Defaults to None (empty list).
        """
        if not self.winfo_exists():  # Ensure window is still active.
            logging.warning("MpkStore.add_app: Window destroyed, cannot add apps.")
            return

        app_dict = app_dict or []

        logging.info(f"MpkStore.add_app: Attempting to add/update {len(app_dict)} plugin UI elements.")
        new_items_added_count = 0
        for index, data in enumerate(app_dict):
            plugin_id = data.get('id')
            plugin_name_for_log = data.get('name', 'Unnamed Plugin')
            logging.debug(
                f"MpkStore.add_app: Processing item {index + 1}/{len(app_dict)} - ID: '{plugin_id}', Name: '{plugin_name_for_log}'")

            if not plugin_id:  # Skip if plugin ID is missing.
                logging.warning(f"MpkStore.add_app: Skipping plugin data at index {index} due to missing ID: {data}")
                continue

            # Skip if UI for this plugin ID already exists and is valid.
            if plugin_id in self.app_infos and self.app_infos[plugin_id].winfo_exists():
                logging.debug(f"MpkStore.add_app: Plugin UI for ID '{plugin_id}' already exists. Skipping.")
                continue

            new_items_added_count += 1

            # Main frame for each plugin entry.
            f = ttk.LabelFrame(self.label_frame, text=data.get('name', plugin_id))
            self.app_infos[plugin_id] = f  # Store frame reference.

            # Configure column weights for layout within the plugin frame.
            f.columnconfigure(0, weight=0, minsize=70)  # Icon column (fixed size).
            f.columnconfigure(1, weight=1)  # Info column (flexible).
            f.columnconfigure(2, weight=0, minsize=100)  # Buttons column (fixed size).

            icon_label = ttk.Label(f, image=self.logo)  # Placeholder icon.
            icon_label.grid(row=0, column=0, sticky="nw", padx=(5, 10), pady=5)

            # Frame to hold textual information (author, version, size, description).
            info_container_frame = ttk.Frame(f)
            info_container_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
            info_container_frame.columnconfigure(0, weight=1)

            # Extract and display plugin metadata.
            author_text = data.get('author', getattr(lang, 'unknown_author', 'Unknown'))
            version_text = data.get('version', getattr(lang, 'unknown_version', 'N/A'))
            size_bytes = data.get('size', 0)
            size_hum = hum_convert(size_bytes)  # the hum_convert must be callable

            ttk.Label(info_container_frame, text=f"{getattr(lang, 't21', 'Author:')} {author_text}", anchor="w").grid(
                row=0, column=0, sticky="ew", pady=(0, 1))
            ttk.Label(info_container_frame, text=f"{getattr(lang, 't22', 'Version:')} {version_text}", anchor="w").grid(
                row=1, column=0, sticky="ew", pady=(0, 1))
            ttk.Label(info_container_frame, text=f"{getattr(lang, 'size', 'Size:')} {size_hum}", anchor="w").grid(row=2,
                                                                                                                  column=0,
                                                                                                                  sticky="ew",
                                                                                                                  pady=(
                                                                                                                      0,
                                                                                                                      5))

            desc_text_content = data.get('desc', getattr(lang, 'no_description_available', 'No Description.'))

            # Frame for description text (to allow for a scrollbar if needed).
            desc_outer_frame = ttk.Frame(info_container_frame)
            desc_outer_frame.grid(row=3, column=0, sticky="nsew", pady=(2, 0))
            info_container_frame.rowconfigure(3, weight=1)  # Allow description area to expand.
            desc_outer_frame.columnconfigure(0, weight=1)
            desc_outer_frame.rowconfigure(0, weight=1)

            desc_text_widget = tk.Text(desc_outer_frame, wrap=tk.WORD, height=5, relief=tk.SOLID, borderwidth=1,
                                       font=("TkDefaultFont",), takefocus=False)  # Read-only description.
            desc_text_widget.insert(tk.END, desc_text_content)
            desc_text_widget.config(state=tk.DISABLED)

            desc_scrollbar = ttk.Scrollbar(desc_outer_frame, orient=tk.VERTICAL, command=desc_text_widget.yview)
            desc_text_widget.config(yscrollcommand=desc_scrollbar.set)

            desc_text_widget.grid(row=0, column=0, sticky="nsew")
            desc_scrollbar.grid(row=0, column=1, sticky="ns")  # Show scrollbar only if text overflows.

            # Frame for Install/Uninstall buttons.
            buttons_frame = ttk.Frame(f)
            buttons_frame.grid(row=0, column=2, sticky="ne", padx=5, pady=5)

            # Prepare arguments for download/install/uninstall actions.
            files_data = data.get('files')
            if isinstance(files_data, str):
                files_list = [files_data]
            elif isinstance(files_data, list):
                files_list = files_data
            else:
                files_list = []

            depends_data = data.get('depend')
            if isinstance(depends_data, str):
                depends_list = depends_data.split()
            elif isinstance(depends_data, list):
                depends_list = depends_data
            else:
                depends_list = []

            download_args = (files_list, size_bytes, plugin_id, depends_list)

            # Determine button width, allowing for localization.
            button_width_from_lang = getattr(lang, 'mpk_store_button_min_width', 12)
            try:
                MIN_BUTTON_WIDTH_CHARS = int(button_width_from_lang)
            except (ValueError, TypeError):
                MIN_BUTTON_WIDTH_CHARS = 12
                logging.warning(
                    f"MpkStore.add_app: Could not parse 'mpk_store_button_min_width' "
                    f"from lang (value: '{button_width_from_lang}'). Using default width: {MIN_BUTTON_WIDTH_CHARS}."
                )
            # Install button.
            bu = ttk.Button(buttons_frame, text=lang.text21,
                            command=lambda a=download_args: create_thread(self.download, *a),
                            width=MIN_BUTTON_WIDTH_CHARS)
            bu.pack(side=TOP, fill=X, pady=(0, 3))
            # Uninstall button.
            uninstall_button = ttk.Button(buttons_frame, text=lang.text20,
                                          command=lambda current_id=plugin_id: create_thread(self.uninstall,
                                                                                             current_id),
                                          width=MIN_BUTTON_WIDTH_CHARS)
            uninstall_button.pack(side=TOP, fill=X, pady=(3, 0))

            # Set initial state of buttons based on whether the plugin is installed.
            if not module_manager.is_installed(plugin_id):
                bu.config(style="Accent.TButton")
                uninstall_button.config(state='disabled')
            else:
                bu.config(state='disabled', text=getattr(lang, 'plugin_installed_button', lang.text21))
                uninstall_button.config(style="Accent.TButton", state='normal')

            self.control[plugin_id] = bu, uninstall_button  # Store button references.
            f.pack(padx=5, pady=5, fill=X, expand=False)
            logging.debug(f"MpkStore.add_app: Successfully created UI for '{plugin_id}'.")

        logging.info(f"MpkStore.add_app: Finished processing. Added {new_items_added_count} new UI elements.")
        if new_items_added_count > 0 or not app_dict:
            if self.label_frame.winfo_exists(): self.label_frame.update_idletasks()
            if self.canvas.winfo_exists(): self._on_label_frame_configure()

    def uninstall(self, id_):

        module_manager.uninstall_gui(id_, wait=True)

        if self.winfo_exists() and id_ in self.control:
            install_button, uninstall_button = self.control[id_]
            is_installed_after_attempt = module_manager.is_installed(id_)

            if not is_installed_after_attempt:
                install_button.config(text=lang.text21, style="Accent.TButton", state='normal')
                uninstall_button.config(text=lang.text20, style="", state='disabled')
            else:
                install_button.config(text=getattr(lang, 'plugin_installed_button', lang.text21), style="",
                                      state='disabled')
                uninstall_button.config(text=lang.text20, style="Accent.TButton", state='normal')

    def clear(self):

        if self.label_frame.winfo_exists():
            for widget in self.label_frame.winfo_children():
                widget.destroy()

        self.app_infos.clear()
        self.control.clear()

        if self.canvas.winfo_exists():
            self._on_label_frame_configure()

    def modify_repo(self):
        """Allows the user to modify the plugin repository URL.

        Opens a dialog asking for a new repository URL. If a new URL is provided
        and it's different from the current one, it updates the internal `repo` attribute,
        saves it to settings, and refreshes the plugin database from the new URL.
        """
        input_var = StringVar()
        current_repo_val = getattr(settings, 'plugin_repo', self.repo)  # Get current repo URL from settings or default.
        input_var.set(current_repo_val)

        # Create a Toplevel window for repository URL input.
        a = Toplevel()
        a.title(lang.t58)  # Set window title (e.g., "Modify Repository").
        a.transient(self)  # Make it a child of the MpkStore window.
        a.grab_set()  # Make the dialog modal.

        ttk.Entry(a, textvariable=input_var, width=60).pack(pady=10, padx=10, fill=X)

        button_frame_repo = ttk.Frame(a)
        button_frame_repo.pack(pady=5, padx=10, fill=X)

        def on_ok_repo():
            """Handles the OK button click in the repository modification dialog."""
            new_repo_val = input_var.get()
            settings.set_value('plugin_repo', new_repo_val)

            a.destroy()  # Close the dialog.

            if new_repo_val != current_repo_val:  # If the URL changed.
                self.init_repo()  # Re-initialize repository related settings.
                create_thread(self.get_db, True)  # Refresh database from the new repository in a separate thread.

        ttk.Button(button_frame_repo, text=getattr(lang, 'cancel', "Cancel"), command=a.destroy).pack(side=LEFT,
                                                                                                      padx=(0, 5),
                                                                                                      expand=True,
                                                                                                      fill=X)
        ttk.Button(button_frame_repo, text=getattr(lang, 'ok', "OK"), command=on_ok_repo, style="Accent.TButton").pack(
            side=LEFT, padx=(5, 0), expand=True, fill=X)

        move_center(a)  # Center the dialog relative to the MpkStore window.

    def download(self, files, size, id_, depends):
        if not self.winfo_exists():
            logging.warning(f"MpkStore.download: Window destroyed before download/install for '{id_}' could start.")
            if id_ in self.tasks: self.tasks.remove(id_)
            return

        logging.info(
            f"MpkStore.download: Initiating download for plugin ID '{id_}'. Files: {files}, Size: {size}, Depends: {depends}")
        if id_ in self.tasks:
            logging.info(f"MpkStore.download: Plugin '{id_}' download already in progress or queued.")
            return
        self.tasks.append(id_)

        install_button, uninstall_button = None, None
        current_plugin_info_for_name = next((item for item in self.data if item.get('id') == id_), None)
        plugin_display_name = current_plugin_info_for_name.get('name', id_) if current_plugin_info_for_name else id_

        if id_ in self.control:
            if self.control[id_] and len(self.control[id_]) == 2:
                install_button, uninstall_button = self.control[id_]
                if install_button and install_button.winfo_exists():
                    install_button.config(state='disabled', text=lang.text40)
            else:
                logging.error(f"MpkStore.download: Control entry for plugin '{id_}' is malformed.")
        else:
            logging.warning(f"MpkStore.download: Control buttons for plugin ID '{id_}' not found.")

        dependencies_ok = True
        if depends and isinstance(depends, list):
            for dep_id_str in depends:
                if not self.winfo_exists(): dependencies_ok = False; break
                if not dep_id_str: continue

                if module_manager.is_installed(dep_id_str):
                    logging.info(
                        f"MpkStore.download: Dependency '{dep_id_str}' for plugin '{id_}' is already installed. Skipping.")
                    continue

                dep_info = next((item for item in self.data if item.get('id') == dep_id_str), None)
                dep_name_display = dep_info.get('name', dep_id_str) if dep_info else dep_id_str

                if dep_info:
                    logging.info(
                        f"MpkStore.download: Attempting to install dependency '{dep_name_display}' (ID: {dep_id_str}) for plugin '{plugin_display_name}'.")
                    # Synchronous call to install the dependency in the same thread.
                    self.download(
                        dep_info.get('files'),
                        dep_info.get('size'),
                        dep_id_str,
                        dep_info.get('depend')
                    )

                    if not module_manager.is_installed(dep_id_str):
                        logging.error(
                            f"MpkStore.download: Dependency '{dep_name_display}' for plugin '{plugin_display_name}' failed to install.")
                        if self.winfo_exists():
                            # --- USING win.message_pop ---
                            msg_template = getattr(lang, "dependency_installation_failed_msg",
                                                   "Installation of plugin '{plugin_name}' aborted because dependency '{dep_name}' failed to install.")
                            win.message_pop(
                                text=msg_template.format(plugin_name=plugin_display_name, dep_name=dep_name_display),
                                color='orange',  # Orange for a warning.
                                title=getattr(lang, "dependency_error_title", "Dependency Error")
                            )
                            # --- END OF USING win.message_pop ---
                        dependencies_ok = False
                        break
                else:
                    logging.warning(
                        f"MpkStore.download: Info for dependency '{dep_id_str}' not found in self.data. Cannot install for '{plugin_display_name}'.")
                    if self.winfo_exists():
                        # --- USING win.message_pop ---
                        msg = getattr(lang, "dependency_not_in_repo_msg",
                                      "Cannot install '{plugin_name}'. Required dependency '{dep_name}' not found in the repository.")
                        win.message_pop(
                            text=msg.format(plugin_name=plugin_display_name, dep_name=dep_name_display),
                            color='orange',
                            title=getattr(lang, "dependency_error_title", "Dependency Error")
                        )
                        # --- END OF USING win.message_pop ---
                    dependencies_ok = False
                    break

            if not dependencies_ok:
                if id_ in self.tasks: self.tasks.remove(id_)
                if install_button and install_button.winfo_exists():
                    install_button.config(text=lang.text21, state='normal',
                                          style="Accent.TButton")  # lang.text21 likely means "Install"
                return

        download_successful_for_all_files = True
        installation_successful_for_all_files = True

        try:
            files_to_download_list = [files] if isinstance(files, str) else (files if isinstance(files, list) else [])
            logging.info(f"MpkStore.download: For plugin '{id_}', files to download: {files_to_download_list}")

            if not files_to_download_list:
                logging.warning(f"MpkStore.download: No files specified for download for plugin ID '{id_}'.")
                download_successful_for_all_files = False

            for file_index, file_name_in_list in enumerate(files_to_download_list):
                if not self.winfo_exists(): download_successful_for_all_files = False; break
                if not file_name_in_list:
                    logging.warning(
                        f"MpkStore.download: Empty file name at index {file_index} for plugin '{id_}'. Skipping.")
                    continue

                mpk_file_path_in_temp = os.path.join(temp, file_name_in_list)
                logging.debug(
                    f"MpkStore.download: Processing file '{file_name_in_list}' for plugin '{id_}'. Target path: '{mpk_file_path_in_temp}'")

                expected_file_size_from_data = size

                if os.path.exists(mpk_file_path_in_temp) and os.path.isfile(mpk_file_path_in_temp) and \
                        (expected_file_size_from_data <= 0 or os.path.getsize(
                            mpk_file_path_in_temp) == expected_file_size_from_data):
                    logging.info(f'MpkStore.download: Using cached package: {mpk_file_path_in_temp} for plugin {id_}.')
                    file_downloaded_this_iteration = True
                else:
                    if os.path.exists(mpk_file_path_in_temp):
                        logging.info(
                            f"MpkStore.download: Cached file '{mpk_file_path_in_temp}' exists but size mismatch or expected size unknown/zero. Re-downloading.")

                    logging.info(
                        f"MpkStore.download: Downloading: {self.repo + file_name_in_list} to {mpk_file_path_in_temp}")
                    download_generator = download_api(self.repo + file_name_in_list, temp,
                                                      size_=expected_file_size_from_data,
                                                      chunk_size=expected_file_size_from_data // 4)
                    for percentage, speed_val, bytes_down, file_size_val, elapsed_val in download_generator:
                        if not self.winfo_exists():
                            download_successful_for_all_files = False
                            break
                        if percentage == "Error":
                            logging.error(
                                f"MpkStore.download: download_api reported an error for {file_name_in_list} (plugin {id_}).")
                            download_successful_for_all_files = False
                            break

                        if install_button and install_button.winfo_exists():
                            try:
                                install_button.config(text=f"{percentage} %")
                            except tk.TclError:
                                download_successful_for_all_files = False
                                break
                        elif not self.winfo_exists():
                            download_successful_for_all_files = False
                            break
                    if not download_successful_for_all_files: break
                    file_downloaded_this_iteration = True

                if file_downloaded_this_iteration:
                    logging.info(
                        f"MpkStore.download: Attempting to install plugin '{id_}' from file: '{mpk_file_path_in_temp}'")
                    install_result, reason_text = module_manager.install(mpk_file_path_in_temp)
                    if install_result != module_error_codes.Normal:
                        logging.error(
                            f"MpkStore.download: Failed to install plugin '{id_}' from '{file_name_in_list}'. Reason: '{reason_text}', Code: {install_result}")
                        if self.winfo_exists():
                            msg_template_key = "plugin_install_failed_dependency_mpkstore" if install_result == module_error_codes.DependsMissing else "plugin_install_failed_mpkstore"
                            error_msg_template = getattr(lang, msg_template_key,
                                                         "Failed to install plugin {plugin_name}: {reason_text}")

                            dep_name_to_show = reason_text if install_result == module_error_codes.DependsMissing else str(
                                reason_text)

                            if install_result == module_error_codes.DependsMissing:
                                final_reason = getattr(lang, "dependency_missing_for_plugin_install",
                                                       "Missing dependency: '{dependency_name}'.").format(
                                    dependency_name=dep_name_to_show)
                            else:
                                final_reason = str(reason_text)
                            # --- USING win.message_pop ---
                            win.message_pop(
                                text=error_msg_template.format(plugin_name=plugin_display_name,
                                                               reason_text=final_reason),
                                color='orange',
                                title=getattr(lang, "dependency_error_title", "Installation Error")
                                # Or a more general title
                            )
                            # --- END OF USING win.message_pop ---
                        installation_successful_for_all_files = False
                        break
                    else:
                        logging.info(
                            f"MpkStore.download: Successfully installed components from '{file_name_in_list}' for plugin '{id_}'.")
                else:
                    installation_successful_for_all_files = False
                    break

            if not download_successful_for_all_files or not installation_successful_for_all_files:
                logging.warning(
                    f"MpkStore.download: Plugin installation process for '{id_}' was not fully successful. Download success: {download_successful_for_all_files}, Install success: {installation_successful_for_all_files}")

        except (ConnectTimeout, HTTPError) as e_conn:
            logging.exception(f'MpkStore.download: Connection/HTTP error during download for plugin {id_}: {e_conn}')
            if self.winfo_exists():
                win.message_pop(
                    text=f"{getattr(lang, 'download_failed', 'Download failed')}: {e_conn}",
                    color='orange',
                    title=getattr(lang, "download_error_title", "Download Error")  # New key for the title
                )
        except Exception as e_generic:
            logging.exception(
                f'MpkStore.download: Generic error during download/install process for plugin {id_}: {e_generic}')
        finally:
            if self.winfo_exists() and id_ in self.control:
                install_button_final, uninstall_button_final = self.control[id_]
                buttons_exist_final = install_button_final and install_button_final.winfo_exists() and \
                                      uninstall_button_final and uninstall_button_final.winfo_exists()

                if buttons_exist_final:
                    is_installed_final = module_manager.is_installed(id_)
                    if is_installed_final:
                        install_button_final.config(text=getattr(lang, 'plugin_installed_button', lang.text21),
                                                    state='disabled', style="")
                        uninstall_button_final.config(text=lang.text20, state='normal', style="Accent.TButton")
                    else:
                        install_button_final.config(text=lang.text21, state='normal', style="Accent.TButton")
                        uninstall_button_final.config(text=lang.text20, state='disabled', style="")

            if id_ in self.tasks:
                try:
                    self.tasks.remove(id_)
                except ValueError:
                    pass
            logging.info(f"MpkStore.download: Download/install process finished for plugin '{id_}'.")

    def get_db(self, refresh: bool = False):
        """Fetches the plugin database from the repository and populates the UI.

        Clears existing plugin listings, downloads 'plugin.json' from the configured
        repository URL, parses it, and then calls `add_app` to create UI elements
        for each plugin. Handles potential network errors and invalid data.
        """
        if not self.winfo_exists():  # Ensure window is still active.
            logging.debug("MpkStore.get_db: Main widget destroyed, exiting thread.")
            return

        self.clear()  # Clear existing UI elements and internal data structures.
        logging.info("MpkStore.get_db: Cleared existing plugin UI elements.")

        try:
            if not refresh and os.path.exists(self.local_db_path) and (data := JsonEdit(self.local_db_path).read()):
                self.data = data
            else:
                # Fetch plugin database (plugin.json).
                url_response = requests.get(self.repo + 'plugin.json', timeout=10)
                url_response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx).
                self.data = url_response.json()  # Parse JSON response.
                JsonEdit(self.local_db_path).write(self.data)

            self.apps = self.data  # Store parsed data for app population.
            logging.info(
                f"MpkStore.get_db: Successfully loaded {len(self.data)} plugin entries from {self.repo + 'plugin.json'}")
        except requests.exceptions.RequestException as e_req:  # Handle network-related errors.
            logging.error(f"MpkStore.get_db: Failed to get plugin.json due to network error: {e_req}")
            self.data = self.apps = []  # Reset data on error.
            win.message_pop(f"{getattr(lang, 'repo_fetch_error', 'Error fetching plugin list')}:\n{e_req}",
                            color="orange", title="Repository Error")
        except json.JSONDecodeError as e_json:  # Handle errors parsing JSON.
            logging.error(f"MpkStore.get_db: Failed to parse plugin.json: {e_json}")
            self.data = self.apps = []  # Reset data on error.
            win.message_pop(getattr(lang, 'repo_parse_error', 'Error parsing plugin list.'), color="orange",
                            title="Repository Error")
        except Exception as e_unexp:  # Catch other unexpected errors.
            logging.exception(f'MpkStore.get_db: Unexpected error during data fetch: {e_unexp}')
            self.data = self.apps = []  # Reset data on error.

        if self.winfo_exists():  # Check if window still exists before UI update.
            logging.debug(f"MpkStore.get_db: Calling add_app with {len(self.apps or [])} items.")
            self.add_app(self.apps or [])  # Populate UI with plugins.
        else:
            logging.warning("MpkStore.get_db: Window was destroyed before UI update could be completed.")


@animation
class PackHybridRom:
    def __init__(self):
        if not project_manger.exist():
            win.message_pop(lang.warn1)
            return
        if os.path.exists((dir_ := project_manger.current_work_output_path()) + "firmware-update"):
            os.rename(f"{dir_}/firmware-update", f"{dir_}/images")
        if not os.path.exists(f"{dir_}/images"):
            os.makedirs(f'{dir_}/images')
        if os.path.exists(os.path.join(project_manger.current_work_output_path(), 'payload.bin')):
            print("Found payload.bin ,Stop!")
            return
        if os.path.exists(f'{dir_}/META-INF'):
            rmdir(f'{dir_}/META-INF')
        shutil.copytree(f"{cwd_path}/bin/extra_flash", dir_, dirs_exist_ok=True)
        right_device = input_(lang.t26, 'olive', master=win)
        with open(f"{dir_}/bin/right_device", 'w', encoding='gbk') as rd:
            rd.write(right_device + "\n")
        with open(
                f'{dir_}/META-INF/com/google/android/update-binary',
                'r+', encoding='utf-8', newline='\n') as script:
            lines = script.readlines()
            lines.insert(45, f'right_device="{right_device}"\n')
            add_line = self.get_line_num(lines, '#Other images')
            for t in os.listdir(f"{dir_}/images"):
                if t.endswith('.img') and not os.path.isdir(dir_ + t):
                    print(f"Add Flash method {t} to update-binary")
                    if os.path.getsize(os.path.join(f'{dir_}/images', t)) > 209715200:
                        self.zstd_compress(os.path.join(f'{dir_}/images', t))
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
                        move(os.path.join(dir_, f"{t}.zst"), os.path.join(f"{dir_}/images", f"{t}.zst"))
                        lines.insert(add_line,
                                     f'package_extract_zstd "images/{t}.zst" "/dev/block/by-name/{t[:-4]}"\n')
                    else:
                        lines.insert(add_line,
                                     f'package_extract_file "images/{t}" "/dev/block/by-name/{t[:-4]}"\n')
                        move(os.path.join(dir_, t), os.path.join(f"{dir_}/images", t))
            script.seek(0)
            script.truncate()
            script.writelines(lines)

    @staticmethod
    def get_line_num(data, text):
        for i, t_ in enumerate(data):
            if text in t_:
                return i
        raise ValueError("The line u looking for isn't exist.")

    @staticmethod
    def zstd_compress(path):
        basename = os.path.basename(path)
        if os.path.exists(path):
            if gettype(path) == "sparse":
                print(f"[INFO] {basename} is (sparse), converting to (raw)")
                utils.simg2img(path)
            try:
                print(f"[Compress] {basename}...")
                call(['zstd', '-5', '--rm', path, '-o', f'{path}.zst'])
            except Exception as e:
                logging.exception('Bugs')
                print(f"[Fail] Compress {basename} Fail:{e}")


# multi group_size must 4194304 less than super
# new_postinstall_config_file config
class NewPostInstallConfig(Toplevel):
    """
    #The Config Like it.
    RUN_POSTINSTALL_[part_name]=true
    POSTINSTALL_PATH_[part_name]=bin/checkpoint_gc
    FILESYSTEM_TYPE_[part_name]=ext4
    POSTINSTALL_OPTIONAL_[part_name]=true
    """

    def __init__(self):
        super().__init__()
        self.title("New Postinstall Config")
        self.data = {}
        self.selected = []
        self.post_install_path = StringVar(value="")
        self.filesystem_type = StringVar(value="")
        self.run_postinstall = BooleanVar(value=False)
        self.postinstall_optional = BooleanVar(value=False)
        self.config_file = os.path.join(prog_path, 'bin', 'config', 'postinstall_config.txt')
        self.read_config()
        self.gui()
        self.read_value()
        move_center(self)

    def read_config(self):
        if self.data:
            self.data.clear()
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                for i in f.readlines():
                    if not i:
                        continue
                    if i[0] == "#":
                        continue
                    if not "=" in i:
                        continue
                    i = i.strip("\n")
                    name, value = i.split("=")
                    attrib_name1, attrib_name2, part_name = name.split("_", 2)
                    attrib_name = f"{attrib_name1}_{attrib_name2}"
                    if not part_name in self.data:
                        self.data[part_name] = {}
                    self.data[part_name][attrib_name] = value

    def read_value(self):
        part_name = self.combox.get()
        if part_name not in self.data:
            return None
        data: dict = self.data[part_name]
        self.run_postinstall.set(data["RUN_POSTINSTALL"] == 'true')
        self.post_install_path.set(data["POSTINSTALL_PATH"])
        if 'FILESYSTEM_TYPE' in data.keys():
            self.filesystem_type.set(data['FILESYSTEM_TYPE'])
        else:
            self.filesystem_type.set("")
        if 'POSTINSTALL_OPTIONAL' in data.keys():
            self.postinstall_optional.set(data['POSTINSTALL_OPTIONAL'] == 'true')
        else:
            self.postinstall_optional.set(False)

    def save_value(self):
        part_name = self.combox.get()
        if part_name not in self.data:
            return None
        self.data[part_name]["RUN_POSTINSTALL"] = str(self.run_postinstall.get()).lower()
        self.data[part_name]["POSTINSTALL_PATH"] = self.post_install_path.get()
        self.data[part_name]["FILESYSTEM_TYPE"] = self.filesystem_type.get()
        self.data[part_name]["POSTINSTALL_OPTIONAL"] = str(self.postinstall_optional.get()).lower()

    def add_new_part(self):
        part_name = input_("New partition name", master=self)
        if part_name.strip() != part_name:
            warn_win("The name is invalid!")
            return
        if not part_name:
            return
        self.data[part_name] = {"RUN_POSTINSTALL": "false", "POSTINSTALL_PATH": ""}
        self.combox.config(values=list(self.data.keys()))
        self.combox.set(part_name)
        self.read_value()

    def save_data(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'w', encoding='utf-8') as f:
                for i in self.data:
                    for name in ['RUN_POSTINSTALL', "POSTINSTALL_PATH", "FILESYSTEM_TYPE", "POSTINSTALL_OPTIONAL"]:
                        value = self.data[i].get(name)
                        if value:
                            f.write(f"{name}_{i}={value}\n")

    def gui(self):
        self.frame_up = Frame(self)
        self.combox = ttk.Combobox(self.frame_up)
        self.combox.config(values=list(self.data.keys()))
        self.combox.bind('<<ComboboxSelected>>', lambda *x: self.read_value())
        if self.data:
            self.combox.current(0)
        self.combox.pack(padx=5, pady=5, side='left', expand=True, fill=X)
        self.add_button = ttk.Button(self.frame_up, text="+", command=lambda: create_thread(self.add_new_part()))
        self.add_button.pack(padx=5, pady=5, side='left', expand=True, fill=X)
        self.apply_button = ttk.Button(self.frame_up, text="apply", command=lambda: create_thread(self.save_value()))
        self.apply_button.pack(padx=5, pady=5, side='left', expand=True, fill=X)
        self.frame_down = ttk.LabelFrame(self, text='config')
        frame = Frame(self.frame_down)
        ttk.Label(frame, text='RUN_POSTINSTALL').pack(padx=5, pady=5, side='left', expand=True, fill=X)
        self.run_postinstall_checkbutton = ttk.Checkbutton(frame, variable=self.run_postinstall, onvalue=True,
                                                           offvalue=False, style="Switch.TCheckbutton")
        self.run_postinstall_checkbutton.pack(padx=5, pady=5, side='left', expand=True, fill=X)
        frame.pack(padx=5, pady=5, expand=True, side='top', fill=X)
        frame = Frame(self.frame_down)
        ttk.Label(frame, text='POSTINSTALL_PATH').pack(padx=5, pady=5, side='left', expand=True, fill=X)
        self.post_install_path_entry = ttk.Entry(frame, textvariable=self.post_install_path)
        self.post_install_path_entry.pack(padx=5, pady=5, side='left', expand=True, fill=X)
        frame.pack(padx=5, pady=5, expand=True, side='top', fill=X)
        #
        frame = Frame(self.frame_down)
        ttk.Label(frame, text='FILESYSTEM_TYPE').pack(padx=7, pady=5, side='left', expand=True, fill=X)
        self.filesystem_type_combobox = ttk.Combobox(frame, textvariable=self.filesystem_type, values=('ext4', "erofs"),
                                                     width=14)
        self.filesystem_type_combobox.current(0)
        self.filesystem_type_combobox.pack(padx=5, pady=5, side='left', expand=True, fill=X)
        frame.pack(padx=5, pady=5, expand=True, side='top', fill=X)
        #
        frame = Frame(self.frame_down)
        ttk.Label(frame, text='POSTINSTALL_OPTIONAL').pack(padx=1, pady=5, side='left', expand=True, fill=X)
        self.postinstall_optional_checkbobox = ttk.Checkbutton(frame, variable=self.postinstall_optional, onvalue=True,
                                                               offvalue=False, style="Switch.TCheckbutton")
        self.postinstall_optional_checkbobox.pack(padx=5, pady=5, side='left', expand=True, fill=X)
        frame.pack(padx=5, pady=5, expand=True, side='top', fill=X)
        self.frame_down.pack(padx=5, pady=5, expand=True, side='top', fill=X)
        self.frame_up.pack(padx=5, pady=5, expand=True, side='top', fill=X)
        ttk.Button(self, text="Save", command=lambda: create_thread(self.save_data()), style="Accent.TButton").pack(
            padx=5, pady=5, expand=True, side='bottom', fill=X)


# dynamic_partitions_info config
class DynamicPartitionsInfo(Toplevel):
    """
    #The Config File Like following.
    virtual_ab=true
super_partition_size=17179869184
super_{group_name}_group_size=17175674880
super_partition_groups={group_name}
super_{group_name}_partition_list=my_company my_preload vbmeta
    """

    def __init__(self):
        super().__init__()


class PackPayload(Toplevel):
    def __init__(self):
        super().__init__()
        self.title("Repack Payload")
        # variables
        self.new_postinstall_config_file = StringVar()  # file
        self.dynamic_partition_info_file = StringVar()  # file
        self.sign_key = StringVar()  # file default : testkey from google
        self.partition_names = []
        self.new_partitions = []  # file

    def gui(self):
        ...
        # For Config new_postinstall_config_file


class PackSuper(Toplevel):
    def __init__(self):
        super().__init__()
        self.title(lang.text53)
        self.super_size = IntVar(value=9126805504)
        self.is_sparse = BooleanVar()
        self.super_type = IntVar()
        self.attrib = StringVar(value='readonly')
        self.group_name = StringVar()
        self.delete_source_file = BooleanVar(value=False)
        self.block_device_name = StringVar(value='super')
        self.selected = []
        (lf1 := ttk.LabelFrame(self, text=lang.text54)).pack(fill=BOTH)
        (lf1_r := ttk.LabelFrame(self, text=lang.attribute)).pack(fill=BOTH)
        (lf2 := ttk.LabelFrame(self, text=lang.settings)).pack(fill=BOTH)
        (lf3 := ttk.LabelFrame(self, text=lang.text55)).pack(fill=BOTH, expand=True)
        self.super_type.set(1)

        radios = [("A-only", 1), ("Virtual-ab", 2), ("A/B", 3)]
        for text, value in radios:
            ttk.Radiobutton(lf1, text=text, variable=self.super_type, value=value).pack(side='left', padx=10, pady=10)

        ttk.Radiobutton(lf1_r, text="Readonly", variable=self.attrib, value='readonly').pack(side='left', padx=10,
                                                                                             pady=10)
        ttk.Radiobutton(lf1_r, text="None", variable=self.attrib, value='none').pack(side='left', padx=10, pady=10)
        Label(lf2, text=lang.text56).pack(side='left', padx=10, pady=10)
        (show_group_name := ttk.Combobox(lf2, textvariable=self.group_name,
                                         values=("qti_dynamic_partitions", "main", "mot_dp_group"))).pack(
            side='left',
            padx=10,
            pady=10,
            fill='both')
        show_group_name.current(0)
        Label(lf2, text=lang.text57).pack(side='left', padx=10, pady=10)
        (super_size := ttk.Entry(lf2, textvariable=self.super_size)).pack(side='left', padx=10, pady=10)
        super_size.bind("<KeyRelease>",
                        lambda *x: super_size.state(["!invalid" if super_size.get().isdigit() else "invalid"]))

        self.tl = ListBox(lf3)
        self.tl.gui()
        self.work = project_manger.current_work_path()

        self.tl.pack(padx=10, pady=10, expand=True, fill=BOTH)

        ttk.Checkbutton(self, text=lang.text58, variable=self.is_sparse, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(
            padx=10, pady=10, fill=BOTH)
        t_frame = Frame(self)
        ttk.Checkbutton(t_frame, text=lang.t11, variable=self.delete_source_file, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(side=LEFT,
                                                          padx=10, pady=10, fill=BOTH)
        ttk.Button(t_frame, text=lang.refresh, command=self.refresh).pack(side=RIGHT, padx=10, pady=10)
        self.g_b = ttk.Button(t_frame, text=lang.t27, command=lambda: create_thread(self.generate))
        self.g_b.pack(side=LEFT, padx=10, pady=10, fill=BOTH)
        t_frame.pack(fill=X)
        move_center(self)

        ttk.Button(self, text=lang.cancel, command=self.destroy).pack(side='left', padx=10, pady=10,
                                                                      fill=X,
                                                                      expand=True)
        ttk.Button(self, text=lang.pack, command=lambda: create_thread(self.start_), style="Accent.TButton").pack(
            side='left',
            padx=5,
            pady=5, fill=X,
            expand=True)
        self.read_list()
        create_thread(self.refresh)

    def start_(self):
        try:
            self.super_size.get()
        except (Exception, BaseException):
            self.super_size.set(0)
            logging.exception('Bugs')
        if not self.verify_size():
            ask_win(lang.t10.format(self.super_size.get()), is_top=True)
            return False
        lbs = self.tl.selected.copy()
        sc = self.delete_source_file.get()
        self.destroy()
        if not project_manger.exist():
            warn_win(text=lang.warn1)
            return False
        pack_super(sparse=self.is_sparse.get(), group_name=self.group_name.get(), size=self.super_size.get(),
                   super_type=self.super_type.get(),
                   part_list=lbs, del_=sc,
                   attrib=self.attrib.get(), block_device_name=self.block_device_name.get())
        return None

    def verify_size(self):
        size = sum([os.path.getsize(f"{self.work}/{i}.img") for i in self.tl.selected])
        diff_size = size
        if size > self.super_size.get():
            for i in range(20):
                if not i:
                    continue
                i = i - 0.25
                t = (1024 ** 3) * i - size
                if t < 0:
                    continue
                if t < diff_size:
                    diff_size = t
                else:
                    size = i * (1024 ** 3)
                    break
            self.super_size.set(int(size))
            return False
        else:
            return True

    def generate(self):
        self.g_b.config(text=lang.t28, state='disabled')
        utils.generate_dynamic_list(group_name=self.group_name.get(), size=self.super_size.get(),
                                    super_type=self.super_type.get(),
                                    part_list=self.tl.selected.copy(), work=project_manger.current_work_path())
        self.g_b.config(text=lang.text34)
        time.sleep(1)
        try:
            self.g_b.config(text=lang.t27, state='normal')
        except TclError:
            logging.exception('Bugs')

    def refresh(self):
        self.tl.clear()
        for file_name in os.listdir(self.work):
            if file_name.endswith(".img"):
                if is_empty_img(self.work + file_name):
                    name = file_name[:-4]
                    self.tl.insert(f"{name} [empty]", name, name in self.selected)
                    continue
                if (file_type := gettype(self.work + file_name)) in ["ext", "erofs", 'f2fs', 'sparse']:
                    name = file_name[:-4]
                    self.tl.insert(f"{name} [{file_type}]", name, name in self.selected)

    def read_list(self):
        # Read parts_config
        parts_info = f"{self.work}/config/parts_info"
        if os.path.exists(parts_info):
            try:
                data: dict = JsonEdit(parts_info).read().get('super_info')
                if data is None:
                    raise AttributeError("super_info is not dict")
            except (Exception, BaseException, AttributeError):
                logging.exception('PackSupper:read_parts_info')
            else:
                # get block device name
                for i in data.get('block_devices', []):
                    self.block_device_name.set(i.get('name', 'super'))
                    if isinstance(i.get('size'), int):
                        self.super_size.set(i.get('size', self.super_size.get()))

                for i in data.get('group_table', []):
                    name = i.get('name')
                    if isinstance(name, str) and name != 'default':
                        self.group_name.set(name)

                selected = []
                for i in data.get('partition_table', []):
                    name = i.get('name')
                    if isinstance(name, str) and name not in selected:
                        selected.append(name)
                self.selected = selected

        # Read dynamic_partitions_op_list
        list_file = f"{self.work}/dynamic_partitions_op_list"
        if os.path.exists(list_file):
            try:
                data = utils.dynamic_list_reader(list_file)
            except (Exception, BaseException):
                logging.exception('Bugs')
                return
            if len(data) > 1:
                fir, sec = data
                if fir[:-2] == sec[:-2]:
                    self.group_name.set(fir[:-2])
                    self.super_type.set(2)
                    self.super_size.set(int(data[fir]['size']))
                    self.selected = data[fir].get('parts', [])
                    selected = self.selected
                    for i in self.selected:
                        name = i[:-2] if i.endswith('_a') or i.endswith('_b') else i
                        if not name in selected:
                            selected.append(name)
                    self.selected = selected

            else:
                group_name, = data
                self.group_name.set(group_name)
                self.super_size.set(int(data[group_name]['size']))
                self.selected = data[group_name].get('parts', [])
                self.super_type.set(1)


@animation
def pack_super(sparse: bool, group_name: str, size: int, super_type, part_list: list, del_: bool = False, return_cmd=0,
               attrib='readonly',
               output_dir: str = None, work: str = None, block_device_name: str = 'None'):
    if not block_device_name:
        block_device_name = 'super'
    if not work:
        work = project_manger.current_work_path()
    if not output_dir:
        output_dir = project_manger.current_work_output_path()
    lb_c = []
    for part in part_list:
        if part.endswith('_b') or part.endswith('_a'):
            part = part[:-2]
        if part not in lb_c:
            lb_c.append(part)
    part_list = lb_c
    for part in part_list:
        if not os.path.exists(f'{work}/{part}.img') and os.path.exists(f'{work}/{part}_a.img'):
            try:
                os.rename(f'{work}/{part}_a.img', f'{work}/{part}.img')
            except:
                logging.exception('Bugs')
    command = ['lpmake', '--metadata-size', '65536', '-super-name', block_device_name, '-metadata-slots']
    if super_type == 1:
        command += ['2', '-device', f'{block_device_name}:{size}', "--group", f"{group_name}:{size}"]
        for part in part_list:
            command += ['--partition', f"{part}:{attrib}:{os.path.getsize(f'{work}/{part}.img')}:{group_name}",
                        '--image', f'{part}={work}/{part}.img']
    else:
        command += ["3", '-device', f'super:{size}', '--group', f"{group_name}_a:{size}"]
        for part in part_list:
            command += ['--partition',
                        f"{part}_a:{attrib}:{os.path.getsize(f'{work}/{part}.img')}:{group_name}_a",
                        '--image', f'{part}_a={work + part}.img']
        command += ["--group", f"{group_name}_b:{size}"]
        for part in part_list:
            if not os.path.exists(f"{work + part}_b.img"):
                command += ['--partition', f"{part}_b:{attrib}:0:{group_name}_b"]
            else:
                command += ['--partition',
                            f"{part}_b:{attrib}:{os.path.getsize(f'{work}/{part}_b.img')}:{group_name}_b",
                            '--image', f'{part}_b={work}/{part}_b.img']
        if super_type == 2:
            command += ["--virtual-ab"]
    if sparse: command += ["--sparse"]
    output_super_path = f'{output_dir}/super.img'
    command += ['--out', output_super_path]
    if return_cmd == 1:
        return command
    if call(command, debug_binary=states.development) == 0:
        if os.access(output_super_path, os.F_OK):
            print(lang.text59 % output_super_path)
            if del_:
                for img in part_list:
                    if os.path.exists(f"{work}/{img}.img"):
                        try:
                            os.remove(f"{work}/{img}.img")
                        except Exception:
                            logging.exception('Bugs')
        else:
            win.message_pop(lang.warn10)
        return 1
    else:
        win.message_pop(lang.warn10)
        return 1


def download_api(url, path=None, int_=True, size_: int = 0, chunk_size: int = 2048576):
    """
    return percentage, speed, bytes_downloaded, file_size, elapsed
    """
    start_time = time.time()
    session = requests.Session()  # Create a session once

    try:
        # HEAD request to get the file size. Verify=True by default.
        # Add a timeout to prevent hanging
        response_head = session.head(url, timeout=10)  # 10-second timeout
        response_head.raise_for_status()  # Check for HTTP errors (4xx, 5xx)
        file_size = int(response_head.headers.get("Content-Length", 0))
    except requests.exceptions.RequestException as e_head:
        logging.error(f"Error making HEAD request to {url}: {e_head}")
        # In case of a HEAD error, we can either abort or try to download without a known file_size.
        # Here, we will continue; file_size will remain 0, and if size_ is provided, it will be used.
        file_size = 0  # or an exception could be raised and handled further up

    # GET request to download the file.
    # Removed verify=False, so the default True is used.
    try:
        # Add a timeout for the GET request as well (for establishing the connection)
        response_get = session.get(url, stream=True, timeout=10)
        response_get.raise_for_status()  # Check for HTTP errors
    except requests.exceptions.RequestException as e_get:
        logging.error(f"Error making GET request to {url}: {e_get}")
        # If the GET request fails, the generator needs to be interrupted.
        # An exception can be raised, or an empty yield can be returned.
        yield "Error", 0, 0, 0, 0  # Example of returning an error
        return

    last_time = time.time()
    if file_size == 0 and size_ > 0:  # Use the provided size_ if not obtained from the header
        file_size = size_
    file_save_path = os.path.join(path or settings.path, os.path.basename(url))
    logging.info(f"Starting download: {url} to {file_save_path}, expected size: {file_size}")

    try:
        with open(file_save_path, "wb") as f:
            bytes_downloaded = 0
            for data in response_get.iter_content(chunk_size=chunk_size):
                if not data:  # Check for empty data if the connection was dropped
                    break
                f.write(data)
                bytes_downloaded += len(data)

                current_time = time.time()
                elapsed_total = current_time - start_time

                # Speed calculation
                # To avoid division by zero if the time interval is very small
                time_since_last_chunk = current_time - last_time
                speed = 0
                if time_since_last_chunk > 0.001:  # Avoid division by a very small number
                    speed = (len(data) / 1024) / time_since_last_chunk  # Speed of the current chunk
                else:  # If the time interval is very small, use the average speed
                    if elapsed_total > 0.001:
                        speed = (bytes_downloaded / 1024) / elapsed_total

                last_time = current_time

                percentage = "Unknown"  # If file_size is unknown
                if file_size > 0:
                    percentage_float = (bytes_downloaded / file_size) * 100
                    percentage = int(percentage_float) if int_ else percentage_float

                yield percentage, speed, bytes_downloaded, file_size, elapsed_total
    except IOError as e_io:
        logging.error(f"IOError during download or saving file {file_save_path}: {e_io}")
        yield "Error", 0, bytes_downloaded, file_size, time.time() - start_time  # Return an error
    except Exception as e_download:  # Catch other potential errors during download
        logging.exception(f"Unexpected error during download of {url}: {e_download}")
        yield "Error", 0, bytes_downloaded, file_size, time.time() - start_time
    else:
        logging.info(f"Finished download: {url} to {file_save_path}, total bytes: {bytes_downloaded}")


@animation
def unpack_boot(name: str = 'boot', boot: str | None = None, work: str | None = None):
    if not work:
        work = project_manger.current_work_path()
    if not boot:
        if not (boot := findfile(f"{name}.img", work)):
            print(lang.warn3.format(name))
            return
    if not os.path.exists(boot):
        win.message_pop(lang.warn3.format(name))
        return
    if os.path.exists(work + name):
        if rmdir(work + name) != 0:
            print(lang.text69)
            return
    re_folder(work + name)
    os.chdir(work + name)
    if call(['magiskboot', 'unpack', '-h', '-n' if settings.magisk_not_decompress == '1' else '', boot]) != 0:
        print(f"Unpack {boot} Fail...")
        os.chdir(cwd_path)
        rmtree(work + name)
        return
    if os.access(f"{work}/{name}/second", os.F_OK):
        if gettype(f"{work}/{name}/second") == 'rk_rsce':
            print("Unpack Rk resource...")
            rsceutil_unpack(f"{work}/{name}/second", f"{work}/{name}/second_dump", f"{work}/{name}/second_order")
            print("Unpack Rk resource successfully...")
    if os.access(f"{work}/{name}/ramdisk.cpio", os.F_OK) and settings.boot_skip_ramdisk == '0':
        comp = gettype(f"{work}/{name}/ramdisk.cpio")
        print(f"Ramdisk is {comp}")
        with open(f"{work}/{name}/comp", "w", encoding='utf-8') as f:
            f.write(comp)
        if comp != "unknown":
            os.rename(f"{work}/{name}/ramdisk.cpio", f"{work}/{name}/ramdisk.cpio.comp")
            if call(["magiskboot", "decompress", f'{work}/{name}/ramdisk.cpio.comp',
                     f'{work}/{name}/ramdisk.cpio']) != 0:
                print("Failed to decompress Ramdisk...")
                return
        if not os.path.exists(f"{work}/{name}/ramdisk"):
            os.mkdir(f"{work}/{name}/ramdisk")
        print("Unpacking Ramdisk...")
        if settings.cpio_impl == 'python':
            cpio_extract(os.path.join(work, name, 'ramdisk.cpio'), os.path.join(work, name, 'ramdisk'),
                         os.path.join(work, name, 'ramdisk.txt'))
        else:
            os.chdir(work + name)
            call(['cpio', '-i', '-d', '-F', 'ramdisk.cpio', '-D', 'ramdisk'])
            os.chdir(cwd_path)
    print("Unpack Done!")
    os.chdir(cwd_path)


@animation
def repack_boot(name: str = 'boot', source: str | None = None, boot: str | None = None):
    work = project_manger.current_work_path()
    flag = ''
    if boot is None:
        boot = findfile(f"{name}.img", work)
        if not boot:
            print("Origin boot is lost.Cannot repack boot.img.")
            return
    if source is None:
        source = work + name
    if not os.path.exists(source):
        print(f"Cannot Find {name}...")
        return
    if os.path.isfile(f'{source}/second_order'):
        print("Repack Rk resource...")
        rsceutil_repack(f"{source}/second_dump", f"{source}/second", f"{source}/second_order")
        print("Repack Rk resource successfully...")
    if os.path.isdir(f"{source}/ramdisk") and settings.boot_skip_ramdisk == '0':
        if settings.cpio_impl == 'python':
            cpio_repack(f"{source}/ramdisk", f"{source}/ramdisk.txt", f"{source}/ramdisk-new.cpio")
        else:
            cpio = os.path.join(settings.tool_bin, 'cpio' if os.name != 'nt' else "cpio.exe")
            cpio = os.path.realpath(cpio)
            if os.name == 'nt':
                cpio = cpio.replace("\\", '/')

            os.chdir(f"{source}/ramdisk")
            call(exe=["busybox", "ash", "-c", f"find | sed 1d | {cpio} -H newc -R 0:0 -o -F ../ramdisk-new.cpio"])
        with open(f"{source}/comp", "r", encoding='utf-8') as compf:
            comp = compf.read()
        print(f"Compressing:{comp}")
        os.chdir(source)
        if comp != "unknown":
            if call(['magiskboot', f'compress={comp}', 'ramdisk-new.cpio']) != 0:
                print("Failed to pack Ramdisk...")
                os.remove("ramdisk-new.cpio")
            else:
                try:
                    os.remove("ramdisk.cpio")
                except (Exception, BaseException):
                    logging.exception('Bugs')
                if comp == 'gzip':
                    comp = 'gz'
                os.rename(f"ramdisk-new.cpio.{comp.split('_')[0]}", "ramdisk.cpio")
        else:
            if os.path.exists('ramdisk.cpio'):
                os.remove("ramdisk.cpio")
            if os.path.exists('ramdisk-new.cpio'):
                os.rename("ramdisk-new.cpio", "ramdisk.cpio")
            else:
                print("Failed to repack ramdisk.")
                return 1
        print(f"Ramdisk Compression:{comp}")
        if comp == "unknown":
            flag = "-n"
        print("Successfully packed Ramdisk..")
    if call(['magiskboot', 'repack', flag, boot]) != 0:
        print("Failed to Pack boot...")
        os.chdir(cwd_path)
    else:
        os.remove(boot)
        os.rename(f"{source}/new-boot.img", project_manger.current_work_output_path() + f"/{name}.img")
        os.chdir(cwd_path)
        try:
            rmdir(source)
        except (Exception, BaseException):
            print(lang.warn11.format(name))
        print("Successfully packed Boot...")


class PackPartition(Toplevel):
    def __init__(self, parts: list):
        self.chosen_parts: list = parts
        self.spatchvb = IntVar()
        self.custom_size = {}
        self.ext4_packer = StringVar(value='make_ext4fs')
        self.format = StringVar(value='raw')
        self.erofs_compress_format = StringVar(value='lz4hc')
        self.scale = IntVar(value=0)
        self.UTC = IntVar(value=int(time.time()))
        self.scale_erofs = IntVar()
        self.remove_source_files = IntVar()
        self.ext4_method = StringVar(value=lang.t32)

        self.origin_fs = StringVar(value='ext')
        self.modify_fs = StringVar(value='ext')

        self.fs_conver = BooleanVar(value=False)

        self.erofs_old_kernel = BooleanVar(value=False)
        self.f2fs_read_only = BooleanVar(value=False)
        self.f2fs_compresion = BooleanVar(value=False)
        if not self.verify():
            self.start_()
            return
        super().__init__()

        self.title(lang.text42)
        lf1 = ttk.LabelFrame(self, text=lang.text43)
        lf1.pack(fill=BOTH, padx=5, pady=5)
        lf2 = ttk.LabelFrame(self, text=lang.text44)
        lf2.pack(fill=BOTH, padx=5, pady=5)
        f2fs_frame = ttk.LabelFrame(self, text=lang.f2fs_settings)
        f2fs_frame.pack(fill=BOTH, padx=5, pady=5)
        lf3 = ttk.LabelFrame(self, text=lang.text45)
        lf3.pack(fill=BOTH, padx=5, pady=5)
        lf4 = ttk.LabelFrame(self, text=lang.text46)
        lf4.pack(fill=BOTH, pady=5, padx=5)
        (sf1 := Frame(lf3)).pack(fill=X, padx=5, pady=5, side=TOP)
        # EXT4 Settings
        Label(lf1, text=lang.text48).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf1, state="readonly", values=("make_ext4fs", "mke2fs+e2fsdroid"),
                     textvariable=self.ext4_packer).pack(
            side='left', padx=5, pady=5)
        Label(lf1, text=lang.t31).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf1, state="readonly", values=(lang.t32, lang.t33), textvariable=self.ext4_method).pack(
            side='left', padx=5, pady=5)
        self.modify_size_button = ttk.Button(lf1, text=lang.t37, command=self.modify_custom_size)
        self.modify_size_button.pack(
            side='left', padx=5, pady=5)
        self.show_modify_size = lambda: self.modify_size_button.pack_forget() if self.ext4_method.get() == lang.t32 else self.modify_size_button.pack(
            side='left', padx=5, pady=5)
        self.ext4_method.trace('w', lambda *x: self.show_modify_size())
        create_thread(self.show_modify_size)
        #
        Label(lf3, text=lang.text49).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf3, state="readonly", textvariable=self.format, values=("raw", "sparse", "br", "dat")).pack(
            padx=5,
            pady=5,
            side='left')
        # Erofs
        Label(lf2, text=lang.text50).pack(side='left', padx=5, pady=5)
        ttk.Combobox(lf2, state="readonly", textvariable=self.erofs_compress_format,
                     values=("lz4", "lz4hc", "lzma", "deflate", "zstd")).pack(side='left', padx=5, pady=5)
        ttk.Checkbutton(lf2, text=lang.t35, variable=self.erofs_old_kernel, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)
        # --
        scales_erofs = ttk.Scale(lf2, from_=0, to=9, orient="horizontal",
                                 command=lambda x: self.label_e.config(text=lang.t30.format(int(float(x)))),
                                 variable=self.scale_erofs)
        self.label_e = tk.Label(lf2, text=lang.t30.format(int(scales_erofs.get())))
        self.label_e.pack(side='left', padx=5, pady=5)
        scales_erofs.pack(fill="x", padx=5, pady=5)
        #
        ttk.Checkbutton(f2fs_frame, text=lang.readonly, variable=self.f2fs_read_only, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH, side='left')
        ttk.Checkbutton(f2fs_frame, text=lang.compression, variable=self.f2fs_compresion, onvalue=True, offvalue=False,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=BOTH)
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
        ttk.Checkbutton(frame_t, text=lang.t11, variable=self.remove_source_files, onvalue=1, offvalue=0,
                        style="Switch.TCheckbutton").pack(
            padx=5, pady=5, fill=X, side=LEFT)
        frame_t.pack(fill=X, padx=5, pady=5, side=BOTTOM)
        ttk.Checkbutton(lf3, text=lang.fs_converter, variable=self.fs_conver, onvalue=True, offvalue=False,
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
        ttk.Button(self, text=lang.pack, command=lambda: create_thread(self.start_), style="Accent.TButton").pack(
            side='left',
            padx=2, pady=2,
            fill=X,
            expand=True)
        move_center(self)
        module_manager.addon_loader.run_entry(module_manager.addon_entries.before_pack)

    def start_(self):
        module_manager.addon_loader.run_entry(module_manager.addon_entries.packing)
        try:
            self.destroy()
        except AttributeError:
            logging.exception('Bugs')
        self.packrom()

    def verify(self):
        parts_dict = JsonEdit(project_manger.current_work_path() + "config/parts_info").read()
        for i in self.chosen_parts:
            if i not in parts_dict.keys():
                parts_dict[i] = 'unknown'
            if parts_dict[i] in ['ext', 'erofs', 'f2fs']:
                return True
        return False

    def modify_custom_size(self):
        work = project_manger.current_work_path()

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
            for dname in self.chosen_parts:
                if self.custom_size.get(dname, ''):
                    continue
                ext4_size_value = 0
                if self.ext4_method.get() == lang.t33:
                    if os.path.exists(f"{work}/dynamic_partitions_op_list"):
                        with open(f"{work}/dynamic_partitions_op_list", 'r', encoding='utf-8') as t:
                            for _i_ in t.readlines():
                                _i = _i_.strip().split()
                                if len(_i) < 3:
                                    continue
                                if _i[0] != 'resize':
                                    continue
                                if _i[1] in [dname, f'{dname}_a', f'{dname}_b']:
                                    ext4_size_value = max(ext4_size_value, int(_i[2]))
                    elif os.path.exists(f"{work}/config/{dname}_size.txt"):
                        with open(f"{work}/config/{dname}_size.txt", encoding='utf-8') as size_f:
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
        move_center(ck)
        ck.wait_window()

    @animation
    def packrom(self) -> bool | None:
        if not project_manger.exist():
            win.message_pop(lang.warn1, "red")
            return False
        parts_dict = JsonEdit((work := project_manger.current_work_path()) + "config/parts_info").read()
        for i in self.chosen_parts:
            dname = os.path.basename(i)
            if dname not in parts_dict.keys():
                parts_dict[dname] = 'unknown'
            if self.spatchvb.get() == 1:
                for j in "vbmeta.img", "vbmeta_system.img", "vbmeta_vendor.img":
                    file = findfile(j, work)
                    if gettype(file) == 'vbmeta':
                        print(lang.text71 % file)
                        utils.Vbpatch(file).disavb()
            if os.access(os.path.join(f"{work}/config", f"{dname}_fs_config"), os.F_OK):
                if os.name == 'nt':
                    try:
                        if folder := findfolder(work, "com.google.android.apps.nbu."):
                            call(['mv', folder,
                                  folder.replace('com.google.android.apps.nbu.', 'com.google.android.apps.nbu')])
                    except Exception:
                        logging.exception('Bugs')
                fspatch.main(work + dname, os.path.join(f"{work}/config", f"{dname}_fs_config"))
                utils.remove_duplicate(f"{work}/config/{dname}_fs_config")
                contexts_file = f"{work}/config/{dname}_file_contexts"
                if os.path.exists(contexts_file):
                    if settings.contextpatch == "1":
                        contextpatch.main(work + dname, contexts_file, context_rule_file)
                        new_rules = contextpatch.scan_context(contexts_file)
                        rules = JsonEdit(context_rule_file)
                        rules.write(new_rules | rules.read())

                    utils.remove_duplicate(contexts_file)
                if self.fs_conver.get():
                    if parts_dict[dname] == self.origin_fs.get():
                        parts_dict[dname] = self.modify_fs.get()
                if parts_dict[dname] == 'erofs':
                    if mkerofs(dname, str(self.erofs_compress_format.get()), work=work,
                               work_output=project_manger.current_work_output_path(), level=int(self.scale_erofs.get()),
                               old_kernel=self.erofs_old_kernel.get(), UTC=self.UTC.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.remove_source_files.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.format.get() in ["dat", "br", "sparse"]:
                            img2simg(project_manger.current_work_output_path() + dname + ".img")
                            if self.format.get() == 'dat':
                                datbr(project_manger.current_work_output_path(), dname, "dat",
                                      int(parts_dict.get('dat_ver', 4)))
                            elif self.format.get() == 'br':
                                datbr(project_manger.current_work_output_path(), dname, self.scale.get(),
                                      int(parts_dict.get('dat_ver', 4)))
                            else:
                                print(lang.text3.format(dname))
                elif parts_dict[dname] == 'f2fs':
                    if make_f2fs(dname, work=work, work_output=project_manger.current_work_output_path(),
                                 UTC=self.UTC.get(), readonly=self.f2fs_read_only.get(),
                                 compress=self.f2fs_compresion.get()) != 0:
                        print(lang.text75 % dname)
                    else:
                        if self.remove_source_files.get() == 1:
                            rdi(work, dname)
                        print(lang.text3.format(dname))
                        if self.format.get() in ["dat", "br", "sparse"]:
                            img2simg(project_manger.current_work_output_path() + dname + ".img")
                            if self.format.get() == 'dat':
                                datbr(project_manger.current_work_output_path(), dname, "dat",
                                      int(parts_dict.get('dat_ver', 4)))
                            elif self.format.get() == 'br':
                                datbr(project_manger.current_work_output_path(), dname, self.scale.get(),
                                      int(parts_dict.get('dat_ver', 4)))
                            else:
                                print(lang.text3.format(dname))

                else:
                    ext4_size_value = self.custom_size.get(dname, 0)
                    if self.ext4_method.get() == lang.t33 and not self.custom_size.get(dname, ''):
                        list_file = f"{work}/dynamic_partitions_op_list"
                        if os.path.exists(list_file):
                            with open(list_file, 'r', encoding='utf-8') as t:
                                for _i_ in t.readlines():
                                    _i = _i_.strip().split()
                                    if len(_i) < 3:
                                        continue
                                    if _i[0] != 'resize':
                                        continue
                                    if _i[1] in [dname, f'{dname}_a', f'{dname}_b']:
                                        ext4_size_value = max(ext4_size_value, int(_i[2]))
                        elif os.path.exists(f"{work}/config/{dname}_size.txt"):
                            with open(f"{work}/config/{dname}_size.txt", encoding='utf-8') as f:
                                try:
                                    ext4_size_value = int(f.read().strip())
                                except ValueError:
                                    ext4_size_value = 0
                    if self.ext4_packer.get() == "make_ext4fs":
                        exit_code = make_ext4fs(name=dname, work=work,
                                                work_output=project_manger.current_work_output_path(),
                                                sparse=self.format.get() in ["dat", "br", "sparse"],
                                                size=ext4_size_value,
                                                UTC=self.UTC.get(), has_contexts=os.path.exists(contexts_file))

                    else:
                        exit_code = mke2fs(
                            name=dname, work=work,
                            work_output=project_manger.current_work_output_path(),
                            sparse=self.format.get() in [
                                "dat",
                                "br",
                                "sparse"],
                            size=ext4_size_value,
                            UTC=self.UTC.get())
                    if exit_code:
                        print(lang.text75 % dname)
                        continue

                    if self.remove_source_files.get() == 1:
                        rdi(work, dname)
                    if self.format.get() == "dat":
                        datbr(project_manger.current_work_output_path(), dname, "dat",
                              int(parts_dict.get('dat_ver', '4')))
                    elif self.format.get() == "br":
                        datbr(project_manger.current_work_output_path(), dname, self.scale.get(),
                              int(parts_dict.get('dat_ver', '4')))
                    else:
                        print(lang.text3.format(dname))
            elif parts_dict[i] in ['boot', 'vendor_boot']:
                repack_boot(i)
            elif parts_dict[i] == 'dtbo':
                pack_dtbo()
            elif parts_dict[i] == 'splash':
                splash_repack(os.path.join(work, dname), os.path.join(work, f"{dname}.img"))
            elif parts_dict[i] == 'logo':
                logo_pack()
            elif parts_dict[i] == 'guoke_logo':
                GuoKeLogo().pack(os.path.join(work, dname), os.path.join(work, f"{dname}.img"))
            else:
                if os.path.exists(os.path.join(work, i)):
                    print(f"Unsupported {i}:{parts_dict[i]}")
                logging.warning(f"{i} Not Supported.")


def rdi(work: str, part_name: str) -> bool:
    if not os.listdir(f"{work}/config"):
        rmtree(f"{work}/config")
        return False
    if os.access(f"{work}/{part_name}.img", os.F_OK):
        print(lang.text72 % part_name)
        try:
            rmdir(work + part_name)
            for i_ in ["%s_size.txt", "%s_file_contexts", '%s_fs_config', '%s_fs_options']:
                path_ = os.path.join(work, "config", i_ % part_name)
                if os.access(path_, os.F_OK):
                    os.remove(path_)
        except Exception:
            logging.exception(lang.text73 % (part_name, 'E'))
        print(lang.text3.format(part_name))
    else:
        win.message_pop(lang.text75 % part_name, "red")
    return True


def script2fs(path: str):
    if os.path.exists(os.path.join(path, "system", "app")):
        if not os.path.exists(path + "/config"):
            os.makedirs(path + "/config")
        extra.script2fs_context(findfile("updater-script", f"{path}/META-INF"), f"{path}/config", path)
        json_ = JsonEdit(os.path.join(path, "config", "parts_info"))
        parts = json_.read()
        for v in os.listdir(path):
            if os.path.exists(path + f"/config/{v}_fs_config"):
                if v not in parts.keys():
                    parts[v] = 'ext'
        json_.write(parts)


@animation
def copy_project(dir_path: str):
    name = os.path.basename(dir_path)
    print(lang.copying_project, name)
    if not os.path.exists(dir_path):
        print('No Such Folder.')
        return 1
    if os.path.isfile(dir_path):
        return unpackrom(dir_path)
    if os.path.exists(project_manger.get_work_path(name)) and os.path.samefile(project_manger.get_work_path(name),
                                                                               os.path.abspath(dir_path)):
        print("Same File!")
        return 1

    if project_manger.exist(name):
        name += v_code()
    project_path = project_manger.new(name)
    current_project_name.set(name)
    project_menu.listdir()
    project_menu.set_project(name)
    shutil.copytree(dir_path, project_path, dirs_exist_ok=True)
    return 0


@animation
def unpackrom(ifile: str) -> None:
    print(lang.text77 + ifile, f'Type:[{(ftype := gettype(ifile))}]')
    # gzip
    if ftype == 'gzip':
        print(lang.text79 + ifile)
        name = os.path.splitext(os.path.basename(ifile))[0]
        current_project_name.set(name)
        if not project_manger.exist(name):
            re_folder(project_manger.current_work_path())
        output_file_name = os.path.basename(ifile)
        if ifile.endswith(".gz"):
            output_file_name = output_file_name[:-3]

        output_file_ = os.path.join(project_manger.current_work_path(), output_file_name)
        with open(output_file_, "wb") as output, gzip.open(ifile, "rb") as input_file:
            data = input_file.read(8192)
            while len(data) == 8192:
                output.write(data)
                data = input_file.read(8192)
            else:
                if len(data) > 0:
                    output.write(data)
        old_project_name = os.path.splitext(os.path.basename(ifile))[0]
        unpackrom(output_file_)
        if old_project_name != (new_project_name := current_project_name.get()):
            current_project_name.set(old_project_name)
            project_menu.remove()
        current_project_name.set(new_project_name)
        return
    # ozip
    if ftype == "ozip":
        print(lang.text78 + ifile)
        ozipdecrypt.main(ifile)
        decrypted = os.path.dirname(ifile) + os.sep + os.path.basename(ifile)[:-4] + "zip"
        if not os.path.exists(decrypted):
            print(f"{ifile} decrypt Fail!!!")
            return
        unpackrom(decrypted)
        try:
            os.remove(decrypted)
        except:
            print(f"{ifile} remove Fail!!!")
        return
    # tar
    if ftype == 'tar':
        print(lang.text79 + ifile)
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not project_manger.exist():
            re_folder(project_manger.current_work_path())
        with tarsafe.TarSafe(ifile) as f:
            f.extractall(project_manger.current_work_path())
        return
    # kdz
    if ftype == 'kdz':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if not project_manger.exist():
            re_folder(project_manger.current_work_path())
        KDZFileTools(ifile, project_manger.current_work_path(), extract_all=True)
        for i in os.listdir(project_manger.current_work_path()):
            file = project_manger.current_work_path() + os.sep + i
            if not os.path.isfile(file):
                continue
            if i.endswith('.dz') and gettype(file) == 'dz':
                DZFileTools(file, project_manger.current_work_path(),
                            extract_all=True)
        return
    # ofp
    if os.path.splitext(ifile)[1] == '.ofp':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        if ask_win(lang.t12) == 1:
            ofp_mtk_decrypt.main(ifile, project_manger.current_work_path())
        else:
            ofp_qc_decrypt.main(ifile, project_manger.current_work_path())
            script2fs(project_manger.current_work_path())
        unpackg.refs(True)
        return
    # ops
    if os.path.splitext(ifile)[1] == '.ops':
        current_project_name.set(os.path.basename(ifile).split('.')[0])
        args = {'decrypt': True,
                "<filename>": ifile,
                'outdir': os.path.join(settings.path, project_manger.current_work_path())}
        opscrypto.main(args)
        unpackg.refs(True)
        return
    # pac
    ftype = gettype(ifile)
    if ftype == 'pac':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        unpac(ifile, project_manger.current_work_path(), PACMODE.EXTRACT)
        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(project_manger.current_work_path())])
        return
    # NTPI
    if ftype == 'cpb':
        prog_name = os.path.splitext(os.path.basename(ifile))[:1]
        current_project_name.set("".join(prog_name))
        extract_cpb(ifile, project_manger.current_work_path(mkdir=True))
        return
    if ftype == 'NTPI':
        prog_name = os.path.splitext(os.path.basename(ifile))[0]
        current_project_name.set(prog_name)
        ntpiparser.parse_ntpi_file(ifile, project_manger.current_work_path(mkdir=True))
        ntpiextractor.stage2_extract_files(project_manger.current_work_path(), project_manger.current_work_path())
        return
    # zip
    if ftype == 'zip':
        current_project_name.set(os.path.splitext(os.path.basename(ifile))[0])
        with zipfile.ZipFile(ifile, 'r') as fz:
            for fi in fz.namelist():
                try:
                    member_name = fi.encode('cp437').decode('gbk')
                except (Exception, BaseException):
                    try:
                        member_name = fi.encode('cp437').decode('utf-8')
                    except (Exception, BaseException):
                        member_name = fi
                print(lang.text79 + member_name)
                try:
                    fz.extract(fi, project_manger.current_work_path())
                    if fi != member_name:
                        os.rename(os.path.join(project_manger.current_work_path(), fi),
                                  os.path.join(project_manger.current_work_path(), member_name))
                except Exception as e:
                    print(lang.text80 % (member_name, e))
                    win.message_pop(lang.warn4.format(member_name))
            print(lang.text81)
            if os.path.isdir(project_manger.current_work_path()):
                project_menu.listdir()
                project_menu.set_project(os.path.splitext(os.path.basename(ifile))[0])
            script2fs(project_manger.current_work_path())
            unpackg.refs(True)

        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(project_manger.current_work_path())])
        return

    # othters.
    if ftype != 'unknown':
        file_name: str = os.path.basename(ifile)
        project_folder = os.path.join(settings.path, os.path.splitext(file_name)[0])
        folder = os.path.join(settings.path, os.path.splitext(file_name)[0] + v_code()) if os.path.exists(
            project_folder) else project_folder
        try:
            current_project_name.set(os.path.basename(folder))
            os.mkdir(folder)
            project_manger.current_work_path()
            project_manger.current_work_output_path()
        except Exception as e:
            win.message_pop(str(e))
        project_dir = str(folder) if settings.project_struct != 'split' else str(folder + '/Source/')
        copy(ifile, project_dir)
        # File Rename
        if os.path.exists(os.path.join(project_dir, file_name)):
            if not '.' in file_name:
                shutil.move(os.path.join(project_dir, file_name), os.path.join(project_dir, file_name + ".img"))
            if file_name.endswith(".bin"):
                shutil.move(os.path.join(project_dir, file_name), os.path.join(project_dir, file_name[:-4] + ".img"))
        current_project_name.set(os.path.basename(folder))
        project_menu.listdir()
        project_menu.set_project(current_project_name.get())
        if settings.auto_unpack == '1':
            unpack([i.split('.')[0] for i in os.listdir(project_manger.current_work_path())])
    else:
        print(lang.text82 % ftype)
    unpackg.refs(True)





project_manger = ProjectManager()


@animation
def unpack(chose: list | dict, form: str = '') -> bool:
    if os.name == 'nt':
        if windll.shell32.IsUserAnAdmin():
            try:
                ensure_dir_case_sensitive(project_manger.current_work_path())
            except (Exception, BaseException):
                logging.exception('Bugs')
    if not project_manger.exist():
        win.message_pop(lang.warn1)
        return False
    elif not os.path.exists(project_manger.current_work_path()):
        win.message_pop(lang.warn1, "red")
        return False
    json_ = JsonEdit((work := project_manger.current_work_path()) + "config/parts_info")
    parts = json_.read()
    if not chose:
        return False
    if form == 'payload':
        time_start = time.time()
        print(lang.text79 + "payload")
        with open(f"{work}/payload.bin", "rb") as f:
            extract_partitions_from_payload(
                f,
                (
                    chose
                ),
                work,
                os.cpu_count() or 2,
            )
        tooks = time.time() - time_start
        print("Done! tooks: %.2f" % tooks)
        return True
    elif form == 'super':
        print(lang.text79 + "Super")
        file_type = gettype(f"{work}/super.img")
        if file_type == "sparse":
            print(lang.text79 + f"super.img [{file_type}]")
            try:
                utils.simg2img(f"{work}/super.img")
            except (Exception, BaseException):
                win.message_pop(lang.warn11.format("super.img"))
        if gettype(f"{work}/super.img") == 'super':
            # should get info here.
            parts["super_info"] = lpunpack.get_info(os.path.join(work, "super.img"))
            lpunpack.unpack(os.path.join(work, "super.img"), work, chose)
            for file_name in os.listdir(work):
                if file_name.endswith('_a.img') and not os.path.exists(work + file_name.replace('_a', '')):
                    os.rename(work + file_name, work + file_name.replace('_a', ''))
                if file_name.endswith('_b.img'):
                    if not os.path.getsize(work + file_name):
                        os.remove(work + file_name)
            json_.write(parts)
            parts.clear()
        return True
    elif form == 'update.app':
        splituapp.extract(f"{work}/UPDATE.APP", work, chose)
        return True
    for i in chose:
        if os.access(f"{work}/{i}.zst", os.F_OK):
            print(f"{lang.text79} {i}.zst")
            call(['zstd', '--rm', '-d', f"{work}/{i}.zst"])
            return True
        if os.access(f"{work}/{i}.new.dat.xz", os.F_OK):
            print(lang.text79 + f"{i}.new.dat.xz")
            Unxz(f"{work}/{i}.new.dat.xz")
        if os.access(f"{work}/{i}.new.dat.br", os.F_OK):
            print(lang.text79 + f"{i}.new.dat.br")
            call(['brotli', '-dj', f"{work}/{i}.new.dat.br"])
        if os.access(f"{work}/{i}.new.dat.1", os.F_OK):
            with open(f"{work}/{i}.new.dat", 'ab') as ofd:
                for n in range(100):
                    if os.access(f"{work}/{i}.new.dat.{n}", os.F_OK):
                        print(lang.text83 % (i + f".new.dat.{n}", f"{i}.new.dat"))
                        with open(f"{work}/{i}.new.dat.{n}", 'rb') as fd:
                            ofd.write(fd.read())
                        os.remove(f"{work}/{i}.new.dat.{n}")
        if os.access(f"{work}/{i}.new.dat", os.F_OK):
            print(lang.text79 + f"{work}/{i}.new.dat")
            if os.path.getsize(f"{work}/{i}.new.dat") != 0:
                transferfile = f"{work}/{i}.transfer.list"
                if os.access(transferfile, os.F_OK):
                    parts['dat_ver'] = Sdat2img(transferfile, f"{work}/{i}.new.dat", f"{work}/{i}.img").version
                    if os.access(f"{work}/{i}.img", os.F_OK):
                        os.remove(f"{work}/{i}.new.dat")
                        os.remove(transferfile)
                        try:
                            os.remove(f'{work}/{i}.patch.dat')
                        except (Exception, BaseException):
                            logging.exception('Bugs')
                    else:
                        print("File May Not Extracted.")
                else:
                    print("transferfile" + lang.text84)
        if os.access(f"{work}/{i}.img", os.F_OK):
            try:
                if i in parts:
                    parts.pop(i)
            except KeyError:
                logging.exception('Key')
            if gettype(f"{work}/{i}.img") != 'sparse':
                parts[i] = gettype(f"{work}/{i}.img")
            if gettype(f"{work}/{i}.img") == 'dtbo':
                un_dtbo(i)
            if gettype(f"{work}/{i}.img") in ['boot', 'vendor_boot']:
                unpack_boot(i)
            if i == 'logo':
                try:
                    utils.LogoDumper(f"{work}/{i}.img", f'{work}/{i}').check_img(f"{work}/{i}.img")
                except AssertionError:
                    logging.exception('Bugs')
                else:
                    logo_dump(f"{work}/{i}.img", output_name=i)
            if gettype(f"{work}/{i}.img") == 'vbmeta':
                print(f"{lang.text85}AVB:{i}")
                utils.Vbpatch(f"{work}/{i}.img").disavb()
            file_type = gettype(f"{work}/{i}.img")
            if file_type == "sparse":
                print(lang.text79 + f"{i}.img[{file_type}]")
                try:
                    utils.simg2img(f"{work}/{i}.img")
                except (Exception, BaseException) as e:
                    logging.exception(e)
                    win.message_pop(e)
                    continue
            if i not in parts.keys():
                parts[i] = gettype(f"{work}/{i}.img")
            print(lang.text79 + f"{i}.img[{file_type}]")
            if gettype(f"{work}/{i}.img") == 'super':
                parts["super_info"] = lpunpack.get_info(f"{work}/{i}.img")
                lpunpack.unpack(f"{work}/{i}.img", work)
                for file_name in os.listdir(work):
                    file_path = work + file_name
                    if file_name.endswith('_a.img'):
                        if os.path.exists(file_path) and os.path.exists(work + file_name.replace('_a', '')):
                            if pathlib.Path(file_path).samefile(work + file_name.replace('_a', '')):
                                os.remove(file_path)
                            else:
                                os.remove(work + file_name.replace('_a', ''))
                                os.rename(file_path, work + file_name.replace('_a', ''))
                        else:
                            os.rename(file_path, work + file_name.replace('_a', ''))
                    if file_name.endswith('_b.img'):
                        if not os.path.getsize(file_path):
                            os.remove(file_path)
                json_.write(parts)
                parts.clear()
            if (file_type := gettype(f"{work}/{i}.img")) == "ext":
                with open(f"{work}/{i}.img", 'rb+') as e:
                    mount = ext4.Volume(e).get_mount_point
                    if mount[:1] == '/':
                        mount = mount[1:]
                    if '/' in mount:
                        mount = mount.split('/')
                        mount = mount[len(mount) - 1]
                    if mount != i and mount and i != 'mi_ext':
                        parts[mount] = 'ext'
                # libutils.ext4_extractor(f'{work}/config', f"/{mount}", project_manger.current_work_path() + i + ".img", f'{work}/{i}', 4096, 'e', False, i)
                imgextractor.Extractor().main(project_manger.current_work_path() + f"{i}.img", f'{work}/{i}', work)
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except Exception as e:
                        win.message_pop(lang.warn11.format(f"{i}.img:{e.__str__()}"))
            if file_type == 'romfs':
                fs = RomfsParse(project_manger.current_work_path() + f"{i}.img")
                fs.extract(work)
            if file_type in ['rkfw', 'rkaf']:
                call(['afptool', 'unpack', f"{project_manger.current_work_path()}/{i}.img", work])
            if file_type == 'guoke_logo':
                GuoKeLogo().unpack(os.path.join(project_manger.current_work_path(), f'{i}.img'), f'{work}/{i}')
            if file_type == 'splash':
                if not os.path.exists(splash_out_dir := os.path.join(work, i)):
                    os.makedirs(splash_out_dir, True)
                process_splashimg(os.path.join(project_manger.current_work_path(), f'{i}.img'),
                                  f"{work}/{i}/splash.png")
            if file_type == 'gpt':
                reader = GPTReader(os.path.join(project_manger.current_work_path(), f'{i}.img'), sector_size=512)
                for partition in reader.partition_table.valid_entries():
                    print('guid/type={} first-block={} size={} name={}'.format(
                        partition.partition_type, partition.first_block, partition.length, partition.name))
                    if True:
                        file_base_name = partition.name if partition.name else str(partition.partition_id)

                        out_file = os.path.join(work, f'{file_base_name}.img')
                        print(f'Writing partition to file {out_file}')

                        with open(out_file, 'wb+') as fout:
                            for block in reader.block_reader.blocks_in_range(partition.first_block, partition.length):
                                fout.write(block)

            if file_type == "erofs":
                if call(exe=['extract.erofs', '-i', os.path.join(project_manger.current_work_path(), f'{i}.img'), '-o',
                             work,
                             '-x'],
                        out=False) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'f2fs':
                if call(exe=['imgkit', 'unpack', "-i", os.path.join(project_manger.current_work_path(), f'{i}.img'),
                             "-o", work],
                        out=False) != 0:
                    print('Unpack failed...')
                    continue
                if os.path.exists(f'{work}/{i}'):
                    try:
                        os.remove(f"{work}/{i}.img")
                    except (Exception, BaseException):
                        win.message_pop(lang.warn11.format(i + ".img"))
            if file_type == 'amlogic':
                aml_main(os.path.join(project_manger.current_work_path(), f'{i}.img'), work)
            if file_type == 'unknown' and is_empty_img(f"{work}/{i}.img"):
                print(lang.text141)
    if not os.path.exists(f"{work}/config"):
        os.makedirs(f"{work}/config")
    json_.write(parts)
    parts.clear()
    print(lang.text8)
    return True


def ask_win(text='', ok=None, cancel=None, wait=True, is_top: bool = False, master: tk.Tk | Toplevel = None) -> int:
    ok = ok or lang.ok
    cancel = cancel or lang.cancel
    value = IntVar()
    master = master or win
    if is_top:
        ask = Toplevel()
        move_center(ask)
    else:
        ask = ttk.LabelFrame(master)
        ask.place(relx=0.5, rely=0.5, anchor="center")
    frame_inner = ttk.Frame(ask)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)
    ttk.Label(frame_inner, text=text, font=(None, 20), wraplength=400).pack(side=TOP)
    frame_button = ttk.Frame(frame_inner)

    ttk.Button(frame_button, text=cancel, command=lambda: close_ask(0)).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                             expand=True)
    ttk.Button(frame_button, text=ok, command=lambda: close_ask(1), style="Accent.TButton").pack(side='left', padx=5,
                                                                                                 pady=5,
                                                                                                 fill=BOTH,
                                                                                                 expand=True)
    frame_button.pack(side=TOP, fill=BOTH)

    def close_ask(value_=1):
        value.set(value_)
        ask.destroy()

    if wait:
        ask.wait_window()
    return value.get()


def info_win(text: str, ok: Optional[str] = None, master: Optional[tk.Wm] = None) -> None:
    """
    Displays a modal informational window that stays until the user clicks "OK".

    Similar to `warn_win` but intended for general information (e.g., success
    messages). It creates a modal dialog that remains on top of its parent.

    Args:
        text: The message to be displayed.
        ok: The text for the confirmation button. Defaults to a localized "OK".
        master: The parent widget for this dialog. If None, the main application
                window (`win`) is used.
    """
    ok_text = ok or getattr(lang, 'ok', 'OK')

    parent = master if master and master.winfo_exists() else win

    dialog = Toplevel()
    dialog.title("")  # A clean, title-less dialog window.

    # Make the dialog transient and modal.
    dialog.transient(parent)
    dialog.grab_set()

    frame_inner = ttk.Frame(dialog)
    frame_inner.pack(expand=True, fill=BOTH, padx=20, pady=20)

    ttk.Label(frame_inner, text=text, font=(None, 20), wraplength=400).pack(side=TOP)

    def close_dialog() -> None:
        """Releases the grab and destroys the dialog."""
        dialog.grab_release()
        dialog.destroy()

    ttk.Button(frame_inner, text=ok_text, command=close_dialog, style="Accent.TButton").pack(padx=5, pady=5,
                                                                                             fill=X, side=LEFT,
                                                                                             expand=True)
    dialog.update_idletasks()
    move_center(dialog)

    parent.wait_window(dialog)


@animation
def datbr(work: str, name: str, brl: str | int, dat_ver: int = 4):
    """

    :param work: working dir
    :param name: the name of the partitition
    :param brl: if its a int , will convert the file to br, if "dat" just convert to dat
    :param dat_ver: dat version
    :return:None
    """
    print(lang.text86 % (name, name))
    if not os.path.exists(f"{work}/{name}.img"):
        print(f"{work}/{name}.img" + lang.text84)
        return
    else:
        utils.img2sdat(f"{work}/{name}.img", work, dat_ver, name)
    if os.access(f"{work}/{name}.new.dat", os.F_OK):
        try:
            os.remove(f"{work}/{name}.img")
        except Exception:
            logging.exception('Bugs')
            os.remove(f"{work}/{name}.img")
    if brl == "dat":
        print(lang.text87 % name)
    else:
        print(lang.text88 % (name, 'br'))
        call(['brotli', '-q', str(brl), '-j', '-w', '24', f"{work}/{name}.new.dat", '-o', f"{work}/{name}.new.dat.br"])
        if os.access(f"{work}/{name}.new.dat", os.F_OK):
            try:
                os.remove(f"{work}/{name}.new.dat")
            except Exception:
                logging.exception('Bugs')
        print(lang.text89 % (name, 'br'))


def mkerofs(name: str, format_, work, work_output, level, old_kernel: bool = False, UTC: int = None):
    if not UTC:
        UTC = int(time.time())
    print(lang.text90 % (name, format_ + f',{level}', "1.x"))
    extra_ = f'{format_},{level}' if format_ != 'lz4' else format_
    other_ = ['-E', 'legacy-compress'] if old_kernel else []
    cmd = ['mkfs.erofs', *other_, f'-z{extra_}', '-T', f'{UTC}', f'--mount-point=/{name}',
           f'--product-out={work}',
           f'--fs-config-file={work}/config/{name}_fs_config',
           f'--file-contexts={work}/config/{name}_file_contexts',
           f'{work_output}/{name}.img', f'{work}/{name}/']
    return call(cmd, out=True)


@animation
def make_ext4fs(name: str, work: str, work_output, sparse: bool = False, size: int = 0, UTC: int = None,
                has_contexts: bool = True):
    if not has_contexts:
        print('Warning:file_context not found!!!')
    print(lang.text91 % name)
    if not UTC:
        UTC = int(time.time())
    if not size:
        size = GetFolderSize(work + name, 1, 3, f"{work}/dynamic_partitions_op_list").rsize_v
    print(f"{name}:[{size}]")
    context_cmd = ['-S', f'{work}/config/{name}_file_contexts'] if has_contexts else []
    command = ['make_ext4fs', '-J', '-T', f'{UTC}', '-s' if sparse else '', *context_cmd, '-l',
               f'{size}',
               '-C', f'{work}/config/{name}_fs_config', '-L', name, '-a', f'/{name}', f"{work_output}/{name}.img",
               work + name]
    return call(command)


@animation
def make_f2fs(name: str, work: str, work_output: str, UTC: int | None = None, readonly: bool = False,
              compress: bool = False):
    print(lang.text91 % name)
    size = GetFolderSize(work + name, 1, 1).rsize_v
    part_uuid = str(uuid.uuid4())
    print(f"{name} - {size} - {part_uuid}")

    def align_to_4k(size):
        # Align the size upwards to multiples of 4096 bytes.
        return (size + 4095) // 4096 * 4096

    # Set to 64MB to reserve space for F2FS Metadata
    size_f2fs = (64 * 1024 * 1024) + size
    # Apply a safety margin
    size_f2fs = int(size_f2fs * 1.15)
    # Align size to 4096-byte multiples.
    # Android dynamic partitions require sector alignment. 
    # Mismatched block sizes will cause 'lpmake' read errors or mount failures.
    size_f2fs = align_to_4k(size_f2fs)

    if not UTC:
        UTC = int(time.time())
    with open(f"{work + name}.img", 'wb') as f:
        f.truncate(size_f2fs)
    # /usr/bin/make_f2fs -d 0 -l odm -O extra_attr,compression,ro -U d6112980-bd3b-4b9e-bf4c-fba453cfdb42 -T 1230768000 ./Projects/Project_name/Build/odm.img -f
    #
    if call(['mkfs.f2fs', '-d', '0', '-l', name, '-O',
             "extra_attr,compression,ro" if readonly else 'extra_attr,inode_checksum,sb_checksum,compression', "-U",
             part_uuid, '-T', str(UTC), f"{work_output}/{name}.img", '-f']):
        return 1
    # The efficiency of verifying and adding file contexts has been improved.
    # Let's confirm that the basic context for the partition is present.
    line_to_ensure = f'/{name}/{name} u:object_r:system_file:s0\n'
    file_contexts_path = f'{work}/config/{name}_file_contexts'

    found = False
    with suppress(FileNotFoundError):
        with open(file_contexts_path, 'r', encoding='utf-8') as f_read:
            for line in f_read:
                if line.strip() == line_to_ensure.strip():
                    found = True
                    break

    if not found:
        with open(file_contexts_path, 'a', encoding='utf-8') as f_append:
            f_append.write(line_to_ensure)
    return call(['sload.f2fs', '-d', '0', '-c' if compress else '', '-r' if readonly else '', '-C',
                 f'{work}/config/{name}_fs_config', '-f', work + name, '-p', f'{work_output}/{name}.img', '-s',
                 f'{work}/config/{name}_file_contexts', '-t', f'/{name}', '-T', str(UTC), f'{work_output}/{name}.img'])


def mke2fs(name: str, work: str, sparse: bool, work_output: str, size: int = 0, UTC: int = None):
    if isinstance(size, str): size = int(size)
    print(lang.text91 % name)
    size = GetFolderSize(work + name, 4096, 3,
                         f"{work}/dynamic_partitions_op_list").rsize_v if not size else size / 4096
    print(f"{name}:[{size}]")
    if not UTC:
        UTC = int(time.time())
    if call(
            ['mke2fs', '-O',
             '^has_journal,^metadata_csum,extent,huge_file,^flex_bg,^64bit,uninit_bg,dir_nlink,extra_isize', '-L', name,
             '-I', '256', '-M', f'/{name}', '-m', '0', '-t', 'ext4', '-b', '4096', f'{work_output}/{name}_new.img',
             f'{int(size)}']) != 0:
        rmdir(f'{work_output}/{name}_new.img')
        print(lang.text75 % name)
        return 1
    ret = call(
        ['e2fsdroid', '-e', '-T', f'{UTC}', '-S', f'{work}/config/{name}_file_contexts', '-C',
         f'{work}/config/{name}_fs_config', '-a', f'/{name}', '-f', f'{work}/{name}',
         f'{work_output}/{name}_new.img'], out=not os.name == 'posix')
    if ret != 0:
        rmdir(f'{work}/{name}_new.img')
        print(lang.text75 % name)
        return 1
    if sparse:
        call(['img2simg', f'{work_output}/{name}_new.img', f'{work_output}/{name}.img'])
        try:
            os.remove(f"{work_output}/{name}_new.img")
        except (Exception, BaseException):
            logging.exception('Bugs')
    else:
        if os.path.isfile(f"{work_output}/{name}.img"):
            try:
                os.remove(f"{work_output}/{name}.img")
            except (Exception, BaseException):
                logging.exception('Bugs')
        os.rename(f"{work_output}/{name}_new.img", f"{work_output}/{name}.img")
    return 0


@animation
def rmdir(path: str, quiet: bool = False):
    if not path and not quiet:
        win.message_pop(lang.warn1)
    else:
        if not quiet:
            print(f"{lang.text97} {path}")
        try:
            try:
                rmtree(path)
            except (Exception, BaseException):
                logging.exception("Rmtree")
                call(['busybox', 'rm', '-rf', path], out=not quiet)
        except (Exception, BaseException):
            print(lang.warn11.format(path))
        if not quiet:
            win.message_pop(lang.warn11.format(path)) if os.path.exists(path) else print(lang.text98 + path)





def dndfile(files: list):
    for fi in files:
        if fi.endswith('}') and fi.startswith('{'):
            fi = fi[1:-1]
        try:
            if hasattr(fi, 'decode'):
                fi = fi.decode('gbk')
        except (Exception, BaseException):
            logging.exception('fI')
        if os.path.exists(fi):
            if os.path.isfile(fi):
                if fi.endswith(".mpk"):
                    InstallMpk(fi)
                else:
                    if gettype(fi) == 'unknown':
                        editor.main(os.path.dirname(fi), os.path.basename(fi))
                    else:
                        create_thread(unpackrom, fi)
            elif os.path.isdir(fi):
                create_thread(copy_project, fi)
        else:
            print(fi + lang.text84)


class ProjectMenuUtils(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text12)
        self.combobox: ttk.Combobox
        self.pack(padx=5, pady=5)

    @staticmethod
    def open_dir():
        name = current_project_name.get()
        if not project_manger.exist(name):
            win.message_pop(lang.warn1)
            return

        path = project_manger.get_work_path(name)
        if not path or not os.path.exists(path):
            win.message_pop(f"Cannot open folder:\n{path}")
            return

        try:
            path = os.path.normpath(path)
            if os.name == 'nt':
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception:
            logging.exception("Failed to open project folder: %s", path)
            win.message_pop(f"Cannot open folder:\n{path}")

    def gui(self):
        top_row = ttk.Frame(self)
        top_row.pack(side="top", padx=10, pady=10, fill=X)
        self.combobox = ttk.Combobox(top_row, textvariable=current_project_name, state='readonly')
        self.combobox.pack(side="left", fill=X, expand=True)
        self.combobox.bind('<<ComboboxSelected>>', lambda *x: print(lang.text96 + current_project_name.get()))
        icon = ttk.Button(top_row, text=lang.open, command=self.open_dir)
        icon.pack(side="right", padx=(6, 0))
        functions = [
            (lang.refresh, self.listdir),
            (lang.text115, self.new),
            (lang.text116, lambda: create_thread(self.remove)),
            (lang.text117, lambda: create_thread(self.rename)),
        ]
        for text, func in functions:
            ttk.Button(self, text=text, command=func).pack(side="left", padx=10, pady=10)

    @staticmethod
    def set_project(name):
        if not project_manger.exist(name):
            return
        current_project_name.set(name)

    def listdir(self):
        projects = list(project_manger.get_projects())
        origin_project = current_project_name.get()
        self.combobox["value"] = projects
        if not projects:
            current_project_name.set('')
            self.combobox.current()
        else:
            if origin_project and project_manger.exist(origin_project):
                self.set_project(origin_project)
            else:
                self.combobox.current(0)

    def rename(self) -> bool:
        name = current_project_name.get()
        if not project_manger.exist(name):
            print(lang.warn1)
            return False
        if project_manger.exist((inputvar := input_(lang.text102 + name, name, master=win))):
            print(lang.text103)
            return False
        if inputvar != name:
            os.rename(project_manger.get_work_path(name), project_manger.get_work_path(inputvar))
            self.listdir()
            self.set_project(inputvar)
        else:
            print(lang.text104)
        return True

    def remove(self):
        name = current_project_name.get()
        if not project_manger.exist(name):
            win.message_pop(lang.warn1)
        project_manger.remove(name)
        self.listdir()

    def new(self):
        if not (inputvar := input_(master=win.tk_root)):
            win.message_pop(lang.warn12)
        else:
            inputvar = inputvar.replace(' ', '_').strip()
            if not inputvar.isprintable():
                win.message_pop(lang.warn12)
            print(lang.text99 % inputvar)
            project_manger.new(inputvar)
        self.listdir()


class Frame3(ttk.LabelFrame):
    def __init__(self):
        super().__init__(master=win.tab2, text=lang.text112)
        self.pack(padx=5, pady=5)

    def gui(self):
        row = 0
        functions = [
            (lang.text122, lambda: create_thread(pack_zip)),
            (lang.text123, lambda: create_thread(PackSuper)),
            (lang.text19, lambda: win.notepad.select(win.tab7)),
            (lang.t13, lambda: create_thread(FormatConversion)),
            (lang.apk_manager, lambda: ApkManager(current_project_name.get())),
            # ("打包 Payload", lambda: create_thread(NewPostInstallConfig)),
        ]
        for index, (text, func) in enumerate(functions):
            column = index % 4
            if not column:
                row += 1
            ttk.Button(self, text=text, command=func, width=11).grid(row=row, column=column, padx=5, pady=5)


class UnpackGui(ttk.LabelFrame):
    """
    A GUI component for selecting partitions to pack or unpack.
    It provides controls to switch between pack/unpack modes, select file formats,
    and lists the available items for the selected operation.
    """

    def __init__(self):
        super().__init__(master=win.tab2, text=lang.t57)
        self.ch = BooleanVar()  # Variable to toggle between Pack (False) and Unpack (True) modes.
        current_project_name.trace_add("write", self._on_project_change)

    def _on_project_change(self, *args):
        """
        Callback method that is automatically invoked when `current_project_name` changes.
        It refreshes the list of items to reflect the contents of the new project.
        """
        # Check if the `hd` method exists and the widget itself is still valid before calling.
        if self.winfo_exists() and hasattr(self, 'hd'):
            # Calling `hd()` will update the list of sections for the new project,
            # taking into account the current mode (Unpack/Pack).
            self.hd()

    def gui(self):
        """Builds the graphical user interface for this component."""
        self.pack(padx=5, pady=5)
        self.ch.set(True)  # Default to Unpack mode.
        run_Select_canvas = Canvas(self)
        run_Select_canvas.config(highlightthickness=0)

        # Combobox for selecting the file format to unpack.
        self.fm = ttk.Combobox(run_Select_canvas, state="readonly",
                               values=(
                                   'new.dat.br', 'new.dat.xz', "new.dat", 'img', 'zst', 'payload', 'super',
                                   'update.app'))

        self.lsg = ListBox(self)  # The listbox for displaying items.
        self.menu = Menu(self.lsg, tearoff=False, borderwidth=0)  # Context menu for listbox items.
        self.menu.add_command(label=lang.attribute, command=self.info)
        self.lsg.bind('<Button-3>', self.show_menu)

        self.fm.current(0)
        self.fm.bind("<<ComboboxSelected>>", lambda *x: self.refs())
        self.lsg.gui()
        self.lsg.canvas.bind('<Button-3>', self.show_menu)

        # Frame for Pack/Unpack radio buttons.
        ff1 = ttk.Frame(self)
        ttk.Radiobutton(ff1, text=lang.unpack, variable=self.ch,
                        value=True).pack(padx=5, pady=5, side='left')
        ttk.Radiobutton(ff1, text=lang.pack, variable=self.ch,
                        value=False).pack(padx=5, pady=5, side='left')

        self.fm.pack(padx=5, pady=5, fill=Y, side=LEFT)
        ttk.Button(run_Select_canvas, text=lang.run, command=lambda: create_thread(self.close_)).pack(padx=5, pady=5,
                                                                                                      side=LEFT)

        # Layout the components.
        run_Select_canvas.pack(side=BOTTOM, fill=X)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=50, side=BOTTOM, fill=X)
        ff1.pack(padx=5, pady=5, fill=X, side=BOTTOM)
        ttk.Separator(self, orient=HORIZONTAL).pack(padx=50, side=BOTTOM, fill=X)
        self.lsg.pack(padx=5, pady=5, fill=Y, side=BOTTOM, expand=True)

        self.refs()  # Initial population of the listbox.
        self.ch.trace("w", lambda *x: self.hd())  # Add trace to update UI on mode change.

    def show_menu(self, event):
        """Displays the context menu if a single image item is selected."""
        if len(self.lsg.selected) == 1 and self.fm.get() == 'img':
            self.menu.post(event.x_root, event.y_root)

    def info(self):
        """Displays detailed information about the selected image file."""
        ck_ = Toplevel()
        move_center(ck_)
        ck_.title(lang.attribute)
        if not self.lsg.selected:
            ck_.destroy()
            return

        f_path = os.path.join(project_manger.current_work_path(), self.lsg.selected[0] + ".img")
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
        if not hasattr(self, 'fm'):
            return
        if self.ch.get():  # True = Unpack mode
            self.fm.configure(state='readonly')
            self.refs()
        else:  # False = Pack mode
            self.fm.configure(state="disabled")
            # Special handling for payload in pack mode
            self.refs2()

    def refs_payload_pack(self):
        """
        Displays images available for packing into a payload.bin.
        """
        self.lsg.clear()
        work = project_manger.current_work_path()
        if not os.path.exists(work):
            win.message_pop(lang.warn1)
            return False

        parts_dict = JsonEdit(f"{work}/config/parts_info").read()

        # Find .img files in the working directory to be packed into the payload.
        for file_name in os.listdir(work):
            if file_name.endswith('.img'):
                partition_name = file_name.split('.img')[0]
                img_path = os.path.join(work, file_name)
                # Skip empty images.
                if not os.path.getsize(img_path):
                    continue
                f_type = gettype(img_path)
                if f_type == 'unknown':
                    f_type = 'img'

                # Check if a corresponding folder type exists in parts_info.
                folder_type = parts_dict.get(partition_name, f_type)

                self.lsg.insert(f'{partition_name} [{folder_type}] ({hum_convert(os.path.getsize(img_path))})',
                                partition_name)

        return True

    def refs(self, auto: bool = False):
        """
        Refreshes the list of items available for unpacking based on the selected format.
        """
        if auto:
            for index, value in enumerate(self.fm.cget("values")):
                self.fm.current(index)
                self.__refs()
                if len(self.lsg.vars):
                    return True
            self.fm.current(0)
            return True
        return create_thread(self.__refs)

    @animation
    def __refs(self):
        """The actual logic for refreshing the unpack list, runs in a separate thread."""
        self.lsg.clear()
        work = project_manger.current_work_path()
        if not project_manger.exist():
            return False

        form = self.fm.get()
        if form == 'payload':
            if os.path.exists(f"{work}/payload.bin"):
                with open(f"{work}/payload.bin", 'rb') as pay:
                    for i in utils.payload_reader(pay).partitions:
                        self.lsg.insert(f"{i.partition_name}{hum_convert(i.new_partition_info.size):>10}",
                                        i.partition_name)
        elif form == 'super':
            if os.path.exists(f"{work}/super.img"):
                if gettype(f"{work}/super.img") == 'sparse':
                    print("The image is sparse, pls convert it to raw first.")
                    return False
                for i in lpunpack.get_parts(f"{work}/super.img"):
                    self.lsg.insert(i, i)
        elif form == 'update.app':
            if os.path.exists(f"{work}/UPDATE.APP"):
                for i in splituapp.get_parts(f"{work}/UPDATE.APP"):
                    self.lsg.insert(i, i)
        else:
            for file_name in os.listdir(work):
                if file_name.endswith(form):
                    if file_name.endswith("img"):
                        f_type = gettype(work + file_name)
                        if f_type == 'unknown':
                            f_type = form
                    else:
                        f_type = form
                    self.lsg.insert(f'{file_name[:-len(f".{form}")]} [{f_type}]',
                                    file_name[:-len(f".{form}")])
        return True

    def refs2(self):
        """Refreshes the list of items available for packing (e.g., unpacked directories)."""
        self.lsg.clear()
        work = project_manger.current_work_path()
        if not os.path.exists(work):
            win.message_pop(lang.warn1)
            return False
        parts_dict = JsonEdit(f"{work}/config/parts_info").read()
        for folder in os.listdir(work):
            if os.path.isdir(work + folder) and folder in parts_dict.keys():
                self.lsg.insert(f"{folder} [{parts_dict.get(folder, 'Unknown')}]", folder)
        return True

    def close_(self):
        """
        Initiates the pack or unpack operation based on the current mode and user selection.
        """
        lbs = self.lsg.selected.copy()

        # Update the UI before starting a potentially long operation.
        if self.winfo_exists():
            self.update_idletasks()

        if self.ch.get():  # Unpack mode (True)
            unpack(lbs, self.fm.get())
            self.refs()
        else:  # Pack mode (False)
            PackPartition(lbs)


class ApkManager(Toplevel):
    def __init__(self, project_name: str = "generic"):
        super().__init__()
        self.title(f"{lang.apk_manager} [{project_name}]")
        self.apkManager = ApkManagerContent(self, project_manger.current_work_path())
        create_thread(self.apkManager.parse_dir)
        move_center(self)


class FormatConversion(ttk.LabelFrame):
    def __init__(self):
        super().__init__(text=lang.t13)
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.frame = Frame(self)
        self.frame.pack(pady=5, padx=5, fill=X)
        self.h = ttk.Combobox(self.frame, values=("raw", "sparse", 'dat', 'br', 'xz'), state='readonly')
        self.h.current(0)
        self.h.bind("<<ComboboxSelected>>", lambda *x: self.relist())
        self.h.pack(side='left', padx=5)
        Label(self.frame, text='>>>>>>').pack(side='left', padx=5)
        self.f = ttk.Combobox(self.frame, values=("raw", "sparse", 'dat', 'br'), state='readonly')
        self.f.current(0)
        self.f.pack(side='left', padx=5)
        self.list_b = ListBox(self)
        self.list_b.gui()
        self.list_b.pack(padx=5, pady=5, fill=BOTH)
        create_thread(self.relist)
        t = Frame(self)
        ttk.Button(t, text=lang.cancel, command=self.destroy).pack(side='left', padx=5, pady=5, fill=BOTH,
                                                                   expand=True)
        ttk.Button(t, text=lang.ok, command=lambda: create_thread(self.conversion), style='Accent.TButton').pack(
            side='left',
            padx=5, pady=5,
            fill=BOTH,
            expand=True)
        t.pack(side=BOTTOM, fill=BOTH)

    def relist(self):
        work = project_manger.current_work_path()
        self.list_b.clear()
        if self.h.get() == "br":
            for i in self.refile(".new.dat.br"):
                self.list_b.insert(i, i)
        elif self.h.get() == 'xz':
            for i in self.refile(".new.dat.xz"):
                self.list_b.insert(i, i)
        elif self.h.get() == 'dat':
            for i in self.refile(".new.dat"):
                self.list_b.insert(i, i)
        elif self.h.get() == 'sparse':
            for i in os.listdir(work):
                if os.path.isfile(f'{work}/{i}') and gettype(f'{work}/{i}') == 'sparse':
                    self.list_b.insert(i, i)
        elif self.h.get() == 'raw':
            for i in os.listdir(work):
                if os.path.isfile(f'{work}/{i}'):
                    if gettype(f'{work}/{i}') in ['ext', 'erofs', 'super', 'f2fs']:
                        self.list_b.insert(i, i)

    @staticmethod
    def refile(f):
        for i in os.listdir(work := project_manger.current_work_output_path()):
            if i.endswith(f) and os.path.isfile(f'{work}/{i}'):
                yield i

    @animation
    def conversion(self):
        work = project_manger.current_work_output_path()
        f_get = self.f.get()
        hget = self.h.get()
        selection = self.list_b.selected.copy()
        self.destroy()
        if f_get == hget:
            return
        for i in selection:
            print(f'[{hget}->{f_get}]{i}')
            if f_get == 'sparse':
                basename = os.path.basename(i).split('.')[0]
                if hget == 'br':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        call(['brotli', '-dj', f'{work}/{i}'])
                if hget == 'xz':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        Unxz(f'{work}/{i}')
                if hget == 'dat':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + f'{work}/{i}')
                        transferfile = os.path.abspath(
                            os.path.dirname(work)) + f"/{basename}.transfer.list"
                        if os.access(transferfile, os.F_OK) and os.path.getsize(f'{work}/{i}') != 0:
                            Sdat2img(transferfile, f'{work}/{i}', f"{work}/{basename}.img")
                            if os.access(f"{work}/{basename}.img", os.F_OK):
                                os.remove(f'{work}/{i}')
                                os.remove(transferfile)
                                try:
                                    os.remove(f'{work}/{basename}.patch.dat')
                                except (IOError, PermissionError, FileNotFoundError):
                                    logging.exception('Bugs')
                        else:
                            print("transferpath" + lang.text84)
                    if os.path.exists(f'{work}/{basename}.img'):
                        img2simg(f'{work}/{basename}.img')
                if hget == 'raw':
                    if os.path.exists(f'{work}/{basename}.img'):
                        img2simg(f'{work}/{basename}.img')
            elif f_get == 'raw':
                basename = os.path.basename(i).split('.')[0]
                if hget == 'br':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        call(['brotli', '-dj', f'{work}/{i}'])
                if hget == 'xz':
                    if os.access(f'{work}/{i}', os.F_OK):
                        print(lang.text79 + i)
                        Unxz(f'{work}/{i}')
                if hget in ['dat', 'br', 'xz']:
                    if os.path.exists(work):
                        if hget == 'br':
                            i = i.replace('.br', '')
                        if hget == 'xz':
                            i = i.replace('.xz', '')
                        print(lang.text79 + f'{work}/{i}')
                        transferfile = os.path.abspath(
                            os.path.dirname(work)) + f"/{basename}.transfer.list"
                        if os.access(transferfile, os.F_OK) and os.path.getsize(f'{work}/{i}') != 0:
                            Sdat2img(transferfile, f'{work}/{i}', f"{work}/{basename}.img")
                            if os.access(f"{work}/{basename}.img", os.F_OK):
                                try:
                                    os.remove(f'{work}/{i}')
                                    os.remove(transferfile)
                                    if not os.path.getsize(f'{work}/{basename}.patch.dat'):
                                        os.remove(f'{work}/{basename}.patch.dat')
                                except (PermissionError, IOError, FileNotFoundError, IsADirectoryError):
                                    logging.exception('Bugs')
                        else:
                            print("transferfile" + lang.text84)
                if hget == 'sparse':
                    utils.simg2img(f'{work}/{i}')
            elif f_get == 'dat':
                if hget == 'raw':
                    img2simg(f'{work}/{i}')
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], "dat")
                if hget == 'br':
                    print(lang.text79 + i)
                    call(['brotli', '-dj', f'{work}/{i}'])
                if hget == 'xz':
                    print(lang.text79 + i)
                    Unxz(f'{work}/{i}')

            elif f_get == 'br':
                if hget == 'raw':
                    img2simg(f'{work}/{i}')
                if hget in ['raw', 'sparse']:
                    datbr(work, os.path.basename(i).split('.')[0], 0)
                if hget in ['dat', 'xz']:
                    if hget == 'xz':
                        print(lang.text79 + i)
                        Unxz(f'{work}/{i}')
                        i = i.rsplit('.xz', 1)[0]

                    print(lang.text88 % (os.path.basename(i).split('.')[0], 'br'))
                    call(['brotli', '-q', '0', '-j', '-w', '24', f'{work}/{i}', '-o', f'{work}/{i}.br'])
                    if os.access(f'{work}/{i}.br', os.F_OK):
                        try:
                            os.remove(f'{work}/{i}')
                        except Exception:
                            logging.exception('Bugs')
        print(lang.text8)


def init_verify():
    if not os.path.exists(settings.tool_bin):
        error(1, 'Sorry,Not support your device yet.')
    if not settings.path.isprintable():
        ask_win(lang.warn16 % lang.special_words, is_top=True)
    if " " in settings.path:
        ask_win(f"The path ({settings.path}) do not allow [space], please change the path!", is_top=True)


def init_tk(windows_tk):
    global win
    win = windows_tk
    # Prevent multiple initializations (ensure home_page / Tk init runs only once)
    if states.inited:
        logging.debug("init_tk: already initialized, skipping.")
        return
    if not os.path.exists(temp):
        re_folder(temp, quiet=True)
    if not os.path.exists(tool_log):
        open(tool_log, 'w', encoding="utf-8", newline="\n").close()
    if not states.development:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(asctime)s:%(filename)s:%(name)s:%(message)s',
                            filename=tool_log, filemode='w')
    else:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(asctime)s:%(filename)s:%(name)s:%(message)s')
    animation.master = windows_tk.tk_root
    global current_project_name, theme, language
    current_project_name = utils.project_name = StringVar()
    theme = StringVar()
    language = StringVar()
    settings.load()
    if settings.updating == 'true':
        updater = Updater()
        try:
            updater.wait_window()
        except (BaseException, Exception):
            logging.exception('Cannot wait the Updater.Maybe the step completed.')
    if int(settings.oobe) < 5:
        if pyi_splash_available:
            pyi_splash.close()
        Welcome()
    init_verify()
    try:
        win.tk_root.winfo_exists()
    except TclError:
        logging.exception('TclError')
        return
    win.gui()
    global unpackg
    unpackg = UnpackGui()
    global project_menu
    project_menu = ProjectMenuUtils()
    project_menu.gui()
    project_menu.listdir()
    unpackg.gui()
    Frame3().gui()
    animation.load_gif(open_img(BytesIO(getattr(images, f"loading_dark_byte"))))
    animation.init()
    if not is_pro:
        print(lang.text108)
    if is_pro:
        if not verify.state:
            Active(verify, settings, win, images, lang).gui()
    win.update()
    if pyi_splash_available:
        pyi_splash.close()
    if settings.check_upgrade == '1':
        win.loops.append(check_upgrade)
    print(lang.text134 % (dti() - start))
    states.inited = True
    win.tk_root.protocol("WM_DELETE_WINDOW", exit_tool)
    try:
        win.start_loops()
    except KeyboardInterrupt:
        exit_tool()


# Hey! IF U READ IT, PLEASE STOP WORK AND REMOVE THIS FILE.
# Cool Init
# Miside 米塔
# Link: https://store.steampowered.com/app/2527500/


def restart(er: Toplevel = None):
    try:
        if animation.tasks:
            if not ask_win("Your operation will not be saved.", is_top=True):
                return
    except (TclError, ValueError, AttributeError):
        logging.exception('Restart')

    def _inner():
        argv = [sys.executable]
        if not pathlib.Path(tool_self).samefile(pathlib.Path(argv[0])):
            # only needed when running within a Python intepreter
            argv.append(tool_self)
        argv.extend(sys.argv[1:])
        p = subprocess.Popen(argv)
        p.wait()
        sys.exit(p.returncode)

    if er: er.destroy()
    try:
        for i in win.winfo_children():
            try:
                i.destroy()
            except (TclError, ValueError, AttributeError):
                logging.exception('Restart')
        win.destroy()
    except (Exception, BaseException):
        logging.exception('Restart')

    threading.Thread(target=_inner).start()
