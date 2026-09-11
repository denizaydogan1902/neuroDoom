"""C derleyicisi testleri: C → asm → brain-gate CPU üzerinde koş."""
import pytest
from neurodoom.cc.compiler import compile_c
from neurodoom.assembler import assemble
from neurodoom import datasheet as ds

# test CPU (gate-registry üzerine kurulu) -------------------------------------------------
from scipy.sparse import lil_matrix
import numpy as np
from neurodoom.synth.brain import BrainGraph
from neurodoom.synth.gate_registry import scan_nand_cells
from neurodoom.synth.alu import ALU
from neurodoom.cpu.regfile import RegisterFile
from neurodoom.cpu.memory import Memory
from neurodoom.cpu.cpu import NeuroCPU


def _cpu():
    rng = np.random.default_rng(7)
    n = 512
    W = lil_matrix((n, n), dtype=np.float64)
    for t in range(n):
        s = rng.choice(n, size=2, replace=False)
        W[s, t] = rng.uniform(0.5, 2.0, size=2)
    reg = scan_nand_cells(BrainGraph(n_neurons=n, W=W.tocsr()), limit=400)
    return NeuroCPU(ALU(reg), RegisterFile(), Memory())


def _run(c_src: str, max_steps: int = 20000) -> NeuroCPU:
    asm = compile_c(c_src)
    prog, labels = assemble(asm)
    cpu = _cpu()
    cpu.load(prog)
    cpu.run(max_steps=max_steps)
    return cpu


def test_basic_arithmetic():
    cpu = _run("""
        int x;
        int main() { x = 5 + 3; return x; }
    """)
    assert cpu.reg.read(1) == 8


def test_while_loop():
    cpu = _run("""
        int i;
        int main() { i = 0; while (i < 5) { i = i + 1; } return i; }
    """)
    assert cpu.reg.read(1) == 5


def test_for_and_array():
    cpu = _run("""
        int arr[4];
        int s;
        int main() {
            s = 0;
            for (int j = 0; j < 4; j = j + 1) { arr[j] = j; }
            for (int j = 0; j < 4; j = j + 1) { s = s + arr[j]; }
            return s;
        }
    """)
    assert cpu.reg.read(1) == 6


def test_function_call_and_if():
    cpu = _run("""
        int double_it(int a) { return a + a; }
        int main() {
            int r;
            r = double_it(21);
            if (r > 40) { return 99; }
            return 0;
        }
    """)
    assert cpu.reg.read(1) == 99


def test_shifts_and_mul():
    cpu = _run("""
        int main() { return (2 << 2) + (16 >> 2) + (3 * 5); }
    """)
    assert cpu.reg.read(1) == 8 + 4 + 15


def test_assign_in_condition():
    cpu = _run("""
        int main() {
            int a;
            a = 0;
            if (a == 0) { a = 7; }
            return a;
        }
    """)
    assert cpu.reg.read(1) == 7