from dataclasses import dataclass, field
from typing import ClassVar

from .protocol import Packet, make_response, make_error, make_report

LCD_WIDTH = 244
LCD_HEIGHT = 68
TEXT_COLS = 20
TEXT_ROWS = 4

KEY_UP_PRESS = 1
KEY_DOWN_PRESS = 2
KEY_LEFT_PRESS = 3
KEY_RIGHT_PRESS = 4
KEY_ENTER_PRESS = 5
KEY_EXIT_PRESS = 6
KEY_UP_RELEASE = 7
KEY_DOWN_RELEASE = 8
KEY_LEFT_RELEASE = 9
KEY_RIGHT_RELEASE = 10
KEY_ENTER_RELEASE = 11
KEY_EXIT_RELEASE = 12

ERR_UNKNOWN_COMMAND = 2
ERR_INVALID_LENGTH = 3

INTERFACE_USB = 1


@dataclass
class LED:
    green: int = 0
    red: int = 0


@dataclass
class CFA835Device:
    framebuffer: bytearray = field(default_factory=lambda: bytearray(LCD_WIDTH * LCD_HEIGHT))
    text_buffer: list[list[int]] = field(default_factory=lambda: [[0x20] * TEXT_COLS for _ in range(TEXT_ROWS)])
    leds: list[LED] = field(default_factory=lambda: [LED() for _ in range(4)])
    cursor_col: int = 0
    cursor_row: int = 0
    cursor_style: int = 0
    contrast: int = 127
    display_brightness: int = 100
    keypad_brightness: int = 100
    key_press_mask: int = 0x3F
    key_release_mask: int = 0x3F
    user_flash: bytearray = field(default_factory=lambda: bytearray(124))
    keys_pressed: int = 0
    keys_pressed_since_poll: int = 0
    keys_released_since_poll: int = 0
    pending_reports: list[Packet] = field(default_factory=list)
    manual_flush: bool = False
    gamma_correction: bool = False
    _pending_image: dict | None = field(default=None, repr=False)
    _image_buf: bytearray = field(default_factory=bytearray, repr=False)

    @property
    def waiting_for_image_data(self) -> bool:
        return self._pending_image is not None

    def feed_image_data(self, data: bytes) -> Packet | None:
        self._image_buf.extend(data)
        img = self._pending_image
        if len(self._image_buf) >= img["size"]:
            x, y, w, h = img["x"], img["y"], img["w"], img["h"]
            invert = img["invert"]
            transparent = img["transparent"]
            idx = 0
            for py in range(y, y + h):
                for px in range(x, x + w):
                    if idx < len(self._image_buf):
                        shade = self._image_buf[idx]
                        if invert:
                            shade = 255 - shade
                        if not transparent or shade != 0:
                            self._set_pixel(px, py, shade)
                        idx += 1
            self._pending_image = None
            self._image_buf = bytearray()
            return make_response(40, bytes([2]))
        return None

    def handle_packet(self, packet: Packet) -> Packet | None:
        handler = self._handlers.get(packet.command)
        if handler is None:
            return make_error(packet.command, INTERFACE_USB, ERR_UNKNOWN_COMMAND)
        return handler(self, packet)

    def key_event(self, key_code: int):
        is_press = key_code <= 6
        if is_press:
            bit = 1 << (key_code - 1)
            self.keys_pressed |= bit
            self.keys_pressed_since_poll |= bit
            if self.key_press_mask & bit:
                self.pending_reports.append(make_report(0x00, bytes([key_code])))
        else:
            bit = 1 << (key_code - 7)
            self.keys_pressed &= ~bit
            self.keys_released_since_poll |= bit
            if self.key_release_mask & bit:
                self.pending_reports.append(make_report(0x00, bytes([key_code])))

    def take_reports(self) -> list[Packet]:
        reports = self.pending_reports
        self.pending_reports = []
        return reports

    def _cmd_ping(self, packet: Packet) -> Packet:
        return make_response(0, packet.data)

    def _cmd_get_info(self, packet: Packet) -> Packet:
        if len(packet.data) == 0 or packet.data[0] == 0:
            return make_response(1, b"CFA835:h1.3,f1.0")
        elif packet.data[0] == 1:
            return make_response(1, b"0000835EMU00000001")
        return make_error(1, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_write_flash(self, packet: Packet) -> Packet:
        length = len(packet.data)
        if length < 1 or length > 124:
            return make_error(2, INTERFACE_USB, ERR_INVALID_LENGTH)
        self.user_flash[:length] = packet.data
        return make_response(2)

    def _cmd_read_flash(self, packet: Packet) -> Packet:
        if len(packet.data) != 1:
            return make_error(3, INTERFACE_USB, ERR_INVALID_LENGTH)
        count = packet.data[0]
        if count < 1 or count > 124:
            return make_error(3, INTERFACE_USB, ERR_INVALID_LENGTH)
        return make_response(3, bytes(self.user_flash[:count]))

    def _cmd_store_boot(self, packet: Packet) -> Packet:
        return make_response(4)

    def _cmd_restart(self, packet: Packet) -> Packet:
        return make_response(5)

    def _cmd_clear(self, packet: Packet) -> Packet:
        self.framebuffer = bytearray(LCD_WIDTH * LCD_HEIGHT)
        self.text_buffer = [[0x20] * TEXT_COLS for _ in range(TEXT_ROWS)]
        self.cursor_col = 0
        self.cursor_row = 0
        return make_response(6)

    def _cmd_special_char(self, packet: Packet) -> Packet:
        if len(packet.data) == 1:
            idx = packet.data[0]
            return make_response(9, bytes([idx]) + bytes(8))
        elif len(packet.data) == 9:
            return make_response(9)
        return make_error(9, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_cursor_pos(self, packet: Packet) -> Packet:
        if len(packet.data) == 0:
            return make_response(11, bytes([self.cursor_col, self.cursor_row]))
        if len(packet.data) == 2:
            self.cursor_col = min(packet.data[0], TEXT_COLS - 1)
            self.cursor_row = min(packet.data[1], TEXT_ROWS - 1)
            return make_response(11)
        return make_error(11, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_cursor_style(self, packet: Packet) -> Packet:
        if len(packet.data) == 0:
            return make_response(12, bytes([self.cursor_style]))
        if len(packet.data) == 1:
            self.cursor_style = packet.data[0]
            return make_response(12)
        return make_error(12, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_contrast(self, packet: Packet) -> Packet:
        if len(packet.data) == 0:
            return make_response(13, bytes([self.contrast]))
        if len(packet.data) == 1:
            self.contrast = packet.data[0]
            return make_response(13)
        return make_error(13, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_backlight(self, packet: Packet) -> Packet:
        if len(packet.data) == 0:
            return make_response(14, bytes([self.display_brightness, self.keypad_brightness]))
        if len(packet.data) == 1:
            self.display_brightness = min(packet.data[0], 100)
            self.keypad_brightness = min(packet.data[0], 100)
            return make_response(14)
        if len(packet.data) == 2:
            self.display_brightness = min(packet.data[0], 100)
            self.keypad_brightness = min(packet.data[1], 100)
            return make_response(14)
        return make_error(14, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_key_reporting(self, packet: Packet) -> Packet:
        if len(packet.data) == 0:
            return make_response(23, bytes([self.key_press_mask, self.key_release_mask]))
        if len(packet.data) == 2:
            self.key_press_mask = packet.data[0] & 0x3F
            self.key_release_mask = packet.data[1] & 0x3F
            return make_response(23)
        return make_error(23, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_read_keypad(self, packet: Packet) -> Packet:
        result = bytes([self.keys_pressed, self.keys_pressed_since_poll, self.keys_released_since_poll])
        self.keys_pressed_since_poll = 0
        self.keys_released_since_poll = 0
        return make_response(24, result)

    def _cmd_atx(self, packet: Packet) -> Packet:
        if len(packet.data) == 0:
            return make_response(28, bytes([0, 32]))
        return make_response(28)

    def _cmd_watchdog(self, packet: Packet) -> Packet:
        if len(packet.data) == 0:
            return make_response(29, bytes([0]))
        return make_response(29)

    def _cmd_write_text(self, packet: Packet) -> Packet:
        if len(packet.data) < 3:
            return make_error(31, INTERFACE_USB, ERR_INVALID_LENGTH)
        col = packet.data[0]
        row = packet.data[1]
        text = packet.data[2:]
        if row >= TEXT_ROWS or col >= TEXT_COLS:
            return make_error(31, INTERFACE_USB, ERR_INVALID_LENGTH)
        for i, ch in enumerate(text):
            c = col + i
            if c >= TEXT_COLS:
                break
            self.text_buffer[row][c] = ch
        self._render_text()
        return make_response(31)

    def _cmd_read_text(self, packet: Packet) -> Packet:
        if len(packet.data) != 3:
            return make_error(32, INTERFACE_USB, ERR_INVALID_LENGTH)
        col, row, length = packet.data[0], packet.data[1], packet.data[2]
        if row >= TEXT_ROWS or col >= TEXT_COLS:
            return make_error(32, INTERFACE_USB, ERR_INVALID_LENGTH)
        end = min(col + length, TEXT_COLS)
        return make_response(32, bytes(self.text_buffer[row][col:end]))

    def _cmd_interface_options(self, packet: Packet) -> Packet:
        if len(packet.data) >= 1 and packet.data[0] == 1:
            return make_response(33, bytes([1, 0x1F]))
        if len(packet.data) >= 1 and packet.data[0] == 0:
            return make_response(33, bytes([0, 0x1F, 1]))
        return make_response(33)

    GPIO_LED_MAP: ClassVar[dict] = {
        5:  (3, "green"),
        6:  (3, "red"),
        7:  (2, "green"),
        8:  (2, "red"),
        9:  (1, "green"),
        10: (1, "red"),
        11: (0, "green"),
        12: (0, "red"),
    }

    def _cmd_gpio(self, packet: Packet) -> Packet:
        if len(packet.data) == 1:
            idx = packet.data[0]
            mapping = self.GPIO_LED_MAP.get(idx)
            if mapping:
                led_idx, color = mapping
                led = self.leds[led_idx]
                val = led.red if color == "red" else led.green
                return make_response(34, bytes([idx, val, val, 0]))
            return make_response(34, bytes([idx, 0, 0, 0]))
        if len(packet.data) >= 2:
            idx = packet.data[0]
            val = min(packet.data[1], 100)
            mapping = self.GPIO_LED_MAP.get(idx)
            if mapping:
                led_idx, color = mapping
                led = self.leds[led_idx]
                if color == "red":
                    led.red = val
                else:
                    led.green = val
            return make_response(34)
        return make_error(34, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _cmd_graphic_options(self, packet: Packet) -> Packet:
        if len(packet.data) < 1:
            return make_error(40, INTERFACE_USB, ERR_INVALID_LENGTH)
        subcmd = packet.data[0]
        if subcmd == 0:
            if len(packet.data) >= 2:
                flags = packet.data[1]
                self.manual_flush = bool(flags & 0x01)
                self.gamma_correction = bool(flags & 0x02)
            return make_response(40, bytes([0]))
        elif subcmd == 1:
            return make_response(40, bytes([1]))
        elif subcmd == 5:
            if len(packet.data) == 4:
                x, y, shade = packet.data[1], packet.data[2], packet.data[3]
                if x < LCD_WIDTH and y < LCD_HEIGHT:
                    self.framebuffer[y * LCD_WIDTH + x] = shade
                return make_response(40, bytes([5]))
            elif len(packet.data) == 3:
                x, y = packet.data[1], packet.data[2]
                if x < LCD_WIDTH and y < LCD_HEIGHT:
                    shade = self.framebuffer[y * LCD_WIDTH + x]
                    return make_response(40, bytes([5, shade]))
                return make_response(40, bytes([5, 0]))
        elif subcmd == 6:
            if len(packet.data) == 6:
                x0, y0, x1, y1, shade = packet.data[1], packet.data[2], packet.data[3], packet.data[4], packet.data[5]
                self._draw_line(x0, y0, x1, y1, shade)
                return make_response(40, bytes([6]))
        elif subcmd == 7:
            if len(packet.data) == 7:
                x, y, w, h, line_shade, fill_shade = (
                    packet.data[1], packet.data[2], packet.data[3],
                    packet.data[4], packet.data[5], packet.data[6],
                )
                self._draw_rect(x, y, w, h, line_shade, fill_shade)
                return make_response(40, bytes([7]))
        elif subcmd == 8:
            if len(packet.data) == 6:
                cx, cy, r, line_shade, fill_shade = (
                    packet.data[1], packet.data[2], packet.data[3],
                    packet.data[4], packet.data[5],
                )
                self._draw_circle(cx, cy, r, line_shade, fill_shade)
                return make_response(40, bytes([8]))
        elif subcmd == 2:
            if len(packet.data) == 6:
                flags = packet.data[1]
                x, y, w, h = packet.data[2], packet.data[3], packet.data[4], packet.data[5]
                self._pending_image = {
                    "x": x, "y": y, "w": w, "h": h,
                    "transparent": bool(flags & 0x01),
                    "invert": bool(flags & 0x02),
                    "size": w * h,
                }
                return None
        return make_error(40, INTERFACE_USB, ERR_INVALID_LENGTH)

    def _set_pixel(self, x: int, y: int, shade: int):
        if 0 <= x < LCD_WIDTH and 0 <= y < LCD_HEIGHT:
            self.framebuffer[y * LCD_WIDTH + x] = shade

    def _draw_line(self, x0: int, y0: int, x1: int, y1: int, shade: int):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self._set_pixel(x0, y0, shade)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def _draw_rect(self, x: int, y: int, w: int, h: int, line_shade: int, fill_shade: int):
        if fill_shade > 0:
            for fy in range(y + 1, y + h - 1):
                for fx in range(x + 1, x + w - 1):
                    self._set_pixel(fx, fy, fill_shade)
        for i in range(w):
            self._set_pixel(x + i, y, line_shade)
            self._set_pixel(x + i, y + h - 1, line_shade)
        for i in range(h):
            self._set_pixel(x, y + i, line_shade)
            self._set_pixel(x + w - 1, y + i, line_shade)

    def _draw_circle(self, cx: int, cy: int, r: int, line_shade: int, fill_shade: int):
        x = 0
        y = r
        d = 3 - 2 * r
        while x <= y:
            if fill_shade > 0:
                self._hline(cx - x, cx + x, cy + y, fill_shade)
                self._hline(cx - x, cx + x, cy - y, fill_shade)
                self._hline(cx - y, cx + y, cy + x, fill_shade)
                self._hline(cx - y, cx + y, cy - x, fill_shade)
            self._set_pixel(cx + x, cy + y, line_shade)
            self._set_pixel(cx - x, cy + y, line_shade)
            self._set_pixel(cx + x, cy - y, line_shade)
            self._set_pixel(cx - x, cy - y, line_shade)
            self._set_pixel(cx + y, cy + x, line_shade)
            self._set_pixel(cx - y, cy + x, line_shade)
            self._set_pixel(cx + y, cy - x, line_shade)
            self._set_pixel(cx - y, cy - x, line_shade)
            if d < 0:
                d += 4 * x + 6
            else:
                d += 4 * (x - y) + 10
                y -= 1
            x += 1

    def _hline(self, x0: int, x1: int, y: int, shade: int):
        for x in range(x0, x1 + 1):
            self._set_pixel(x, y, shade)

    CHAR_WIDTH: ClassVar[int] = 6
    CHAR_HEIGHT: ClassVar[int] = 8
    ROW_SPACING: ClassVar[int] = 17

    def _render_text(self):
        for row in range(TEXT_ROWS):
            for col in range(TEXT_COLS):
                ch = self.text_buffer[row][col]
                px = col * self.CHAR_WIDTH
                py = row * self.ROW_SPACING
                self._render_char(px, py, ch)

    def _render_char(self, px: int, py: int, ch: int):
        from . import font
        bitmap = font.get_char_bitmap(ch)
        for cy in range(self.CHAR_HEIGHT):
            for cx in range(self.CHAR_WIDTH - 1):
                bit = bitmap[cy] & (1 << (4 - cx)) if cx < 5 else 0
                shade = 0xFF if bit else 0x00
                self._set_pixel(px + cx, py + cy, shade)
            self._set_pixel(px + self.CHAR_WIDTH - 1, py + cy, 0x00)

    _handlers: ClassVar[dict] = {
        0: _cmd_ping,
        1: _cmd_get_info,
        2: _cmd_write_flash,
        3: _cmd_read_flash,
        4: _cmd_store_boot,
        5: _cmd_restart,
        6: _cmd_clear,
        9: _cmd_special_char,
        11: _cmd_cursor_pos,
        12: _cmd_cursor_style,
        13: _cmd_contrast,
        14: _cmd_backlight,
        23: _cmd_key_reporting,
        24: _cmd_read_keypad,
        28: _cmd_atx,
        29: _cmd_watchdog,
        31: _cmd_write_text,
        32: _cmd_read_text,
        33: _cmd_interface_options,
        34: _cmd_gpio,
        40: _cmd_graphic_options,
    }
