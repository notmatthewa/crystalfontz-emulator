from ._font import get_char_bitmap

LCD_WIDTH = 244
LCD_HEIGHT = 68
CHAR_W = 6
CHAR_H = 8


class FrameBuffer:
    """Local 244x68 grayscale framebuffer with drawing primitives."""

    def __init__(self):
        self.width = LCD_WIDTH
        self.height = LCD_HEIGHT
        self.buf = bytearray(LCD_WIDTH * LCD_HEIGHT)

    def clear(self, shade: int = 0x00):
        for i in range(len(self.buf)):
            self.buf[i] = shade

    def set_pixel(self, x: int, y: int, shade: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.buf[y * self.width + x] = shade

    def get_pixel(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.buf[y * self.width + x]
        return 0

    def hline(self, x: int, y: int, w: int, shade: int):
        for i in range(w):
            self.set_pixel(x + i, y, shade)

    def vline(self, x: int, y: int, h: int, shade: int):
        for i in range(h):
            self.set_pixel(x, y + i, shade)

    def rect(self, x: int, y: int, w: int, h: int, shade: int, fill: int = 0):
        if fill:
            for fy in range(y, y + h):
                for fx in range(x, x + w):
                    self.set_pixel(fx, fy, fill)
        self.hline(x, y, w, shade)
        self.hline(x, y + h - 1, w, shade)
        self.vline(x, y, h, shade)
        self.vline(x + w - 1, y, h, shade)

    def dashed_rect(self, x: int, y: int, w: int, h: int, shade: int,
                    dash: int = 2, gap: int = 2):
        """Draw a rectangle with dashed lines."""
        period = dash + gap
        for i in range(w):
            if i % period < dash:
                self.set_pixel(x + i, y, shade)
                self.set_pixel(x + i, y + h - 1, shade)
        for i in range(h):
            if i % period < dash:
                self.set_pixel(x, y + i, shade)
                self.set_pixel(x + w - 1, y + i, shade)

    def rounded_rect(self, x: int, y: int, w: int, h: int, shade: int,
                     fill: int = 0):
        """Draw a rectangle with 1px rounded corners."""
        if fill:
            for fy in range(y, y + h):
                for fx in range(x, x + w):
                    if (fx == x or fx == x + w - 1) and (fy == y or fy == y + h - 1):
                        continue
                    self.set_pixel(fx, fy, fill)
        self.hline(x + 1, y, w - 2, shade)
        self.hline(x + 1, y + h - 1, w - 2, shade)
        self.vline(x, y + 1, h - 2, shade)
        self.vline(x + w - 1, y + 1, h - 2, shade)

    def fill_rect(self, x: int, y: int, w: int, h: int, shade: int):
        for fy in range(y, y + h):
            for fx in range(x, x + w):
                self.set_pixel(fx, fy, shade)

    def draw_char(self, x: int, y: int, ch: int, shade: int = 0xFF) -> int:
        """Draw a single character. Returns the advance width."""
        bitmap = get_char_bitmap(ch)
        for cy in range(CHAR_H):
            for cx in range(5):
                if bitmap[cy] & (1 << (4 - cx)):
                    self.set_pixel(x + cx, y + cy, shade)
        return CHAR_W

    def draw_text(self, x: int, y: int, text: str, shade: int = 0xFF) -> int:
        """Draw a string. Returns the total width drawn."""
        ox = x
        for ch in text:
            self.draw_char(ox, y, ord(ch), shade)
            ox += CHAR_W
        return ox - x

    def text_width(self, text: str) -> int:
        return len(text) * CHAR_W

    def invert_rect(self, x: int, y: int, w: int, h: int):
        """Invert all pixels in a rectangle (for selection highlight)."""
        for fy in range(y, y + h):
            for fx in range(x, x + w):
                if 0 <= fx < self.width and 0 <= fy < self.height:
                    idx = fy * self.width + fx
                    self.buf[idx] = 255 - self.buf[idx]
