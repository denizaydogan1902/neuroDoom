/* NÖRODOOM — hemibrain kapılarından doğmuş 8-bit işlemci üzerinde
 * çalışan birinci şahıs raycasting motoru.
 *
 * Bu dosya C altsetinde yazılır, gömülü derleyici (neurodoom/cc) tarafından
 * derlenir, beyin NAND kapılarından kurulan NeuroCPU-8 üzerinde koşar.
 *
 * Harita: ORİJİNAL Doom shareware (DOOM1.WAD) E1M1 "Hangar" girişi.
 *   Doom birimleri dünyasından (x: 96, y: -272) 8x8 ızgaraya rasterlenir,
 *   nöromap alt-üst (screen: satır0 tepede) için y-simetrik çevrilir.
 * Görüş: 16x16 piksel ASCII framebuffer.
 * Girdi: port 0 (klavye), Çıktı: port 2 (frame sync).
 */

#define W 16
#define H 16

char screen[256];   /* W * H */

char map[64] = {0,0,0,0,0,0,0,0,
                0,1,1,1,1,1,1,1,
                0,1,0,0,0,0,0,0,
                1,1,0,0,0,0,0,0,
                1,1,0,0,0,0,0,0,
                1,1,0,0,0,0,0,0,
                0,1,1,1,1,1,1,1,
                0,0,0,0,0,0,0,0};

char sintab[64] = {0,1,2,2,3,4,4,5,6,6,7,7,7,8,8,8,8,8,8,8,7,7,7,6,6,5,4,4,3,2,2,1,0,255,254,254,253,252,252,251,250,250,249,249,249,248,248,248,248,248,248,248,249,249,249,250,250,251,252,252,253,254,254,255};
char costab[64] = {8,8,8,8,7,7,7,6,6,5,4,4,3,2,2,1,0,255,254,254,253,252,252,251,250,250,249,249,249,248,248,248,248,248,248,248,249,249,249,250,250,251,252,252,253,254,254,255,0,1,2,2,3,4,4,5,6,6,7,7,7,8,8,8};

char px;
char py;
char pa;

void frame()
{
    int x;
    int y;
    for (x = 0; x < W; x = x + 1)
    {
        int ang;
        int rx;
        int ry;
        int dx;
        int dy;
        int d;
        int h;
        int top;
        int bottom;
        int hit;
        ang = (pa + x - 8 + 64) & 63;
        dx = sintab[ang];
        dy = costab[ang];
        rx = px + 16;
        ry = py + 16;
        d = 0;
        h = 1;
        hit = 0;
        while (d < 32 && hit == 0)
        {
            rx = rx + dx;
            ry = ry + dy;
            d = d + 1;
            if (map[((ry >> 5) * 8) + (rx >> 5)] != 0)
            {
                h = 64 / d;
                if (h > H) { h = H; }
                if (h < 1) { h = 1; }
                hit = 1;
            }
        }
        top = (16 - h) / 2;
        bottom = top + h;
        for (y = 0; y < H; y = y + 1)
        {
            char sprite;
            sprite = ' ';
            if (y < top) { sprite = '.'; }
            if (top <= y && y < bottom)
            {
                if (d < 7) { sprite = '#'; }
                if (d >= 7 && d < 14) { sprite = '%'; }
                if (d >= 14) { sprite = '+'; }
            }
            screen[y * W + x] = sprite;
        }
    }
}

void main()
{
    px = 4 * 32 + 16;
    py = 4 * 32 + 16;
    pa = 16;
    while (1)
    {
        int k;
        int nx;
        int ny;
        k = rdport(0);
        if (k == 'a' || k == 'A') { pa = (pa + 2) & 63; }
        if (k == 'd' || k == 'D') { pa = (pa - 2) & 63; }
        if (k == 'w' || k == 'W')
        {
            nx = px + sintab[pa];
            ny = py + costab[pa];
            if (map[((ny >> 5) * 8) + (nx >> 5)] == 0) { px = nx; py = ny; }
        }
        if (k == 's' || k == 'S')
        {
            nx = px - sintab[pa];
            ny = py - costab[pa];
            if (map[((ny >> 5) * 8) + (nx >> 5)] == 0) { px = nx; py = ny; }
        }
        frame();
        wrport(2, 1);
    }
}