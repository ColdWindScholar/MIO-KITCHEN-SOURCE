from configparser import ConfigParser
import os
import tkinter.font
from tkinter import Label as orig_Label
from tkinter import ttk

_SETTING_FILE = 'bin/setting.ini'

_DEFFONT = 'Yu Gothic UI'

_TK_DEFFONT = 'TkDefaultFont'

_OVERRIDE_FONT_NAMES = [_TK_DEFFONT] + ['SunValleyCaptionFont', 'SunValleyBodyFont',
                                        'SunValleyBodyStrongFont', 'SunValleyBodyLargeFont',
                                        'SunValleySubtitleFont', 'SunValleyTitleFont',
                                        'SunValleyTitleLargeFont', 'SunValleyDisplayFont']


def _FIX_TKINTER() -> bool:
    if os.name != 'nt':
        return False

    cp = ConfigParser()
    try:
        cp.read(_SETTING_FILE)
        return cp.get('setting', 'language') == 'Japanese'
    except:
        pass

    return False


def _label_init_wrapper(orig_init, *args, **kwargs):
    if _FIX_TKINTER():
        font_arr = kwargs.get('font', (None,))
        new_font_arr = (_DEFFONT,) + font_arr[1:]
        kwargs['font'] = new_font_arr

    return orig_init(*args, **kwargs)


def _do_hook_label_init():
    orig_init = ttk.Label.__init__
    ttk.Label.__init__ = lambda *args, **kwargs: _label_init_wrapper(orig_init, *args, **kwargs)


def do_set_window_deffont(root):
    if not _FIX_TKINTER():
        return

    deffont = tkinter.font.nametofont(_TK_DEFFONT)
    root.option_add("*Font", deffont)


def do_override_fonts():
    if not _FIX_TKINTER():
        return

    for _override_font_name in _OVERRIDE_FONT_NAMES:
        tkinter.font.nametofont(_override_font_name).configure(family=_DEFFONT)


class Label(orig_Label):
    def __init__(*args, **kwargs):
        return _label_init_wrapper(orig_Label.__init__, *args, **kwargs)


_do_hook_label_init()
