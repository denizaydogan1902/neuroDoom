"""Küçük assembler: kaynak metin -> NeuroCPU-8 baytları.

Gramer:
    label:          (satır başında ":" ile biter)
    MOV R1, R2      # yorum ';' ya da '#'
Komut boyutları yalnızca mnemonic'e bağlı olduğundan etiket adresleri ilk
geçişte oturur; ikinci geçiş operanları çözer.
"""
from __future__ import annotations

from . import datasheet as ds

# mnemonic -> opcode
_ALIAS = {
    "LDI": ds.LDI, "MOV": ds.MOV, "IN": ds.IN, "OUT": ds.OUT,
    "ADD": ds.ADD, "SUB": ds.SUB, "AND": ds.AND, "OR": ds.OR,
    "XOR": ds.XOR, "NAND": ds.NAND, "SHL": ds.SHL, "SHR": ds.SHR,
    "MUL": ds.MUL, "PSH": ds.PSH, "POP": ds.POP,
    "LDA": ds.LDA, "STA": ds.STA, "JMP": ds.JMP, "CALL": ds.CALL,
    "JZ": ds.JMP, "JNZ": ds.JMP, "JC": ds.JMP, "JNC": ds.JMP,
    "RET": ds.RET, "HLT": ds.HLT,
}


def _reg(tok: str) -> int:
    tok = tok.upper()
    return int(tok[1:] if tok.startswith("R") else tok, 0)


def _num(tok: str) -> int:
    return int(tok, 0)


def _resolve(tok: str, labels: dict[str, int]) -> int:
    return labels[tok] if tok in labels else int(tok, 0)


def clean_lines(src: str) -> list[str]:
    out = []
    for raw in src.splitlines():
        s = raw.split(";")[0].split("#")[0].strip()
        if s:
            out.append(s)
    return out


def split_labels(line: str) -> tuple[list[tuple[str, str]], str]:
    """'a: b: MOV ...' -> (etiketler, geri kalan komut)."""
    labels = []
    rest = line
    while rest:
        toks = rest.split(None, 1)
        head = toks[0]
        if head.endswith(":"):
            labels.append((head[:-1],))
            rest = toks[1].strip() if len(toks) > 1 else ""
            if not rest:
                break
            continue
        break
    return labels, rest


def assemble(src: str, base: int = 0) -> tuple[list[int], dict[str, int]]:
    lines = clean_lines(src)

    # geçiş 1: etiket adresleri (uzunluk mnemonic'e bağlı, sabit)
    labels: dict[str, int] = {}
    pc = 0
    for ln in lines:
        lbls, rest = split_labels(ln)
        for lab, *_ in lbls:
            labels[lab] = pc + base
        if rest:
            mnem = rest.split()[0].upper()
            pc += ds.n_bytes(_ALIAS[mnem])

    # geçiş 2: bayt üret
    prog: list[int] = []
    for ln in lines:
        _, rest = split_labels(ln)
        if not rest:
            continue
        toks = rest.replace(",", " ").split()
        mnem = toks[0].upper()
        op = _ALIAS[mnem]

        if mnem in ("RET", "HLT"):
            insn = ds.pack(op)
        elif mnem in ("PSH", "POP"):
            insn = ds.pack(op, dst=_reg(toks[1]))
        elif mnem == "MOV":
            insn = ds.pack(op, dst=_reg(toks[1]), a=_reg(toks[2]))
        elif mnem == "LDI":
            insn = ds.pack(op, dst=_reg(toks[1]), imm=_num(toks[2]))
        elif mnem == "IN":
            insn = ds.pack(op, dst=_reg(toks[1]), port=_num(toks[2]))
        elif mnem == "OUT":
            insn = ds.pack(op, dst=_reg(toks[2]), port=_num(toks[1]))
        elif mnem in ("SHL", "SHR", "MUL"):
            insn = ds.pack(op, a=_reg(toks[1]), b=_reg(toks[2]))
        elif mnem in ("ADD", "SUB", "AND", "OR", "XOR", "NAND"):
            insn = ds.pack(op, dst=_reg(toks[1]), a=_reg(toks[2]),
                           b=_reg(toks[3]))
        elif mnem == "LDA":
            insn = ds.pack(op, dst=_reg(toks[1]), addr=_resolve(toks[2], labels))
        elif mnem == "STA":
            insn = ds.pack(op, dst=_reg(toks[2]), addr=_resolve(toks[1], labels))
        elif mnem in ("JZ", "JNZ", "JC", "JNC"):
            cond = {"JZ": ds._JZ, "JNZ": ds._JNZ,
                    "JC": ds._JC, "JNC": ds._JNC}[mnem]
            insn = ds.pack(op, dst=cond, addr=_resolve(toks[1], labels))
        else:                                  # JMP / CALL
            insn = ds.pack(op, addr=_resolve(toks[1], labels))
        prog.extend(insn)
    return prog, labels