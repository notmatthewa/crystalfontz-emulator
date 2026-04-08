from __future__ import annotations
from .framebuffer import FrameBuffer


class Widget:
    """Base class for all UI widgets."""

    def __init__(self):
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.focusable = False
        self.focused = False
        self.active = False  # When True, widget captures all directional input
        self.parent: Widget | None = None
        self.visible = True
        self.flex = False  # If True, expands to fill remaining space in Row

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        """Return (width, height) this widget wants. Override in subclasses."""
        return (0, 0)

    def layout(self, x: int, y: int, w: int, h: int):
        """Position this widget at (x, y) with given bounds."""
        self.x = x
        self.y = y
        self.width = w
        self.height = h

    def draw(self, fb: FrameBuffer):
        """Render this widget to the framebuffer. Override in subclasses."""
        pass

    def get_focusable_widgets(self) -> list[Widget]:
        """Return list of focusable widgets in order."""
        if self.focusable and self.visible:
            return [self]
        return []

    def on_enter(self):
        """Called when Enter is pressed on this focused widget."""
        pass

    def on_left(self):
        """Called when Left is pressed on this focused widget."""
        pass

    def on_right(self):
        """Called when Right is pressed on this focused widget."""
        pass

    def on_up(self):
        """Called when Up is pressed on this active widget."""
        pass

    def on_down(self):
        """Called when Down is pressed on this active widget."""
        pass

    def on_exit(self):
        """Called when Exit is pressed on this active widget."""
        self.active = False
