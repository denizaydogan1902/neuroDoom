/* NÖRODOOM — hemibrain kapılarından doğmuş 8-bit işlemci üzerinde
 * çalışan birinci şahıs raycasting motoru.
 *
 * Bu dosya C altsetinde yazılır, gömülü derleyici (neurodoom/cc) tarafından
 * derlenir, beyin NAND kapılarından kurulan NeuroCPU-8 üzerinde koşar.
 *
 * Harita: ORİJİNAL Doom shareware (DOOM1.WAD) E1M1 "Hangar" girişi.
 *   Doom birimleri dünyasından (x: 96, y: -272) 16x16 ızgaraya rasterlenir.
 *   Hücre boyutu 16 birim — her orijinal hücre 2x2 olarak genişletildi.
 * Görüş: 32x32 piksel ASCII framebuffer.
 * Girdi: port 0 (klavye), Çıktı: port 2 (frame sync).
 */

#define W 32
#define H 32

/* 32x32 framebuffer, 4 x 256'lık dilim — NÖRO-8'in 8-bit indeksi
 * tek diziyi 256'da keser; dilimler bellek içinde ARDIŞIK durur,
 * böylece dış okuyucu (screenshot/GIF) tek parça görür. */
char screen0[256];
char screen1[256];
char screen2[256];
char screen3[256];

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
        int row;
        int pix;
        ang = (pa + x - 16 + 64) & 63;
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
            }
        }
        top = (32 - h) / 2;
        bottom = top + h;
        for (y = 0; y < H; y = y + 1)
        {
            char sprite;
            sprite = ' ';
            if (y < top) { sprite = '.'; }
            if (top <= y && y < bottom)
            {
                if (d < 4) { sprite = '@'; }
                if (d >= 4 && d < 7) { sprite = '#'; }
                if (d >= 7 && d < 10) { sprite = '%'; }
                if (d >= 10 && d < 13) { sprite = '+'; }
                if (d >= 13) { sprite = '.'; }
            }
            if (y >= bottom && hit == 0) { sprite = '.'; }   /* zemin */
            if (y >= bottom + 11) { sprite = '%'; }          /* zemine yakın */
            row = y >> 3;              /* 0..3: hangi dilim */
            pix = (y - row * 8) * W + x;   /* dilim içi 0..255 */
            if (row == 0) { screen0[pix] = sprite; }
            if (row == 1) { screen1[pix] = sprite; }
            if (row == 2) { screen2[pix] = sprite; }
            if (row == 3) { screen3[pix] = sprite; }
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