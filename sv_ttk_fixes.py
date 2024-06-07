import tkinter.font
from tkinter import Label as orig_Label
from tkinter import ttk

_SV_TTK_FONT_NAMES = ['SunValleyCaptionFont', 'SunValleyBodyFont',
                      'SunValleyBodyStrongFont', 'SunValleyBodyLargeFont',
                      'SunValleySubtitleFont', 'SunValleyTitleFont',
                      'SunValleyTitleLargeFont', 'SunValleyDisplayFont']


def _tk_get_font(family: str = 'TkDefaultFont'):
    return tkinter.font.nametofont(family)


def _tk_get_font_family(font_=None) -> str:
    if font_ is None:
        font_ = _tk_get_font()

    return font_.config()['family']


def _label_init_wrapper(orig_init, *args, **kwargs):
    font_arr = kwargs.get('font', (None,))
    new_font_arr = (_tk_get_font_family(),) + font_arr[1:]
    kwargs['font'] = new_font_arr

    return orig_init(*args, **kwargs)


def _do_hook_label_init():
    orig_init = ttk.Label.__init__
    ttk.Label.__init__ = lambda *args, **kwargs: _label_init_wrapper(orig_init, *args, **kwargs)


def do_set_window_deffont(root):
    root.option_add("*Font", _tk_get_font())


def do_override_sv_ttk_fonts():
    for _sv_ttk_font_name in _SV_TTK_FONT_NAMES:
        _tk_get_font(_sv_ttk_font_name).configure(family=_tk_get_font_family())


class Label(orig_Label):
    def __init__(*args, **kwargs):
        return _label_init_wrapper(orig_Label.__init__, *args, **kwargs)


_do_hook_label_init()
