"""Datasheet + assembler testleri."""
import pytest

from neurodoom import datasheet as ds
from neurodoom.assembler import assemble


def test_pack_roundtrip():
    for insn in (
        ds.Insn(ds.MOV, dst=1, a=2),
        ds.Insn(ds.ADD, dst=3, a=1, b=2),
        ds.Insn(ds.SUB, dst=0, a=0, b=0),
        ds.Insn(ds.LDI, dst=5, imm=0xAB),
        ds.Insn(ds.LDA, dst=2, addr=0x1122),
        ds.Insn(ds.STA, dst=3, addr=0x3344),
        ds.Insn(ds.JMP, addr=0x5555),
        ds.Insn(ds.CALL, addr=0x6666),
        ds.Insn(ds.IN, dst=4, port=7),
        ds.Insn(ds.OUT, dst=4, port=3),
        ds.Insn(ds.PSH, dst=6),
        ds.Insn(ds.POP, dst=6),
        ds.Insn(ds.RET),
        ds.Insn(ds.HLT),
    ):
        buf = ds.pack(insn.op, insn.dst, insn.a, insn.b, insn.imm,
                      insn.port, insn.addr)
        got, _ = ds._decode(buf, 0)
        assert got == insn, f"{insn} != {got}"


def test_assemble_forward_label():
    src = """
        LDI R1, 5
        JMP done
        LDI R2, 99
      done:
        ADD R3, R1, R1
        HLT
    """
    prog, labels = assemble(src)
    assert labels["done"] == 7                 # LDI(2) + JMP(3) + LDI(2)
    assert prog[0:2] == ds.pack(ds.LDI, 1, imm=5)
    assert prog[2:5] == ds.pack(ds.JMP, addr=7)
    assert prog[7:9] == ds.pack(ds.ADD, 3, 1, 1)


def test_disasm_smoke():
    prog, _ = assemble("""
        LDI R3, 0x20
        MOV R1, R3
        JMP loop
    loop:
        HLT
    """)
    lines = ds.disasm(prog)
    assert lines[0] == "LDI R3, 32"
    assert lines[-1] == "HLT"