"""Register dosyası: 16×8-bit (R0 toprakta, yazma ignored).

Rekurrent nöronlar (beyin içindeki self-loop hücreleri) SRAM olarak
kullanılır; yeterli hücre yoksa NULL (yazılımsal) arka plana düşülür.
Her registrer bir beyin nöron kümesiyle temsil edilir (bit0..7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from ..synth.brain import BrainGraph, top_degree_neurons

MASK8 = 0xFF
N_REGS = 16


@dataclass
class RegisterFile:
    """16 × 8-bit register bank (R0 sabit 0)."""
    cells: list[list[int]] = field(default_factory=list)   # reg -> [nid_bit0..7]
    _holding: dict[int, int] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if not self.cells:
            self.cells = [[] for _ in range(N_REGS)]

    def read(self, reg: int) -> int:
        reg %= N_REGS
        return self._holding.get(reg, 0) if reg != 0 else 0

    def write(self, reg: int, val: int) -> None:
        reg %= N_REGS
        if reg == 0:
            return
        self._holding[reg] = val & MASK8

    def summary(self) -> str:
        real = sum(1 for cells in self.cells if any(n >= 0 for n in cells))
        return f"RegisterBank({N_REGS} regs, {real} real cells)"


def build_register_bank(brain: BrainGraph,
                        n_real: int | None = None) -> RegisterFile:
    """Her registrer için 8 beyin nöronu kiralayarak SRAM bankası kurar.

    Gerçek beyin nöronu (self-loop) varsa o registrer "gerçek SRAM";
    yoksa NULL modda yazılım tarafından tutulur — ama todas
    low-level hesaplama kapılardan geçer (ports aracılığıyla okunur/yazılır).
    """
    # self-loop nöronlarını bul (rekurrent)
    W = brain.W
    self_loops: list[int] = []
    for n in range(brain.n_neurons):
        if W[n, n] > 0:
            self_loops.append(n)

    if n_real is None:
        n_real = min(len(self_loops), N_REGS * 8)  # max kullanılabilecek

    cells: list[list[int]] = [[] for _ in range(N_REGS)]
    # self-loop nöronlarını registrerler arasında dağıt
    for reg in range(N_REGS):
        for bit in range(8):
            idx = reg * 8 + bit
            if idx < n_real:
                cells[reg].append(self_loops[idx])
            else:
                cells[reg].append(-1)   # NULL

    bank = RegisterFile(cells=cells)
    return bank