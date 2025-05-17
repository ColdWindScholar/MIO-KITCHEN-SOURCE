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
import os # os is used for os.path and os.name
# Assuming TkinterDnD.py is in 'tkui' and utils.py is in 'core' which is one level up from 'tkui'
from ..core import utils 
# from ..core.utils import prog_path # This specific import is now covered by 'utils.prog_path'

TkdndVersion = None # Stores the loaded tkdnd library version

def _require(tkroot: tkinter.Tk): # Added type hint for tkroot
    """
    Loads the platform-specific tkdnd library.

    This internal function determines the correct tkdnd binary to load based on
    the operating system and architecture, then tells the Tcl interpreter
    where to find it and requires the 'tkdnd' package.

    Args:
        tkroot: The root Tkinter window instance.

    Returns:
        str: The version string of the loaded tkdnd package.

    Raises:
        RuntimeError: If the platform/architecture is unsupported or
                      if the tkdnd library cannot be loaded by Tcl.
    """
    global TkdndVersion
    if TkdndVersion is not None: # Avoid reloading if already loaded
        return TkdndVersion

    try:
        # os.path is implicitly available via 'import os'
        import platform # Standard library for platform information
        
        # Determine the machine architecture string locally without modifying global platform.machine
        current_machine_arch = platform.machine()
        system_name = platform.system()

        # Adjust architecture string for specific Windows cases (32-bit Python on 64-bit OS)
        if system_name == "Windows": # Changed from os.name == "nt" for consistency with platform.system()
            if platform.architecture()[0] == '32bit' and current_machine_arch == 'AMD64':
                current_machine_arch = 'x86' 
        
        # Determine the tkdnd platform representation string
        if system_name == "Darwin": # macOS
            if current_machine_arch == "arm64":
                tkdnd_platform_rep = "osx-arm64"
            elif current_machine_arch == "x86_64":
                tkdnd_platform_rep = "osx-x64"
            else:
                raise RuntimeError(f'Unsupported macOS architecture: {current_machine_arch}')
        elif system_name == "Linux":
            if current_machine_arch == "aarch64": # ARM64 on Linux
                tkdnd_platform_rep = "linux-arm64"
            elif current_machine_arch == "x86_64":
                tkdnd_platform_rep = "linux-x64"
            else:
                raise RuntimeError(f'Unsupported Linux architecture: {current_machine_arch}')
        elif system_name == "Windows":
            if current_machine_arch == "ARM64":
                tkdnd_platform_rep = "win-arm64"
            elif current_machine_arch == "AMD64": # Standard 64-bit Windows
                tkdnd_platform_rep = "win-x64"
            elif current_machine_arch == "x86": # 32-bit Windows
                tkdnd_platform_rep = "win-x86"
            else:
                raise RuntimeError(f'Unsupported Windows architecture: {current_machine_arch}')
        else:
            raise RuntimeError(f'Platform not supported by this tkdnd setup: {system_name}')

        # Construct the path to the tkdnd library directory
        # CRITICAL: utils.prog_path must be correctly set for both dev and bundled environments
        tkdnd_lib_dir = os.path.join(utils.prog_path, 'bin', 'tkdnd', tkdnd_platform_rep)
        
        # Add the library path to Tcl's auto_path and require the package
        tkroot.tk.call('lappend', 'auto_path', tkdnd_lib_dir)
        TkdndVersion = tkroot.tk.call('package', 'require', 'tkdnd')

    except tkinter.TclError as e_tcl: 
        # This occurs if Tcl fails to load the package (e.g., file not found, wrong architecture)
        # import logging # Optional: for more detailed logging if available
        # logging.exception("Failed to load tkdnd Tcl package")
        raise RuntimeError(f'Unable to load tkdnd Tcl package from {tkdnd_lib_dir}. TclError: {e_tcl}')
    except Exception as e_general:
        # Catch other potential errors during platform detection or path construction
        # import logging
        # logging.exception("Unexpected error during tkdnd library requirement")
        raise RuntimeError(f'Unexpected error requiring tkdnd: {e_general}')
        
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
class Tk(tkinter.Tk, DnDWrapper): # Inherits from standard tkinter.Tk and our DnDWrapper
    """
    A Tkinter.Tk root window subclass that initializes and enables TkDnD
    functionality for itself and all its descendant widgets.
    """
    def __init__(self, screenName: str = None, baseName: str = None, className: str = 'Tk', useTk: bool = True, sync: bool = False, use: str = None):
        """
        Initializes the Tk root window and loads the TkDnD extension.
        Arguments are the same as for tkinter.Tk.
        """
        super().__init__(screenName, baseName, className, useTk, sync, use)
        try:
            self.TkdndVersion = _require(self) # Load and initialize TkDnD
        except RuntimeError as e:
            # Handle tkdnd loading failure gracefully, e.g., log and disable DnD features.
            # For now, re-raise as it's a critical part of this module.
            # import logging # If logging is desired here
            # logging.error(f"Failed to initialize TkDnD: {e}")
            # self.TkdndVersion = None # Indicate DnD is not available
            raise # Re-raise the error if DnD is essential
