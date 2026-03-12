import os, time
from cfa835.device import CFA835Device, LCD_WIDTH, LCD_HEIGHT
from cfa835.serial_interface import SerialInterface
from cfa835.crc import get_crc

device = CFA835Device()
serial = SerialInterface(device)
slave_fd = os.open(serial.pty_path, os.O_RDWR | os.O_NOCTTY)
os.set_blocking(slave_fd, False)

W, H = LCD_WIDTH, LCD_HEIGHT

def make_img_pkt(w, h):
    payload = bytes([40, 6, 2, 0, 0, 0, w, h])
    crc = get_crc(payload)
    return payload + crc.to_bytes(2, "little")

def write_chunked(data):
    off = 0
    while off < len(data):
        try:
            n = os.write(slave_fd, data[off:off+4096])
            off += n
        except BlockingIOError:
            time.sleep(0.005)
        time.sleep(0.002)

def poll_all():
    for _ in range(20):
        serial.poll()
        time.sleep(0.005)

for frame in range(10):
    val = (frame * 25) % 256
    pixels = bytes([val] * (W * H))
    pkt = make_img_pkt(W, H)
    write_chunked(pkt + pixels)
    poll_all()

    try:
        os.read(slave_fd, 65536)
    except OSError:
        pass

    sample = device.framebuffer[0]
    match = all(device.framebuffer[i] == val for i in range(W * H))
    print(f"Frame {frame}: expected={val}, pixel[0]={sample}, all_match={match}")

serial.close()
os.close(slave_fd)
