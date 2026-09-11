"""NeuroCPU-8 veri sayfası: komut seti, kodlama, çözümleme, sökücü.

Çok sade bir 8-bit RISC. R0 toprağa bağlıdır (yazma yok sayılır).
Bayraklar: Z (sıfır), C (taşıma/borç). Adresler 16-bit, büyük-endian.

Kodlama (1..3 byte):
    tek    : PSH/POP/RET/HLT               (RET=0xFF, HLT=0xFE)
    2 byte : MOV/ALU/LDI/IN/OUT + 1 operan
             byte0[7:4]=op, byte0[3:0]=dst  (MOV için byte1[7:4]=src;
             ADD..NAND için byte1[7:4]=a, byte1[3:0]=b; LDI: byte1=imm)
    3 byte : LDA/STA/JMP/CALL + adr16      (byte0[3:0]=reg)
             JMP/CALL byte0[3:0]=0xFF_ignored

Assembler satırları (bölge harfleri önemsiz):
    MOV Rr, Ra         ADD Rr, Ra, Rb      SUB...
    LDI Rr, imm        IN Rr, port         OUT port, Rr
    PSH Rr             POP Rr              RET              HLT
    LDA Rr, 0xADDR     STA 0xADDR, Rr
    JMP 0xADDR         CALL 0xADDR
"""
from __future__ import annotations

from dataclasses import dataclass

# opcode'lar (byte0 yüksek nibble; RET/HLT tekil özel bayt)
MOV = 0x0
ADD = 0x1
SUB = 0x2
AND = 0x3
OR = 0x4
XOR = 0x5
NAND = 0x6
LDI = 0x7
IN = 0x8
OUT = 0x9
PSH = 0xA
POP = 0xB
LDA = 0xC
STA = 0xD
JMP = 0xE
CALL = 0xF
RET = 0xFF
HLT = 0xFE
# genişletilmiş kapılar (C derleyicisi için; CALL R1/2/3 asla üretilmez,
# bu yüzden 0xF1..F3 slotları boşta sayılır)
SHL = 0xF1
SHR = 0xF2
MUL = 0xF3

_NAME = {
    MOV: "MOV", ADD: "ADD", SUB: "SUB", AND: "AND", OR: "OR", XOR: "XOR",
    NAND: "NAND", LDI: "LDI", IN: "IN", OUT: "OUT", PSH: "PSH", POP: "POP",
    LDA: "LDA", STA: "STA", JMP: "JMP", CALL: "CALL", RET: "RET", HLT: "HLT",
    SHL: "SHL", SHR: "SHR", MUL: "MUL",
}

_ONE_BYTE = {RET, HLT}                       # operansız özel baytlar
_TWO_BYTE = {MOV, ADD, SUB, AND, OR, XOR, NAND, LDI, IN, OUT, SHL, SHR, MUL}
_THREE_BYTE = {LDA, STA, JMP, CALL}
_REG_BYTE = {PSH, POP}                       # tek byte, düşük nibble = reg


@dataclass
class Insn:
    op: int
    dst: int = 0     # hedef reg (STA için kaynak reg)
    a: int = 0
    b: int = 0
    imm: int = 0
    port: int = 0
    addr: int = 0

    def text(self) -> str:
        n = _NAME[self.op]
        if self.op == MOV:
            return f"MOV R{self.dst}, R{self.a}"
        if self.op in (ADD, SUB, AND, OR, XOR, NAND):
            return f"{n} R{self.dst}, R{self.a}, R{self.b}"
        if self.op in (SHL, SHR, MUL):
            return f"{n} R{self.a}, R{self.b}"
        if self.op == LDI:
            return f"LDI R{self.dst}, {self.imm}"
        if self.op == IN:
            return f"IN R{self.dst}, {self.port}"
        if self.op == OUT:
            return f"OUT {self.port}, R{self.dst}"
        if self.op in (PSH, POP):
            return f"{n} R{self.dst}"
        if self.op == LDA:
            return f"LDA R{self.dst}, 0x{self.addr:04x}"
        if self.op == STA:
            return f"STA 0x{self.addr:04x}, R{self.dst}"
        if self.op == JMP:
            cn = _COND_NAME.get(self.dst & 0xF, "JMP")
            return f"{cn} 0x{self.addr:04x}"
        if self.op == CALL:
            return f"CALL 0x{self.addr:04x}"
        if self.op == RET:
            return "RET"
        return "HLT"


# ---- encode/decode ----------------------------------------------------------
def pack(op: int, dst=0, a=0, b=0, imm=0, port=0, addr=0) -> list[int]:
    """Komutu byte listesine dönüştürür."""
    if op in _ONE_BYTE:
        return [op]
    if op in (SHL, SHR, MUL):                       # tam-byte genişletilmiş
        return [op, ((a & 0xF) << 4) | (b & 0xF)]
    out = [((op & 0xF) << 4) | (dst & 0xF)]
    if op in _REG_BYTE:
        return out
    if op in _TWO_BYTE:
        if op == MOV:
            out.append((a & 0xF) << 4)
        elif op in (ADD, SUB, AND, OR, XOR, NAND, SHL, SHR, MUL):
            out.append(((a & 0xF) << 4) | (b & 0xF))
        elif op == LDI:
            out.append(imm & 0xFF)
        else:                                # IN/OUT potu
            out.append(port & 0xFF)
    elif op in _THREE_BYTE:
        out.append((addr >> 8) & 0xFF)
        out.append(addr & 0xFF)
    return out


_JZ  = 0x1
_JNZ = 0x2
_JC  = 0x3
_JNC = 0x4
_COND_NAME = {0: "JMP", _JZ: "JZ", _JNZ: "JNZ", _JC: "JC", _JNC: "JNC"}


def n_bytes(op: int) -> int:
    if op in _ONE_BYTE:
        return 1
    if op in _REG_BYTE:
        return 1
    if op in _TWO_BYTE:
        return 2
    if op in _THREE_BYTE:
        return 3
    raise ValueError(f"bilinmeyen opcode {op:#x}")


def _decode(buf: list[int], pc: int) -> tuple[Insn, int]:
    """buf[pc]'den bir komut ve yeni pc döner."""
    byte0 = buf[pc]
    op = byte0 >> 4
    dst = byte0 & 0xF
    if byte0 in (RET, HLT):                 # tekil özel baytlar
        return Insn(byte0), pc + 1
    if byte0 == SHL:
        ob = buf[pc + 1]
        return Insn(SHL, dst=1, a=ob >> 4, b=ob & 0xF), pc + 2
    if byte0 == SHR:
        ob = buf[pc + 1]
        return Insn(SHR, dst=1, a=ob >> 4, b=ob & 0xF), pc + 2
    if byte0 == MUL:
        ob = buf[pc + 1]
        return Insn(MUL, dst=1, a=ob >> 4, b=ob & 0xF), pc + 2

    if op in (ADD, SUB, AND, OR, XOR, NAND):
        ob = buf[pc + 1]
        return Insn(op, dst=dst, a=ob >> 4, b=ob & 0xF), pc + 2
    if op == MOV:
        ob = buf[pc + 1]
        return Insn(op, dst=dst, a=ob >> 4), pc + 2
    if op == LDI:
        return Insn(op, dst=dst, imm=buf[pc + 1]), pc + 2
    if op in (IN, OUT):
        return Insn(op, dst=dst, port=buf[pc + 1]), pc + 2
    if op in (LDA, STA):
        addr = (buf[pc + 1] << 8) | buf[pc + 2]
        return Insn(op, dst=dst, addr=addr), pc + 3
    if op == JMP:
        addr = (buf[pc + 1] << 8) | buf[pc + 2]
        return Insn(op, dst=dst, addr=addr), pc + 3
    if op == CALL:
        addr = (buf[pc + 1] << 8) | buf[pc + 2]
        return Insn(op, addr=addr), pc + 3
    if op in (PSH, POP):
        return Insn(op, dst=dst), pc + 1
    raise ValueError(f"çözülemeyen komut baytı: {byte0:#04x} @ {pc:#06x}")


def disasm(buf: list[int]) -> list[str]:
    out = []
    pc = 0
    while pc < len(buf):
        insn, pc = _decode(buf, pc)
        out.append(insn.text())
    return out