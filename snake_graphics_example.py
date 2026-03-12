import sys
import os
import time
import random

from cfa835.crc import get_crc
from cfa835.font import get_char_bitmap

if len(sys.argv) < 2:
    print("Usage: python snake_graphics_example.py /dev/pts/X")
    sys.exit(1)

fd = os.open(sys.argv[1], os.O_RDWR | os.O_NOCTTY)
os.set_blocking(fd, False)

LCD_W = 244
LCD_H = 68

CELL = 4
BORDER = 1
SCORE_W = 40

GRID_X = BORDER
GRID_Y = BORDER
GRID_W = (LCD_W - SCORE_W - BORDER * 2) // CELL
GRID_H = (LCD_H - BORDER * 2) // CELL
GRID_PX_W = GRID_W * CELL
GRID_PX_H = GRID_H * CELL

UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3

SHADE_BG = 0x00
SHADE_WALL = 0x60
SHADE_SNAKE = 0xFF
SHADE_HEAD = 0xD0
SHADE_FOOD = 0xA0
SHADE_TEXT = 0xFF


def send_packet(command: int, data: bytes = b""):
    payload = bytes([command, len(data)]) + data
    crc = get_crc(payload)
    os.write(fd, payload + crc.to_bytes(2, "little"))


def read_packets(timeout: float = 0.0) -> list[tuple[int, int, bytes]]:
    deadline = time.monotonic() + timeout
    buf = bytearray()
    results = []
    while True:
        try:
            chunk = os.read(fd, 4096)
            buf.extend(chunk)
        except OSError:
            pass
        while len(buf) >= 4:
            data_len = buf[1]
            total = 2 + data_len + 2
            if len(buf) < total:
                break
            raw_type = buf[0]
            results.append((raw_type & 0xC0, raw_type & 0x3F, bytes(buf[2:2 + data_len])))
            buf = buf[total:]
        if time.monotonic() >= deadline:
            break
    return results


def write_raw(data: bytes):
    offset = 0
    while offset < len(data):
        try:
            n = os.write(fd, data[offset:offset + 4096])
            offset += n
        except BlockingIOError:
            time.sleep(0.005)
        time.sleep(0.002)


def drain():
    deadline = time.monotonic() + 0.05
    while time.monotonic() < deadline:
        try:
            os.read(fd, 65536)
        except OSError:
            pass
        time.sleep(0.005)


def send_image(x: int, y: int, w: int, h: int, pixels: bytes):
    send_packet(40, bytes([2, 0, x, y, w, h]))
    time.sleep(0.01)
    write_raw(pixels)
    drain()


def clear():
    send_packet(6)
    drain()


def set_led(led: int, green: int, red: int):
    send_packet(34, bytes([11 - led * 2, green]))
    read_packets(0.01)
    send_packet(34, bytes([12 - led * 2, red]))
    read_packets(0.01)


def enable_key_reports():
    send_packet(23, bytes([0x3F, 0x3F]))
    read_packets(0.05)


def poll_keys() -> list[int]:
    keys = []
    for pkt_type, cmd, data in read_packets():
        if pkt_type == 0x80 and len(data) == 1:
            keys.append(data[0])
    return keys


def stamp_text(fb: bytearray, fb_w: int, px: int, py: int, text: str, shade: int = SHADE_TEXT):
    for ci, ch in enumerate(text):
        bitmap = get_char_bitmap(ord(ch))
        for cy in range(8):
            for cx in range(5):
                if bitmap[cy] & (1 << (4 - cx)):
                    x = px + ci * 6 + cx
                    y = py + cy
                    if 0 <= x < fb_w and 0 <= y < LCD_H:
                        fb[y * fb_w + x] = shade


def render_frame(snake: list, food: tuple, score: int) -> bytes:
    fb = bytearray(LCD_W * LCD_H)

    for x in range(LCD_W):
        fb[x] = SHADE_WALL
        fb[(LCD_H - 1) * LCD_W + x] = SHADE_WALL
    for y in range(LCD_H):
        fb[y * LCD_W] = SHADE_WALL
        fb[y * LCD_W + GRID_X + GRID_PX_W] = SHADE_WALL

    for sx, sy in snake:
        px = GRID_X + sx * CELL + 1
        py = GRID_Y + sy * CELL + 1
        for dy in range(CELL - 1):
            for dx in range(CELL - 1):
                fb[(py + dy) * LCD_W + (px + dx)] = SHADE_SNAKE

    hx, hy = snake[0]
    px = GRID_X + hx * CELL + 1
    py = GRID_Y + hy * CELL + 1
    for dy in range(CELL - 1):
        for dx in range(CELL - 1):
            fb[(py + dy) * LCD_W + (px + dx)] = SHADE_HEAD

    fx, fy = food
    cx = GRID_X + fx * CELL + CELL // 2
    cy = GRID_Y + fy * CELL + CELL // 2
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            if 0 <= cx + dx < LCD_W and 0 <= cy + dy < LCD_H:
                fb[(cy + dy) * LCD_W + (cx + dx)] = SHADE_FOOD

    panel_x = GRID_X + GRID_PX_W + 4
    stamp_text(fb, LCD_W, panel_x, 2, "SNAKE")
    stamp_text(fb, LCD_W, panel_x, 16, f"Score")
    stamp_text(fb, LCD_W, panel_x, 28, f"  {score}")

    length = len(snake)
    bar_x = panel_x
    bar_y = 42
    bar_h = LCD_H - bar_y - 4
    filled = min(length * 2, bar_h)
    for dy in range(bar_h):
        shade = SHADE_SNAKE if dy >= (bar_h - filled) else 0x20
        for dx in range(SCORE_W - 10):
            fb[(bar_y + dy) * LCD_W + (bar_x + dx)] = shade

    return bytes(fb)


def render_text_screen(lines: list[str]) -> bytes:
    fb = bytearray(LCD_W * LCD_H)
    for i, line in enumerate(lines):
        stamp_text(fb, LCD_W, 4, 4 + i * 10, line)
    return bytes(fb)


def place_food(snake: list) -> tuple:
    while True:
        pos = (random.randint(0, GRID_W - 1), random.randint(0, GRID_H - 1))
        if pos not in snake:
            return pos


def run():
    clear()

    title = render_text_screen([
        "=== SNAKE ===",
        "",
        f"Grid: {GRID_W}x{GRID_H}",
        "",
        "Arrow keys to move",
        "Press any key...",
    ])
    send_image(0, 0, LCD_W, LCD_H, title)

    set_led(0, 30, 0)
    set_led(1, 0, 0)
    set_led(2, 0, 0)
    set_led(3, 0, 0)
    enable_key_reports()

    while not poll_keys():
        time.sleep(0.05)

    mid_x = GRID_W // 2
    mid_y = GRID_H // 2
    snake = [(mid_x, mid_y), (mid_x - 1, mid_y), (mid_x - 2, mid_y)]
    direction = RIGHT
    food = place_food(snake)
    score = 0
    speed = 0.15

    while True:
        frame = render_frame(snake, food, score)
        send_image(0, 0, LCD_W, LCD_H, frame)

        deadline = time.monotonic() + speed
        while time.monotonic() < deadline:
            for key in poll_keys():
                if key == 1 and direction != DOWN:
                    direction = UP
                elif key == 2 and direction != UP:
                    direction = DOWN
                elif key == 3 and direction != RIGHT:
                    direction = LEFT
                elif key == 4 and direction != LEFT:
                    direction = RIGHT
                elif key == 6:
                    return
            time.sleep(0.015)

        hx, hy = snake[0]
        if direction == UP:
            hy -= 1
        elif direction == DOWN:
            hy += 1
        elif direction == LEFT:
            hx -= 1
        elif direction == RIGHT:
            hx += 1

        if hx < 0 or hx >= GRID_W or hy < 0 or hy >= GRID_H:
            break
        if (hx, hy) in snake:
            break

        snake.insert(0, (hx, hy))

        if (hx, hy) == food:
            score += 1
            food = place_food(snake)
            speed = max(0.08, speed - 0.005)
            led_idx = min(score - 1, 3)
            set_led(led_idx, min(score * 15, 100), 0)
        else:
            snake.pop()

    for i in range(4):
        set_led(i, 0, 100)

    over = render_text_screen([
        "GAME OVER!",
        "",
        f"Score: {score}",
        f"Length: {len(snake)}",
        "",
        "OK=Again  X=Quit",
    ])
    send_image(0, 0, LCD_W, LCD_H, over)
    time.sleep(0.5)

    while True:
        for key in poll_keys():
            if key == 5:
                return
            if key == 6:
                clear()
                os.close(fd)
                sys.exit(0)
        time.sleep(0.05)


try:
    while True:
        run()
except KeyboardInterrupt:
    clear()
    os.close(fd)
