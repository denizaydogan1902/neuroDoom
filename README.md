# NeuroDoom

Doom running on an 8-bit CPU built from the NAND gates extracted from the
neural network of a fruit fly.

A biological brain does not play this game — **the brain's gates *are* the
hardware, and Doom is the software running on it.**

Every frame goes through real neurons traced from *Drosophila melanogaster*:
**812 NAND gates** reshape a raycasted, texture-shaded 16×16 viewport at
roughly half a million gate activations per frame.

> Cell shading: the closer a wall, the brighter the glyph.
> `#` near, `%` mid, `+`/`.` far, `<space>` void.

![Start — player at (3.5, 3.5) facing east](docs/screenshots/start.png)
![Advanced — player moved forward to (4.5, 3.5)](docs/screenshots/advanced.png)
![Turned — player rotated 90° yaw](docs/screenshots/turned.png)
![Retreat — player backed to (2.5, 3.5)](docs/screenshots/retreat.png)

> Shading model: each screen column casts one ray; distance to the wall
> selects the glyph. Movement and rotation update `px,py,pa` by
> `sintab`/`costab`, collision is a single map lookup. All of this is C,
> compiled to machine code that only the neurons above execute.

## How it works

```
Doom (C)                  neurodoom/apps/doom.c — 16×16 raycast engine
  │  compiled by our own C compiler (statics, loops, calls, #define)
  ▼
NÖRO-8 machine code        2.1KB: DDA raycaster + multiply/divide
  │  assembler → 16-bit address space, 8-bit data
  ▼
NAND netlist → ALU         a full register machine from first principles:
  │   CALL/RET stack, conditional jumps, SHL/SHR/MUL, port-mapped I/O
  ▼
Real neural hardware       Drosophila hemibrain: 21,739 neurons,
                           3,550,403 synapses → 812 NAND gates
```

The CPU, the ALU, the register file and the memory bus **do not exist apart
from the brain.** `neurodoom/synth/` turns the traced connectome into a
boolean circuit: a neuron with two strong presynaptic inputs fires only when
*both* are active — a NAND. The whole thing is evaluated gate by gate for
every instruction cycle.

## Play it

```sh
python -m venv .venv && source .venv/bin/activate
pip install numpy scipy pytest

pytest -q                       # 21 tests — CPU, compiler, brain scan

python -m neurodoom.frontpanel  # boot the fly brain and play
```

| Key     | Action            |
|---------|-------------------|
| `W`     | move forward      |
| `S`     | move backward     |
| `A` / `D` | turn left / right |
| `ESC` / `Ctrl-C` | quit       |

## Pipeline details

- `neurodoom/cc/` — the C subset compiler (globals, arrays, functions without
  pointers, `#define`, loops, conditionals, arithmetic) feeding our own
  two-pass assembler. No hand-written assembly anywhere.
- `neurodoom/cpu/` — `NeuroCPU` hosting a real `RegisterFile` built from the
  same brain; 3.5M synapses scanned once, then run as NAND gates.
- `neurodoom/screenshot.py` — regenerates the PNG captures above from actual
  gate-level execution.

## Data

- `data/traced-total-connections.csv` — 3,550,403 traced synapses
- `data/traced-neurons.csv` — 21,739 traced neurons

Everything is self-contained: the game logic lives in
`neurodoom/apps/doom.c`, the silicon in `neurodoom/synth/`, the machine in
`neurodoom/cpu/`, the toolchain in `neurodoom/cc/`. Nothing anywhere "plays"
the game for the CPU — the CPU itself is neural.