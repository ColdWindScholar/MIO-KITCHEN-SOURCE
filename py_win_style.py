"""
Py-Win-Styles
Author: Akash Bora
Version: 1.8
"""

from __future__ import annotations

try:
    from ctypes import byref, c_int, sizeof, windll

except ImportError:
    raise ImportError("pywinstyles import errror: No windows environment detected!")


class apply_style:
    """different styles for windows"""

    def __init__(self, window) -> None:
        window.update()
        self.HWND = windll.user32.GetParent(window.winfo_id())

        ChangeDWMAttrib(self.HWND, 19, c_int(1))
        ChangeDWMAttrib(self.HWND, 1029, c_int(0x01))


def ChangeDWMAttrib(hWnd: int, attrib: int, color) -> None:
    windll.dwmapi.DwmSetWindowAttribute(hWnd, attrib, byref(color), sizeof(c_int))
