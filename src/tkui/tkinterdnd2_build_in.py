# File: src/tkui/tkinterdnd2_build_in.py
# This file acts as a wrapper or an easy import point for TkinterDnD functionality.

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
FileGroupDescriptor = 'FileGroupDescriptor - FileContents'
FileGroupDescriptorW = 'FileGroupDescriptorW - FileContents' # Unicode version

# --- Import the main DnD-enabled Tk class from the sibling TkinterDnD.py module ---
# This uses a relative import, assuming TkinterDnD.py is in the same directory (src/tkui/)
# and 'src.tkui' is treated as a package.

# Store the original ImportError exception if it occurs, for better diagnostics
_tkinterdnd_import_error = None

try:
    # Attempt to import the 'Tk' class directly from the .TkinterDnD module
    # (which corresponds to TkinterDnD.py within the current package src.tkui).
    from .TkinterDnD import Tk

except ImportError as e:
    _tkinterdnd_import_error = e # Store the exception
    # Fallback or error handling will be done after this try-except block
    # to allow for potentially more informative error messages if Tk is accessed later.
    # For now, we define Tk as None so that the file can be imported,
    # but any attempt to use Tk() will fail if the import truly failed.
    Tk = None
except Exception as e_unexpected: # Catch other unexpected errors during import
    _tkinterdnd_import_error = e_unexpected
    Tk = None


# Check if Tk was successfully imported. If not, raise a comprehensive error.
if Tk is None:
    import sys
    import os
    
    current_module_name = __name__
    current_package_path = __file__ if hasattr(sys, 'frozen') or '__file__' in globals() else 'Unknown (likely interactive)'

    error_message_lines = [
        f"CRITICAL ERROR in '{current_module_name}' (tkinterdnd2_build_in.py):",
        f"  Failed to import the DnD-enabled 'Tk' class from relative module '.TkinterDnD'.",
        f"  This is essential for Drag and Drop functionality.",
        f"  Possible reasons:",
        f"    1. 'TkinterDnD.py' is missing from the expected location:",
        f"       (should be in the same directory as '{os.path.basename(current_package_path)}').",
        f"    2. 'TkinterDnD.py' was not correctly packaged by PyInstaller.",
        f"    3. There's an issue with Python's ability to resolve relative imports for package '{current_module_name.rsplit('.', 1)[0] if '.' in current_module_name else '(root level)'}'.",
        f"    4. 'TkinterDnD.py' itself has an import error or syntax error preventing its load.",
        f"  Original error stored: {_tkinterdnd_import_error}",
        f"  Current sys.path includes:"
    ]
    for p_item in sys.path:
        error_message_lines.append(f"    - {p_item}")
    
    # Try to get a more specific traceback from the stored error
    if _tkinterdnd_import_error and hasattr(_tkinterdnd_import_error, '__traceback__'):
        import traceback
        error_message_lines.append("  Traceback of original import error:")
        tb_lines = traceback.format_exception(type(_tkinterdnd_import_error), _tkinterdnd_import_error, _tkinterdnd_import_error.__traceback__)
        error_message_lines.extend([f"    {line.strip()}" for line in tb_lines])

    # Attempt to write to sys.stderr if available, otherwise use sys.__stderr__ or print.
    effective_stderr = getattr(sys, 'stderr', None)
    if not effective_stderr:
        effective_stderr = getattr(sys, '__stderr__', None)

    final_error_message = "\n".join(error_message_lines)
    if effective_stderr and hasattr(effective_stderr, 'write'):
        effective_stderr.write(final_error_message + "\n")
        effective_stderr.flush()
    else:
        print(final_error_message)
    
    # Re-raise a new ImportError to halt execution, making it clear this module failed.
    # Include the original error as the cause if possible (Python 3).
    if _tkinterdnd_import_error:
        raise ImportError(
            f"Critical failure in '{current_module_name}': Could not initialize TkinterDnD support. See console/log for details."
        ) from _tkinterdnd_import_error
    else:
        raise ImportError(
             f"Critical failure in '{current_module_name}': Could not initialize TkinterDnD support (Tk class not loaded)."
        )

# Now, Tk should be the DnD-enabled class from .TkinterDnD
# The constants (PRIVATE, DND_FILES, etc.) are defined directly in this file.
