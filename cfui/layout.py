from __future__ import annotations
from typing import Callable

from .widget import Widget
from .framebuffer import FrameBuffer, CHAR_W, CHAR_H


class Column(Widget):
    """Vertical stack of widgets."""

    def __init__(self, children: list[Widget] | None = None, spacing: int = 1,
                 padding: int = 0):
        super().__init__()
        self.children = children or []
        self.spacing = spacing
        self.padding = padding
        for child in self.children:
            child.parent = self

    def add(self, child: Widget) -> Widget:
        child.parent = self
        self.children.append(child)
        return child

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        inner_w = max_w - 2 * self.padding
        inner_h = max_h - 2 * self.padding
        total_h = 0
        max_child_w = 0
        for i, child in enumerate(self.children):
            if not child.visible:
                continue
            cw, ch = child.measure(inner_w, inner_h - total_h)
            max_child_w = max(max_child_w, cw)
            total_h += ch
            if i < len(self.children) - 1:
                total_h += self.spacing
        return (max_child_w + 2 * self.padding, total_h + 2 * self.padding)

    def layout(self, x: int, y: int, w: int, h: int):
        super().layout(x, y, w, h)
        inner_x = x + self.padding
        inner_y = y + self.padding
        inner_w = w - 2 * self.padding
        inner_h = h - 2 * self.padding
        cy = inner_y
        for child in self.children:
            if not child.visible:
                continue
            cw, ch = child.measure(inner_w, inner_h - (cy - inner_y))
            child.layout(inner_x, cy, inner_w, ch)
            cy += ch + self.spacing

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        for child in self.children:
            if child.visible:
                child.draw(fb)

    def get_focusable_widgets(self) -> list[Widget]:
        result = []
        for child in self.children:
            if child.visible:
                result.extend(child.get_focusable_widgets())
        return result


class Row(Widget):
    """Horizontal layout of widgets."""

    def __init__(self, children: list[Widget] | None = None, spacing: int = 2,
                 padding: int = 0, align: str = "left"):
        super().__init__()
        self.children = children or []
        self.spacing = spacing
        self.padding = padding
        self.align = align  # "left", "center", "right", "spread"
        for child in self.children:
            child.parent = self

    def add(self, child: Widget) -> Widget:
        child.parent = self
        self.children.append(child)
        return child

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        inner_w = max_w - 2 * self.padding
        total_w = 0
        max_child_h = 0
        for i, child in enumerate(self.children):
            if not child.visible:
                continue
            cw, ch = child.measure(inner_w - total_w, max_h - 2 * self.padding)
            total_w += cw
            max_child_h = max(max_child_h, ch)
            if i < len(self.children) - 1:
                total_w += self.spacing
        return (total_w + 2 * self.padding, max_child_h + 2 * self.padding)

    def layout(self, x: int, y: int, w: int, h: int):
        super().layout(x, y, w, h)
        inner_x = x + self.padding
        inner_y = y + self.padding
        inner_w = w - 2 * self.padding
        inner_h = h - 2 * self.padding

        visible_children = [c for c in self.children if c.visible]
        if not visible_children:
            return

        # First pass: measure fixed (non-flex) children
        fixed_total = 0
        flex_count = 0
        sizes = {}
        for child in visible_children:
            if child.flex:
                flex_count += 1
            else:
                cw, ch = child.measure(inner_w, inner_h)
                sizes[id(child)] = (cw, ch)
                fixed_total += cw

        gap_total = self.spacing * max(0, len(visible_children) - 1)
        remaining = inner_w - fixed_total - gap_total

        # Second pass: measure flex children with remaining space
        if flex_count > 0:
            flex_w = max(0, remaining // flex_count)
            for child in visible_children:
                if child.flex:
                    cw, ch = child.measure(flex_w, inner_h)
                    sizes[id(child)] = (min(cw, flex_w), ch)

        # Compute total for alignment
        all_sizes = [sizes[id(c)] for c in visible_children]
        total_w = sum(s[0] for s in all_sizes) + gap_total

        if self.align == "center":
            cx = inner_x + (inner_w - total_w) // 2
        elif self.align == "right":
            cx = inner_x + inner_w - total_w
        elif self.align == "spread" and len(all_sizes) > 1:
            content_w = sum(s[0] for s in all_sizes)
            gap = (inner_w - content_w) // (len(all_sizes) - 1)
            cx = inner_x
            for i, child in enumerate(visible_children):
                cw, ch = sizes[id(child)]
                child.layout(cx, inner_y, cw, inner_h)
                cx += cw + (gap if i < len(visible_children) - 1 else 0)
            return
        else:
            cx = inner_x

        for child in visible_children:
            cw, ch = sizes[id(child)]
            child.layout(cx, inner_y, cw, inner_h)
            cx += cw + self.spacing

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        for child in self.children:
            if child.visible:
                child.draw(fb)

    def get_focusable_widgets(self) -> list[Widget]:
        result = []
        for child in self.children:
            if child.visible:
                result.extend(child.get_focusable_widgets())
        return result


class Tabs(Widget):
    """Tabbed container. Left/Right on the tab bar switches tabs."""

    def __init__(self, tabs: dict[str, Widget] | None = None, spacing: int = 1):
        super().__init__()
        self._tabs: list[tuple[str, Widget]] = []
        self.active_index = 0
        self.focusable = True
        self.tab_bar_height = CHAR_H + 2
        self.spacing = spacing
        if tabs:
            for name, content in tabs.items():
                self.add_tab(name, content)

    def add_tab(self, name: str, content: Widget):
        content.parent = self
        self._tabs.append((name, content))

    @property
    def tab_names(self) -> list[str]:
        return [name for name, _ in self._tabs]

    @property
    def active_content(self) -> Widget | None:
        if 0 <= self.active_index < len(self._tabs):
            return self._tabs[self.active_index][1]
        return None

    def measure(self, max_w: int, max_h: int) -> tuple[int, int]:
        return (max_w, max_h)

    def layout(self, x: int, y: int, w: int, h: int):
        super().layout(x, y, w, h)
        content_y = y + self.tab_bar_height + self.spacing
        content_h = h - self.tab_bar_height - self.spacing
        for _, content in self._tabs:
            content.layout(x, content_y, w, content_h)

    def draw(self, fb: FrameBuffer):
        if not self.visible:
            return
        # Draw tab headers
        tx = self.x
        for i, (name, _) in enumerate(self._tabs):
            label = f" {name} "
            tw = len(label) * CHAR_W
            if i == self.active_index:
                fb.fill_rect(tx, self.y, tw, self.tab_bar_height, 0xFF)
                fb.draw_text(tx, self.y + 1, label, 0x00)
            else:
                fb.draw_text(tx, self.y + 1, label, 0xFF)
            tx += tw + 2
        # Separator line
        fb.hline(self.x, self.y + self.tab_bar_height, self.width, 0x80)
        # Draw active content
        content = self.active_content
        if content:
            content.draw(fb)

    def on_left(self):
        if self.active_index > 0:
            self.active_index -= 1

    def on_right(self):
        if self.active_index < len(self._tabs) - 1:
            self.active_index += 1

    def get_focusable_widgets(self) -> list[Widget]:
        result = [self] if self.visible else []
        content = self.active_content
        if content and content.visible:
            result.extend(content.get_focusable_widgets())
        return result
