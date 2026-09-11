"""ALU kapı devresi testleri."""
import numpy as np
from neurodoom.synth.brain import BrainGraph, load_hemibrain
from neurodoom.synth.gate_registry import scan_nand_cells
from neurodoom.synth.alu import ALU
from neurodoom import datasheet as ds


def _tiny_brain() -> BrainGraph:
    """Küçük test beyni: 256 nöron, fanin=2 çoğunlukta."""
    from scipy.sparse import lil_matrix
    rng = np.random.default_rng(42)
    n = 256
    W = lil_matrix((n, n), dtype=np.float64)
    for t in range(n):
        presyn = rng.choice(n, size=2, replace=False)
        W[presyn, t] = rng.uniform(0.5, 2.0, size=2)
    return BrainGraph(n_neurons=n, W=W.tocsr())


def test_gate_scan_finds_dual_fanin():
    brain = _tiny_brain()
    reg = scan_nand_cells(brain, limit=100)
    assert len(reg.gates) > 0


def test_adder_basic():
    brain = _tiny_brain()
    reg = scan_nand_cells(brain)
    alu = ALU(reg)
    for a, b in [(0, 0), (1, 2), (127, 1), (0xFF, 1), (0xAB, 0xCD)]:
        res, flags, energy = alu.compute(ds.ADD, a, b)
        assert res == (a + b) & 0xFF, f"ADD {a}+{b} = {res}, expected {(a+b)&0xFF}"
        assert energy > 0


def test_sub_basic():
    brain = _tiny_brain()
    reg = scan_nand_cells(brain)
    alu = ALU(reg)
    for a, b in [(5, 3), (0, 1), (0xFF, 0xFF), (0x10, 0x01)]:
        res, flags, energy = alu.compute(ds.SUB, a, b)
        assert res == (a - b) & 0xFF, f"SUB {a}-{b} = {res}"


def test_logic_ops():
    brain = _tiny_brain()
    reg = scan_nand_cells(brain)
    alu = ALU(reg)
    for a, b in [(0xFF, 0x0F), (0xAB, 0xCD), (0x55, 0xAA)]:
        assert alu.compute(ds.AND, a, b)[0] == (a & b)
        assert alu.compute(ds.OR, a, b)[0] == (a | b)
        assert alu.compute(ds.XOR, a, b)[0] == (a ^ b)


def test_alu_cycles_accumulate():
    brain = _tiny_brain()
    reg = scan_nand_cells(brain)
    alu = ALU(reg)
    start = alu.cycle_count
    alu.compute(ds.ADD, 3, 4)
    alu.compute(ds.ADD, 5, 6)
    assert alu.cycle_count > start