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
 *   64 ışın x 5 özdeş sütun = 320 sütun; 90° FOV (orijinal Doom gibi).
 * Renk: 8 doku x 8 gölge = 64 duvar tonu (byte 48..111) + zemin (0..15)
 *       + gökyüzü (16..20).
 *
 * 8-BİT TAŞMA DÜZELTMESİ: ışın koordinatları (rx,ry) byte taşmasıyla
 *   haritanın uzak ucuna "dolanır" ve hayalet duvar bulurdu; artık her
 *   adımda yönüne göre sarım (wrap) denetlenir — sarılırsa ışın uzayın
 *   boşluğuna düşer ve gökyüzü/zemin çizilir.
 *
 * PERSPEKTİF: dik mesafe cos(off) ile düzeltilir — balık gözü yok.
 *
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

/* 256 girişlik sin/kos dalga tabloları — her giriş 1.40625°; negatif
 * değerler ikiye-tümleyen (0xF8 = -8).  dx = 8*sin(ağ), dy = 8*cos(ağ). */
char sintab[256] = {
        0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3,
        3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 6,
        6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7,
        7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
        8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 7,
        7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6,
        6, 6, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 3, 3,
        3, 3, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 0, 0,
        0, 0, 0, 255, 255, 255, 255, 255, 254, 254, 254, 254, 254, 253, 253, 253,
        253, 253, 253, 252, 252, 252, 252, 252, 252, 251, 251, 251, 251, 251, 251, 250,
        250, 250, 250, 250, 250, 250, 250, 249, 249, 249, 249, 249, 249, 249, 249, 249,
        249, 249, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248,
        248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 249,
        249, 249, 249, 249, 249, 249, 249, 249, 249, 249, 250, 250, 250, 250, 250, 250,
        250, 250, 251, 251, 251, 251, 251, 251, 252, 252, 252, 252, 252, 252, 253, 253,
        253, 253, 253, 253, 254, 254, 254, 254, 254, 255, 255, 255, 255, 255, 0, 0 };
char costab[256] = {
        8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 7,
        7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6,
        6, 6, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 3, 3,
        3, 3, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 0, 0,
        0, 0, 0, 255, 255, 255, 255, 255, 254, 254, 254, 254, 254, 253, 253, 253,
        253, 253, 253, 252, 252, 252, 252, 252, 252, 251, 251, 251, 251, 251, 251, 250,
        250, 250, 250, 250, 250, 250, 250, 249, 249, 249, 249, 249, 249, 249, 249, 249,
        249, 249, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248,
        248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 248, 249,
        249, 249, 249, 249, 249, 249, 249, 249, 249, 249, 250, 250, 250, 250, 250, 250,
        250, 250, 251, 251, 251, 251, 251, 251, 252, 252, 252, 252, 252, 252, 253, 253,
        253, 253, 253, 253, 254, 254, 254, 254, 254, 255, 255, 255, 255, 255, 0, 0,
        0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3,
        3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 6,
        6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7,
        7, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8 };

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
        int off;
        int co;
        int rx;
        int ry;
        int prx;
        int pry;
        int dx;
        int dy;
        int d;
        int pd;
        int h;
        int hit;
        int tex;
        int sh;
        int top;
        int bottom;
        int skyl;
        int w;
        int w1;
        int fl;
        int s;
        off = a - 32;                       /* -32..31: FOV ortasından sapma */
        ang = (pa + off) & 255;             /* 90° FOV, 1.40625°/adım */
        co = 32 - a;
        if (a > 32) { co = a - 32; }        /* |off| */
        dx = sintab[ang];
        dy = costab[ang];
        rx = px + 8;
        ry = py + 8;
        d = 0;
        hit = 0;
        while (d < 30 && hit == 0)
        {
            prx = rx;
            pry = ry;
            rx = prx + dx;
            ry = pry + dy;
            d = d + 1;
            /* 8-bit sarım denetimi: ışın harita boyunu aşıyorsa boşluğa düş */
            if (dx < 128) { if (rx < prx) { hit = 2; } }
            else { if (rx > prx) { hit = 2; } }
            if (hit != 2 && dy < 128) { if (ry < pry) { hit = 2; } }
            if (hit != 2 && dy >= 128) { if (ry > pry) { hit = 2; } }
            if (hit == 0)
            {
                if (map[((ry >> 4) * 16) + (rx >> 4)] != 0)
                {
                    hit = 1;
                    tex = ((rx >> 4) + (ry >> 4)) & 7;
                    pd = (d * costab[co]) / 8;   /* dik mesafe = d*cos(off) */
                    if (pd < 1) { pd = 1; }
                    h = 200 / pd;
                    if (h > H) { h = H; }
                    if (h < 1) { h = 1; }
                    sh = 7;
                    if (pd >= 3) { sh = 6; }
                    if (pd >= 5) { sh = 5; }
                    if (pd >= 8) { sh = 4; }
                    if (pd >= 12) { sh = 3; }
                    if (pd >= 17) { sh = 2; }
                    if (pd >= 23) { sh = 1; }
                    if (pd >= 30) { sh = 0; }
                }
            }
        }
        if (hit == 2) { d = 30; }
        if (hit != 1) { h = 1; }
        top = (H - h) / 2;
        bottom = top + h;
        skyl = top - 24;                    /* ufuk pus bandı üst sınırı */
        w = 48 + tex * 8 + sh;              /* 48..111: 64 duvar tonu */
        w1 = w - 1;                          /* doku içi yarı-ton */
        if (w < 49) { w1 = w; }
        fl = 2;
        if (d < 22) { fl = 5; }
        if (d < 14) { fl = 8; }
        if (d < 8) { fl = 11; }
        if (d < 4) { fl = 14; }
        for (x = 0; x < 5; x = x + 1)       /* 64 ışın x 5 = 320 kolon */
        {
            for (y = 0; y < top; y = y + 1)
            {
                s = 16;
                if (y >= skyl) { s = 19; }
                if (y >= skyl + 12) { s = 20; }
                wrport(0x92, s);
            }
            for (y = top; y < bottom; y = y + 1)
            {
                s = w;
                if ((y & 1) != 0) { s = w1; }   /* doku içi yarı-ton */
                wrport(0x92, s);
            }
            for (y = bottom; y < H; y = y + 1)
            {
                s = fl;
                if ((y & 16) != 0) { s = fl - 1; }   /* zemin gridi */
                if (x == 3) { s = fl - 1; }          /* dikey grid çizgisi */
                wrport(0x92, s);
            }
        }
    }
}

void main()
{
    px = 8 * 16 + 8;
    py = 8 * 16 + 8;
    pa = 64;                             /* Doom 0° = Doğu, 256 tablo */
    while (1)
    {
        int k;
        int nx;
        int ny;
        k = rdport(0);
        if (k == 'a' || k == 'A') { pa = (pa + 4) & 255; }
        if (k == 'd' || k == 'D') { pa = (pa - 4) & 255; }
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