"""Doom.c framebuffer piksellerini renge çeviren ortak palet.

doom.c her pencereyi byte olarak basar (port 0x92, kolon-major video[]):
    0..15   = zemin mesafe tonları (yakın parlak -> uzak koyu)
    16..23  = gökyüzü gradyanı (17 üst koyu, 20 pus bandı UFC)
    48..111 = 8 doku rengi x 8 uzaklık gölgesi = 64 duvar tonu

PNG üretiminde (screenshot/GIF) RGB, terminalde (frontpanel) 256-renk ANSI
aynı palette dayanır — piksel ne derse o.
"""
from __future__ import annotations

import numpy as np

# Her doku: (uzak, koyu) -> (yakın, parlak) uç renkleri. Doom E1M1'in
# "hangar" dokusuna yakın, doygunluğu düşük teknoloji-metal tonları.
_TEX = [
    ((56, 62, 56), (168, 172, 158)),     # 0 STARTAN-gri; gri-yeşil beton
    ((58, 66, 80), (148, 164, 184)),     # 1 çelik mavi panel
    ((78, 60, 42), (186, 152, 116)),     # 2 paslı boru / kahverengi
    ((62, 84, 62), (150, 182, 140)),     # 3 askeri yeşil (STARTAN3)
    ((84, 50, 44), (180, 118, 100)),     # 4 tuğla-kırmızı kompresör
    ((50, 78, 82), (132, 188, 186)),     # 5 teal/Gray 7 makine
    ((74, 70, 50), (186, 176, 138)),     # 6 kamuflaj zeytin
    ((46, 48, 52), (138, 142, 146)),     # 7 (farklı gri ton)
]

WALL_BASE = 48

# Gökyüzü: 16 en üstte koyu ... 20 ufka doğru pus bandı artar.
_SKY = [
    (38, 48, 64),    # 16 derin
    (48, 62, 82),    # 17
    (58, 74, 96),    # 18
    (72, 90, 112),   # 19 pus (ufuk alt bandı)
    (86, 104, 126),  # 20 en aydınlık ufuk
]

# Zemin: 0 uzak-koyu ... 15 yakın-parlak
_FLOOR = [(20 + int(i * 6.5), 20 + int(i * 6.5), 24 + int(i * 7.0))
          for i in range(16)]

VOID = (10, 10, 12)


def build_palette() -> dict[int, tuple[int, int, int]]:
    pal: dict[int, tuple[int, int, int]] = {}
    for i, col in enumerate(_FLOOR):
        pal[i] = col
    for i, col in enumerate(_SKY):
        pal[16 + i] = col
    for t in range(8):
        dark, light = _TEX[t]
        for s in range(8):               # s=7 yakın, s=0 uzak
            f = 0.35 + s / 7 * 0.75
            pal[WALL_BASE + t * 8 + s] = tuple(
                int(dark[i] + (light[i] - dark[i]) * f) for i in range(3))
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