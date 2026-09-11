"""Gerçek hemibrain CPU'sunda çekilen karelerden yürüyüş GIF'i üretir.

Kareler: doom.c, NAND kapılarından kurulu NÖRO-8 üzerinde koşar, her sahnede
framebuffer RAM'den okunur ve Pillow ile GIF'e birleştirilir.

Kullanım:  python -m neurodoom.make_gif
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .cc.compiler import compile_with_map
from .assembler import assemble
from .synth.brain import load_hemibrain
from .synth.gate_registry import scan_nand_cells
from .synth.alu import ALU
from .cpu.regfile import RegisterFile
from .cpu.memory import Memory
from .cpu.cpu import NeuroCPU

BASE = 0x1000
SCALE = 24                 # her pikselin kenar uzunluğu
PALET = {
    ' ': (12, 12, 14),
    '.': (58, 60, 66),
    '+': (116, 108, 96),
    '%': (178, 162, 122),
    '#': (238, 222, 182),
}


def _frame(cpu_ready: tuple, vm: dict, preset: tuple[int, int, int]) -> np.ndarray:
    raise NotImplementedError


def main() -> None:
    src = (Path(__file__).parent / "apps" / "doom.c").read_text()
    asm, vm = compile_with_map(src)
    prog, _ = assemble(asm, base=BASE)
    brain = load_hemibrain(
        Path(__file__).parent.parent / "data" / "traced-total-connections.csv",
        Path(__file__).parent.parent / "data" / "traced-neurons.csv")
    gates = scan_nand_cells(brain)
    alu = ALU(gates)

    def render(preset: tuple[int, int, int]) -> list[list[str]]:
        mem = Memory()
        mem.load_program(prog, BASE)
        cpu = NeuroCPU(alu, RegisterFile(brain), mem)
        cpu.state.pc = BASE
        frames = 0
        while frames < 2:                 # 1. kare: __f_main pozisyon yazar
            cpu.step()
            if mem.ports.get(2, None):
                mem.ports[2] = 0
                frames += 1
                if frames == 1 and preset:
                    mem.ram[vm['px']] = preset[0] & 0xFF
                    mem.ram[vm['py']] = preset[1] & 0xFF
                    mem.ram[vm['pa']] = preset[2] & 0xFF
        s = vm['screen']
        return [[chr(int(mem.ram[s + y * 16 + x])) for x in range(16)]
                for y in range(16)]

    sx = 4 * 32 + 16
    poses = [(sx + dx * 6, 4 * 32 + 16, 16) for dx in range(0, 7)]      # doğuya yürü
    poses += [(sx + 6 * 6, 4 * 32 + 16, 24),
              (sx + 6 * 6, 4 * 32 + 16, 32),
              (sx + 6 * 6, 4 * 32 + 16, 40)]                             # dön
    poses += [(sx + 7 * 6, 4 * 32 + 16, 48),
              (sx + 5 * 6, 4 * 32 + 16, 48)]                             # geri gel

    frames: list[Image.Image] = []
    size = 16 * SCALE
    for p in poses:
        chars = render(p)
        img = Image.new('RGB', (size, size))
        px = img.load()
        for y in range(16):
            for x in range(16):
                c = PALET.get(chars[y][x], PALET[' '])
                for yy in range(SCALE):
                    for xx in range(SCALE):
                        px[x * SCALE + xx, y * SCALE + yy] = c
        frames.append(img)
        print(f'kare: px={p[0]} pa={p[2]}  ({p[1]},{p[0]} convarsız)')

    dst = Path(__file__).parent.parent / "docs" / "screenshots" / "e1m1_run.gif"
    frames[0].save(dst, save_all=True, append_images=frames[1:],
                   duration=350, loop=0)
    print(f'OK: {dst}  {len(frames)} kare, {size}x{size}px')


if __name__ == "__main__":
    main()