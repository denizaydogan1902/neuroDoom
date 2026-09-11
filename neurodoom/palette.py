"""Doom.c framebuffer piksellerini renge çeviren ortak palet.

doom.c her pencereyi byte olarak basar (port 0x92, kolon-major video[]):
    32  = tavan / boşluk (koyu)
    46  = yakın zemin  ('~' uzak zemin = 126)
    48..111 = 8 doku rengi x 8 uzaklık gölgesi = 64 duvar tonu

PNG üretiminde (screenshot/GIF) RGB, terminalde (frontpanel) 256-renk ANSI
aynı palette dayanır — piksel ne derse o.
"""
from __future__ import annotations

import numpy as np

# Her doku: (uzak, koyu) -> (yakın, parlak) uc renkleri.
_TEX = [
    ((46, 48, 52), (150, 154, 164)),     # 0  beton-gri
    ((40, 62, 88), (120, 178, 224)),     # 1  çelik mavi
    ((92, 66, 30), (196, 158, 100)),     # 2  pas / kahve
    ((54, 84, 52), (150, 208, 128)),     # 3  askeri yeşil
    ((92, 40, 34), (206, 122, 96)),      # 4  kırmızı tuğla / metal
    ((56, 84, 88), (130, 208, 200)),     # 5  turkuaz makine
    ((84, 54, 104), (190, 140, 220)),    # 6  mor lamba/panel
    ((104, 92, 36), (232, 210, 120)),    # 7  sarı uyarı şeridi
]

WALL_BASE = 48                          # 48 + tex*8 + gölge (0..63)
FLOOR_NEAR = (132, 130, 124)
FLOOR_FAR = (50, 50, 55)
VOID = (10, 10, 12)


def build_palette() -> dict[int, tuple[int, int, int]]:
    pal: dict[int, tuple[int, int, int]] = {}
    for t in range(8):
        dark, light = _TEX[t]
        for s in range(8):               # s=7 yakın, s=0 uzak
            f = 0.35 + s / 7 * 0.75      # uzak koyu -> yakın parlak
            col = tuple(int(dark[i] + (light[i] - dark[i]) * f) for i in range(3))
            pal[WALL_BASE + t * 8 + s] = col
    pal[32] = VOID
    pal[46] = FLOOR_NEAR
    pal[126] = FLOOR_FAR
    return pal


PALET = build_palette()

SCREEN_W, SCREEN_H = 320, 200


def video_to_img(mem) -> np.ndarray:
    """Kolon-major framebuffer (video[x*H + y]) -> (H, W, 3) RGB."""
    v = np.asarray(mem.video, dtype=np.uint8).reshape(SCREEN_W, SCREEN_H)
    img = np.empty((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
    for y in range(SCREEN_H):
        for x in range(SCREEN_W):
            img[y, x] = PALET.get(int(v[x, y]), VOID)
    return img


def ansi256(rgb: tuple[int, int, int]) -> int:
    """RGB'yi terminal 256-renk koduna çevir (0..255)."""
    r, g, b = rgb
    ri = round(r / 255 * 5)
    gi = round(g / 255 * 5)
    bi = round(b / 255 * 5)
    if ri == gi == bi:
        return 232 + round(r / 255 * 23)
    return 16 + 36 * ri + 6 * gi + bi


def ascii_repr(img: np.ndarray) -> list[str]:
    """RGB kareyi ANSI kodlu satırlara çevir (terminal önizleme)."""
    rows = []
    for y in range(img.shape[0]):
        row = []
        for x in range(img.shape[1]):
            rgb = tuple(int(c) for c in img[y, x])
            row.append('\x1b[48;5;%dm ' % ansi256(rgb))
        rows.append(''.join(row))
    return rows