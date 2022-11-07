from __future__ import annotations

from typing import Any, Optional, Union, List, Tuple
from frontend.ast.tree import Function, NULL, Declaration
from frontend.symbol.varsymbol import VarSymbol
from utils.label.funclabel import *
from utils.label.label import Label, LabelKind

from .context import Context
from .funcvisitor import FuncVisitor
from .tacprog import TACProg


class ProgramWriter:
    def __init__(self, funcs: List[Function], globalDecls: List[Declaration]) -> None:
        self.funcs = []
        self.ctx = Context()
        self.globalDecls = globalDecls
        for func in funcs:
            self.funcs.append(func)
            self.ctx.putFuncLabel(func.ident.value)

    def visitFunc(self, name: str, numArgs: int, local_arrays: List[VarSymbol]) -> FuncVisitor:
        entry = self.ctx.getFuncLabel(name)
        return FuncVisitor(entry, numArgs, local_arrays, self.ctx)

    def visitEnd(self) -> TACProg:
        return TACProg(self.ctx.funcs, self.globalDecls)
