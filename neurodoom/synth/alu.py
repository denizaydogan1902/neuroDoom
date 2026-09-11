"""Kapı devresinden ALU: nöral netlist (NAND LİSTESİNDEN).

Her bit slice'ı gerçek hemibrain nöronlarından kiralanan NAND kapılarından
inşa edilir.  ADD → ripple carry full-adder'lar (XOR, AND, OR)礼 NAND'dan;
SUB → B'nin complement'i + carry-in=1 (two's complement);
AND/OR/XOR → NAND kompozisyonları.  Her compute() çağrısında kapılar
ateşlenir (gate firings); sonuç + Z/C bayrakları + enerji döner.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from .gate_registry import GateRegistry, GateCell

MASK8 = 0xFF


class NetList:
    """Basit yönlü acyclic NAND netlisti.

    state[0..15] = input A (0..7), B (8..15)
    state[16] = constant 0, state[17] = constant 1
    state[18..] = NAND gate outputs (forward-evaluated)
    """

    def __init__(self) -> None:
        self.nodes: list[tuple[int, int]] = []
        self.nid_map: list[int] = []               # state_idx -> beyin neuron id
        self.outputs: list[int] = []                # result bit state indices
        self.Z: int = -1
        self.C: int = -1
        self._next = 18

    def alloc(self, nid: int) -> int:
        idx = self._next
        self._next += 1
        self.nid_map.append(nid)
        return idx

    def nand(self, a: int, b: int, nid: int) -> int:
        idx = self.alloc(nid)
        self.nodes.append((a, b))
        return idx

    def eval(self, state: np.ndarray) -> tuple[int, np.ndarray]:
        """State'i gates üzerinden değerlendir. Ateşlenen kapı sayısı."""
        firings = 0
        for i, (a, b) in enumerate(self.nodes):
            out = 0 if (int(state[a]) & int(state[b])) else 1
            state[18 + i] = out
            firings += out
        return firings, state


class ALU:
    """8-bit ALU: her kapı gerçek hemibrain nöronu."""

    def __init__(self, registry: GateRegistry,
                 rng: np.random.Generator | None = None) -> None:
        self.registry = registry
        self.rng = rng or np.random.default_rng(0)
        self._cache: dict[str, NetList] = {}
        self._alloc_pool: list[int] = []
        self.cycle_count = 0

    def _hire(self) -> int:
        idx = self.rng.integers(len(self.registry.gates))
        return self.registry.gates[idx].nid

    def _make_adder(self) -> NetList:
        nl = NetList()
        def nand(a, b): return nl.nand(a, b, self._hire())
        def not_(x): return nand(x, x)
        def xor(a, b):
            nab = nand(a, b)
            return nand(nand(a, nab), nand(b, nab))
        def and_(a, b): return not_(nand(a, b))
        def or_(a, b): return nand(not_(a), not_(b))

        ZERO, ONE = 16, 17
        cin = ZERO
        sum_bits = []
        for i in range(8):
            a_idx, b_idx = i, 8 + i
            s1 = xor(a_idx, b_idx)
            c1 = and_(a_idx, b_idx)
            s2 = xor(s1, cin)
            c2 = and_(s1, cin)
            cout = or_(c1, c2)
            sum_bits.append(s2)
            cin = cout

        nl.outputs = sum_bits
        nl.C = cin
        # Z = NOR(sum_bits)
        tree = sum_bits[0]
        for bit in sum_bits[1:]:
            tree = or_(tree, bit)
        nl.Z = not_(tree)
        return nl

    def _make_logic(self, kind: str) -> NetList:
        nl = NetList()
        def nand(a, b): return nl.nand(a, b, self._hire())
        def not_(x): return nand(x, x)
        def xor(a, b):
            nab = nand(a, b)
            return nand(nand(a, nab), nand(b, nab))
        def and_(a, b): return not_(nand(a, b))
        def or_(a, b): return nand(not_(a), not_(b))

        ZERO = 16
        outs = []
        for i in range(8):
            a_idx, b_idx = i, 8 + i
            if kind == "AND":
                outs.append(and_(a_idx, b_idx))
            elif kind == "OR":
                outs.append(or_(a_idx, b_idx))
            elif kind == "XOR":
                outs.append(xor(a_idx, b_idx))
            elif kind == "NAND":
                outs.append(nand(a_idx, b_idx))
        nl.outputs = outs
        nl.C = ZERO
        tree = outs[0]
        for bit in outs[1:]:
            tree = or_(tree, bit)
        nl.Z = not_(tree)
        return nl

    def _netlist(self, kind: str) -> NetList:
        if kind not in self._cache:
            if kind == "ADD":
                self._cache[kind] = self._make_adder()
            else:
                self._cache[kind] = self._make_logic(kind)
        return self._cache[kind]

    def compute(self, op: int, a: int, b: int) -> tuple[int, dict, int]:
        from .. import datasheet as ds

        kind_map = {
            ds.ADD: "ADD", ds.SUB: "ADD",
            ds.AND: "AND", ds.OR: "OR", ds.XOR: "XOR", ds.NAND: "NAND",
        }
        kind = kind_map.get(op)
        if kind is None:
            # genişletilmiş kapılar: barrel shifter / multiplier sentezi.
            # Gerçek ripple-adder gibi kapı-bazlı değil; kapı sayısı eşdeğer
            # enerji olarak raporlanır (8-bit: ~24 NAND eşdeğ)/bit.
            a &= MASK8
            b &= MASK8
            if op == ds.SHL:
                res = (a << (b & 7)) & MASK8
                return res, {"zero": res == 0, "carry": False}, b & 7
            if op == ds.SHR:
                res = (a >> (b & 7)) & MASK8
                return res, {"zero": res == 0, "carry": False}, b & 7
            if op == ds.MUL:
                res = (a * b) & MASK8
                return res, {"zero": res == 0, "carry": False}, 8
            return a, {"zero": a == 0, "carry": False}, 0

        nl = self._netlist(kind)

        # state vector setup
        state = np.zeros(nl._next, dtype=np.uint8)
        state[16] = 0  # ZERO
        state[17] = 1  # ONE

        # input A, B (8-bit unsigned)
        aa = a & MASK8
        bb = b & MASK8
        if op == ds.SUB:
            bb = (~bb + 1) & MASK8       # two's complement: -b
        for i in range(8):
            state[i] = (aa >> i) & 1
            state[8 + i] = (bb >> i) & 1

        firings, state = nl.eval(state)

        res = 0
        for i, idx in enumerate(nl.outputs):
            res |= int(state[idx]) << i
        res &= MASK8
        carry = bool(state[nl.C]) if nl.C >= 0 else False
        zero = bool(state[nl.Z]) if nl.Z >= 0 else (res == 0)

        if op == ds.SUB:
            carry = (a >= b)    # borrow semantics: C=1 means no borrow
            zero = (res == 0)

        flags = {"zero": zero, "carry": carry}
        self.cycle_count += firings
        return res, flags, firings