"""Beyin netlist yükleme: hemibrain CSV → seyrek çizge + istatistikler.

Her nöron bir düğüm, her sinaps bir yönlü kenardır. Tüm hemibrain
ağırlıkları pozitif (kimyasal salınım = 100% eksitasyon) olduğundan
"NAND sentezi" farklı bir面对面对面 bakar: fanin=2 nöronlarını高尔奇 hücresi
olarak alır, "--guard fallback" ile en zayıf presinaptiği koruma olarak
atar.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np
from scipy.sparse import csr_array, lil_matrix


@dataclass
class BrainGraph:
    """Seyrek çizge + istatistik."""
    n_neurons: int
    W: csr_array            # n×n, W[i][j] = j→i ağırlık (veya j→i directed)
    W_in: csr_array | None = None   # transpoz
    name: str = "hemibrain"
    neuron_ids: list[int] | None = None
    neuron_types: list[str] | None = None

    def __post_init__(self):
        self.W_in = self.W.T.tocsr() if self.W_in is None else self.W_in

    def stats(self) -> dict:
        n_edges = self.W.nnz
        n_exc = int((self.W.data > 0).sum())
        n_inh = int((self.W.data <= 0).sum())
        fan_in = n_edges / self.n_neurons if self.n_neurons else 0
        return dict(name=self.name, neurons=self.n_neurons,
                    synapses=n_edges, exc=n_exc, inh=n_inh,
                    sparsity=n_edges / (self.n_neurons ** 2),
                    avg_fan_in=fan_in)

    def __repr__(self):
        s = self.stats()
        return f"BrainGraph({s['neurons']}N/{s['synapses']}E)"


def load_hemibrain(connections_csv: Path, neurons_csv: Path | None = None,
                   name: str = "hemibrain-v1.2") -> BrainGraph:
    """Daha büyük boyutlu CSV'yi np.loadtxt ile okur, CSR'ye dönüştürür."""
    print(f"[brain] {connections_csv.name} yükleniyor...")
    raw = np.loadtxt(connections_csv, dtype=np.int64, delimiter=",",
                     skiprows=1)  # başlık satırını atla (bodyId_pre,bodyId_post,weight)
    id_set: set[int] = set()
    ext_ids: list[int] = []
    seen: set[int] = set()
    for col in (0, 1):
        for i in raw[:, col]:
            if i not in seen:
                ext_ids.append(int(i))
                seen.add(i)
    ext_ids.sort()
    remap = {old: new for new, old in enumerate(ext_ids)}
    n = len(ext_ids)
    print(f"[brain] {n} benzersiz nöron, {len(raw)} sinaps")

    rows = np.array([remap[int(r)] for r in raw[:, 0]], dtype=np.int32)
    cols = np.array([remap[int(r)] for r in raw[:, 1]], dtype=np.int32)
    data = np.array(raw[:, 2], dtype=np.float64)
    sp = lil_matrix((n, n), dtype=np.float64)
    sp[rows, cols] = data
    W = sp.tocsr()

    # nöron tipleri (varsa)
    neuron_types: list[str] | None = None
    if neurons_csv and neurons_csv.exists():
        try:
            neuron_info = np.genfromtxt(neurons_csv, delimiter=",",
                                        names=True, dtype=None,
                                        encoding="utf-8")
            if "type" in neuron_info.dtype.names:
                id_col = neuron_info.dtype.names[0]
                type_col = "type"
                id_map = {int(neuron_info[i][id_col]): str(neuron_info[i][type_col])
                          for i in range(len(neuron_info))}
                neuron_types = [id_map.get(eid, "") for eid in ext_ids]
        except Exception:
            neuron_types = None

    return BrainGraph(n_neurons=n, W=W, name=name,
                      neuron_ids=ext_ids, neuron_types=neuron_types)


def top_degree_neurons(brain: BrainGraph, k: int,
                       outgoing: bool = True) -> list[int]:
    mat = brain.W if outgoing else brain.W_in
    deg = np.diff(mat.indptr)
    return np.argsort(deg)[::-1][:k].astype(int).tolist()