from __future__ import annotations
from typing import Callable

from .widget import Widget
from .framebuffer import FrameBuffer, CHAR_W, CHAR_H


class Text(Widget):
    """Static text label."""

    def __init__(self, text: str = "", shade: int = 0xFF, align: str = "left"):
        super().__init__()
        self._text = text
        self.shade = shade
        self.align = align  # "left", "center", "right"

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str):
        self._text = value

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        return (min(len(self._text) * CHAR_W, max_w), CHAR_H)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        tw = len(self._text) * CHAR_W
        if self.align == "center":
            x = self.x + (self.width - tw) // 2
        elif self.align == "right":
            x = self.x + self.width - tw
        else:
            x = self.x
        fb.draw_text(max(x, self.x), self.y, self._text, self.shade)


class Button(Widget):
    """Focusable button with label and callback."""

    def __init__(self, label: str, on_press: Callable | None = None,
                 style: str = "bracket", align: str = "center"):
        super().__init__()
        self.label = label
        self.on_press = on_press
        self.focusable = True
        self.style = style  # "bracket" shows [Label], "plain" just highlights
        self.align = align  # "left", "center", "right"

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        if self.style == "bracket":
            w = (len(self.label) + 2) * CHAR_W  # [Label]
        else:
            w = len(self.label) * CHAR_W
        return (min(w, max_w), CHAR_H)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        if self.style == "bracket":
            display = f"[{self.label}]"
        else:
            display = self.label
        tw = len(display) * CHAR_W
        if self.align == "left":
            x = self.x
        elif self.align == "right":
            x = self.x + self.width - tw
        else:
            x = self.x + (self.width - tw) // 2 if tw < self.width else self.x
        fb.draw_text(x, self.y, display, 0xFF)
        if self.focused:
            fb.invert_rect(x - 1, self.y - 1, tw + 2, CHAR_H + 2)

    def on_enter(self):
        if self.on_press:
            self.on_press()


class HRule(Widget):
    """Horizontal divider line."""

    def __init__(self, shade: int = 0x80):
        super().__init__()
        self.shade = shade

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        return (max_w, 3)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        fb.hline(self.x, self.y + 1, self.width, self.shade)


class ProgressBar(Widget):
    """Horizontal progress bar (0.0 to 1.0)."""

    def __init__(self, value: float = 0.0, height: int = 6,
                 border_shade: int = 0xFF, fill_shade: int = 0xFF):
        super().__init__()
        self._value = max(0.0, min(1.0, value))
        self.bar_height = height
        self.border_shade = border_shade
        self.fill_shade = fill_shade
        self.flex = True

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = max(0.0, min(1.0, v))

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        return (max_w, self.bar_height)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        fb.rect(self.x, self.y, self.width, self.bar_height, self.border_shade)
        inner_w = self.width - 2
        filled = int(inner_w * self._value)
        if filled > 0:
            fb.fill_rect(self.x + 1, self.y + 1, filled, self.bar_height - 2,
                         self.fill_shade)


class Slider(Widget):
    """Focusable progress bar with optional inline label.

    Press Enter to activate, then Left/Right to adjust.
    When focused, the border blinks to indicate selection.
    """

    BLINK_PERIOD = 0.5  # seconds per blink phase

    def __init__(self, value: float = 0.0, step: float = 0.05, height: int = 6,
                 label: str = "", on_change: Callable | None = None,
                 border_shade: int = 0xFF, fill_shade: int = 0xFF):
        super().__init__()
        self._value = max(0.0, min(1.0, value))
        self.step = step
        self.bar_height = height
        self.label = label
        self.on_change = on_change
        self.border_shade = border_shade
        self.fill_shade = fill_shade
        self.focusable = True
        self.flex = True

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = max(0.0, min(1.0, v))

    @property
    def needs_blink(self) -> bool:
        return self.focused and not self.active

    def _label_width(self) -> int:
        if not self.label:
            return 0
        return len(self.label) * CHAR_W + CHAR_W  # label text + gap

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        h = max(self.bar_height, CHAR_H) if self.label else self.bar_height
        return (max_w, h)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return

        label_w = self._label_width()
        bar_x = self.x + label_w
        bar_w = self.width - label_w

        # Draw inline label
        if self.label:
            label_y = self.y + (self.bar_height - CHAR_H) // 2
            fb.draw_text(self.x, max(label_y, self.y), self.label, 0xFF)

        # Border shade: blink when focused, solid when active or idle
        if self.focused and not self.active:
            import time
            phase = int(time.monotonic() / self.BLINK_PERIOD) % 2
            border = self.border_shade if phase == 0 else self.border_shade // 2
        elif self.active:
            border = self.border_shade
        else:
            border = self.border_shade // 2

        # Draw bar
        fb.rect(bar_x, self.y, bar_w, self.bar_height, border)
        inner_w = bar_w - 2
        filled = int(inner_w * self._value)
        if filled > 0:
            fb.fill_rect(bar_x + 1, self.y + 1, filled, self.bar_height - 2,
                         self.fill_shade)

        # Draw handle marker when active
        if self.active:
            hx = bar_x + 1 + filled
            fb.vline(hx, self.y, self.bar_height, 0xFF)
            if hx + 1 < bar_x + bar_w:
                fb.vline(hx + 1, self.y, self.bar_height, 0xFF)

    def on_enter(self):
        self.active = not self.active

    def on_exit(self):
        self.active = False

    def _adjust(self, delta: float):
        old = self._value
        self._value = max(0.0, min(1.0, self._value + delta))
        if self._value != old and self.on_change:
            self.on_change(self._value)

    def on_left(self):
        self._adjust(-self.step)

    def on_right(self):
        self._adjust(self.step)


class Spacer(Widget):
    """Empty space with fixed dimensions."""

    def __init__(self, width: int = 0, height: int = 0):
        super().__init__()
        self._w = width
        self._h = height

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        return (min(self._w, max_w), min(self._h, max_h))


class Icon(Widget):
    """Small bitmap icon from raw pixel data."""

    def __init__(self, bitmap: list[list[int]], shade: int = 0xFF):
        super().__init__()
        self.bitmap = bitmap  # 2D list: bitmap[row][col] = 0 or 1
        self.shade = shade

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        h = len(self.bitmap)
        w = len(self.bitmap[0]) if h else 0
        return (min(w, max_w), min(h, max_h))

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        for ry, row in enumerate(self.bitmap):
            for rx, pixel in enumerate(row):
                if pixel:
                    fb.set_pixel(self.x + rx, self.y + ry, self.shade)
