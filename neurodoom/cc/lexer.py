"""C-çözümleyici (lexer): NeuroCPU-8 için minimal C alt kümesi.

Tokenlar: keyword'ler, tanımlayıcılar, sayı/char sabitleri, operatörler,
yorumları (//, /* */) ayıklanan kaynak.  #define basit makro genişletmesi
desteğiyle (objekt gibi sabitler).
"""
from __future__ import annotations

from dataclasses import dataclass

KEYWORDS = {
    "int", "char", "void", "if", "else", "while", "for", "return",
    "break", "continue",
}

OP2 = {"==", "!=", "<=", ">=", "&&", "||", "<<", ">>", "++", "--"}
OP1 = set("+-*/%&|^~!<>=()[]{},;:?")


@dataclass
class Token:
    kind: str            # 'id'/'num'/'str'/'ch'/'op'/'kw'/';'
    val: str | int
    line: int


def preprocess(src: str) -> str:
    """#define macrolarını genişlet (objekt benzeri sabitler)."""
    import re

    defines: dict[str, str] = {}

    def expand(line: str) -> str:
        if not defines:
            return line
        pat = re.compile(r"\b(" + "|".join(map(re.escape, defines)) + r")\b")
        for _ in range(4):                       # zincirleme makro (A→B→16)
            new = pat.sub(lambda m: defines[m.group(0)], line)
            if new == line:
                break
            line = new
        return line

    out: list[str] = []
    for raw in src.splitlines(keepends=True):
        line = raw.strip()
        if line.startswith("#define "):
            parts = line[len("#define "):].split(None, 1)
            if len(parts) == 2:
                defines[parts[0]] = parts[1]
        elif line.startswith("#include"):
            continue          # gömülü projede include yok; hepsi tek dosya
        else:
            out.append(expand(raw))
    return "".join(out)


def tokenize(src: str) -> list[Token]:
    src = preprocess(src)
    toks: list[Token] = []
    i, line = 0, 1
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        # satır yorumu
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            line += src.count("\n", i, j if j >= 0 else n)
            i = n if j < 0 else j + 2
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            if word in KEYWORDS:
                toks.append(Token("kw", word, line))
            else:
                toks.append(Token("id", word, line))
            i = j
            continue
        if c.isdigit():
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            toks.append(Token("num", int(src[i:j], 0), line))
            i = j
            continue
        if c == "'":
            j = src.index("'", i + 1)
            body = src[i + 1:j]
            val = ord(body) if len(body) == 1 else int(body, 0)
            toks.append(Token("num", val, line))
            i = j + 1
            continue
        if i + 1 < n and src[i:i + 2] in OP2:
            toks.append(Token("op", src[i:i + 2], line))
            i += 2
            continue
        if c in OP1:
            toks.append(Token("op", c, line))
            i += 1
            continue
        raise SyntaxError(f"bilinmeyen karakter {c!r} satır {line}")
    toks.append(Token("eof", "", line))
    return toks