"""TkLineNumbers - A line number widget for tkinter Text widgets"""
from __future__ import annotations

from platform import system
from tkinter import Canvas, Event, Misc, Text, getboolean
from tkinter.font import Font
from typing import Callable, Optional

SYSTEM = system()


def scroll_fix(delta: int, num: bool = False) -> int:
    """Corrects scrolling numbers across platforms"""

    # The scroll events passed by macOS are different from Windows and Linux
    # so it must to be rectified to work properly when dealing with the events.
    # Originally found here: https://stackoverflow.com/a/17457843/17053202
    if delta in (4, 5) and num:  # X11 (maybe macOS with X11 too)
        return 1 if delta == 4 else -1

    if SYSTEM == "Darwin":  # macOS
        return -delta

    # Windows, needs to be divided by 120
    return -(delta // 120)


class TkLineNumError(Exception):
    ...


class TkLineNumbers(Canvas):
    """
    Creates a line number widget for a text widget. Options are the same as a tkinter Canvas widget and add the following:
        * -textwidget (Text): The text widget to attach the line numbers to. (Required) (Second argument after master)
        * -justify (str): The justification of the line numbers. Can be "left", "right", or "center". Default is "left".

    Methods to be used outside externally:
        * .redraw(): Redraws the widget (to be used when the text widget is modified)
    """

    def __init__(
        self: TkLineNumbers,
        master: Misc,
        textwidget: Text,
        justify: str = "left",
        # None means take colors from text widget (default).
        # Otherwise it is a function that takes no arguments and returns (fg, bg) tuple.
        colors: Callable[[], tuple[str, str]] | tuple[str, str] | None = None,
        *args,
        **kwargs,
    ) -> None:
        """Initializes the widget -- Internal use only"""

        # Initialize the Canvas widget
        Canvas.__init__(
            self,
            master,
            width=kwargs.pop("width", 40),
            highlightthickness=kwargs.pop("highlightthickness", 0),
            borderwidth=kwargs.pop("borderwidth", 2),
            relief=kwargs.pop("relief", "ridge"),
            *args,
            **kwargs,
        )

        # Set variables
        self.textwidget = textwidget
        self.master = master
        self.justify = justify
        self.colors = colors
        self.cancellable_after: Optional[str] = None
        self.click_pos: None = None
        self.x: int | None = None
        self.y: int | None = None

        # Set style and its binding
        self.set_colors()
        self.bind("<<ThemeChanged>>", self.set_colors, add=True)

        # Mouse scroll binding
        self.bind("<MouseWheel>", self.mouse_scroll, add=True)
        self.bind("<Button-4>", self.mouse_scroll, add=True)
        self.bind("<Button-5>", self.mouse_scroll, add=True)

        # Click bindings
        self.bind("<Button-1>", self.click_see, add=True)
        self.bind("<ButtonRelease-1>", self.unclick, add=True)
        self.bind("<Double-Button-1>", self.double_click, add=True)

        # Mouse drag bindings
        self.bind("<Button1-Motion>", self.in_widget_select_mouse_drag, add=True)
        self.bind("<Button1-Leave>", self.mouse_off_screen_scroll, add=True)
        self.bind("<Button1-Enter>", self.stop_mouse_off_screen_scroll, add=True)

        # Set the yscrollcommand of the text widget to redraw the widget
        textwidget["yscrollcommand"] = self.redraw

        # Redraw the widget
        self.redraw()

    def redraw(self, *_) -> None:
        """Redraws the widget"""

        # Resize the widget based on the number of lines in the textwidget and set colors
        self.resize()
        self.set_colors()

        # Delete all the old line numbers
        self.delete("all")

        # Get the first and last line numbers for the textwidget (all other lines are in between)
        first_line = int(self.textwidget.index("@0,0").split(".")[0])
        last_line = int(
            self.textwidget.index(f"@0,{self.textwidget.winfo_height()}").split(".")[0]
        )

        # Draw the line numbers looping through the lines
        for lineno in range(first_line, last_line + 1):
            # Check if line is elided
            tags: tuple[str] = self.textwidget.tag_names(f"{lineno}.0")
            elide_values: tuple[str] = (
                self.textwidget.tag_cget(tag, "elide") for tag in tags
            )
            # elide values can be empty
            line_elided: bool = any(getboolean(v or "false") for v in elide_values)

            # If the line is not visible, skip it
            dlineinfo: tuple[
                int, int, int, int, int
            ] | None = self.textwidget.dlineinfo(f"{lineno}.0")
            if dlineinfo is None or line_elided:
                continue

            # Create the line number
            self.create_text(
                0
                if self.justify == "left"
                else int(self["width"])
                if self.justify == "right"
                else int(self["width"]) / 2,
                dlineinfo[1],
                text=f" {lineno} " if self.justify != "center" else f"{lineno}",
                anchor={"left": "nw", "right": "ne", "center": "n"}[self.justify],
                font=self.textwidget.cget("font"),
                fill=self.foreground_color,
            )

    def mouse_scroll(self, event: Event) -> None:
        """Scrolls the text widget when the mouse wheel is scrolled -- Internal use only"""

        # Scroll the text widget and then redraw the widget
        self.textwidget.yview_scroll(
            int(
                scroll_fix(
                    event.delta if event.delta else event.num,
                    True if event.num != "??" else False,
                )
            ),
            "units",
        )
        self.redraw()

    def click_see(self, event: Event) -> None:
        """When clicking on a line number it scrolls to that line if not shifting -- Internal use only"""

        # If the shift key is down, redirect to self.shift_click()
        if event.state == 1:
            self.shift_click(event)
            return

        # Remove the selection tag from the text widget
        self.textwidget.tag_remove("sel", "1.0", "end")

        line: str = self.textwidget.index(f"@{event.x},{event.y}").split(".")[0]
        click_pos = f"{line}.0"

        # Set the insert position to the line number clicked
        self.textwidget.mark_set("insert", click_pos)

        # Scroll to the location of the insert position
        self.textwidget.see("insert")

        self.click_pos: str = click_pos
        self.redraw()

    def unclick(self, _: Event) -> None:
        """When the mouse button is released it removes the selection -- Internal use only"""

        self.click_pos = None

    def double_click(self, _: Event) -> None:
        """Selects the line when double clicked -- Internal use only"""

        # Remove the selection tag from the text widget and select the line
        self.textwidget.tag_remove("sel", "1.0", "end")
        self.textwidget.tag_add("sel", "insert", "insert + 1 line")
        self.redraw()

    def mouse_off_screen_scroll(self, event: Event) -> None:
        """Automatically scrolls the text widget when the mouse is near the top or bottom,
        similar to the in_widget_select_mouse_drag function -- Internal use only"""

        self.x = event.x
        self.y = event.y
        self.text_auto_scan(event)

    def text_auto_scan(self, event):
        if self.click_pos is None:
            return

        # Taken from the Text source: https://github.com/tcltk/tk/blob/main/library/text.tcl#L676
        # Scrolls the widget if the cursor is off of the screen
        if self.y >= self.winfo_height():
            self.textwidget.yview_scroll(1 + self.y - self.winfo_height(), "pixels")
        elif self.y < 0:
            self.textwidget.yview_scroll(-1 + self.y, "pixels")
        elif self.x >= self.winfo_width():
            self.textwidget.xview_scroll(2, "units")
        elif self.x < 0:
            self.textwidget.xview_scroll(-2, "units")
        else:
            return

        # Select the text
        self.select_text(self.x - self.winfo_width(), self.y)

        # After 50ms, call this function again
        self.cancellable_after = self.after(50, self.text_auto_scan, event)
        self.redraw()

    def stop_mouse_off_screen_scroll(self, _: Event) -> None:
        """Stops the auto scroll when the cursor re-enters the line numbers -- Internal use only"""

        # If the after has not been cancelled, cancel it
        if self.cancellable_after is not None:
            self.after_cancel(self.cancellable_after)
            self.cancellable_after = None

    def check_side_scroll(self, event: Event) -> None:
        """Detects if the mouse is off the screen to the sides \
(a case not covered in mouse_off_screen_scroll) -- Internal use only"""

        # Determine if the mouse is off the sides of the widget
        off_side = (
            event.x < self.winfo_x() or event.x > self.winfo_x() + self.winfo_width()
        )
        if not off_side:
            return

        # Determine if its above or below the widget
        if event.y >= self.winfo_height():
            self.textwidget.yview_scroll(1, "units")
        elif event.y < 0:
            self.textwidget.yview_scroll(-1, "units")
        else:
            return

        # Select the text
        self.select_text(event.x - self.winfo_width(), event.y)

        # Redraw the widget
        self.redraw()

    def in_widget_select_mouse_drag(self, event: Event) -> None:
        """When click in_widget_select_mouse_dragging it selects the text -- Internal use only"""

        # If the click position is None, return
        if self.click_pos is None:
            return

        self.x = event.x
        self.y = event.y

        # Select the text
        self.select_text(event.x - self.winfo_width(), event.y)
        self.redraw()

    def select_text(self, x, y) -> None:
        """Selects the text between the start and end positions -- Internal use only"""

        drag_pos = self.textwidget.index(f"@{x}, {y}")
        if self.textwidget.compare(drag_pos, ">", self.click_pos):
            start = self.click_pos
            end = drag_pos
        else:
            start = drag_pos
            end = self.click_pos

        self.textwidget.tag_remove("sel", "1.0", "end")
        self.textwidget.tag_add("sel", start, end)
        self.textwidget.mark_set("insert", drag_pos)

    def shift_click(self, event: Event) -> None:
        """When shift clicking it selects the text between the click and the cursor -- Internal use only"""

        # Add the selection tag to the text between the click and the cursor
        start_pos: str = self.textwidget.index("insert")
        end_pos: str = self.textwidget.index(f"@0,{event.y}")
        self.textwidget.tag_remove("sel", "1.0", "end")
        if self.textwidget.compare(start_pos, ">", end_pos):
            start_pos, end_pos = end_pos, start_pos
        self.textwidget.tag_add("sel", start_pos, end_pos)
        self.redraw()

    def resize(self) -> None:
        """Resizes the widget to fit the text widget -- Internal use only"""

        # Get amount of lines in the text widget
        end: str = self.textwidget.index("end").split(".")[0]

        # Set the width of the widget to the required width to display the biggest line number
        temp_font = Font(font=self.textwidget.cget("font"))
        measure_str = " 1234 " if int(end) <= 1000 else f" {end} "
        self.config(width=temp_font.measure(measure_str))

    def set_colors(self, _: Event | None = None) -> None:
        """Sets the colors of the widget according to self.colors - Internal use only"""

        # If the color provider is None, set the foreground color to the Text widget's foreground color
        if self.colors is None:
            self.foreground_color: str = self.textwidget["fg"]
            self["bg"]: str = self.textwidget["bg"]
        elif isinstance(self.colors, tuple):
            self.foreground_color: str = self.colors[0]
            self["bg"]: str = self.colors[1]
        else:
            returned_colors: tuple[str, str] = self.colors()
            self.foreground_color: str = returned_colors[0]
            self["bg"]: str = returned_colors[1]


if __name__ == "__main__":
    from tkinter import Tk
    from tkinter.ttk import Style

    root = Tk()

    style = Style()
    style.configure("TkLineNumbers", foreground="#2197db", background="#ffffff")

    text = Text(root)
    text.pack(side="right")

    for i in range(50):
        text.insert("end", f"Line {i+1}\n")

    def ttk_theme_colors() -> tuple[str, str]:
        fg: str = style.lookup("TkLineNumbers", "foreground", default="black")
        bg: str = style.lookup("TkLineNumbers", "background", default="white")
        return (fg, bg)

    linenums = TkLineNumbers(root, text, colors=ttk_theme_colors)
    linenums.pack(fill="y", side="left", expand=True)

    text.bind("<<Modified>>", lambda _: linenums.redraw())
    text.config(font=("Courier New bold", 15))

    root.mainloop()
