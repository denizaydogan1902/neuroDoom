"""Gerçek Doom (shareware DOOM1.WAD) verisinden E1M1 haritasını çıkarır.

Doom'un BSP haritası: VERTEXES (köşeler) + LINEDEFS (duvarlar, köşeleri
birleştiren çizgiler) + SIDEDEFS + THINGS (oyuncu başlangıcı) + SECTORS.

Bu araç WAD'ın ilk seviyesini (E1M1 — Hangar) parse edip, oyuncunun
başladığı açık alanı çevreleyen gerçek Doom duvarlarını 8x8 hücrelik bir
NÖRO-8 haritasına rasterize eder. Böylece "aynen orijinal oyunun ilk
odasında" açılırız — ama motorumuz micro kartımız (812 NAND) üzerinde.

Kullanım:  python -m neurodoom.tools.doom2neuro
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

# --- WAD okuma -----------------------------------------------------------

def read_wad(data: bytes) -> dict[str, bytes]:
    assert data[:4] == b"IWAD", "bu bir IWAD değil"
    lump_count, dir_offset = struct.unpack("II", data[4:12])
    lumps: dict[str, bytes] = {}
    order: list[str] = []
    for i in range(lump_count):
        off = dir_offset + i * 16
        lump_off, lump_size = struct.unpack("II", data[off:off + 8])
        name = data[off + 8:off + 16].split(b"\x00")[0].decode()
        lumps[name] = data[lump_off:lump_off + lump_size]
        order.append(name)
    return lumps, order


def map_lump(lumps: dict[str, bytes], order: list[str],
             map_name: str, kind: str) -> bytes:
    """Bir haritanın (örn. E1M1) parçası olan lump'ı sırayla bulur."""
    try:
        base = order.index(map_name)
    except ValueError:
        raise KeyError(f"WAD'da {map_name} yok")
    kinds = ["THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES",
             "SEGS", "SSECTORS", "NODES", "SECTORS", "REJECT", "BLOCKMAP"]
    return lumps[order[base + 1 + kinds.index(kind)]]


def parse_vertices(raw: bytes) -> np.ndarray:
    n = len(raw) // 4
    v = np.frombuffer(raw, dtype="<i2").reshape(n, 2)
    # bazı sürümler vertex'i iki kez yazar; linedef'de kullanılan indeksleri
    # aştıkça hepsini kullan (shareware v1.0'da doubling yok)
    return v


def parse_linedefs(raw: bytes) -> np.ndarray:
    n = len(raw) // 14
    l = np.zeros((n, 2), dtype=np.int32)
    for i in range(n):
        off = i * 14
        l[i] = (
            struct.unpack("<H", raw[off:off + 2])[0],
            struct.unpack("<H", raw[off + 2:off + 4])[0],
        )
    return l


def parse_things(raw: bytes) -> list[tuple[int, int, int, int]]:
    n = len(raw) // 10
    things = []
    for i in range(n):
        off = i * 10
        x, y, angle, kind, flags = struct.unpack("<hhhhH", raw[off:off + 10])
        things.append((x, y, angle, kind))
    return things


# --- harita ızgarasına rasterleme ------------------------------------------

def build_grid(vertices, linedefs, size: int = 8, cell: int = 32,
               px: int | None = None, py: int | None = None) -> tuple:
    """Gerçek Doom duvarlarını size×size hücrelik bir grid'e çevirir.

    px, py verilirse görüş penceresi o noktanın çevresiyle sınırlanır
    (E1M1'in ilk odası — haritanın tamamı değil).
    """
    if px is not None:
        x0, y0 = px - size * cell // 2, py - size * cell // 2
        w = h = size * cell
    else:
        xs = [v[0] for v in vertices]; ys = [v[1] for v in vertices]
        x0, y0 = min(xs), min(ys)
        w = max(xs) - x0; h = max(ys) - y0
    scale = 1.0  # pencere vs w/h zaten size*cell boyutunda
    grid = np.zeros((size, size), dtype=np.int32)

    def to_cell(x: float, y: float) -> tuple[int, int]:
        return int((x - x0) * scale // cell), int((y - y0) * scale // cell)

    # sadece pencereyle kesişen duvar çizgileri
    for v1, v2 in linedefs[:, :2].astype(int):
        a, b = vertices[v1], vertices[v2]
        if (max(a[0], b[0]) < x0 or min(a[0], b[0]) > x0 + w or
                max(a[1], b[1]) < y0 or min(a[1], b[1]) > y0 + h):
            continue
        ca, cb = to_cell(*a), to_cell(*b)
        c0, c1 = ca, cb
        if c0 == c1:
            continue
        x, y = c0
        dx, dy = abs(c1[0] - x), 0 - abs(c1[1] - y)
        sx, sy = 1 if x < c1[0] else -1, 1 if y < c1[1] else -1
        err = dx + dy
        while True:
            if 0 <= x < size and 0 <= y < size:
                grid[y, x] = 1
            if (x, y) == c1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x += sx
            if e2 <= dx:
                err += dx; y += sy

    return grid, x0, y0, scale, w, h


def main() -> None:
    wad_path = Path(__file__).parent.parent.parent / "data" / "doom1.wad"
    data = wad_path.read_bytes()
    lumps, order = read_wad(data)

    verts = parse_vertices(map_lump(lumps, order, "E1M1", "VERTEXES"))
    ld = parse_linedefs(map_lump(lumps, order, "E1M1", "LINEDEFS"))
    things = parse_things(map_lump(lumps, order, "E1M1", "THINGS"))

    # oyuncu 1. açık oda çevresini kaplayan pencere
    player = next((t for t in things if t[3] == 1), things[0])
    px, py = player[0], player[1]

    grid, x0, y0, scale, w, h = build_grid(verts, ld, px=px, py=py)
    pcell0 = (px - x0) // 32
    pcell1 = (py - y0) // 32
    if 0 <= pcell0 < 8 and 0 <= pcell1 < 8:
        grid[pcell1, pcell0] = 0   # oyuncu hücresi boş

    print(f"E1M1 Hangar girişi: pencere x∈[{x0},{x0 + w}] y∈[{y0},{y0 + h}]")
    print(f"oyuncu THINGS: x={px} y={py} açı={player[2]} tip={player[3]}")
    print(f"oyuncu hücresi: col={pcell0} row={pcell1}")
    for row in grid:
        print("".join("#" if g else "." for g in row))

    np.save(Path(__file__).parent.parent.parent / "data" / "e1m1_grid.npy",
            grid.astype(np.uint8))


if __name__ == "__main__":
    main()