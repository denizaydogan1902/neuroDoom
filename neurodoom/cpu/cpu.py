"""NeuroCPU-8: fetch / decode / execute döngüsü.

Her talimat ALU aracılığıyla beyin kapılarından geçer; PC, SP, flag'ler
yazılımsal olarak tutulur (bu bir "mikro denetleyici" — decod firmware,
ALU datapath ise kapı devresi).  Tam çapraz doğruluk: assemble edilmiş
gerçek program kodu, kapı devresinde üretilen sonuçlarla çalışır.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from .. import datasheet as ds
from ..synth.alu import ALU
from ..synth.gate_registry import GateRegistry
from .memory import Memory, STACK_TOP, MASK16
from .regfile import RegisterFile

MASK8 = 0xFF


@dataclass
class CPUState:
    pc: int = 0
    sp: int = STACK_TOP
    flags: dict = field(default_factory=lambda: {"zero": False, "carry": False})
    halted: bool = False
    cycles: int = 0
    gate_firings: int = 0
    mar: int = 0           # Memory Address Register (port ile ayarlanır)


class NeuroCPU:
    def __init__(self, alu: ALU, reg: RegisterFile, mem: Memory) -> None:
        self.alu = alu
        self.reg = reg
        self.mem = mem
        self.state = CPUState()
        self._trace: list[str] = []

    def step(self) -> str | None:
        if self.state.halted:
            return None
        pc = self.state.pc
        byte0 = self.mem.rb(pc)
        insn, off = ds._decode([self.mem.rb(pc + i) for i in range(3)], 0)
        self.state.pc = pc + off
        self.state.cycles += 1

        op = insn.op
        if op == ds.RET:
            hi = self.mem.rb(self.state.sp)      # CALL low'u yukarı, high'ı aşağı push'lar
            lo = self.mem.rb(self.state.sp + 1)
            self.state.sp = (self.state.sp + 2) & MASK16
            self.state.pc = (hi << 8) | lo
        elif op == ds.HLT:
            self.state.halted = True
        elif op == ds.LDI:
            self.reg.write(insn.dst, insn.imm)
        elif op == ds.MOV:
            self.reg.write(insn.dst, self.reg.read(insn.a))
        elif op in (ds.ADD, ds.SUB, ds.AND, ds.OR, ds.XOR, ds.NAND,
                    ds.SHL, ds.SHR, ds.MUL):
            a_val = self.reg.read(insn.a)
            b_val = self.reg.read(insn.b)
            res, flags, firings = self.alu.compute(op, a_val, b_val)
            self.reg.write(insn.dst, res)
            self.state.flags = flags
            self.state.gate_firings += firings
        elif op == ds.IN:
            port = insn.port
            if port == 0xFC:       # MEM_READ: mar'dan byte oku
                self.reg.write(insn.dst, self.mem.rb(self.state.mar))
            else:
                self.reg.write(insn.dst, self.mem.port_read(port))
        elif op == ds.OUT:
            val = self.reg.read(insn.dst)
            port = insn.port
            if port == 0xFD:       # MAR low byte
                self.state.mar = (self.state.mar & 0xFF00) | val
            elif port == 0xFE:     # MAR high byte
                self.state.mar = (self.state.mar & 0x00FF) | (val << 8)
            elif port == 0xFB:     # MEM_WRITE: yaz mar'a
                self.mem.wb(self.state.mar, val)
            else:
                self.mem.port_write(port, val)
        elif op == ds.PSH:
            self.state.sp = (self.state.sp - 1) & MASK16
            self.mem.wb(self.state.sp, self.reg.read(insn.dst))
        elif op == ds.POP:
            self.reg.write(insn.dst, self.mem.rb(self.state.sp))
            self.state.sp = (self.state.sp + 1) & MASK16
        elif op == ds.LDA:
            self.reg.write(insn.dst, self.mem.rb(insn.addr))
        elif op == ds.STA:
            self.mem.wb(insn.addr, self.reg.read(insn.dst))
        elif op == ds.JMP:
            z = self.state.flags.get("zero", False)
            c = self.state.flags.get("carry", False)
            cond = {
                0: True,                 # JMP
                1: z,                    # JZ
                2: not z,                # JNZ
                3: c,                    # JC
                4: not c,                # JNC
            }.get(insn.dst & 0xF, True)
            if cond:
                self.state.pc = insn.addr
        elif op == ds.CALL:
            ret = self.state.pc & MASK16
            self.state.sp = (self.state.sp - 1) & MASK16
            self.mem.wb(self.state.sp, ret & 0xFF)
            self.state.sp = (self.state.sp - 1) & MASK16
            self.mem.wb(self.state.sp, (ret >> 8) & 0xFF)
            self.state.pc = insn.addr
        else:
            raise RuntimeError(f"bilinmeyen opcode: {op:#x}")

        return insn.text()

    def run(self, max_steps: int = 100_000) -> list[str]:
        trace = []
        for _ in range(max_steps):
            line = self.step()
            if line is None:
                break
            trace.append(line)
        self._trace = trace
        return trace

    def load(self, prog: list[int], start: int = 0) -> None:
        self.mem.load_program(prog, start)
        self.state.pc = start
        self.state.sp = STACK_TOP
        self.state.halted = False

    def regs_snapshot(self) -> dict[str, int]:
        return {f"R{i}": self.reg.read(i) for i in range(16)}