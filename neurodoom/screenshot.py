"""Gerçek hemibrain CPU'sundan PNG ekran görüntüleri üretir.

Her sahne: beyin kapılarından kurulan NÖRO-8 üzerinde doom.c'nin ilk
kareleri koşar, framebuffer'ın sahibi olan RAM bölgesi ham olarak okunur
ve 16x16 piksellik görüntü komşu-katlanarak (nearest) PNG'ye yazılır.

Kullanım:  python -m neurodoom.screenshot
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

from .cc.compiler import compile_with_map
from .assembler import assemble
from .synth.brain import load_hemibrain
from .synth.gate_registry import scan_nand_cells
from .synth.alu import ALU
from .cpu.regfile import RegisterFile
from .cpu.memory import Memory
from .cpu.cpu import NeuroCPU

BASE = 0x1000
FACTOR = 36              # her pikselin kenar uzunluğu
# gölgelendirme paleti → ışıklı sıcak tonlar (Wolfenstein 3D havası)
PALET = {
    ' ': (12, 12, 14),
    '.': (58, 60, 66),
    '+': (116, 108, 96),
    '%': (178, 162, 122),
    '#': (238, 222, 182),
}


def _png(path: Path, rgb: np.ndarray) -> None:
    h, w, _ = rgb.shape

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + row.tobytes() for row in rgb)
    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))
    path.write_bytes(data)


def capture() -> dict[str, np.ndarray]:
    asm, varmap = compile_with_map(
        (Path(__file__).parent / "apps" / "doom.c").read_text())
    prog, _labels = assemble(asm, base=BASE)
    brain = load_hemibrain(
        Path(__file__).parent.parent / "data" / "traced-total-connections.csv",
        Path(__file__).parent.parent / "data" / "traced-neurons.csv")
    gates = scan_nand_cells(brain)

    def frame(preset: tuple[int, int, int] | None) -> np.ndarray:
        mem = Memory()
        mem.load_program(prog, BASE)
        cpu = NeuroCPU(ALU(gates), RegisterFile(brain), mem)
        cpu.state.pc = BASE
        frames = 0
        while frames < 2:                 # 1. kare: __f_main pozisyonu yazar
            cpu.step()
            if mem.ports.get(2, None):
                mem.ports[2] = 0
                frames += 1
                if frames == 1 and preset:
                    mem.ram[varmap['px']] = preset[0] & 0xFF
                    mem.ram[varmap['py']] = preset[1] & 0xFF
                    mem.ram[varmap['pa']] = preset[2] & 0xFF
        scr = varmap['screen']
        cells = [[chr(int(mem.ram[scr + y * 16 + x])) for x in range(16)]
                 for y in range(16)]
        img = np.zeros((16 * FACTOR, 16 * FACTOR, 3), dtype=np.uint8)
        for y in range(16):
            for x in range(16):
                img[y * FACTOR:(y + 1) * FACTOR, x * FACTOR:(x + 1) * FACTOR] \
                    = PALET.get(cells[y][x], PALET[' '])
        return img, cpu.state.gate_firings

    out: dict[str, np.ndarray] = {}
    out["start"] = frame(None)[0]                    # E1M1 spawn (144,144,16=Doğu)
    out["advanced"] = frame((176, 144, 16))[0]       # koridorda doğuya yürümüş
    out["turned"] = frame((144, 144, 32))[0]         # sola dönmüş (Kuzey)
    out["retreat"] = frame((112, 144, 16))[0]        # girişe doğru geri
    return out


def main() -> None:
    shots = capture()
    dst = Path(__file__).parent.parent / "docs" / "screenshots"
    dst.mkdir(parents=True, exist_ok=True)
    for name, img in shots.items():
        _png(dst / f"{name}.png", img)
        print(f"{name}.png  {img.shape[1]}x{img.shape[0]}px")


if __name__ == "__main__":
    main()