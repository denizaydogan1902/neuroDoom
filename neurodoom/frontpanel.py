"""NÖRODOOM ön paneli — beyin kapılarından kurulu CPU'nun oyun ekranı.

Gerçek hemibrain NAND kapılarından NetList-ALU ile çalışan NeuroCPU-8,
gömülü C derleyicimizin derlediği doom.c dosyasını çalıştırır.
320x200 video framebuffer'ı terminalde indirgenmiş boyutta (80x50)
ANSI 256-renk bloklar olarak çizer.

Çalıştır:  python -m neurodoom.frontpanel
"""
from __future__ import annotations

import os
import select
import sys
import termios
import tty
import time
from pathlib import Path

from .cc.compiler import compile_with_map
from .assembler import assemble
from .synth.brain import load_hemibrain
from .synth.gate_registry import scan_nand_cells
from .synth.alu import ALU
from .cpu.regfile import RegisterFile
from .cpu.memory import Memory
from .cpu.cpu import NeuroCPU
from .palette import PALET, ansi256, SCREEN_W, SCREEN_H

BASE = 0x1000
# Terminal için 320x200 -> 80x50 (her 4 piksel 1, her 4 satır 1 blok)
DW, DH = 80, 50
STEP_X = SCREEN_W // DW
STEP_Y = SCREEN_H // DH


def build_environment() -> tuple[NeuroCPU, Memory, dict, dict]:
    src = (Path(__file__).parent / "apps" / "doom.c").read_text()
    asm, varmap = compile_with_map(src)
    prog, labels = assemble(asm, base=BASE)
    brain = load_hemibrain(
        Path(__file__).parent.parent / "data" / "traced-total-connections.csv",
        Path(__file__).parent.parent / "data" / "traced-neurons.csv")
    gates = scan_nand_cells(brain)
    mem = Memory()
    mem.load_program(prog, BASE)
    cpu = NeuroCPU(ALU(gates), RegisterFile(brain), mem)
    cpu.state.pc = BASE
    return cpu, mem, varmap, labels


def draw_frame(mem: Memory, varmap: dict, port_log: list[int]) -> None:
    out = ["\x1b[H"]
    for sy in range(DH):
        row = ""
        for sx in range(DW):
            # Kolum-major: video[x*200 + y]
            v = int(mem.video[(sx * STEP_X) * SCREEN_H + (sy * STEP_Y)])
            rgb = PALET.get(v, (10, 10, 12))
            row += "\x1b[48;5;%dm " % ansi256(rgb)
        out.append(row + "\x1b[0m")
    px = int(mem.ram[varmap["px"]]) / 16.0
    py = int(mem.ram[varmap["py"]]) / 16.0
    pa = int(mem.ram[varmap["pa"]])
    firings = port_log[-1] if port_log else 0
    out.append(f"\x1b[0;90m pos=({px:.1f},{py:.1f}) pa={pa} "
               f"frames={len(port_log)} firings={firings}\x1b[0m")
    sys.stdout.write("\n".join(out))
    sys.stdout.flush()


def read_keys(fd: int, timeout: float = 0.0) -> list[str]:
    keys: list[str] = []
    while True:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            break
        ch = os.read(fd, 3).decode(errors="replace")
        if not ch:
            break
        for k in ch:
            if ord(k) == 3 or ord(k) == 27:     # Ctrl-C / ESC
                raise KeyboardInterrupt
            if k.lower() in "wasd":
                keys.append(k)
        timeout = 0.0
    return keys


def run() -> None:
    cpu, mem, varmap, labels = build_environment()
    port_log: list[int] = []                     # her skyma fire sayısı

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        print("\x1b[2J\x1b[?25l")
        steps = 0
        while True:
            try:
                keys = read_keys(fd, 0.04)
            except KeyboardInterrupt:
                break
            if keys:
                mem.ports[0] = ord(keys[-1]) & 0xFF    # klavye → port 0
            cpu.step()
            steps += 1
            # frame sync: port 2'ye yazıldığında ekranı çiz
            if mem.ports.get(2, None):
                mem.ports[2] = 0
                port_log.append(cpu.state.gate_firings)
                draw_frame(mem, varmap, port_log)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print("\x1b[0m\x1b[?25h\x1b[H")