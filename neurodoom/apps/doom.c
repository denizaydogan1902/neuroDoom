/* NÖRODOOM — hemibrain kapılarından doğmuş 8-bit işlemci üzerinde
 * çalışan birinci şahıs raycasting motoru.
 *
 * Bu dosya C altsetinde yazılır, gömülü derleyici (neurodoom/cc) tarafından
 * derlenir, beyin NAND kapılarından kurulan NeuroCPU-8 üzerinde koşar.
 *
 * Harita: ORİJİNAL Doom shareware (DOOM1.WAD) E1M1 "Hangar" girişi.
 *   Doom birimleri dünyasından 16x16 ızgaraya rasterlenir; hücre 16 birim.
 *
 * Görüntü: 320x200 piksel (orijinal Doom ile aynı), port 0x92 üzerinden
 *   kolon-major akış olarak basılır: host Memory.video[x*200 + y].
 *   64 ışın x 5 özdeş sütun = 320 sütun; 8-bit sayaç turlamasına gerek yok.
 * Renk: 8 doku x 8 gölge = 64 duvar tonu (byte 48..111) + zemin + tavan.
 * Girdi: port 0 (klavye), Çıktı: port 0x92 (video), port 2 (frame sync).
 */

#define W 320
#define H 200

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

/* 128 girişlik sin/kos dalga tabloları — her bir giriş 2.8125°; negatif
 * değerler ikiye-tümleyen (0xF8 = -8).  dx = 8*sin(ağ), dy = 8*cos(ağ). */
char sintab[128] = {0,0,1,1,2,2,2,3,3,3,4,4,4,5,5,5,6,6,6,6,7,7,7,7,7,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,7,7,7,7,7,6,6,6,6,5,5,5,4,4,4,3,3,3,2,2,2,1,1,0,0,0,255,255,254,254,254,253,253,253,252,252,252,251,251,251,250,250,250,250,249,249,249,249,249,248,248,248,248,248,248,248,248,248,248,248,248,248,248,248,249,249,249,249,249,250,250,250,250,251,251,251,252,252,252,253,253,253,254,254,254,255,255,0};
char costab[128] = {8,8,8,8,8,8,8,8,7,7,7,7,7,6,6,6,6,5,5,5,4,4,4,3,3,3,2,2,2,1,1,0,0,0,255,255,254,254,254,253,253,253,252,252,252,251,251,251,250,250,250,250,249,249,249,249,249,248,248,248,248,248,248,248,248,248,248,248,248,248,248,248,249,249,249,249,249,250,250,250,250,251,251,251,252,252,252,253,253,253,254,254,254,255,255,0,0,0,1,1,2,2,2,3,3,3,4,4,4,5,5,5,6,6,6,6,7,7,7,7,7,8,8,8,8,8,8,8};

char px;
char py;
char pa;

void frame()
{
    int a;
    int x;
    int y;
    wrport(0x90, 0);   /* video cursor low  = 0 */
    wrport(0x91, 0);   /* video cursor high = 0 */
    for (a = 0; a < 64; a = a + 1)
    {
        int ang;
        int rx;
        int ry;
        int dx;
        int dy;
        int d;
        int h;
        int hit;
        int tex;
        int sh;
        int top;
        int bottom;
        int w;
        int fl;
        ang = (pa + a + 96) & 127;      /* pa-32 .. pa+31 = 180° FOV */
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
                h = 200 / d;
                if (h > H) { h = H; }
                if (h < 1) { h = 1; }
                hit = 1;
                tex = ((ry >> 4) * 5 + (rx >> 4) * 3) & 7;
                sh = 7;
                if (d >= 3) { sh = 6; }
                if (d >= 5) { sh = 5; }
                if (d >= 7) { sh = 4; }
                if (d >= 10) { sh = 3; }
                if (d >= 14) { sh = 2; }
                if (d >= 19) { sh = 1; }
                if (d >= 24) { sh = 0; }
            }
        }
        top = (H - h) / 2;
        bottom = top + h;
        w = 48 + tex * 8 + sh;          /* 48..111: 64 duvar tonu */
        fl = 46;                        /* '.' yakın zemin */
        if (d > 12) { fl = 126; }       /* '~' uzak zemin */
        for (x = 0; x < 5; x = x + 1)   /* 64 ışın x 5 = 320 kolon */
        {
            for (y = 0; y < top; y = y + 1) { wrport(0x92, 32); }
            for (y = top; y < bottom; y = y + 1) { wrport(0x92, w); }
            for (y = bottom; y < H; y = y + 1) { wrport(0x92, fl); }
        }
    }
}

void main()
{
    px = 8 * 16 + 8;
    py = 8 * 16 + 8;
    pa = 32;                             /* Doom açı 0° = Doğu */
    while (1)
    {
        int k;
        int nx;
        int ny;
        k = rdport(0);
        if (k == 'a' || k == 'A') { pa = (pa + 4) & 127; }
        if (k == 'd' || k == 'D') { pa = (pa - 4) & 127; }
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