# dnd actions
PRIVATE = 'private'
NONE = 'none'
ASK = 'ask'
COPY = 'copy'
MOVE = 'move'
LINK = 'link'
REFUSE_DROP = 'refuse_drop'

# dnd types
DND_TEXT = 'DND_Text'
DND_FILES = 'DND_Files'
DND_ALL = '*' # Represents all/any types
CF_UNICODETEXT = 'CF_UNICODETEXT' # Clipboard Format Unicode Text
CF_TEXT = 'CF_TEXT'               # Clipboard Format Text
CF_HDROP = 'CF_HDROP'             # Clipboard Format HDROP (File list on Windows)

# These seem to be specific for complex drag-drop scenarios involving file group descriptors,
# often used with OLE on Windows for virtual files or multiple streams.
FileGroupDescriptor = 'FileGroupDescriptor - FileContents' # Usually 'FileGroupDescriptorW' is preferred for Unicode
FileGroupDescriptorW = 'FileGroupDescriptorW - FileContents' # Unicode version

# --- Import from the TkinterDnD module in the same package ---
# This assumes TkinterDnD.py is in the same directory (src/tkui/)
# and 'src.tkui' is treated as a package.

try:
    # Attempt to import the Tk class directly from our sibling module TkinterDnD.py
    # This is the most common and recommended way if TkinterDnD.py defines the Tk class.
    from .TkinterDnD import Tk

    # If you also need to access other elements from TkinterDnD.py as if it were a module,
    # you could also do:
    # from . import TkinterDnD as TkinterDnD_Module
    # And then access, for example, TkinterDnD_Module.SomeOtherElement
    # However, for just the Tk class, the direct import above is cleaner.

except ImportError as e:
    # This block will execute if the import fails, which could indicate a packaging
    # issue with PyInstaller or a structural problem.
    import sys
    current_package_name = __name__.rsplit('.', 1)[0] if '.' in __name__ else '(unknown_package)'
    sys.stderr.write(
        f"ERROR in '{__name__}' (tkinterdnd2_build_in.py):\n"
        f"  Failed to import 'Tk' from '.TkinterDnD' (expected in package '{current_package_name}').\n"
        f"  This usually means 'TkinterDnD.py' is missing, not packaged correctly, or there's an issue with relative imports.\n"
        f"  Current sys.path includes:\n"
    )
    for p_item in sys.path:
        sys.stderr.write(f"    {p_item}\n")
    sys.stderr.write(f"  Original ImportError: {e}\n")
    # Re-raise the error to make it clear that a critical component is missing.
    # The application likely cannot function without the DnD-enabled Tk class.
    raise ImportError(f"Could not import DnD-enabled Tk class from .TkinterDnD in {current_package_name}: {e}") from e


