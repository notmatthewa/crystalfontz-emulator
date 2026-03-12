import sys
import os
import time

from cfa835.crc import get_crc
from cfa835.font import get_char_bitmap

if len(sys.argv) < 2:
    print("Usage: python graphics_example.py /dev/pts/X")
    sys.exit(1)

fd = os.open(sys.argv[1], os.O_RDWR | os.O_NOCTTY)
os.set_blocking(fd, False)

LCD_W = 244
LCD_H = 68
CHAR_W = 6
CHAR_H = 8
TEXT_COLS = LCD_W // CHAR_W  # 40
TEXT_ROWS = LCD_H // CHAR_H  # 8


def send_packet(command: int, data: bytes = b""):
    payload = bytes([command, len(data)]) + data
    crc = get_crc(payload)
    os.write(fd, payload + crc.to_bytes(2, "little"))


def drain():
    deadline = time.monotonic() + 0.1
    while time.monotonic() < deadline:
        try:
            os.read(fd, 65536)
        except OSError:
            pass
        time.sleep(0.005)


def write_raw(data: bytes):
    offset = 0
    while offset < len(data):
        try:
            n = os.write(fd, data[offset:offset + 4096])
            offset += n
        except BlockingIOError:
            time.sleep(0.005)
        time.sleep(0.005)


def clear():
    send_packet(6)
    drain()


def send_image(x: int, y: int, w: int, h: int, pixels: bytes):
    send_packet(40, bytes([2, 0, x, y, w, h]))
    time.sleep(0.02)
    write_raw(pixels)
    drain()


def render_text_line(text: str, max_cols: int = TEXT_COLS) -> bytes:
    text = text[:max_cols].ljust(max_cols)
    pixels = bytearray(len(text) * CHAR_W * CHAR_H)
    for ci, ch in enumerate(text):
        bitmap = get_char_bitmap(ord(ch))
        for cy in range(CHAR_H):
            for cx in range(CHAR_W - 1):
                bit = bitmap[cy] & (1 << (4 - cx))
                if bit:
                    pixels[(cy * len(text) * CHAR_W) + (ci * CHAR_W + cx)] = 0xFF
    return bytes(pixels)


def write_line(row: int, text: str):
    if row < 0 or row >= TEXT_ROWS:
        return
    y = row * CHAR_H
    w = TEXT_COLS * CHAR_W
    pixels = render_text_line(text, TEXT_COLS)
    send_image(0, y, w, CHAR_H, pixels)


def write_all(lines: list[str]):
    buf = bytearray(LCD_W * LCD_H)
    for row, text in enumerate(lines[:TEXT_ROWS]):
        text = text[:TEXT_COLS].ljust(TEXT_COLS)
        for ci, ch in enumerate(text):
            bitmap = get_char_bitmap(ord(ch))
            for cy in range(CHAR_H):
                for cx in range(CHAR_W - 1):
                    bit = bitmap[cy] & (1 << (4 - cx))
                    if bit:
                        py = row * CHAR_H + cy
                        px = ci * CHAR_W + cx
                        buf[py * LCD_W + px] = 0xFF
    send_image(0, 0, LCD_W, LCD_H, bytes(buf))


clear()

print(f"Graphics text mode: {TEXT_COLS} cols x {TEXT_ROWS} rows")
print()
print("Commands:")
print("  line <row> <text>   - write to row 0-7")
print("  fill                - fill all 8 rows with demo text")
print("  scroll <text>       - scroll text up")
print("  clear               - clear display")
print("  quit                - exit")
print()

lines = [""] * TEXT_ROWS

write_all([
    "== Graphics Mode ==",
    "40 cols x 8 rows!",
    "",
    "Use 'fill' to demo",
    "all 8 text lines.",
    "",
    "Type 'line 7 hello'",
    "to write to row 7",
])

while True:
    try:
        cmd = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        break

    if not cmd:
        continue

    parts = cmd.split(maxsplit=1)
    action = parts[0].lower()

    if action == "quit":
        break

    elif action == "line":
        if len(parts) < 2:
            print("Usage: line <row> <text>")
            continue
        args = parts[1].split(maxsplit=1)
        row = int(args[0])
        if row < 0 or row >= TEXT_ROWS:
            print(f"Row must be 0-{TEXT_ROWS - 1}")
            continue
        text = args[1] if len(args) > 1 else ""
        lines[row] = text
        write_line(row, text)
        print(f"Row {row}: '{text}'")

    elif action == "fill":
        lines = [
            "Line 0: Top of screen",
            "Line 1: Hello world!",
            "Line 2: ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "Line 3: 0123456789 !@#$%^&*()",
            "Line 4: The quick brown fox jumps",
            "Line 5: over the lazy dog.",
            "Line 6: 40 characters per line max!!!!",
            "Line 7: Bottom of screen =======",
        ]
        write_all(lines)
        print("Filled all 8 rows")

    elif action == "scroll":
        text = parts[1] if len(parts) > 1 else ""
        lines = lines[1:] + [text]
        write_all(lines)
        print(f"Scrolled up, new bottom: '{text}'")

    elif action == "clear":
        clear()
        lines = [""] * TEXT_ROWS
        print("Cleared")

    else:
        print(f"Unknown: {action}")

clear()
os.close(fd)
