import sys
import time
import os
import struct

from cfa835.crc import get_crc

if len(sys.argv) < 2:
    print("Usage: python example.py /dev/pts/X")
    sys.exit(1)

port_path = sys.argv[1]
fd = os.open(port_path, os.O_RDWR | os.O_NOCTTY)
os.set_blocking(fd, False)


def send_packet(command: int, data: bytes = b""):
    payload = bytes([command, len(data)]) + data
    crc = get_crc(payload)
    raw = payload + crc.to_bytes(2, "little")
    os.write(fd, raw)


def read_response(timeout: float = 0.5) -> tuple[int, int, bytes] | None:
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        try:
            chunk = os.read(fd, 256)
            buf.extend(chunk)
        except OSError:
            pass
        if len(buf) >= 4:
            data_len = buf[1]
            total = 2 + data_len + 2
            if len(buf) >= total:
                raw_type = buf[0]
                pkt_type = raw_type & 0xC0
                cmd = raw_type & 0x3F
                data = bytes(buf[2:2 + data_len])
                return pkt_type, cmd, data
        time.sleep(0.01)
    return None


def write_text(col: int, row: int, text: str):
    send_packet(31, bytes([col, row]) + text.encode("ascii"))
    read_response()


def clear():
    send_packet(6)
    read_response()


def set_led(led: int, green: int, red: int):
    green_idx = 11 - led * 2
    red_idx = 12 - led * 2
    send_packet(34, bytes([green_idx, green]))
    read_response()
    send_packet(34, bytes([red_idx, red]))
    read_response()


def set_backlight(display: int, keypad: int = -1):
    if keypad < 0:
        send_packet(14, bytes([display]))
    else:
        send_packet(14, bytes([display, keypad]))
    read_response()


print("Connected to emulator")
print("Commands: text, clear, led, backlight, listen, quit")
print()

clear()
write_text(0, 0, "CFA835 Emulator")
write_text(0, 1, "Ready!")
set_led(0, 50, 0)

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

    elif action == "text":
        if len(parts) < 2:
            print("Usage: text <row> <message>")
            continue
        args = parts[1].split(maxsplit=1)
        if len(args) < 2:
            print("Usage: text <row> <message>")
            continue
        row = int(args[0])
        if row < 0 or row > 3:
            print("Row must be 0-3")
            continue
        msg = args[1][:20]
        write_text(0, row, msg.ljust(20))
        print(f"Wrote '{msg}' to row {row}")

    elif action == "clear":
        clear()
        print("Display cleared")

    elif action == "led":
        if len(parts) < 2:
            print("Usage: led <0-3> <green> <red>")
            continue
        args = parts[1].split()
        if len(args) < 3:
            print("Usage: led <0-3> <green> <red>")
            continue
        led_num = int(args[0])
        g = int(args[1])
        r = int(args[2])
        set_led(led_num, g, r)
        print(f"LED {led_num}: green={g}, red={r}")

    elif action == "backlight":
        if len(parts) < 2:
            print("Usage: backlight <0-100>")
            continue
        val = int(parts[1])
        set_backlight(val)
        print(f"Backlight set to {val}%")

    elif action == "listen":
        print("Listening for key events (Ctrl+C to stop)...")
        send_packet(23, bytes([0x3F, 0x3F]))
        read_response()
        key_names = {
            1: "UP press", 2: "DOWN press", 3: "LEFT press",
            4: "RIGHT press", 5: "ENTER press", 6: "EXIT press",
            7: "UP release", 8: "DOWN release", 9: "LEFT release",
            10: "RIGHT release", 11: "ENTER release", 12: "EXIT release",
        }
        try:
            while True:
                resp = read_response(timeout=0.1)
                if resp:
                    pkt_type, cmd, data = resp
                    if pkt_type == 0x80 and len(data) == 1:
                        name = key_names.get(data[0], f"unknown({data[0]})")
                        print(f"  Key: {name}")
                    else:
                        print(f"  Packet: type=0x{pkt_type:02x} cmd={cmd} data={data.hex()}")
        except KeyboardInterrupt:
            print("\nStopped listening")

    else:
        print(f"Unknown command: {action}")
        print("Commands: text, clear, led, backlight, listen, quit")

os.close(fd)
