/* NÖRODOOM — hemibrain kapılarından doğmuş 8-bit işlemci üzerinde
 * çalışan birinci şahıs raycasting motoru.
 *
 * Bu dosya C altsetinde yazılır, gömülü derleyici (neurodoom/cc) tarafından
 * derlenir, beyin NAND kapılarından kurulan NeuroCPU-8 üzerinde koşar.
 *
 * Harita: ORİJİNAL Doom shareware (DOOM1.WAD) E1M1 "Hangar" girişi.
 *   Doom birimleri dünyasından 16x16 ızgaraya rasterlenir; hücre 16 birim.
 * Görüş: 64x40 piksel (1.6:1 — orijinal Doom'un 320x200 en-boy oranı).
 * Renk: 8 duvar dokusu x 6 uzaklık gölgesi = 48 ton + zemin - tavan fade.
 * Girdi: port 0 (klavye), Çıktı: port 2 (frame sync).
 */

#define W 64
#define H 40

/* 64x40 framebuffer = 2560 bayt -> 10 x 256'lık dilim. NÖRO-8'in 8-bit
 * indeksi tek diziyi 256'da keser; dilimler bellek içinde ARDIŞIK durur,
 * böylece dış okuyucu (screenshot/GIF) tek parça görür.
 * Dilim: satır = y >> 2 (0..9), piksel = (y & 3) * 64 + x. */
char screen0[256];
char screen1[256];
char screen2[256];
char screen3[256];
char screen4[256];
char screen5[256];
char screen6[256];
char screen7[256];
char screen8[256];
char screen9[256];

char map[256] = {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,
                 0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,
                 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
                 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};

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
        int sl;
        int pix;
        int tex;
        int sh;
        ang = (pa + (x >> 1) - 16 + 64) & 63;
        dx = sintab[ang];
        dy = costab[ang];
        rx = px + 8;
        ry = py + 8;
        d = 0;
        h = 1;
        hit = 0;
        while (d < 24 && hit == 0)
        {
            rx = rx + dx;
            ry = ry + dy;
            d = d + 1;
            if (map[((ry >> 4) * 16) + (rx >> 4)] != 0)
            {
                h = 40 / d;
                if (h > H) { h = H; }
                if (h < 1) { h = 1; }
                hit = 1;
                tex = ((ry >> 4) + (rx >> 4)) & 7;
                if (d < 4) { sh = 5; }
                if (d >= 4 && d < 7) { sh = 4; }
                if (d >= 7 && d < 10) { sh = 3; }
                if (d >= 10 && d < 13) { sh = 2; }
                if (d >= 13 && d < 16) { sh = 1; }
                if (d >= 16) { sh = 0; }
            }
        }
        top = (40 - h) / 2;
        bottom = top + h;
        for (y = 0; y < H; y = y + 1)
        {
            char sprite;
            sprite = ' ';
            if (y < top) { sprite = ' '; }
            if (top <= y && y < bottom)
            {
                if (hit == 1)
                {
                    /* 'A' + 8 doku * 6 gölge -> 48 duvar tonu */
                    sprite = 'A' + tex * 6 + sh;
                }
                else
                {
                    sprite = '-';
                }
            }
            if (y >= bottom)
            {
                if (d < 10) { sprite = '.'; }
                else { sprite = '~'; }
            }
            sl = y >> 2;               /* 0..9: hangi dilim (4 satır x 64) */
            pix = (y & 3) * W + x;     /* dilim içi 0..255 */
            if (sl == 0) { screen0[pix] = sprite; }
            if (sl == 1) { screen1[pix] = sprite; }
            if (sl == 2) { screen2[pix] = sprite; }
            if (sl == 3) { screen3[pix] = sprite; }
            if (sl == 4) { screen4[pix] = sprite; }
            if (sl == 5) { screen5[pix] = sprite; }
            if (sl == 6) { screen6[pix] = sprite; }
            if (sl == 7) { screen7[pix] = sprite; }
            if (sl == 8) { screen8[pix] = sprite; }
            if (sl == 9) { screen9[pix] = sprite; }
        }
    }
}

void main()
{
    px = 8 * 16 + 8;
    py = 8 * 16 + 8;
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
            if (map[((ny >> 4) * 16) + (nx >> 4)] == 0) { px = nx; py = ny; }
        }
        if (k == 's' || k == 'S')
        {
            nx = px - sintab[pa];
            ny = py - costab[pa];
            if (map[((ny >> 4) * 16) + (nx >> 4)] == 0) { px = nx; py = ny; }
        }
        frame();
        wrport(2, 1);
    }
}