"""Simple key-value storage over the CFA835's 124-byte user flash.

Usage:
    store = Storage(app)

    # Define fields (auto-allocated sequentially)
    store.flags("prefs", {0: "dark_mode", 1: "sound", 2: "auto_sleep"})
    store.byte("brightness")
    store.byte("contrast")
    store.string("hostname", max_len=12)

    # Load current values from device
    store.load()

    # Read/write
    store.get("dark_mode")        # -> bool
    store.set("dark_mode", True)
    store.get("brightness")       # -> int (0-255)
    store.set("brightness", 75)
    store.get("hostname")         # -> str
    store.set("hostname", "srv1")

    # Persist to device flash
    store.save()
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import App

FLASH_SIZE = 124


class _Field:
    """Base class for storage field descriptors."""

    def __init__(self, name: str, address: int, size: int):
        self.name = name
        self.address = address
        self.size = size

    def decode(self, buf: bytearray) -> object:
        raise NotImplementedError

    def encode(self, buf: bytearray, value: object):
        raise NotImplementedError


class _ByteField(_Field):
    def __init__(self, name: str, address: int):
        super().__init__(name, address, 1)

    def decode(self, buf: bytearray) -> int:
        return buf[self.address]

    def encode(self, buf: bytearray, value: object):
        buf[self.address] = max(0, min(255, int(value)))


class _FlagField(_Field):
    """A single bit within a flags byte."""

    def __init__(self, name: str, address: int, bit: int):
        super().__init__(name, address, 0)  # size=0, parent flags byte owns the space
        self.bit = bit

    def decode(self, buf: bytearray) -> bool:
        return bool(buf[self.address] & (1 << self.bit))

    def encode(self, buf: bytearray, value: object):
        if value:
            buf[self.address] |= (1 << self.bit)
        else:
            buf[self.address] &= ~(1 << self.bit)


class _StringBuilder(_Field):
    """Length-prefixed string. First byte is length, rest is ASCII data."""

    def __init__(self, name: str, address: int, max_len: int):
        super().__init__(name, address, max_len + 1)
        self.max_len = max_len

    def decode(self, buf: bytearray) -> str:
        length = buf[self.address]
        if length > self.max_len:
            length = self.max_len
        start = self.address + 1
        return bytes(buf[start:start + length]).decode("ascii", errors="replace")

    def encode(self, buf: bytearray, value: object):
        s = str(value)[:self.max_len].encode("ascii", errors="replace")
        buf[self.address] = len(s)
        start = self.address + 1
        for i in range(self.max_len):
            buf[start + i] = s[i] if i < len(s) else 0


class Storage:
    """Key-value storage backed by CFA835 user flash (124 bytes).

    Define fields with flags(), byte(), and string(). Fields are
    auto-allocated sequentially unless an explicit address is given.
    Overlapping addresses raise a warning.
    """

    def __init__(self, app: App):
        self._app = app
        self._buf = bytearray(FLASH_SIZE)
        self._fields: dict[str, _Field] = {}
        self._regions: list[tuple[int, int, str]] = []  # (start, end, name)
        self._next_address = 0

    def _allocate(self, size: int, address: int | None, name: str) -> int:
        if address is None:
            address = self._next_address
        end = address + size
        if end > FLASH_SIZE:
            raise ValueError(
                f"Field '{name}' at address {address} "
                f"(size {size}) exceeds flash capacity ({FLASH_SIZE} bytes)"
            )
        for start_r, end_r, name_r in self._regions:
            if address < end_r and end > start_r:
                warnings.warn(
                    f"Field '{name}' (bytes {address}-{end - 1}) overlaps "
                    f"with '{name_r}' (bytes {start_r}-{end_r - 1})",
                    stacklevel=3,
                )
        self._regions.append((address, end, name))
        self._next_address = max(self._next_address, end)
        return address

    def _register(self, field: _Field):
        if field.name in self._fields:
            raise ValueError(f"Field '{field.name}' already defined")
        self._fields[field.name] = field

    def flags(self, group_name: str, bits: dict[int, str],
              address: int | None = None):
        """Define a flags byte with named boolean bits.

        Args:
            group_name: Name for the byte (used in overlap warnings).
            bits: Mapping of bit index (0-7) to field name.
            address: Flash byte offset, or None to auto-allocate.

        Example:
            store.flags("prefs", {0: "dark_mode", 1: "sound"})
            store.get("dark_mode")  # -> bool
        """
        addr = self._allocate(1, address, group_name)
        for bit, name in bits.items():
            if not 0 <= bit <= 7:
                raise ValueError(f"Bit index must be 0-7, got {bit}")
            field = _FlagField(name, addr, bit)
            self._register(field)

    def byte(self, name: str, address: int | None = None):
        """Define a single-byte unsigned integer field (0-255).

        Args:
            name: Field name for get/set.
            address: Flash byte offset, or None to auto-allocate.
        """
        addr = self._allocate(1, address, name)
        self._register(_ByteField(name, addr))

    def string(self, name: str, max_len: int, address: int | None = None):
        """Define a length-prefixed ASCII string field.

        Uses max_len + 1 bytes (1 for length prefix).

        Args:
            name: Field name for get/set.
            max_len: Maximum string length (1-123).
            address: Flash byte offset, or None to auto-allocate.
        """
        if max_len < 1 or max_len > FLASH_SIZE - 1:
            raise ValueError(f"max_len must be 1-{FLASH_SIZE - 1}")
        addr = self._allocate(max_len + 1, address, name)
        self._register(_StringBuilder(name, addr, max_len))

    def get(self, name: str):
        """Read a field value from the local buffer."""
        if name not in self._fields:
            raise KeyError(f"Unknown field '{name}'")
        return self._fields[name].decode(self._buf)

    def set(self, name: str, value):
        """Write a field value to the local buffer (call save() to persist)."""
        if name not in self._fields:
            raise KeyError(f"Unknown field '{name}'")
        self._fields[name].encode(self._buf, value)

    def load(self):
        """Read all flash data from the device into the local buffer."""
        resp = self._app._send_and_read(3, bytes([FLASH_SIZE]))
        if resp:
            for i in range(min(len(resp), FLASH_SIZE)):
                self._buf[i] = resp[i]

    def save(self):
        """Write the local buffer to device flash."""
        self._app._send_packet(2, bytes(self._buf))
        self._app._drain()

    @property
    def bytes_used(self) -> int:
        """Number of flash bytes allocated so far."""
        return self._next_address

    @property
    def bytes_free(self) -> int:
        """Number of flash bytes remaining."""
        return FLASH_SIZE - self._next_address

    def dump(self) -> dict[str, object]:
        """Return all field values as a dict."""
        return {name: field.decode(self._buf) for name, field in self._fields.items()}
