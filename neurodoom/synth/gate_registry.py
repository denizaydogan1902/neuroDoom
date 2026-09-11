"""Kapı sözlüğü: beyin çizgesindeki fanin-2 nöronları toplar.

Hemibrain %100 eksitatory olduğundan, koruma rolü (third input) olarak en
zayıf presinaptik komşu atanır. 21.700'den fazla potansiyel kapısı var;
CPU bileşenleri bu havuzdan "kiralayarak" belirir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .brain import BrainGraph


@dataclass
class GateCell:
    nid: int
    presyn: list[int]
    guard: int = -1          # 3. giriş (koruma): en zayıf presinaptik
    fan_in: int = 2


@dataclass
class GateRegistry:
    gates: list[GateCell] = field(default_factory=list)
    _nid_index: dict[int, int] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._nid_index = {g.nid: i for i, g in enumerate(self.gates)}

    def summary(self) -> str:
        n = len(self.gates)
        guarded = sum(1 for g in self.gates if g.guard >= 0)
        return f"GateRegistry({n} NAND, {guarded} guarded)"

    def cell(self, nid: int) -> GateCell:
        return self.gates[self._nid_index[nid]]

    def allocate(self, count: int, rng: np.random.Generator | None = None) -> list[GateCell]:
        """Havuzdan rastgele kapı seç."""
        rng = rng or np.random.default_rng(42)
        pool = list(self.gates)
        rng.shuffle(pool)
        return pool[:count]

    def register(self, cell: GateCell) -> None:
        if cell.nid in self._nid_index:
            return
        self._nid_index[cell.nid] = len(self.gates)
        self.gates.append(cell)


def scan_nand_cells(brain: BrainGraph, limit: int | None = None,
                     max_fanin: int = 20) -> GateRegistry:
    """Beyin çizgesinde fanin 2..max_fanin arası nöronları toplar.

    fanin>=2 olan her nöron bir potansiyel NAND kapısıdır:
    - İlk iki presinaptik gerçek giriş olarak kullanılır.
    - Kalan presinaptikler guard (koruma) sinyali olarak atanır
      (en zayıf ağırlıklılardan biri guard seçilir).
    - Gerçekte kapı devresi soyutlanmıştır: beyin nöronu kimliği korunur,
      devre topolojisi bizim tasarımımıza göredir.
    """
    print("[gate] NAND taraması başlıyor...")
    W = brain.W
    reg = GateRegistry()
    count = 0
    for target in range(brain.n_neurons):
        row_start, row_end = W.indptr[target], W.indptr[target + 1]
        fanin = row_end - row_start
        if fanin < 2 or fanin > max_fanin:
            continue
        presyn = W.indices[row_start:row_end].tolist()
        weights = W.data[row_start:row_end]
        # guard: fanin>2 ise üçüncü input, değilse en zayıf presinaptik
        if fanin > 2:
            guard = presyn[int(np.argmin(np.abs(weights[2:]))) + 2]
        else:
            guard = presyn[int(np.argmin(np.abs(weights)))]
        cell = GateCell(nid=target, presyn=presyn[:2], guard=guard, fan_in=2)
        reg.register(cell)
        count += 1
        if limit and count >= limit:
            break
    print(f"[gate] {reg.summary()}")
    return reg