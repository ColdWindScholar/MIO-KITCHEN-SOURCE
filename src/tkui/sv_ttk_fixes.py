# Workaround ugly font fallbacks on Windows.
# Only for Windows!!
#
# Copyright (C) 2022-2026 The MIO-KITCHEN-SOURCE Project
#
# Licensed under theGNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import tkinter.font
from tkinter import Label as orig_Label
from tkinter import ttk

_SV_TTK_FONT_NAMES = ['SunValleyCaptionFont', 'SunValleyBodyFont',
                      'SunValleyBodyStrongFont', 'SunValleyBodyLargeFont',
                      'SunValleySubtitleFont', 'SunValleyTitleFont',
                      'SunValleyTitleLargeFont', 'SunValleyDisplayFont']

_tk_get_font = lambda family = 'TkDefaultFont':tkinter.font.nametofont(family)

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

do_set_window_deffont = lambda root:root.option_add("*Font", _tk_get_font())

def do_override_sv_ttk_fonts():
    for _sv_ttk_font_name in _SV_TTK_FONT_NAMES:
        _tk_get_font(_sv_ttk_font_name).configure(family=_tk_get_font_family())


class Label(orig_Label):
    def __init__(*args, **kwargs):
        return _label_init_wrapper(orig_Label.__init__, *args, **kwargs)


_do_hook_label_init()
