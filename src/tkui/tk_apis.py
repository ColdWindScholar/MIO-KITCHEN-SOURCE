from ctypes import windll, c_int, sizeof,byref
import os
if os.name == 'nt':
    def set_title_bar_color(window, dark_value: int = 20):
        """Adjusts Windows title bar theme color.

        Args:
            window: Tkinter root window object
            dark_value: Intensity level for dark mode (0-255)

        Uses Windows DWMWA API to force dark/light titlebar theming.
        """
        window.update()
        set_window_attribute = windll.dwmapi.DwmSetWindowAttribute
        get_parent = windll.user32.GetParent
        hwnd = get_parent(window.winfo_id())
        rendering_policy = dark_value
        value = c_int(2)
        set_window_attribute(hwnd, rendering_policy, byref(value), sizeof(value))
        window.update()
