"""64KB bellek + I/O portları.

Bellek gerçek nöronlardan değil — beyin gate fabrikasının kapasitesi
sınırlı, kapı devresi yalnızca HESAPLAMA yapar.  Bellek ve E/Ç, Python
tarafında tutulan gerçeklik-notu olarak dizilerle taklit edilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

MASK16 = 0xFFFF
RAM_SIZE = 64 * 1024     # 64KB
STACK_TOP = 0xFFFE       # yığın: alttan yukarı


@dataclass
class Memory:
    """64KB byte-addressable RAM + 16 I/O port."""
    ram: np.ndarray = field(default_factory=lambda: np.zeros(RAM_SIZE, dtype=np.uint8))
    ports: dict[int, int] = field(default_factory=dict)

    def rb(self, addr: int) -> int:
        return int(self.ram[addr & MASK16])

    def rw(self, addr: int) -> int:
        """16-bit oku (big-endian: [addr]<<8 | [addr+1])."""
        return (int(self.ram[addr & MASK16]) << 8) | int(self.ram[(addr + 1) & MASK16])

    def wb(self, addr: int, val: int) -> None:
        self.ram[addr & MASK16] = val & 0xFF

    def ww(self, addr: int, val: int) -> None:
        """16-bit yaz (big-endian)."""
        self.ram[addr & MASK16] = (val >> 8) & 0xFF
        self.ram[(addr + 1) & MASK16] = val & 0xFF

    def port_read(self, port: int) -> int:
        return self.ports.get(port, 0) & 0xFF

    def port_write(self, port: int, val: int) -> None:
        self.ports[port] = val & 0xFF

    def load_program(self, data: list[int], start: int = 0) -> None:
        for i, b in enumerate(data):
            self.wb(start + i, b)

    def dump(self, addr: int, length: int = 32) -> str:
        return " ".join(f"{self.rb(addr+i):02x}" for i in range(length))