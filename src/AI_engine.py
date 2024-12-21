# Copyright (C) 2024 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
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
import os.path
from difflib import SequenceMatcher
from tkinter import Toplevel, ttk, BOTH
from .core.utils import move_center, prog_path, lang
from json import load
with open(os.path.join(prog_path, 'bin', 'help_document.json'), 'r', encoding='utf-8') as f:
    library = load(f)

def suggest(string: str = '', language='English', ok='ok'):
    catch_error = [i for i in string.split("\n") if 'error' in i]
    if not catch_error:
        catch_error = [i for i in string.split("\n") if 'failed' in i]
        if not catch_error:
            return
        else:
            catch_error = catch_error[0]
    else:
        catch_error = catch_error[0]
    if not catch_error:
        return
    similarity = 0
    window = Toplevel()
    window.resizable(False, False)
    window.title("AI ENGINE")
    text = f"No idea about:\n\t{string}\nPlease Report It To us."
    detail = 'Unknown'
    if string:
        for i in library.keys():
            if not language in library[i]:
                language = 'English'
            if 'detail' in library[i]:
                try:
                    detail = library[i]['detail'][language]
                except (ValueError, KeyError):
                    detail = 'Unknown'
            similarity_ = SequenceMatcher(None, i, catch_error).quick_ratio()
            if similarity_ >= 0.8:
                text = library[i][language]
                break
            else:
                if similarity_ > similarity:
                    similarity = similarity_
                    if similarity < 0.5:
                        break
                else:
                    text = library[i][language]
                    break
    f1 = ttk.LabelFrame(window, text=lang.detail)
    ttk.Label(f1, text=string, font=(None, 12), foreground="orange", wraplength=400).pack(padx=10, pady=5)
    ttk.Label(f1, text=detail, font=(None, 15),foreground="grey", wraplength=400).pack(padx=10, pady=10)
    f1.pack(padx=10, pady=10)
    f2 = ttk.LabelFrame(window, text=lang.solution)
    ttk.Label(f2, text=text, font=(None, 15),foreground="green", wraplength=400).pack(padx=10, pady=10)
    f2.pack(padx=10, pady=10)

    ttk.Button(window, text=ok, command=window.destroy, style="Accent.TButton").pack(padx=10, pady=10, fill=BOTH)
    move_center(window)
