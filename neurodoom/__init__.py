"""NeuroCPU: sinek beyni üzerinde kurulu işlemci.

Beyin kendisi Doom oynamıyor; üzerinde bir işletim ve uygulama çalışıyor:
  1. hemibrain NAND netlisti -> kapı sentezi (synth/)
  2. kapılardan ALU, register dosyası, bellek (synth/, cpu/)
  3. custom 8-bit ISA'nın fetch/decode/execute'ı (cpu/)
  4. kendi C derleyicisi -> Doom motoru bir uygulama olarak yüklenir (cc/, apps/)
"""
__version__ = "0.1.0"