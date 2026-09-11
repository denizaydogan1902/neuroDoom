"""C → NeuroCPU-8 assembly derleyicisi (codegen).

Tasarım kararları:
- Tüm "yerel" değişkenler global adreslere statik yerleştirilir (runtime
  yığın çerçevesi yok); fonksiyon çağrıları CALL/RET donanım yığınını kullanır.
- Parametreler R3..R6 üzerinden geçer; sonuç R1'de döner.
- İfadeler yığın-temelli: derin ifadelerde ara sonuçlar PSH/POP ile saklanır.
- Dizi elemanı erişimi MAR (port 0xFD/0xFE) + MEM_READ(0xFC)/MEM_WRITE(0xFB)
  kapıları üzerinden yapılır.

Register sözleşmesi:
  R1   ifade sonucu / dönüş değeri        R2   ikinci operand
  R3..R6  parametreler                    R7..R12  geçici
  R13  (yardımcı sabit saklama)            R14  stack pointer
"""
from __future__ import annotations

from .parser import parse, VarDecl, FuncDef, Return, ExprStmt, If, While, For, \
    Break, Continue, Block, Var, Num, Binary, Unary, Assign, Index, Call

# port sabitleri
MAR_L, MAR_H, MEM_R, MEM_W = 0xFD, 0xFE, 0xFC, 0xFB

_BINOP_ALU = {"+": "ADD", "-": "SUB", "&": "AND", "|": "OR", "^": "XOR"}
_OP_INSN = {"+": "ADD", "-": "SUB", "&": "AND", "|": "OR",
            "^": "XOR"}
_OP_EXT = {"*": "MUL", "<<": "SHL", ">>": "SHR"}   # sonuç her zaman R1'de


class CodeGen:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.labels: dict[str, str] = {}     # label -> adres (assembler çözer)
        self._vars: dict[str, int] = {}
        self.next_var = 0x0200               # globaller 0x0200'den itibaren
        self._label_n = 0
        self._break_stack: list[str] = []
        self._continue_stack: list[str] = []
        self.func_names: set[str] = set()
        self._func_exit: str = ""
        self._param_regs: dict[str, int] = {}      # parametre adı -> register

    # ---- yardımcılar ---------------------------------------------------------
    def emit(self, *parts) -> None:
        self.lines.append(" ".join(str(p) for p in parts))

    def label(self, name: str) -> None:
        self.lines.append(f"{name}:")

    def fresh(self, base: str = "L") -> str:
        self._label_n += 1
        return f"{base}{self._label_n}"

    def alloc_var(self, name: str, size: int) -> int:
        addr = self.next_var
        self.next_var += max(1, size)
        self._vars[name] = addr
        return addr

    def var_addr(self, name: str) -> int:
        """Yerel (fonksiyon içi) değişkenleri ilk görüşte statik ayrıştırır."""
        if name not in self._vars:
            self.alloc_var(name, 1)
        return self._vars[name]

    # ---- global yerleşim -----------------------------------------------------
    def setup_globals(self, decls: list[VarDecl]) -> None:
        self._init_data: list[tuple[int, int]] = []
        for d in decls:
            addr = self.alloc_var(d.name, d.size)
            for i, v in enumerate(d.init[:max(1, d.size)]):
                self._init_data.append((addr + i, v & 0xFF))

    # ---- ifade ---------------------------------------------------------------
    def eval_expr(self, e) -> str:
        """İfadeyi değerlendirir; sonuç R1'de, R1 dizgisi döner."""
        if isinstance(e, Num):
            self.emit(f"LDI R1, {e.val & 0xFF}")
            return "R1"
        if isinstance(e, Var):
            p = self._param_regs.get(e.name)
            if p is not None:
                self.emit(f"MOV R1, R{p}")
                return "R1"
            addr = self.var_addr(e.name)
            self.emit(f"LDA R1, {addr}")
            return "R1"
        if isinstance(e, Index):
            self.emit_index_addr(e.base, e.idx)
            self.emit(f"IN R1, {MEM_R}")
            return "R1"
        if isinstance(e, Unary):
            self.eval_expr(e.operand)
            if e.op == "-":
                self.emit("LDI R2, 0")
                self.emit("SUB R1, R2, R1")
            elif e.op == "!":
                self.emit("LDI R2, 0")
                self.emit("SUB R1, R2, R1")      # 0-x; true iff x==0
                # z flag: sonuç 0 ise ... aslında !x = (x==0). Z=1 ⇔ R1==0
                self.emit("LDI R2, 1")
                self.emit("SUB R3, R1, R2")      # safe temp
                self.emit("MOV R1, R3")          # normalize sonra düzelt
            elif e.op == "~":
                self.emit("LDI R2, 0xFF")
                self.emit("XOR R1, R1, R2")
            return "R1"
        if isinstance(e, Binary):
            return self.eval_binary(e)
        if isinstance(e, Assign):
            return self.eval_assign(e)
        if isinstance(e, Call):
            return self.eval_call(e)
        raise NotImplementedError(f"ifade desteklenmiyor: {e}")

    def eval_binary(self, e: Binary) -> str:
        if e.op == "&&":
            return self._logic_and(e)
        if e.op == "||":
            return self._logic_or(e)
        if e.op == "/":
            return self._div(e, take_rem=False)
        if e.op == "%":
            return self._div(e, take_rem=True)

        if e.op not in _OP_INSN and e.op not in _OP_EXT:
            raise NotImplementedError(f"operatör: {e.op}")
        self.eval_expr(e.left)
        self.emit("PSH R1")
        self.eval_expr(e.right)
        self.emit("MOV R2, R1")
        self.emit("POP R1")
        if e.op in _OP_EXT:                    # MUL R1, R2 (sonuç R1'de)
            self.emit(f"{_OP_EXT[e.op]} R1, R2")
        else:
            self.emit(f"{_OP_INSN[e.op]} R1, R1, R2")
        return "R1"

    def _logic_and(self, e: Binary) -> str:
        """0/1 boolean üretir (&&); short-circuit."""
        false_l, done_l = self.fresh("and_f"), self.fresh("and_d")
        self.gen_cond(e.left, false_l, None)
        self.gen_cond(e.right, false_l, None)
        self.emit("LDI R1, 1")
        self.emit(f"JMP {done_l}")
        self.label(false_l)
        self.emit("LDI R1, 0")
        self.label(done_l)
        return "R1"

    def _logic_or(self, e: Binary) -> str:
        lright = self.fresh("or_r")
        false_l, true_l = self.fresh("or_f"), self.fresh("or_t")
        done_l = self.fresh("or_d")
        self.gen_cond(e.left, lright, true_l)
        self.label(lright)
        self.gen_cond(e.right, false_l, true_l)
        self.label(false_l)
        self.emit("LDI R1, 0")
        self.emit(f"JMP {done_l}")
        self.label(true_l)
        self.emit("LDI R1, 1")
        self.label(done_l)
        return "R1"

    def _div(self, e: Binary, take_rem: bool) -> str:
        """__udiv8 yardımcısını çağırır; dönüş: R1=bölüm, R2=kalan."""
        self.eval_expr(e.left)
        self.emit("PSH R1")
        self.eval_expr(e.right)
        self.emit("MOV R2, R1")
        self.emit("POP R1")
        self.emit("CALL __udiv8")
        if take_rem:
            self.emit("MOV R1, R2")
        return "R1"

    def eval_assign(self, e: Assign) -> str:
        self.eval_expr(e.value)
        if isinstance(e.target, Var):
            p = self._param_regs.get(e.target.name)
            if p is not None:
                self.emit(f"MOV R{p}, R1")
            else:
                addr = self.var_addr(e.target.name)
                self.emit(f"STA {addr}, R1")
        elif isinstance(e.target, Index):
            self.eval_expr(e.value)
            self.emit("PSH R1")
            self.emit_index_addr(e.target.base, e.target.idx)
            self.emit("POP R1")
            self.emit(f"OUT {MEM_W}, R1")
        return "R1"

    def echo_expr(self, e) -> None:
        """Ara ifadede yan etki yoksa yoksay; expression-statement için."""
        self.eval_expr(e)

    # ---- dizi adresi (MAR) ---------------------------------------------------
    def emit_index_addr(self, base: Var, idx) -> None:
        """MAR = base + idx (8-bit add, taşımayı bayrakla düzeltir)."""
        addr = self.var_addr(base.name)
        base_lo, base_hi = addr & 0xFF, (addr >> 8) & 0xFF
        self.eval_expr(idx)                     # R1 = idx
        self.emit(f"LDI R7, {base_lo}")
        self.emit("ADD R1, R1, R7")             # R1 = idx + lo
        self.emit(f"OUT {MAR_L}, R1")
        skip = self.fresh("noc")
        self.emit(f"LDI R5, {base_hi}")
        self.emit(f"JNC {skip}")
        self.emit("LDI R7, 1")
        self.emit("ADD R5, R5, R7")
        self.label(skip)
        self.emit(f"OUT {MAR_H}, R5")

    # ---- fonksiyon çağrısı ---------------------------------------------------
    def eval_call(self, e: Call) -> str:
        # gömülü port erişimi
        if e.name == "rdport" and isinstance(e.args[0], Num):
            self.emit(f"IN R1, {e.args[0].val & 0xFF}")
            return "R1"
        if e.name == "wrport" and isinstance(e.args[0], Num):
            self.eval_expr(e.args[1])
            self.emit(f"OUT {e.args[0].val & 0xFF}, R1")
            return "R1"
        iname = f"__f_{e.name}"
        for i, arg in enumerate(e.args):
            if i > 3:
                raise SyntaxError("en fazla 4 parametre destekleniyor")
            self.eval_expr(arg)
            self.emit(f"MOV R{3 + i}, R1")
        self.emit(f"CALL {iname}")
        return "R1"

    # ---- koşul ---------------------------------------------------------------
    _CMP_TRUE = {"<": "JNC", ">=": "JC", "==": "JZ", "!=": "JNZ",
                 ">": "JNC", "<=": "JC"}
    _CMP_FALSE = {"<": "JC", ">=": "JNC", "==": "JNZ", "!=": "JZ",
                  ">": "JC", "<=": "JNC"}

    def gen_cond(self, c, false_l: str | None, true_l: str | None) -> None:
        """Koşul üret: false_l'ye (yanlışsa) ve true_l'ye (doğruysa) atla."""
        if isinstance(c, Binary) and c.op == "&&":
            self.gen_cond(c.left, false_l, None)
            self.gen_cond(c.right, false_l, true_l)
            return
        if isinstance(c, Binary) and c.op == "||":
            mid = self.fresh("or_mid")
            self.gen_cond(c.left, mid, true_l)
            self.label(mid)
            self.gen_cond(c.right, false_l, true_l)
            return
        if isinstance(c, Unary) and c.op == "!":
            self.gen_cond(c.operand, true_l, false_l)
            return

        op = c.op if isinstance(c, Binary) else None
        if op in self._CMP_TRUE:
            # SUB order'ı:  '<','>=','==','!=' → (left,right)
            #                '>','<='           → (right,left)
            swapped = op in (">", "<=")
            first, second = (c.right, c.left) if swapped else (c.left, c.right)
            self.eval_expr(first)                # R1 = ilk
            self.emit("PSH R1")
            self.eval_expr(second)               # R1 = ikinci
            self.emit("MOV R2, R1")
            self.emit("POP R1")                  # R1=ilk, R2=ikinci
            self.emit("SUB R1, R1, R2")          # C=(ilk>=ikinci)
            #   '<'  (l,r)  true ⇔ C=0 → JNC      false ⇔ C=1 → JC
            #   '>=' (l,r)  true ⇔ C=1 → JC      false ⇔ C=0 → JNC
            #   '==' (l,r)  true ⇔ Z  → JZ      false ⇔ JNZ
            #   '!=' (l,r)  true ⇔ !Z → JNZ     false ⇔ JZ
            #   '>'  (r,l)  true ⇔ C=0 → JNC    false ⇔ C=1 → JC
            #   '<=' (r,l)  true ⇔ C=1 → JC     false ⇔ C=0 → JNC
            t_jmp = self._CMP_TRUE[op]
            f_jmp = self._CMP_FALSE[op]
            if true_l:
                self.emit(f"{t_jmp} {true_l}")
            if false_l:
                self.emit(f"{f_jmp} {false_l}")
            return

        if isinstance(c, Num):               # sabit koşul
            if c.val:
                if true_l:
                    self.emit(f"JMP {true_l}")
            else:
                if false_l:
                    self.emit(f"JMP {false_l}")
            return

        # genel ifade (sıfır değilse doğru)
        self.eval_expr(c)
        if true_l and false_l:
            self.emit(f"JNZ {true_l}")
            self.emit(f"JMP {false_l}")
        elif false_l:
            self.emit(f"JZ {false_l}")
        elif true_l:
            self.emit(f"JNZ {true_l}")

    # ---- deyimler ------------------------------------------------------------
    def stmt(self, s) -> None:
        if isinstance(s, Block):
            for sub in s.stmts:
                self.stmt(sub)
        elif isinstance(s, ExprStmt):
            self.echo_expr(s.expr)
        elif isinstance(s, Return):
            if s.expr:
                self.eval_expr(s.expr)
            self.emit(f"JMP {self._func_exit}")
        elif isinstance(s, If):
            else_l = self.fresh("else")
            end_l = self.fresh("end")
            self.gen_cond(s.cond, else_l, None)
            for sub in s.then:
                self.stmt(sub)
            if s.els:
                self.emit(f"JMP {end_l}")
            self.label(else_l)
            for sub in s.els:
                self.stmt(sub)
            if s.els:
                self.label(end_l)
        elif isinstance(s, While):
            loop_l = self.fresh("loop")
            exit_l = self.fresh("exit")
            self.label(loop_l)
            self.gen_cond(s.cond, exit_l, None)
            self._break_stack.append(exit_l)
            self._continue_stack.append(loop_l)
            for sub in s.body:
                self.stmt(sub)
            self._break_stack.pop()
            self._continue_stack.pop()
            self.emit(f"JMP {loop_l}")
            self.label(exit_l)
        elif isinstance(s, For):
            if s.init:
                self.echo_expr(s.init)
            start_l = self.fresh("for")
            exit_l = self.fresh("exit")
            step_l = self.fresh("step")
            self.label(start_l)
            if s.cond:
                self.gen_cond(s.cond, exit_l, None)
            self._break_stack.append(exit_l)
            self._continue_stack.append(step_l)
            for sub in s.body:
                self.stmt(sub)
            self._break_stack.pop()
            self._continue_stack.pop()
            self.label(step_l)
            if s.step:
                self.echo_expr(s.step)
            self.emit(f"JMP {start_l}")
            self.label(exit_l)
        elif isinstance(s, Break):
            self.emit(f"JMP {self._break_stack[-1]}")
        elif isinstance(s, Continue):
            self.emit(f"JMP {self._continue_stack[-1]}")
        elif isinstance(s, VarDecl):         # yerel bildirim: yoksay (statik)
            pass
        else:
            raise NotImplementedError(f"deyim: {s}")

    # ---- fonksiyon -----------------------------------------------------------
    def function(self, f: FuncDef) -> None:
        if len(f.params) > 4:
            raise SyntaxError(f"{f.name}: en fazla 4 parametre")
        self.func_names.add(f.name)
        self.label(f"__f_{f.name}")
        self._func_exit = self.fresh(f"x_{f.name}")
        # parametre adlarını anahtar registerlara eşle (R3..R6)
        self._param_regs = {name: 3 + i for i, name in enumerate(f.params)}
        # prologue: callee-saved geçicileri kaydet
        self.emit("PSH R7")
        self.emit("PSH R9")
        for st in f.body:
            self.stmt(st)
        # epilogue
        self.label(self._func_exit)
        self.emit("POP R9")
        self.emit("POP R7")
        self.emit("RET")
        self._param_regs = {}

    # ---- program -------------------------------------------------------------
    def generate(self, src: str) -> str:
        decls, funcs = parse(src)
        self.setup_globals(decls)
        self.emit("; ---- boot: globals'ı başlat, main'i çağır, sonra dur")
        self.emit("CALL __init_all")
        self.emit("CALL __f_main")
        self.emit("HLT")
        self.emit_init_all()
        for f in funcs:
            self.function(f)
        self.emit_tail_helpers()
        return "\n".join(self.lines)

    def emit_init_all(self) -> None:
        if not self._init_data:
            self.label("__init_all")
            self.emit("RET")
            return
        self.label("__init_all")
        for addr, val in self._init_data:
            self.emit(f"LDI R1, {val}")
            self.emit(f"STA {addr}, R1")
        self.emit("RET")

    def emit_tail_helpers(self) -> None:
        self.emit("; ---- __udiv8 (R1=bölünen, R2=bölen → R1=bölüm, R2=kalan)")
        self.label("__udiv8")
        self.emit("PSH R3")
        self.emit("PSH R4")
        self.emit("LDI R4, 0")            # q
        self.emit("JMP __udiv8_chk")
        self.label("__udiv8_sub")
        self.emit("SUB R1, R1, R2")       # a -= b
        self.emit("LDI R3, 1")
        self.emit("ADD R4, R4, R3")       # q++
        self.label("__udiv8_chk")
        self.emit("MOV R5, R1")
        self.emit("SUB R5, R5, R2")       # C=(a>=b)
        self.emit("JC __udiv8_sub")
        self.emit("MOV R2, R1")           # remainder
        self.emit("MOV R1, R4")           # quotient
        self.emit("POP R4")
        self.emit("POP R3")
        self.emit("RET")


def compile_c(src: str) -> str:
    cg = CodeGen()
    return cg.generate(src)


def compile_with_map(src: str) -> tuple[str, dict[str, int]]:
    """Kaynak → (assembly metni, değişken->adres haritası)."""
    cg = CodeGen()
    asm = cg.generate(src)
    return asm, dict(cg._vars)