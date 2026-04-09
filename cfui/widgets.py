from __future__ import annotations
from typing import Callable

from .widget import Widget
from .framebuffer import FrameBuffer, CHAR_W, CHAR_H, LCD_WIDTH, LCD_HEIGHT


class Text(Widget):
    """Static text label."""

    def __init__(self, text: str = "", shade: int = 0xFF, align: str = "left"):
        super().__init__()
        self._text = text
        self.shade = shade
        self.align = align

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
    """Focusable button with label and callback.

    Styles:
        "bracket" - renders as [Label], inverts on focus
        "plain" - renders as Label, inverts on focus
        "bordered" - rounded rectangle border, bright on focus
    """

    def __init__(self, label: str, on_press: Callable | None = None,
                 style: str = "bracket", align: str = "center"):
        super().__init__()
        self.label = label
        self.on_press = on_press
        self.focusable = True
        self.style = style
        self.align = align

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        if self.style == "bracket":
            w = (len(self.label) + 2) * CHAR_W
        elif self.style == "bordered":
            w = len(self.label) * CHAR_W + 6
        else:
            w = len(self.label) * CHAR_W
        h = CHAR_H + 4 if self.style == "bordered" else CHAR_H
        return (min(w, max_w), h)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return

        if self.style == "bordered":
            self._draw_bordered(fb)
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

    def _draw_bordered(self, fb: FrameBuffer):
        tw = len(self.label) * CHAR_W
        btn_w = tw + 6
        btn_h = CHAR_H + 4
        if self.align == "left":
            bx = self.x
        elif self.align == "right":
            bx = self.x + self.width - btn_w
        else:
            bx = self.x + (self.width - btn_w) // 2 if btn_w < self.width else self.x
        by = self.y
        if self.focused:
            fb.rounded_rect(bx, by, btn_w, btn_h, 0xFF, fill=0xFF)
            fb.draw_text(bx + 3, by + 2, self.label, 0x00)
        else:
            fb.rounded_rect(bx, by, btn_w, btn_h, 0xFF)
            fb.draw_text(bx + 3, by + 2, self.label, 0xFF)

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

    Press Enter to activate, then Left/Right to adjust. Press Exit to deactivate.
    Focused/hovered: dim border. Active/editing: dashed border.
    """

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

    def _label_width(self) -> int:
        if not self.label:
            return 0
        return len(self.label) * CHAR_W + CHAR_W

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        h = max(self.bar_height, CHAR_H) if self.label else self.bar_height
        return (max_w, h)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return

        label_w = self._label_width()
        bar_x = self.x + label_w
        bar_w = self.width - label_w

        if self.label:
            label_y = self.y + (self.bar_height - CHAR_H) // 2
            ly = max(label_y, self.y)
            if self.focused and not self.active:
                fb.fill_rect(self.x, ly, label_w - CHAR_W, CHAR_H, 0xFF)
                fb.draw_text(self.x, ly, self.label, 0x00)
            else:
                fb.draw_text(self.x, ly, self.label, 0xFF)

        if self.active:
            fb.dashed_rect(bar_x, self.y, bar_w, self.bar_height,
                           self.border_shade)
        elif self.focused:
            fb.rect(bar_x, self.y, bar_w, self.bar_height,
                    self.border_shade)
        else:
            fb.rect(bar_x, self.y, bar_w, self.bar_height,
                    self.border_shade)

        inner_w = bar_w - 2
        filled = int(inner_w * self._value)
        if filled > 0:
            fb.fill_rect(bar_x + 1, self.y + 1, filled, self.bar_height - 2,
                         self.fill_shade)

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
        if self.active:
            self._adjust(-self.step)

    def on_right(self):
        if self.active:
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
    """Small bitmap icon from a 2D pixel array.

    bitmap is a list of rows, each row a list of 0/1 values.
    """

    def __init__(self, bitmap: list[list[int]], shade: int = 0xFF):
        super().__init__()
        self.bitmap = bitmap
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


class Image(Widget):
    """Grayscale image widget from raw pixel data.

    Data is a flat bytes/bytearray of shade values (0-255),
    row-major order, sized img_w * img_h.
    """

    def __init__(self, data: bytes | bytearray, img_w: int, img_h: int):
        super().__init__()
        self._data = data
        self.img_w = img_w
        self.img_h = img_h

    @property
    def data(self) -> bytes | bytearray:
        return self._data

    @data.setter
    def data(self, value: bytes | bytearray):
        self._data = value

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        return (min(self.img_w, max_w), min(self.img_h, max_h))

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        for iy in range(min(self.img_h, self.height)):
            for ix in range(min(self.img_w, self.width)):
                shade = self._data[iy * self.img_w + ix]
                if shade > 0:
                    fb.set_pixel(self.x + ix, self.y + iy, shade)


class Overlay(Widget):
    """Full-screen overlay that draws above everything.

    Used for loading screens, alerts, splash screens, etc.
    While shown, the App skips page rendering and key handling entirely.

    Usage:
        loading = Overlay(text="Loading...")
        app.show_overlay(loading)
        # ... do work ...
        app.hide_overlay()

    Or with a custom body widget for full layout control:
        overlay = Overlay(body=Column(children=[
            Text("Please wait", align="center"),
            ProgressBar(value=0.5),
        ]))
    """

    def __init__(self, text: str = "", body: Widget | None = None,
                 shade: int = 0xFF):
        super().__init__()
        self._text = text
        self._body = body
        self.shade = shade

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str):
        self._text = value

    @property
    def body(self) -> Widget | None:
        return self._body

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        return (LCD_WIDTH, LCD_HEIGHT)

    def layout(self, x: int, y: int, w: int, h: int):
        super().layout(0, 0, LCD_WIDTH, LCD_HEIGHT)
        if self._body:
            self._body.layout(0, 0, LCD_WIDTH, LCD_HEIGHT)

    def draw(self, fb: FrameBuffer):
        fb.clear()
        if self._body:
            self._body.draw(fb)
        elif self._text:
            tw = len(self._text) * CHAR_W
            tx = (LCD_WIDTH - tw) // 2
            ty = (LCD_HEIGHT - CHAR_H) // 2
            fb.draw_text(tx, ty, self._text, self.shade)
