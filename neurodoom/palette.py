"""Doom.c framebuffer piksellerini renge çeviren ortak palet.

doom.c her duvar pikselini 'A'..'p' arası bir karaktere yerleştirir:
    8 doku rengi x 6 uzaklık gölgesi = 48 ton.
Ek karakterler: ' ' tavan/boşluk, '.' yakın zemin, '~' uzak zemin.

PNG üretiminde (screenshot/GIF) RGB, terminalde (frontpanel) 256-renk ANSI
aynı palette dayanır — piksel ne derse o.
"""
from __future__ import annotations

# Her doku: (uzak, koyu) -> (yakın, parlak) uc renkleri.
# Doku 0 = beton/gri (E1M1 duvarları), diğerleri makine/teneke/metal aksanları.
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

FLOOR_NEAR = (128, 126, 122)
FLOOR_FAR = (46, 46, 50)
VOID = (8, 8, 10)


def glow_chars(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)


def build_palette() -> dict[str, tuple[int, int, int]]:
    pal: dict[str, tuple[int, int, int]] = {}
    for t in range(8):
        dark, light = _TEX[t]
        for s in range(6):                       # s=5 yakın, s=0 uzak
            f = 0.35 + s / 5 * 0.75              # uzak koyu -> yakın parlak
            col = tuple(int(d + (l - d) * f) for d, l in zip(dark, light))
            pal[chr(ord('A') + t * 6 + s)] = col
    pal[' '] = VOID
    pal['-'] = VOID
    pal['.'] = FLOOR_NEAR
    pal['~'] = FLOOR_FAR
    return pal


PALET = build_palette()


def ansi256(rgb: tuple[int, int, int]) -> int:
    """RGB'yi terminal 256-renk koduna çevir (0..255)."""
    r, g, b = rgb
    # 6x6x6 küp (index 16..231) — gri dışı renkler için daha isabetli.
    ri = round(r / 255 * 5)
    gi = round(g / 255 * 5)
    bi = round(b / 255 * 5)
    if ri == gi == bi:
        return 232 + round(r / 255 * 23)
    return 16 + 36 * ri + 6 * gi + bi


def ascii_repr(pixmap: list[list[str]]) -> list[str]:
    """Donuk karakter mayını döndürür: renkleri ANSI kodlarıyla sarmala."""
    rows = []
    for row in pixmap:
        rows.append(''.join('\x1b[38;5;%dm%s\x1b[0m'
                            % (ansi256(PALET.get(c, VOID)), c) for c in row))
    return rows