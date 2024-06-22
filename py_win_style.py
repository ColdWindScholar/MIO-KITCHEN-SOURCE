"""
Py-Win-Styles
Author: Akash Bora
Version: 1.8
"""

from __future__ import annotations
from typing import Any, Union, Callable

try:
    from ctypes import (POINTER, Structure, byref, c_int, pointer, sizeof,
                        windll, c_buffer, WINFUNCTYPE, c_uint64)
    from ctypes.wintypes import DWORD, ULONG
    import platform

except ImportError:
    raise ImportError("pywinstyles import errror: No windows environment detected!")


class ACCENT_POLICY(Structure):
    _fields_ = [
        ("AccentState", DWORD),
        ("AccentFlags", DWORD),
        ("GradientColor", DWORD),
        ("AnimationId", DWORD),
    ]


class WINDOW_COMPOSITION_ATTRIBUTES(Structure):
    _fields_ = [
        ("Attribute", DWORD),
        ("Data", POINTER(ACCENT_POLICY)),
        ("SizeOfData", ULONG),
    ]


class MARGINS(Structure):
    _fields_ = [
        ("cxLeftWidth", c_int),
        ("cxRightWidth", c_int),
        ("cyTopHeight", c_int),
        ("cyBottomHeight", c_int),
    ]


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
        elif style == "optimised":
            ChangeDWMAccent(self.HWND, 30, 1)
        elif style == "dark":
            ChangeDWMAttrib(self.HWND, 19, c_int(1))
            ChangeDWMAttrib(self.HWND, 20, c_int(1))
        elif style == "light":
            ChangeDWMAttrib(self.HWND, 19, c_int(0))
            ChangeDWMAttrib(self.HWND, 20, c_int(0))
        elif style == "inverse":
            ChangeDWMAccent(self.HWND, 6, 1)
        elif style == "win7":
            ChangeDWMAccent(self.HWND, 11, 1)
        elif style == "aero":
            paint(window)
            ChangeDWMAccent(self.HWND, 30, 2)
            ChangeDWMAccent(self.HWND, 19, 3, color=0x000000)
        elif style == "acrylic":
            paint(window)
            ChangeDWMAttrib(self.HWND, 20, c_int(1))
            ChangeDWMAccent(self.HWND, 30, 3, color=0x292929)
            ExtendFrameIntoClientArea(self.HWND)
        elif style == "popup":
            ChangeDWMAccent(self.HWND, 4, 1)
        elif style == "native":
            ChangeDWMAccent(self.HWND, 30, 2)
            ChangeDWMAccent(self.HWND, 19, 2)
        elif style == "transparent":
            paint(window)
            ChangeDWMAccent(self.HWND, 30, 2)
            ChangeDWMAccent(self.HWND, 19, 4, color=0)
        elif style == "normal":
            ChangeDWMAccent(self.HWND, 6, 0)
            ChangeDWMAccent(self.HWND, 4, 0)
            ChangeDWMAccent(self.HWND, 11, 0)
            ChangeDWMAttrib(self.HWND, 19, c_int(0))
            ChangeDWMAttrib(self.HWND, 20, c_int(0))
            ChangeDWMAccent(self.HWND, 30, 0)
            ChangeDWMAccent(self.HWND, 19, 0)
            DisableFrameIntoClientArea(self.HWND)


def ChangeDWMAttrib(hWnd: int, attrib: int, color) -> None:
    windll.dwmapi.DwmSetWindowAttribute(hWnd, attrib, byref(color), sizeof(c_int))


def ChangeDWMAccent(hWnd: int, attrib: int, state: int, color: Union[str, None] = None) -> None:
    accentPolicy = ACCENT_POLICY()

    winCompAttrData = WINDOW_COMPOSITION_ATTRIBUTES()
    winCompAttrData.Attribute = attrib
    winCompAttrData.SizeOfData = sizeof(accentPolicy)
    winCompAttrData.Data = pointer(accentPolicy)

    accentPolicy.AccentState = state
    if color:
        accentPolicy.GradientColor = color

    windll.user32.SetWindowCompositionAttribute(hWnd, pointer(winCompAttrData))


def ExtendFrameIntoClientArea(HWND: int) -> None:
    margins = MARGINS(-1, -1, -1, -1)
    windll.dwmapi.DwmExtendFrameIntoClientArea(HWND, byref(margins))


def DisableFrameIntoClientArea(HWND: int) -> None:
    margins = MARGINS(0, 0, 0, 0)
    windll.dwmapi.DwmExtendFrameIntoClientArea(HWND, byref(margins))


def detect(window: Any):
    """detect the type of UI library and return HWND"""
    try:  # tkinter
        window.update()
        return windll.user32.GetParent(window.winfo_id())
    except:
        pass
    try:  # pyqt/pyside
        return window.winId().__int__()
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


def paint(window: Any) -> None:
    """paint black color in background for acrylic/aero to work"""
    try:  # tkinter
        window.config(bg="black")
        return
    except:
        pass
    try:  # pyqt/pyside
        window.setStyleSheet("background-color: transparent;")
        return
    except:
        pass
    try:  # wxpython
        window.SetBackgroundColour("black")
        return
    except:
        pass
    print("Don't know what the window type is, please paint it black")
