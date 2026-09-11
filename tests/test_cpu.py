"""CPU testleri: derlenen program, beyin kapılarından geçen CPU üzerinde koşuyor."""
import numpy as np
from scipy.sparse import lil_matrix

from neurodoom.synth.brain import BrainGraph, load_hemibrain, top_degree_neurons
from neurodoom.synth.gate_registry import scan_nand_cells
from neurodoom.synth.alu import ALU
from neurodoom.cpu.regfile import RegisterFile, build_register_bank
from neurodoom.cpu.memory import Memory
from neurodoom.cpu.cpu import NeuroCPU
from neurodoom.assembler import assemble
from neurodoom import datasheet as ds


def _cpu() -> NeuroCPU:
    """Küçük synthetic beyin üzerine inşa edilmiş bir CPU."""
    rng = np.random.default_rng(42)
    n = 1024
    W = lil_matrix((n, n), dtype=np.float64)
    for t in range(n):
        src = rng.choice(n, size=2, replace=False)
        W[src, t] = rng.uniform(0.5, 2.0, size=2)
    brain = BrainGraph(n_neurons=n, W=W.tocsr())
    reg = scan_nand_cells(brain, limit=500)
    alu = ALU(reg)
    bank = RegisterFile()     # NULL-backed (yazılımsal)
    mem = Memory()
    return NeuroCPU(alu, bank, mem)


def test_ldi_add_hlt():
    cpu = _cpu()
    prog, _ = assemble("""
        LDI R1, 5
        LDI R2, 3
        ADD R3, R1, R2
        HLT
    """)
    cpu.load(prog)
    cpu.run()
    assert cpu.state.halted
    assert cpu.reg.read(3) == 8
    assert cpu.state.gate_firings > 0


def test_sub_zero_flag():
    cpu = _cpu()
    prog, _ = assemble("""
        LDI R1, 10
        SUB R2, R1, R1
        HLT
    """)
    cpu.load(prog)
    cpu.run()
    assert cpu.state.halted
    assert cpu.reg.read(2) == 0
    assert cpu.state.flags["zero"] is True


def test_loop_call_ret():
    cpu = _cpu()
    prog, labels = assemble("""
        LDI R5, 0
        LDI R6, 3
      loop:
        LDI R1, 1
        ADD R5, R5, R1
        SUB R7, R5, R6
        JZ done
        JMP loop
      done:
        HLT
    """)
    cpu.load(prog)
    cpu.run(max_steps=500)
    assert cpu.state.halted
    assert cpu.reg.read(5) == 3


def test_io_port():
    cpu = _cpu()
    prog, _ = assemble("""
        LDI R1, 42
        OUT 0, R1
        IN  R2, 0
        HLT
    """)
    cpu.load(prog)
    cpu.run()
    assert cpu.reg.read(2) == 42


def test_push_pop():
    cpu = _cpu()
    prog, _ = assemble("""
        LDI R3, 99
        PSH R3
        LDI R3, 0
        POP R3
        HLT
    """)
    cpu.load(prog)
    cpu.run()
    assert cpu.reg.read(3) == 99


def test_lda_sta():
    cpu = _cpu()
    prog, _ = assemble("""
        LDI R4, 0x55
        STA 0x3000, R4
        LDA R5, 0x3000
        HLT
    """)
    cpu.load(prog)
    cpu.run()
    assert cpu.reg.read(5) == 0x55
    assert cpu.mem.rb(0x3000) == 0x55


def test_indirect_mem_via_mar():
    cpu = _cpu()
    prog, _ = assemble("""
        LDI R4, 0x33
        STA 0x2000, R4
        LDI R5, 0x20
        OUT 0xFE, R5       ; MAR hi = 0x20
        LDI R5, 0x00
        OUT 0xFD, R5       ; MAR lo = 0x00   -> MAR = 0x2000
        IN  R6, 0xFC       ; R6 = mem[0x2000]
        HLT
    """)
    cpu.load(prog)
    cpu.run()
    assert cpu.reg.read(6) == 0x33