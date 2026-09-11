"""C-ayraç (parser): recursive-descent → küçük AST.

AST düğümleri diziler/dict'ler yerine basit sınıflarla temsil edilir
(todas statik tipli).  Desteklenen: global değişken (dizi + ilklikçi),
fonksiyon (parametreli), if/else, while, for, return, break, continue,
ifade ifadeleri, atama, ikili + birli operatörler, fonksiyon çağrıları.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .lexer import Token, tokenize


# ---- AST düğümleri -----------------------------------------------------------
@dataclass
class VarDecl:
    name: str
    size: int = 1
    init: list[int] = field(default_factory=list)   # dizi ilklikçileri

@dataclass
class FuncDef:
    name: str
    params: list[str] = field(default_factory=list)
    body: list = field(default_factory=list)

@dataclass
class Return:
    expr: object = None

@dataclass
class ExprStmt:
    expr: object = None

@dataclass
class If:
    cond: object
    then: list
    els: list = field(default_factory=list)

@dataclass
class While:
    cond: object
    body: list

@dataclass
class For:
    init: object
    cond: object
    step: object
    body: list

@dataclass
class Break:
    pass

@dataclass
class Continue:
    pass

@dataclass
class Block:
    stmts: list

@dataclass
class Var:
    name: str

@dataclass
class Num:
    val: int

@dataclass
class Binary:
    op: str
    left: object
    right: object

@dataclass
class Unary:
    op: str
    operand: object

@dataclass
class Assign:
    target: object
    value: object

@dataclass
class Index:
    base: object
    idx: object

@dataclass
class Call:
    name: str
    args: list = field(default_factory=list)


# ---- ayrıştırıcı --------------------------------------------------------------
class Parser:
    def __init__(self, toks: list[Token]) -> None:
        self.toks = toks
        self.i = 0
        self.decls: list[VarDecl] = []
        self.funcs: list[FuncDef] = []

    def peek(self) -> Token:
        return self.toks[self.i]

    def next(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind: str, val: str | None = None) -> Token:
        t = self.next()
        if t.kind != kind or (val is not None and t.val != val):
            raise SyntaxError(
                f"beklenen {val or kind}, bulunan {t.val!r} satır {t.line}")
        return t

    def at(self, val: str) -> bool:
        t = self.peek()
        return t.kind == "op" and t.val == val

    def at_kw(self, kw: str) -> bool:
        t = self.peek()
        return t.kind == "kw" and t.val == kw

    def parse(self) -> tuple[list[VarDecl], list[FuncDef]]:
        while self.peek().kind != "eof":
            if self.at_kw("int") or self.at_kw("char") or self.at_kw("void"):
                self.parse_decl()
            else:
                raise SyntaxError(
                    f"beklenen tür, bulunan {self.peek().val!r} "
                    f"sıra {self.peek().line}")
        return self.decls, self.funcs

    def parse_decl(self) -> None:
        self.next()  # tür (int/char/void)
        name = self.expect("id").val
        if self.at("("):
            self.next()   # ( params
            params: list[str] = []
            if not self.at(")"):
                while True:
                    if self.at_kw("int") or self.at_kw("char"):
                        self.next()
                        params.append(self.expect("id").val)
                    if self.at(")"):
                        break
                    self.expect("op", ",")
            self.expect("op", ")")
            self.expect("op", "{")
            body = self.parse_block_body()
            self.funcs.append(FuncDef(name, params, body))
        elif self.at("{"):
            decl = VarDecl(name)
            self.expect("op", "{")
            # dizi ilklikçisi
            vals: list[int] = []
            while not self.at("}"):
                vals.append(self.expect("num").val)
                if self.at("}"):
                    break
                self.expect("op", ",")
            self.expect("op", "}")
            decl.size = len(vals)
            decl.init = vals
            self.decls.append(decl)
        else:
            # tür var [size] [= sabit, ...] ;
            decl = VarDecl(name)
            if self.at("["):
                self.next()
                decl.size = self.expect("num").val
                self.expect("op", "]")
            if self.at("="):
                self.next()
                vals = []
                if self.at("{"):
                    self.next()
                    while not self.at("}"):
                        vals.append(self.expect("num").val)
                        if self.at("}"):
                            break
                        self.expect("op", ",")
                    self.next()
                else:
                    vals = [self.expect("num").val]
                decl.init = vals
            self.expect("op", ";")
            self.decls.append(decl)

    def parse_block_body(self) -> list:
        stmts = []
        while not self.at("}"):
            if self.peek().kind == "eof":
                raise SyntaxError("fonksiyon gövdesi kapanmadan bitti")
            if self.at_kw("int") or self.at_kw("char"):
                self.parse_local_decl(stmts)
                continue
            stmts.append(self.parse_stmt())
        self.expect("op", "}")
        return stmts

    def parse_local_decl(self, stmts: list) -> None:
        self.next()   # tür
        name = self.expect("id").val
        size = 1
        if self.at("["):
            self.next()
            size = self.expect("num").val
            self.expect("op", "]")
        self.expect("op", ";")
        stmts.append(VarDecl(name, size, []))

    def parse_stmt(self) -> object:
        if self.at_kw("if"):
            self.next()
            self.expect("op", "(")
            cond = self.parse_expr()
            self.expect("op", ")")
            then = [self.parse_stmt()]
            els: list = []
            if self.at_kw("else"):
                self.next()
                els = [self.parse_stmt()]
            return If(cond, then, els)
        if self.at_kw("while"):
            self.next()
            self.expect("op", "(")
            cond = self.parse_expr()
            self.expect("op", ")")
            body = [self.parse_stmt()]
            return While(cond, body)
        if self.at_kw("for"):
            self.next()
            self.expect("op", "(")
            if self.at_kw("int") or self.at_kw("char"):
                self.next()                        # yerel bildirim
                name = self.expect("id").val
                if self.at("="):
                    self.next()
                    init = Assign(Var(name), self.parse_expr())
                else:
                    init = Assign(Var(name), Num(0))
            else:
                init = self.parse_opt_expr()
            self.expect("op", ";")
            cond = self.parse_opt_expr()
            self.expect("op", ";")
            step = self.parse_opt_expr()
            self.expect("op", ")")
            body = [self.parse_stmt()]
            return For(init, cond, step, body)
        if self.at_kw("return"):
            self.next()
            if self.at(";"):
                return Return(None)
            e = self.parse_expr()
            self.expect("op", ";")
            return Return(e)
        if self.at_kw("break"):
            self.next()
            self.expect("op", ";")
            return Break()
        if self.at_kw("continue"):
            self.next()
            self.expect("op", ";")
            return Continue()
        if self.at("{"):
            self.next()
            return Block(self.parse_block_body())
        e = self.parse_opt_expr()
        self.expect("op", ";")
        return ExprStmt(e)

    def parse_opt_expr(self) -> object:
        if self.at(";") or self.at(")"):
            return None
        return self.parse_expr()

    # ---- ifade grameri (öncelik sıralı) ---------------------------------------
    def parse_expr(self) -> object:
        left = self.parse_assign()
        if self.at("?") or self.at(","):
            raise SyntaxError("ternary/virgül desteklenmiyor")
        return left

    def parse_assign(self) -> object:
        left = self.parse_or()
        if self.at("="):
            self.next()
            right = self.parse_assign()
            if isinstance(left, Index):
                return Assign(left, right)
            if isinstance(left, Var):
                return Assign(left, right)
            raise SyntaxError("atama hedefi değişken/dizi elemanı olmalı")
        return left

    def parse_or(self) -> object:
        left = self.parse_and()
        while self.at("||"):
            self.next()
            left = Binary("||", left, self.parse_and())
        return left

    def parse_and(self) -> object:
        left = self.parse_eq()
        while self.at("&&"):
            self.next()
            left = Binary("&&", left, self.parse_eq())
        return left

    def parse_eq(self) -> object:
        left = self.parse_rel()
        while self.at("==") or self.at("!="):
            op = self.next().val
            left = Binary(op, left, self.parse_rel())
        return left

    def parse_rel(self) -> object:
        left = self.parse_shift()
        while self.at("<") or self.at(">") or self.at("<=") or self.at(">="):
            op = self.next().val
            left = Binary(op, left, self.parse_shift())
        return left

    def parse_shift(self) -> object:
        left = self.parse_add()
        while self.at("<<") or self.at(">>"):
            op = self.next().val
            left = Binary(op, left, self.parse_add())
        return left

    def parse_add(self) -> object:
        left = self.parse_mul()
        while self.at("+") or self.at("-"):
            op = self.next().val
            left = Binary(op, left, self.parse_mul())
        return left

    def parse_mul(self) -> object:
        left = self.parse_unary()
        while self.at("*") or self.at("/") or self.at("%") or self.at("&"):
            op = self.next().val
            left = Binary(op, left, self.parse_unary())
        return left

    def parse_unary(self) -> object:
        if self.at("!") or self.at("~") or self.at("-"):
            op = self.next().val
            return Unary(op, self.parse_unary())
        if self.at("++") or self.at("--"):
            op = self.next().val
            tgt = self.parse_unary()
            return Assign(tgt, Binary(op, tgt, Num(1)))
        return self.parse_postfix()

    def parse_postfix(self) -> object:
        e = self.parse_primary()
        while True:
            if self.at("["):
                self.next()
                idx = self.parse_expr()
                self.expect("op", "]")
                e = Index(e, idx)
            elif self.at("("):
                self.next()
                args: list = []
                if not self.at(")"):
                    while True:
                        args.append(self.parse_assign())
                        if self.at(")"):
                            break
                        self.expect("op", ",")
                self.expect("op", ")")
                e = Call(e.name if isinstance(e, Var) else "?", args)
            else:
                break
        return e

    def parse_primary(self) -> object:
        t = self.peek()
        if t.kind == "num":
            self.next()
            return Num(t.val)
        if t.kind == "id":
            self.next()
            return Var(t.val)
        if self.at("("):
            self.next()
            e = self.parse_expr()
            self.expect("op", ")")
            return e
        raise SyntaxError(f"beklenen ifade, var {t.val!r} sıra {t.line}")


def parse(src: str) -> tuple[list[VarDecl], list[FuncDef]]:
    toks = tokenize(src)
    p = Parser(toks)
    return p.parse()