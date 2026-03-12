from dataclasses import dataclass, field

from .crc import get_crc

TYPE_COMMAND = 0x00
TYPE_RESPONSE = 0x40
TYPE_REPORT = 0x80
TYPE_ERROR = 0xC0

MAX_DATA_LENGTH = 124
HEADER_SIZE = 2
CRC_SIZE = 2
MIN_PACKET_SIZE = HEADER_SIZE + CRC_SIZE


@dataclass
class Packet:
    type: int
    command: int
    data: bytes = field(default_factory=bytes)

    def encode(self) -> bytes:
        raw_type = self.type | self.command
        payload = bytes([raw_type, len(self.data)]) + self.data
        crc = get_crc(payload)
        return payload + crc.to_bytes(2, "little")

    @staticmethod
    def decode(buf: bytes) -> "Packet | None":
        if len(buf) < MIN_PACKET_SIZE:
            return None
        raw_type = buf[0]
        data_length = buf[1]
        total = HEADER_SIZE + data_length + CRC_SIZE
        if len(buf) < total:
            return None
        crc_received = int.from_bytes(buf[total - 2 : total], "little")
        crc_calculated = get_crc(buf[: total - 2])
        if crc_received != crc_calculated:
            return None
        return Packet(
            type=raw_type & 0xC0,
            command=raw_type & 0x3F,
            data=bytes(buf[HEADER_SIZE : HEADER_SIZE + data_length]),
        )

    @property
    def total_length(self) -> int:
        return HEADER_SIZE + len(self.data) + CRC_SIZE


def make_response(command: int, data: bytes = b"") -> Packet:
    return Packet(type=TYPE_RESPONSE, command=command, data=data)


def make_error(command: int, interface: int, error_code: int) -> Packet:
    return Packet(type=TYPE_ERROR, command=command, data=bytes([interface, error_code]))


def make_report(code: int, data: bytes = b"") -> Packet:
    return Packet(type=TYPE_REPORT, command=code, data=data)


class PacketReader:
    def __init__(self):
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[Packet]:
        self._buf.extend(data)
        packets = []
        while len(self._buf) >= MIN_PACKET_SIZE:
            packet = Packet.decode(self._buf)
            if packet is None:
                if len(self._buf) >= MIN_PACKET_SIZE:
                    self._buf.pop(0)
                else:
                    break
            else:
                packets.append(packet)
                consumed = HEADER_SIZE + len(packet.data) + CRC_SIZE
                self._buf = self._buf[consumed:]
        return packets
