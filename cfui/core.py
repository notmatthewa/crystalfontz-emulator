from __future__ import annotations

import os
import time
from typing import Callable

from ._crc import get_crc
from .framebuffer import FrameBuffer, LCD_WIDTH, LCD_HEIGHT
from .widget import Widget
from .layout import Column

# CFA835 key codes (press events)
KEY_UP = 1
KEY_DOWN = 2
KEY_LEFT = 3
KEY_RIGHT = 4
KEY_ENTER = 5
KEY_EXIT = 6


class Page:
    """A single screen/view containing a widget tree."""

    def __init__(self, name: str, body: Widget | None = None,
                 on_enter: Callable[[], None] | None = None,
                 on_exit: Callable[[], None] | None = None):
        self.name = name
        self.body = body or Column()
        self.on_enter_page = on_enter
        self.on_exit_page = on_exit
        self._focus_index = 0
        self._focusable: list[Widget] = []

    def refresh_focus_list(self):
        self._focusable = self.body.get_focusable_widgets()
        # Clamp focus index
        if self._focusable:
            self._focus_index = max(0, min(self._focus_index, len(self._focusable) - 1))
            for w in self._focusable:
                w.focused = False
            self._focusable[self._focus_index].focused = True
        else:
            self._focus_index = 0

    def focus_direction(self, dx: int, dy: int):
        """Move focus spatially. dx/dy are -1, 0, or 1."""
        if not self._focusable or len(self._focusable) < 2:
            return
        current = self._focusable[self._focus_index]
        cx, cy = current.focus_center()

        best = None
        best_score = float("inf")

        for i, w in enumerate(self._focusable):
            if i == self._focus_index:
                continue
            wx, wy = w.focus_center()
            rx = wx - cx
            ry = wy - cy

            # Check that the widget is in the requested direction
            if dx > 0 and rx <= 0:
                continue
            if dx < 0 and rx >= 0:
                continue
            if dy > 0 and ry <= 0:
                continue
            if dy < 0 and ry >= 0:
                continue

            # Score: distance along the main axis + heavy penalty for off-axis
            # This strongly prefers widgets on the same row/column
            if dx != 0:
                score = abs(rx) + abs(ry) * 10
            else:
                score = abs(ry) + abs(rx) * 10

            if score < best_score:
                best_score = score
                best = i

        # If nothing found in the exact direction, wrap around (fallback to list order)
        if best is None:
            if dx > 0 or dy > 0:
                best = (self._focus_index + 1) % len(self._focusable)
            else:
                best = (self._focus_index - 1) % len(self._focusable)

        self._focusable[self._focus_index].focused = False
        self._focus_index = best
        self._focusable[self._focus_index].focused = True

    @property
    def focused_widget(self) -> Widget | None:
        if self._focusable and 0 <= self._focus_index < len(self._focusable):
            return self._focusable[self._focus_index]
        return None


class App:
    """Main application. Manages pages, input, and rendering to the CFA835."""

    def __init__(self, pty_path: str, exit_quits: bool = False):
        self.fd = os.open(pty_path, os.O_RDWR | os.O_NOCTTY)
        os.set_blocking(self.fd, False)
        self.fb = FrameBuffer()
        self._last_frame: bytes = b""
        self._pages: dict[str, Page] = {}
        self._page_stack: list[str] = []
        self._running = False
        self._dirty = True
        self._on_key: dict[int, Callable] = {}
        self.dark_mode = False
        self.exit_quits = exit_quits
        self._overlay: object | None = None

    def add_page(self, page: Page):
        self._pages[page.name] = page

    def navigate(self, page_name: str):
        """Push a new page onto the stack."""
        if self._page_stack:
            current = self._pages.get(self._page_stack[-1])
            if current and current.on_exit_page:
                current.on_exit_page()
        self._page_stack.append(page_name)
        page = self._pages[page_name]
        if page.on_enter_page:
            page.on_enter_page()
        self._dirty = True

    def go_back(self) -> bool:
        """Pop current page. Returns False if at root."""
        if len(self._page_stack) <= 1:
            return False
        current = self._pages.get(self._page_stack[-1])
        if current and current.on_exit_page:
            current.on_exit_page()
        self._page_stack.pop()
        page = self._pages.get(self._page_stack[-1])
        if page and page.on_enter_page:
            page.on_enter_page()
        self._dirty = True
        return True

    @property
    def current_page(self) -> Page | None:
        if self._page_stack:
            return self._pages.get(self._page_stack[-1])
        return None

    def invalidate(self):
        """Mark display as needing a redraw."""
        self._dirty = True

    def show_overlay(self, overlay):
        """Show a full-screen overlay. Blocks page rendering and input."""
        self._overlay = overlay
        self._dirty = True

    def hide_overlay(self):
        """Remove the overlay and return to normal page rendering."""
        self._overlay = None
        self._dirty = True

    def set_dark_mode(self, enabled: bool):
        """Toggle dark/light mode by inverting pixel data before sending."""
        self.dark_mode = enabled
        self._dirty = True

    def set_brightness(self, display: int, keypad: int | None = None):
        """Set display brightness (0-100). Optionally set keypad brightness too."""
        display = max(0, min(100, display))
        if keypad is None:
            self._send_packet(14, bytes([display]))
        else:
            keypad = max(0, min(100, keypad))
            self._send_packet(14, bytes([display, keypad]))
        self._drain()

    def get_brightness(self) -> tuple[int, int] | None:
        """Query display and keypad brightness. Returns (display, keypad) or None."""
        resp = self._send_and_read(14)
        if resp and len(resp) >= 2:
            return (resp[0], resp[1])
        return None

    def set_led(self, led: int, green: int = 0, red: int = 0):
        """Set LED color. led: 0-3, green/red: 0-100 brightness.

        LEDs are controlled via GPIO pins. Each LED has a green and red
        channel mapped to consecutive GPIO indices (11/12, 9/10, 7/8, 5/6).
        """
        green_gpio = 11 - led * 2
        red_gpio = 12 - led * 2
        self._send_packet(34, bytes([green_gpio, max(0, min(100, green))]))
        self._send_packet(34, bytes([red_gpio, max(0, min(100, red))]))
        self._drain()

    def on_key(self, key_code: int, handler: Callable):
        """Register a custom key handler."""
        self._on_key[key_code] = handler

    def run(self, start_page: str):
        """Main loop. Blocks until quit."""
        self.navigate(start_page)
        self._running = True
        # Enable key reporting
        self._send_packet(23, bytes([0x3F, 0x3F]))
        self._drain()

        try:
            while self._running:
                self._poll_keys()
                if self._dirty:
                    self._render()
                    self._dirty = False
                    self._poll_keys()
                time.sleep(0.02)
        except KeyboardInterrupt:
            pass
        finally:
            self._send_packet(6)  # clear display
            self._drain()
            os.close(self.fd)

    def quit(self):
        self._running = False

    def _render(self):
        if self._overlay:
            self._overlay.layout(0, 0, LCD_WIDTH, LCD_HEIGHT)
            self._overlay.draw(self.fb)
            self._flush_framebuffer()
            return
        page = self.current_page
        if not page:
            return
        self.fb.clear()
        page.body.layout(0, 0, LCD_WIDTH, LCD_HEIGHT)
        page.refresh_focus_list()
        page.body.draw(self.fb)
        self._flush_framebuffer()

    def _flush_framebuffer(self):
        """Send framebuffer to device. Skips if identical to last frame."""
        if self.dark_mode:
            frame = bytes(self.fb.buf)
        else:
            frame = bytes(255 - b for b in self.fb.buf)
        if frame == self._last_frame:
            return
        self._last_frame = frame
        self._send_packet(40, bytes([2, 0, 0, 0, LCD_WIDTH, LCD_HEIGHT]))
        time.sleep(0.005)
        self._write_raw(frame)
        self._drain()

    def _poll_keys(self):
        try:
            data = os.read(self.fd, 4096)
        except (OSError, BlockingIOError):
            return

        # Parse report packets from device
        i = 0
        while i < len(data):
            if i + 1 >= len(data):
                break
            ptype = data[i] & 0xC0
            cmd = data[i] & 0x3F
            dlen = data[i + 1]
            if i + 2 + dlen + 2 > len(data):
                break
            if ptype == 0x80 and cmd == 0x00 and dlen >= 1:
                key_code = data[i + 2]
                self._handle_key(key_code)
            i += 2 + dlen + 2

    def _handle_key(self, key_code: int):
        if key_code > KEY_EXIT:
            return
        if self._overlay:
            return

        if key_code in self._on_key:
            self._on_key[key_code]()
            self._dirty = True
            return

        page = self.current_page
        if not page:
            return

        w = page.focused_widget

        if w and w.active:
            {
                KEY_UP: w.on_up,
                KEY_DOWN: w.on_down,
                KEY_LEFT: w.on_left,
                KEY_RIGHT: w.on_right,
                KEY_ENTER: w.on_enter,
                KEY_EXIT: w.on_exit,
            }.get(key_code, lambda: None)()
        elif key_code == KEY_ENTER:
            if w:
                w.on_enter()
        elif key_code == KEY_EXIT:
            if not self.go_back() and self.exit_quits:
                self.quit()
        else:
            direction_map = {
                KEY_UP: (w.action_up if w else "move", w.on_up if w else None, (0, -1)),
                KEY_DOWN: (w.action_down if w else "move", w.on_down if w else None, (0, 1)),
                KEY_LEFT: (w.action_left if w else "move", w.on_left if w else None, (-1, 0)),
                KEY_RIGHT: (w.action_right if w else "move", w.on_right if w else None, (1, 0)),
            }
            entry = direction_map.get(key_code)
            if entry:
                action, handler, (dx, dy) = entry
                if action == "move":
                    page.focus_direction(dx, dy)
                elif action == "select" and handler:
                    handler()

        self._dirty = True

    def _send_packet(self, command: int, data: bytes = b""):
        payload = bytes([command, len(data)]) + data
        crc = get_crc(payload)
        os.write(self.fd, payload + crc.to_bytes(2, "little"))

    def _send_and_read(self, command: int, data: bytes = b"",
                       timeout: float = 0.2) -> bytes | None:
        """Send a command and return the response data, or None on timeout."""
        self._send_packet(command, data)
        buf = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = os.read(self.fd, 4096)
                buf.extend(chunk)
            except (OSError, BlockingIOError):
                pass
            # Try to parse a response packet
            if len(buf) >= 4:
                ptype = buf[0] & 0xC0
                cmd = buf[0] & 0x3F
                dlen = buf[1]
                if len(buf) >= 2 + dlen + 2:
                    if ptype == 0x40 and cmd == command:
                        return bytes(buf[2:2 + dlen])
                    # Skip non-matching packets (e.g. key reports)
                    buf = buf[2 + dlen + 2:]
            time.sleep(0.005)
        return None

    def _drain(self):
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline:
            try:
                os.read(self.fd, 65536)
            except OSError:
                pass
            time.sleep(0.005)

    def _write_raw(self, data: bytes):
        offset = 0
        while offset < len(data):
            try:
                n = os.write(self.fd, data[offset:offset + 4096])
                offset += n
            except BlockingIOError:
                time.sleep(0.001)
