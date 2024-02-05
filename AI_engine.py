from difflib import SequenceMatcher
from tkinter import Toplevel, ttk
from utils import jzxs
from Document_Library import library


def suggest(string: str = '', language='cn', ok='ok'):
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
    window.title("AI ENGINE:<Based on bug feedback>")
    text = 'SORRY, No Suggestion For This Problem'
    if string:
        for i in library.keys():
            similarity_ = SequenceMatcher(None, i, catch_error).quick_ratio()
            if similarity_ >= 0.85:
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
    ttk.Label(window, text=text, font=(None, 15), wraplength=400).pack(padx=10, pady=10)
    ttk.Button(window, text=ok, command=window.destroy).pack(padx=10, pady=10)
    jzxs(window)
