from __future__ import annotations

from typing import Any, Optional, Union, Tuple, Dict

from frontend.ast.tree import Declaration, Function
from frontend.symbol.varsymbol import VarSymbol
from frontend.type import ArrayType
from utils.label.funclabel import FuncLabel
from utils.label.label import Label

from .context import Context
from .tacfunc import TACFunc
from .tacinstr import *
from .tacop import *
from .temp import Temp


class FuncVisitor:
    def __init__(self, entry: FuncLabel, numArgs: int, local_arrays: List[VarSymbol], param_arrays: List[Tuple[VarSymbol, int]], ctx: Context, lib_function: Dict[str, Function]) -> None:
        self.ctx = ctx
        self.func = TACFunc(entry, numArgs, local_arrays, param_arrays)
        self.visitLabel(entry)
        self.nextTempId = 0
        self.lib_function = lib_function

        self.continueLabelStack = []
        self.breakLabelStack = []

    # To get a fresh new temporary variable.
    def freshTemp(self) -> Temp:
        temp = Temp(self.nextTempId)
        self.nextTempId += 1
        return temp

    # To get a fresh new label (for jumping and branching, etc).
    def freshLabel(self) -> Label:
        return self.ctx.freshLabel()

    # To count how many temporary variables have been used.
    def getUsedTemp(self) -> int:
        return self.nextTempId

    # In fact, the following methods can be named 'appendXXX' rather than 'visitXXX'. E.g., by calling 'visitAssignment', you add an assignment instruction at the end of current function.
    def visitAssignment(self, dst: Temp, src: Temp) -> Temp:
        self.func.add(Assign(dst, src))
        return src

    def visitLoad(self, value: Union[int, str], temp: Optional[Temp] = None) -> Temp:
        if temp is None:
            temp = self.freshTemp()
        if isinstance(value, int):
            self.func.add(LoadImm4(temp, value))
        else:
            self.func.add(LoadStrConst(temp, value))
        return temp

    def visitUnary(self, op: UnaryOp, operand: Temp) -> Temp:
        temp = self.freshTemp()
        self.func.add(Unary(op, temp, operand))
        return temp

    def visitUnarySelf(self, op: UnaryOp, operand: Temp) -> None:
        self.func.add(Unary(op, operand, operand))

    def visitBinary(self, op: BinaryOp, lhs: Temp, rhs: Temp) -> Temp:
        temp = self.freshTemp()
        self.func.add(Binary(op, temp, lhs, rhs))
        return temp

    def visitBinarySelf(self, op: BinaryOp, lhs: Temp, rhs: Temp) -> None:
        self.func.add(Binary(op, lhs, lhs, rhs))

    def visitBranch(self, target: Label) -> None:
        self.func.add(Branch(target))

    def visitCondBranch(self, op: CondBranchOp, cond: Temp, target: Label) -> None:
        self.func.add(CondBranch(op, cond, target))

    def visitReturn(self, value: Optional[Temp]) -> None:
        self.func.add(Return(value))

    def visitLabel(self, label: Label) -> None:
        self.func.add(Mark(label))

    def visitMemo(self, content: str) -> None:
        self.func.add(Memo(content))

    def visitRaw(self, instr: TACInstr) -> None:
        self.func.add(instr)

    def visitLoadSymbolAddress(self, sym: VarSymbol):
        dst = self.freshTemp()
        self.func.add(LoadSymbolAddress(sym, dst))
        return dst

    def visitLoadFromAddress(self, addr: Temp):
        dst = self.freshTemp()
        self.func.add(LoadWord(dst, addr, 0))
        return dst

    def visitStoreToAddress(self, src: Temp, addr: Temp):
        self.func.add(StoreWord(src, addr, 0))

    def visitCall(self, func_label: Label, dst: Temp, param_temp: List[Temp]) -> None:
        self.func.add(Call(func_label, dst, param_temp))

    def visitLoadFromSymbol(self, sym: VarSymbol, offset: int = 0) -> Temp:
        dst = self.freshTemp()
        self.func.add(LoadSymbolAddress(sym, dst))
        self.func.add(LoadWord(dst, dst, offset))
        return dst

    def visitStoreToSymbol(self, sym: VarSymbol, src: Temp, offset: int = 0) -> None:
        dst = self.freshTemp()
        self.func.add(LoadSymbolAddress(sym, dst))
        self.func.add(StoreWord(src, dst, offset))

    def visitEnd(self) -> None:
        if (len(self.func.instrSeq) == 0) or (not self.func.instrSeq[-1].isReturn()):
            self.func.add(Return(None))
        self.func.tempUsed = self.getUsedTemp()
        self.ctx.funcs.append(self.func)

    # To open a new loop (for break/continue statements)
    def openLoop(self, breakLabel: Label, continueLabel: Label) -> None:
        self.breakLabelStack.append(breakLabel)
        self.continueLabelStack.append(continueLabel)

    # To close the current loop.
    def closeLoop(self) -> None:
        self.breakLabelStack.pop()
        self.continueLabelStack.pop()

    # To get the label for 'break' in the current loop.
    def getBreakLabel(self) -> Label:
        return self.breakLabelStack[-1]

    # To get the label for 'continue' in the current loop.
    def getContinueLabel(self) -> Label:
        return self.continueLabelStack[-1]