# dnd actions
# --- Drag and Drop Actions (Constants) ---
PRIVATE = 'private'
NONE = 'none'
ASK = 'ask'
COPY = 'copy'
MOVE = 'move'
LINK = 'link'
REFUSE_DROP = 'refuse_drop'

# --- Drag and Drop Types (Constants) ---
DND_TEXT = 'DND_Text'           # Represents text data
DND_FILES = 'DND_Files'         # Represents a list of file paths
DND_ALL = '*'                   # Represents all/any data types

# --- Clipboard Formats (Often used with TkDND or for platform interoperability) ---
CF_UNICODETEXT = 'CF_UNICODETEXT' # Clipboard Format for Unicode Text
CF_TEXT = 'CF_TEXT'               # Clipboard Format for ANSI Text
CF_HDROP = 'CF_HDROP'             # Clipboard Format for a list of files (primarily Windows)

# --- FileGroupDescriptor (Advanced Windows OLE Drag and Drop) ---
# Used for dragging virtual files or groups of files with detailed information.
# 'FileGroupDescriptorW' is the Unicode version and generally preferred.
FileGroupDescriptor = 'FileGroupDescriptor - FileContents'
FileGroupDescriptorW = 'FileGroupDescriptorW - FileContents'

# --- Import the main DnD-enabled Tk class from the sibling TkinterDnD.py module ---
# This uses a relative import, assuming TkinterDnD.py is in the same directory (src/tkui/).
try:
    # Attempt to import the 'Tk' class directly from the .TkinterDnD module
    # (which corresponds to TkinterDnD.py within the current package src.tkui).
    from .TkinterDnD import Tk

    # If you needed to access other elements from TkinterDnD.py as a module object,
    # you might do something like:
    # from . import TkinterDnD as TkinterDnD_Module
    # Then you could use TkinterDnD_Module.SomeOtherClass or TkinterDnD_Module.some_function.
    # However, for just importing the main Tk class, the direct import above is cleaner.

except ImportError as e:
    # This block executes if the relative import '.TkinterDnD' fails.
    # This is a critical failure, as the DnD-enabled Tk class is essential.
    import sys # Import sys for stderr and path access for diagnostics
    import os  # For path manipulation if needed for diagnostics

    # Determine the name of the current package for a more informative error message.
    # __name__ for this file should be 'src.tkui.tkinterdnd2_build_in'.
    # The package part would be 'src.tkui'.
    current_module_name = __name__
    current_package_path = __file__ # Path to this tkinterdnd2_build_in.py file

    # Construct an informative error message
    error_message_lines = [
        f"CRITICAL ERROR in '{current_module_name}' (tkinterdnd2_build_in.py):",
        f"  Failed to import 'Tk' from relative module '.TkinterDnD'.",
        f"  This usually means 'TkinterDnD.py' is missing from the expected location",
        f"  (should be in the same directory as '{os.path.basename(current_package_path)}'),",
        f"  or it was not correctly packaged by PyInstaller, or there's an issue",
        f"  with Python's ability to resolve relative imports in this context.",
        f"  Expected package context for '.': '{current_module_name.rsplit('.', 1)[0] if '.' in current_module_name else '(root level, which is wrong for relative import)'}'",
        f"  Current sys.path includes:"
    ]
    for p_item in sys.path:
        error_message_lines.append(f"    - {p_item}")
    error_message_lines.append(f"  Original ImportError: {e}")

    # Attempt to write to sys.stderr if available, otherwise use sys.__stderr__ or print.
    effective_stderr = getattr(sys, 'stderr', None)
    if not effective_stderr: # If sys.stderr was redirected to None
        effective_stderr = getattr(sys, '__stderr__', None) # Try original stderr

    if effective_stderr and hasattr(effective_stderr, 'write'):
        for line in error_message_lines:
            effective_stderr.write(line + "\n")
        effective_stderr.flush()
    else: # Fallback to print if all stderr options fail
        for line in error_message_lines:
            print(line)
    
    # Re-raise the original ImportError to halt execution, as this is a critical failure.
    # Adding context to the re-raised error might be useful in some Python versions.
    raise ImportError(
        f"Could not import DnD-enabled Tk class from '.TkinterDnD' within '{current_module_name.rsplit('.',1)[0]}'. "
        f"Original error: {e}"
    ) from e


