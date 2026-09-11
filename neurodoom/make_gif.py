"""Gerçek hemibrain CPU'sunda çekilen karelerden yürüyüş GIF'i üretir.

Kareler: doom.c, NAND kapılarından kurulu NÖRO-8 üzerinde koşar, her sahnede
320x200 video framebuffer RAM'den okunur ve Pillow ile GIF'e birleştirilir.

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
from .palette import video_to_img

BASE = 0x1000
SCALE = 2                  # her pikselin kenar uzunluğu (320x2=640, 200x2=400)


def main() -> None:
    src = (Path(__file__).parent / "apps" / "doom.c").read_text()
    asm, vm = compile_with_map(src)
    prog, _ = assemble(asm, base=BASE)
    brain = load_hemibrain(
        Path(__file__).parent.parent / "data" / "traced-total-connections.csv",
        Path(__file__).parent.parent / "data" / "traced-neurons.csv")
    gates = scan_nand_cells(brain)
    alu = ALU(gates)

    def render(preset: tuple[int, int, int]) -> np.ndarray:
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
        return video_to_img(mem)

    sx = 8 * 16 + 8                       # 136 — oyuncu hücresi merkezi
    sy = 8 * 16 + 8
    poses = [(sx + dx * 4, sy, 64) for dx in range(0, 8)]               # doğuya yürü
    poses += [(sx + 7 * 4, sy, 96),
              (sx + 7 * 4, sy, 112),
              (sx + 7 * 4, sy, 128)]                                     # kuzeye dön
    poses += [(sx + 5 * 4, sy, 128),
              (sx + 3 * 4, sy, 128),
              (sx + 1 * 4, sy, 112)]                                     # duvara yaklaş

    frames: list[Image.Image] = []
    size = 320 * SCALE, 200 * SCALE
    for p in poses:
        img = Image.fromarray(render(p))
        if SCALE > 1:
            img = img.resize(size, Image.NEAREST)
        frames.append(img)
        print(f'kare: px={p[0]} py={p[1]} pa={p[2]}')

    dst = Path(__file__).parent.parent / "docs" / "screenshots" / "e1m1_run.gif"
    frames[0].save(dst, save_all=True, append_images=frames[1:],
                   duration=400, loop=0)
    print(f'OK: {dst}  {len(frames)} kare, {size[0]}x{size[1]}px')


if __name__ == "__main__":
    main()