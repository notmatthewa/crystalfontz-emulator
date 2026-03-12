import sys
import os
import time
import random

from cfa835.crc import get_crc

if len(sys.argv) < 2:
    print("Usage: python snake_example.py /dev/pts/X")
    sys.exit(1)

fd = os.open(sys.argv[1], os.O_RDWR | os.O_NOCTTY)
os.set_blocking(fd, False)

COLS = 20
ROWS = 4

UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
direction = RIGHT


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
            chunk = os.read(fd, 512)
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


def clear():
    send_packet(6)
    read_packets(0.05)


def write_text(col: int, row: int, text: str):
    send_packet(31, bytes([col, row]) + text.encode("ascii"))
    read_packets(0.01)


def set_led(led: int, green: int, red: int):
    send_packet(34, bytes([11 - led * 2, green]))
    read_packets(0.01)
    send_packet(34, bytes([12 - led * 2, red]))
    read_packets(0.01)


def enable_key_reports():
    send_packet(23, bytes([0x3F, 0x3F]))
    read_packets(0.05)


def poll_keys() -> int | None:
    packets = read_packets()
    for pkt_type, cmd, data in packets:
        if pkt_type == 0x80 and len(data) == 1:
            return data[0]
    return None


def draw_board(snake, food, score):
    grid = [[" "] * COLS for _ in range(ROWS)]
    for x, y in snake:
        grid[y][x] = "#"
    hx, hy = snake[0]
    grid[hy][hx] = "@"
    fx, fy = food
    grid[fy][fx] = "*"
    for row in range(ROWS):
        line = "".join(grid[row])
        write_text(0, row, line)


def place_food(snake):
    while True:
        pos = (random.randint(0, COLS - 1), random.randint(0, ROWS - 1))
        if pos not in snake:
            return pos


def run():
    global direction

    clear()
    write_text(2, 1, "=== SNAKE ===")
    write_text(3, 2, "Press any key")
    set_led(0, 50, 0)
    set_led(1, 0, 0)
    set_led(2, 0, 0)
    set_led(3, 0, 0)
    enable_key_reports()

    while poll_keys() is None:
        time.sleep(0.05)

    snake = [(10, 2), (9, 2), (8, 2)]
    direction = RIGHT
    food = place_food(snake)
    score = 0
    speed = 0.25

    set_led(0, 50, 0)

    while True:
        draw_board(snake, food, score)

        deadline = time.monotonic() + speed
        while time.monotonic() < deadline:
            key = poll_keys()
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
            time.sleep(0.02)

        hx, hy = snake[0]
        if direction == UP:
            hy -= 1
        elif direction == DOWN:
            hy += 1
        elif direction == LEFT:
            hx -= 1
        elif direction == RIGHT:
            hx += 1

        if hx < 0 or hx >= COLS or hy < 0 or hy >= ROWS:
            break
        if (hx, hy) in snake:
            break

        snake.insert(0, (hx, hy))

        if (hx, hy) == food:
            score += 1
            food = place_food(snake)
            speed = max(0.1, speed - 0.01)
            led_idx = min(score - 1, 3)
            set_led(led_idx, 0, 0)
            set_led(led_idx, score * 20, 0)
        else:
            snake.pop()

    for i in range(4):
        set_led(i, 0, 100)
    clear()
    write_text(3, 1, "GAME  OVER!")
    write_text(3, 2, f"Score: {score}")
    time.sleep(3)


try:
    while True:
        run()
        clear()
        write_text(4, 1, "Play again?")
        write_text(3, 2, "OK=Yes  X=Quit")
        while True:
            key = poll_keys()
            if key == 5:
                break
            if key == 6:
                clear()
                os.close(fd)
                sys.exit(0)
            time.sleep(0.05)
except KeyboardInterrupt:
    clear()
    os.close(fd)
