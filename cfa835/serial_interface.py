import os
import pty
import select
import tty

from .protocol import PacketReader
from .device import CFA835Device


class SerialInterface:
    def __init__(self, device: CFA835Device):
        self.device = device
        self.reader = PacketReader()
        self.master_fd, self.slave_fd = pty.openpty()
        tty.setraw(self.master_fd)
        tty.setraw(self.slave_fd)
        self.pty_path = os.ttyname(self.slave_fd)
        os.set_blocking(self.master_fd, False)

    def poll(self):
        while True:
            ready, _, _ = select.select([self.master_fd], [], [], 0)
            if not ready:
                break
            try:
                data = os.read(self.master_fd, 65536)
            except OSError:
                break
            if not data:
                break
            self._process(data)
        for report in self.device.take_reports():
            self._write(report.encode())

    def _process(self, data: bytes):
        if self.device.waiting_for_image_data:
            response = self.device.feed_image_data(data)
            if response:
                self._write(response.encode())
            return

        from .protocol import Packet

        self.reader._buf.extend(data)
        while len(self.reader._buf) >= 4:
            packet = Packet.decode(self.reader._buf)
            if packet is None:
                self.reader._buf.pop(0)
                continue
            consumed = 2 + len(packet.data) + 2
            self.reader._buf = self.reader._buf[consumed:]
            response = self.device.handle_packet(packet)
            if response is not None:
                self._write(response.encode())
            if self.device.waiting_for_image_data:
                if self.reader._buf:
                    leftover = bytes(self.reader._buf)
                    self.reader._buf.clear()
                    img_response = self.device.feed_image_data(leftover)
                    if img_response:
                        self._write(img_response.encode())
                break

    def flush_reports(self):
        for report in self.device.take_reports():
            self._write(report.encode())

    def _write(self, data: bytes):
        try:
            os.write(self.master_fd, data)
        except OSError:
            pass

    def close(self):
        os.close(self.master_fd)
        os.close(self.slave_fd)
