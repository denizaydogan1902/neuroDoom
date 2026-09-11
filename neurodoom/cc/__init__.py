"""C alt kümesi derleyicisi: kaynak → NeuroCPU-8 assembly."""
from .compiler import compile_c, compile_with_map, CodeGen

__all__ = ["compile_c", "compile_with_map", "CodeGen"]