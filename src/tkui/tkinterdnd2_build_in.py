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
    from src.tkui.TkinterDnD import Tk
except ImportError as e_abs:
    # Если абсолютный импорт от src не удался, пробуем относительный как фоллбэк
    # (хотя он у вас уже вызывал проблемы, но стоит оставить как вторую попытку)
    try:
        from .TkinterDnD import Tk
    except ImportError as e_rel:
        import sys
        import os
        current_module_name = __name__
        current_package_path = __file__
        error_message_lines = [
            f"CRITICAL ERROR in '{current_module_name}' (tkinterdnd2_build_in.py):",
            f"  Failed to import 'Tk' using both absolute ('src.tkui.TkinterDnD') and relative ('.TkinterDnD') paths.",
            f"  Absolute import error: {e_abs}",
            f"  Relative import error: {e_rel}",
            f"  This usually means TkinterDnD.py is missing, not packaged correctly, or sys.path is misconfigured by PyInstaller.",
            f"  Expected package context for '.': '{current_module_name.rsplit('.', 1)[0] if '.' in current_module_name else '(root level)'}'",
            f"  Current sys.path includes:"
        ]
        for p_item in sys.path:
            error_message_lines.append(f"    - {p_item}")
        
        effective_stderr = getattr(sys, 'stderr', None) or getattr(sys, '__stderr__', None)
        if effective_stderr and hasattr(effective_stderr, 'write'):
            for line in error_message_lines: effective_stderr.write(line + "\n")
            effective_stderr.flush()
        else:
            for line in error_message_lines: print(line)
        raise ImportError(f"Could not import DnD-enabled Tk class. Abs: {e_abs}, Rel: {e_rel}") from e_rel


