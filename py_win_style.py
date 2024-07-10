"""
Py-Win-Styles
Author: Akash Bora
Version: 1.8
"""

from __future__ import annotations

from typing import Any

try:
    from ctypes import (POINTER, Structure, byref, c_int, pointer, sizeof,
                        windll)
    from ctypes.wintypes import DWORD, ULONG

except ImportError:
    raise ImportError("pywinstyles import errror: No windows environment detected!")


class apply_style:
    """different styles for windows"""

    def __init__(self, window, style: str) -> None:

        styles = ["dark", "mica", "aero", "transparent", "acrylic", "win7",
                  "inverse", "popup", "native", "optimised", "light", "normal"]

        if style not in styles:
            raise ValueError(
                f"Invalid style name! No such window style exists: {style} \nAvailable styles: {styles}"
            )

        self.HWND = detect(window)

        if style == "mica":
            ChangeDWMAttrib(self.HWND, 19, c_int(1))
            ChangeDWMAttrib(self.HWND, 1029, c_int(0x01))


def ChangeDWMAttrib(hWnd: int, attrib: int, color) -> None:
    windll.dwmapi.DwmSetWindowAttribute(hWnd, attrib, byref(color), sizeof(c_int))


def detect(window: Any):
    """detect the type of UI library and return HWND"""
    try:  # tkinter
        window.update()
        return windll.user32.GetParent(window.winfo_id())
    except:
        pass
    try:  # pyqt/pyside
        return int(window.winId())
    except:
        pass
    try:  # wxpython
        return window.GetHandle()
    except:
        pass
    if isinstance(window, int):
        return window  # other ui windows hwnd
    else:
        return windll.user32.GetActiveWindow()  # get active hwnd
