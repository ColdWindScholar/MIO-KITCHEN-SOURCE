"""Python wrapper for the tkdnd tk extension.

The tkdnd extension provides an interface to native, platform specific
drag and drop mechanisms. Under Unix the drag & drop protocol in use is
the XDND protocol version 5 (also used by the Qt toolkit, and the KDE and
GNOME desktops). Under Windows, the OLE2 drag & drop interfaces are used.
Under Macintosh, the Cocoa drag and drop interfaces are used.

Once the TkinterDnD2 package is installed, it is safe to do:

from TkinterDnD2 import * # This refers to the original package name.
                          # In this project, it might be from .tkinterdnd2_build_in import *
                          # or similar, depending on how it's integrated.

This will add the classes TkinterDnD.Tk to the global
namespace, plus the following constants:
PRIVATE, NONE, ASK, COPY, MOVE, LINK, REFUSE_DROP,
DND_TEXT, DND_FILES, DND_ALL, CF_UNICODETEXT, CF_TEXT, CF_HDROP,
FileGroupDescriptor, FileGroupDescriptorW

Drag and drop for the application can then be enabled by using one of the
classes similar to TkinterDnD.Tk() as application main window instead of a regular
tkinter.Tk() window. This will add the drag-and-drop specific methods to the
Tk window and all its descendants.
"""

import tkinter
import os # Добавлен os для os.path и os.name
import sys # Добавлен sys для getattr(sys, 'frozen', False) и sys.stderr
import platform # Используем platform из стандартной библиотеки
import traceback # Для вывода traceback при неожиданных ошибках

# Убедимся, что prog_path импортируется. Если utils.py еще не инициализирован, это может быть проблемой.
# Предполагаем, что к моменту вызова Tk() -> _require(), utils.prog_path уже установлен.
try:
    from ..core.utils import prog_path
except ImportError:
    # Фоллбэк, если относительный импорт не сработал (например, если TkinterDnD.py запускается отдельно)
    # В рабочем приложении это не должно происходить.
    if getattr(sys, 'frozen', False):
        prog_path = os.path.dirname(sys.executable)
    else:
        prog_path = os.path.dirname(os.path.abspath(__file__)) # Не идеально для структуры проекта
    sys.stderr.write(f"[TkinterDnD WARNING] Could not import prog_path from ..core.utils. Using fallback: {prog_path}\n")


TkdndVersion = None

def _require(tkroot):
    """Internal function to load the Tcl tkdnd package."""
    global TkdndVersion
    
    # Если версия уже загружена, не делаем ничего
    # (Это может быть полезно, если _require вызывается несколько раз, хотя обычно не должен)
    # if TkdndVersion:
    #     return TkdndVersion

    # --- Determine platform-specific subdirectory name for tkdnd ---
    current_os = platform.system()
    current_machine = platform.machine()
    current_arch_bits = platform.architecture()[0] # '32bit' or '64bit'
    
    tkdnd_platform_rep = None

    if current_os == "Darwin": # macOS
        if current_machine == "arm64":
            tkdnd_platform_rep = "osx-arm64"
        elif current_machine == "x86_64":
            tkdnd_platform_rep = "osx-x64"
    elif current_os == "Linux":
        if current_machine == "aarch64":
            tkdnd_platform_rep = "linux-arm64"
        elif current_machine == "x86_64":
            tkdnd_platform_rep = "linux-x64"
        elif current_machine in ["i386", "i686"]: # For 32-bit Linux
             tkdnd_platform_rep = "linux-x86" # Assuming this folder name exists
    elif current_os == "Windows":
        if current_machine == "AMD64": # Standard 64-bit
            tkdnd_platform_rep = "win-x64"
        elif current_machine == "ARM64":
            tkdnd_platform_rep = "win-arm64"
        elif current_arch_bits == '32bit' or current_machine.lower() in ['x86', 'i386', 'i686']:
            tkdnd_platform_rep = "win-x86"
        else: # Fallback for Windows if architecture is unusual
            sys.stderr.write(f"[TkinterDnD WARNING] Unknown Windows architecture: {current_machine}. Defaulting based on Python bitness.\n")
            tkdnd_platform_rep = 'win-x64' if sys.maxsize > 2**32 else 'win-x86'
    
    if not tkdnd_platform_rep:
        # This error should be caught by the caller or logged appropriately.
        raise RuntimeError(f"TkinterDnD: Platform not supported or architecture undetermined (OS: {current_os}, Arch: {current_machine}).")

    # --- Construct the path to the tkdnd library ---
    # prog_path should be the root directory of your application bundle (e.g., where MIO-KITCHEN.exe is)
    # Your build.py copies tkdnd to <app_root>/bin/tkdnd/<platform_rep>/
    # So, the path should be os.path.join(prog_path, 'bin', 'tkdnd', tkdnd_platform_rep)
    # If prog_path from utils is already os.path.dirname(sys.executable) for frozen apps, this is correct.

    # Let's determine the base_executable_dir for clarity in frozen state
    if getattr(sys, 'frozen', False):
        # For frozen app (PyInstaller bundle)
        base_executable_dir = os.path.dirname(sys.executable)
        # In this case, prog_path from utils.py *should* be this base_executable_dir.
        # If it's not, then utils.prog_path needs to be fixed.
        # Assuming prog_path is correctly set to the directory containing the .exe
    else:
        # For script mode, prog_path from utils.py should point to the project root.
        base_executable_dir = prog_path # prog_path is project root

    # The tkdnd libraries are expected to be in <base_executable_dir>/bin/tkdnd/<platform_rep>
    # for a one-dir build, or if manually placed there for a one-file build's runtime extraction.
    # The key is that 'bin/tkdnd/...' must be relative to where the app *runs* from.
    # If 'prog_path' from utils.py is always the application's effective root (e.g. dir of .exe),
    # then this is simpler:
    tkdnd_lib_path = os.path.join(prog_path, 'bin', 'tkdnd', tkdnd_platform_rep)
    
    # --- Debugging Output ---
    # Use a logger if available, otherwise print to stderr
    log_func = logging.info if 'logging' in globals() and hasattr(logging, 'info') else lambda msg: sys.stderr.write(f"INFO: {msg}\n")
    warn_func = logging.warning if 'logging' in globals() and hasattr(logging, 'warning') else lambda msg: sys.stderr.write(f"WARNING: {msg}\n")
    
    log_func(f"[TkinterDnD] Determined tkdnd_platform_rep: {tkdnd_platform_rep}")
    log_func(f"[TkinterDnD] utils.prog_path is: {prog_path}") # Check what utils.prog_path gives
    log_func(f"[TkinterDnD] Constructed tkdnd_lib_path: {tkdnd_lib_path}")

    if not os.path.isdir(tkdnd_lib_path):
        warn_func(f"[TkinterDnD] tkdnd library path does not exist or is not a directory: '{tkdnd_lib_path}'")
        # Check contents of the parent 'bin/tkdnd' directory for diagnostics
        parent_tkdnd_dir_check = os.path.join(prog_path, 'bin', 'tkdnd')
        if os.path.isdir(parent_tkdnd_dir_check):
            log_func(f"[TkinterDnD] Contents of '{parent_tkdnd_dir_check}': {os.listdir(parent_tkdnd_dir_check)}")
        else:
            warn_func(f"[TkinterDnD] Parent directory '{parent_tkdnd_dir_check}' also not found.")
        # This error will likely lead to 'package require tkdnd' failing.
        # The RuntimeError below will then be more informative.

    try:
        tkroot.tk.call('lappend', 'auto_path', tkdnd_lib_path)
        TkdndVersion = tkroot.tk.call('package', 'require', 'tkdnd')
        log_func(f"[TkinterDnD] Successfully loaded tkdnd version: {TkdndVersion}")
    except tkinter.TclError as e_tcl:
        err_msg = (f"Unable to load tkdnd Tcl package. "
                   f"Attempted platform: '{tkdnd_platform_rep}'. "
                   f"Attempted library path: '{tkdnd_lib_path}'. "
                   f"Original TclError: {e_tcl}")
        
        # Log detailed error
        error_log_func = logging.error if 'logging' in globals() and hasattr(logging, 'error') else lambda msg: sys.stderr.write(f"ERROR: {msg}\n")
        error_log_func(f"[TkinterDnD] {err_msg}")
        
        raise RuntimeError(err_msg) from e_tcl # Re-raise with more context

    except Exception as e_unexpected: # Catch any other unexpected errors during Tcl calls
        err_msg = f"An unexpected error occurred in tkdnd _require: {e_unexpected}"
        # Log with traceback
        crit_log_func = logging.critical if 'logging' in globals() and hasattr(logging, 'critical') else lambda msg: sys.stderr.write(f"CRITICAL: {msg}\n")
        if 'logging' in globals() and hasattr(logging, 'exception'):
            logging.exception(err_msg)
        else:
            crit_log_func(err_msg)
            traceback.print_exc(file=sys.stderr)
        raise RuntimeError(err_msg) from e_unexpected
        
    return TkdndVersion

class DnDEvent:
    """
    A container for properties of a drag-and-drop event, analogous to
    a standard tkinter.Event.

    Attributes are dynamically assigned based on the Tcl event substitution,
    and may include: action, actions, button, code, codes, commonsourcetypes,
    commontargettypes, data, name, types, modifiers, supportedsourcetypes,
    sourcetypes, type, supportedtargettypes, widget, x_root, y_root.
    Not all attributes are set for every type of DnD event.
    """
    pass # Attributes are set dynamically

class DnDWrapper:
    """
    An internal mixin class that adds Tcl/Tk bindings for tkdnd functionality
    to Tkinter widgets. This class is not intended to be instantiated directly.
    """
    _subst_format_dnd = ('%A', '%a', '%b', '%C', '%c', '{%CST}',
                         '{%CTT}', '%D', '%e', '{%L}', '{%m}', '{%ST}',
                         '%T', '{%t}', '{%TT}', '%W', '%X', '%Y')
    _subst_format_str_dnd = " ".join(_subst_format_dnd)
    
    # Monkey-patch BaseWidget to include these formats for Tcl substitution
    tkinter.BaseWidget._subst_format_dnd = _subst_format_dnd
    tkinter.BaseWidget._subst_format_str_dnd = _subst_format_str_dnd

    def _substitute_dnd(self, *args):
        """
        Internal: Converts Tcl event substitution strings into a DnDEvent object.
        """
        if len(args) != len(self._subst_format_dnd): # Should not happen if Tcl call is correct
            return args 
        
        # Helper to convert string to int if possible, else return string
        def getint_event(s_val):
            try: return int(s_val)
            except ValueError: return s_val
        
        # Helper to split Tcl list strings into Python tuples
        def splitlist_event(s_list):
            try: return self.tk.splitlist(s_list)
            except (tkinter.TclError, ValueError): return s_list # Return as is if not a valid Tcl list

        # Unpack arguments based on _subst_format_dnd
        A, a, b, C, c, CST, CTT, D, e, L, m, ST, T, t, TT, W, X, Y = args
        
        ev = DnDEvent()
        ev.action = A
        ev.actions = splitlist_event(a)
        ev.button = getint_event(b)
        ev.code = C
        ev.codes = splitlist_event(c)
        ev.commonsourcetypes = splitlist_event(CST)
        ev.commontargettypes = splitlist_event(CTT)
        ev.data = D
        ev.name = e # Event name (e.g., <<Drop>>)
        ev.types = splitlist_event(L) # List of data types offered by the source
        ev.modifiers = splitlist_event(m) # Keyboard modifiers (e.g., Shift, Control)
        ev.supportedsourcetypes = splitlist_event(ST)
        ev.sourcetypes = splitlist_event(t) # Alias for ev.types on some events
        ev.type = T # Actual data type chosen for the drop
        ev.supportedtargettypes = splitlist_event(TT)
        try:
            ev.widget = self.nametowidget(W) # Convert widget path to widget instance
        except KeyError:
            ev.widget = W # Fallback to widget path string if instance not found
        ev.x_root = getint_event(X) # X-coordinate relative to the screen root
        ev.y_root = getint_event(Y) # Y-coordinate relative to the screen root
        
        return (ev,) # Return as a tuple, similar to standard Tkinter event handling
    
    # Monkey-patch BaseWidget with this substitution method
    tkinter.BaseWidget._substitute_dnd = _substitute_dnd

    def _dnd_bind(self, what, sequence, func, add, needcleanup=True):
        """
        Internal: Low-level function to bind TkDnD events.
        'what' is typically ('bind', self._w).
        """
        if isinstance(func, str): # If func is a Tcl command string
            self.tk.call(what + (sequence, func))
        elif func: # If func is a Python callable
            funcid = self._register(func, self._substitute_dnd, needcleanup)
            cmd = '%s%s %s' % (add and '+' or '', funcid, self._subst_format_str_dnd)
            self.tk.call(what + (sequence, cmd))
            return funcid
        elif sequence: # If only sequence is given, return current binding
            return self.tk.call(what + (sequence,))
        else: # If no sequence, return all bindings for this type
            return self.tk.splitlist(self.tk.call(what))
            
    # Monkey-patch BaseWidget
    tkinter.BaseWidget._dnd_bind = _dnd_bind

    def dnd_bind(self, sequence=None, func=None, add=None):
        """
        Bind a drag-and-drop event SEQUENCE to a Python function FUNC for this widget.

        Args:
            sequence (str): The DnD event sequence (e.g., '<<Drop>>', '<<Drop:DND_Files>>').
                            Common sequences include:
                            <<DropEnter>>, <<DropPosition>>, <<DropLeave>>, <<Drop>>,
                            <<Drop:type>>, <<DragInitCmd>>, <<DragEndCmd>>.
            func (callable): The Python function to call when the event occurs.
                             It will receive a DnDEvent object as an argument.
            add (str, optional): If '+', add this binding to any existing ones.
                                 Otherwise, this binding replaces existing ones.

        Returns:
            str or list: The Tcl command string of the binding, or a list of bindings.

        Callbacks for <<Drop*>> events (except <<DropLeave>>) should typically return
        an action string (e.g., COPY, MOVE, ASK, PRIVATE, REFUSE_DROP).
        The callback for <<DragInitCmd>> must return a 3-tuple:
        (supported_actions, data_types, data_to_drop).
        """
        return self._dnd_bind(('bind', self._w), sequence, func, add)
        
    # Monkey-patch BaseWidget
    tkinter.BaseWidget.dnd_bind = dnd_bind

    def drag_source_register(self, button: int = 1, *dndtypes):
        """
        Register this widget as a drag source.

        Args:
            button (int, optional): Mouse button to initiate drag (1, 2, or 3). Defaults to 1 (left).
            *dndtypes: Variable number of strings representing the data types this source can offer
                       (e.g., DND_TEXT, DND_FILES, or platform-specific types).
        """
        # Original code had a workaround for button potentially being a dndtype.
        # Modernized to expect button as an int first.
        if not isinstance(button, int) or button not in [1, 2, 3]:
            # If button is not a valid int, assume it's the first dndtype
            dndtypes = (button,) + dndtypes
            button = 1 # Default to button 1
            
        self.tk.call('tkdnd::drag_source', 'register', self._w, dndtypes or DND_ALL, button)
        
    # Monkey-patch BaseWidget
    tkinter.BaseWidget.drag_source_register = drag_source_register

    def drag_source_unregister(self):
        """Unregister this widget as a drag source."""
        self.tk.call('tkdnd::drag_source', 'unregister', self._w)
        
    # Monkey-patch BaseWidget
    tkinter.BaseWidget.drag_source_unregister = drag_source_unregister

    def drop_target_register(self, *dndtypes):
        """
        Register this widget as a drop target.

        Args:
            *dndtypes: Variable number of strings representing the data types this target can accept
                       (e.g., DND_TEXT, DND_FILES, DND_ALL, or platform-specific types).
                       If no types are provided, DND_ALL is typically assumed by tkdnd.
        """
        self.tk.call('tkdnd::drop_target', 'register', self._w, dndtypes or DND_ALL)
        
    # Monkey-patch BaseWidget
    tkinter.BaseWidget.drop_target_register = drop_target_register

    def drop_target_unregister(self):
        """Unregister this widget as a drop target."""
        self.tk.call('tkdnd::drop_target', 'unregister', self._w)
        
    # Monkey-patch BaseWidget
    tkinter.BaseWidget.drop_target_unregister = drop_target_unregister

    # The following methods are tkdnd utility functions, typically called on a widget instance.
    def platform_independent_types(self, *dndtypes) -> tuple:
        """Converts platform-specific DnD types to platform-independent ones."""
        return self.tk.splitlist(self.tk.call('tkdnd::platform_independent_types', dndtypes))
        
    tkinter.BaseWidget.platform_independent_types = platform_independent_types

    def platform_specific_types(self, *dndtypes) -> tuple:
        """Converts platform-independent DnD types to platform-specific ones for the current platform."""
        return self.tk.splitlist(self.tk.call('tkdnd::platform_specific_types', dndtypes))
        
    tkinter.BaseWidget.platform_specific_types = platform_specific_types

    def get_dropfile_tempdir(self) -> str:
        """Returns the temporary directory used by TkDnD for drop operations involving file contents."""
        return self.tk.call('tkdnd::GetDropFileTempDirectory')
        
    tkinter.BaseWidget.get_dropfile_tempdir = get_dropfile_tempdir

    def set_dropfile_tempdir(self, tempdir: str):
        """Sets the temporary directory used by TkDnD."""
        self.tk.call('tkdnd::SetDropFileTempDirectory', tempdir)
        
    tkinter.BaseWidget.set_dropfile_tempdir = set_dropfile_tempdir

# ------------------------------------------------------------------------------
# Main TkinterDnD-enabled Tk class
# Applications should use this (or a subclass) as their root window to enable
# DnD functionality for all widgets within the application.
# ------------------------------------------------------------------------------
class Tk(tkinter.Tk, DnDWrapper):
    """Creates a new instance of a tkinter.Tk() window; all methods of the
    DnDWrapper class apply to this window and all its descendants."""
    def __init__(self, *args, **kw):
        tkinter.Tk.__init__(self, *args, **kw)
        # _require will now raise a more informative RuntimeError if it fails
        self.TkdndVersion = _require(self)
        except RuntimeError as e:
            # Handle tkdnd loading failure gracefully, e.g., log and disable DnD features.
            # For now, re-raise as it's a critical part of this module.
            # import logging # If logging is desired here
            # logging.error(f"Failed to initialize TkDnD: {e}")
            # self.TkdndVersion = None # Indicate DnD is not available
            raise # Re-raise the error if DnD is essential

