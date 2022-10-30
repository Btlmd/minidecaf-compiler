from typing import Sequence, Tuple, Dict

from backend.asmemitter import AsmEmitter
from utils.error import IllegalArgumentException
from utils.label.label import Label, LabelKind
from utils.riscv import Riscv
from utils.tac.reg import Reg
from utils.tac.tacfunc import TACFunc
from utils.tac.tacinstr import *
from utils.tac.tacvisitor import TACVisitor

from ..subroutineemitter import SubroutineEmitter
from ..subroutineinfo import SubroutineInfo

"""
RiscvAsmEmitter: an AsmEmitter for RiscV
"""


class RiscvAsmEmitter(AsmEmitter):
    def __init__(
        self,
        allocatableRegs: list[Reg],
        callerSaveRegs: list[Reg],
        globalDecls: List[Tuple[str, Optional[int]]]
    ) -> None:
        super().__init__(allocatableRegs, callerSaveRegs)

    
        # the start of the asm code
        # int step10, you need to add the declaration of global var here
        self.printer.println(".data")
        for name, initial_val in filter(lambda x: x[1], globalDecls):
            self.printer.printDATAWord(name, initial_val)
        self.printer.println(".bss")
        for name, _ in filter(lambda x: not x[1], globalDecls):
            self.printer.printBSS(name, 4)

        self.printer.println(".text")
        self.printer.println(".global main")
        self.printer.println("")

    # transform tac instrs to RiscV instrs
    # collect some info which is saved in SubroutineInfo for SubroutineEmitter
    def selectInstr(self, func: TACFunc) -> tuple[list[str], SubroutineInfo]:

        selector: RiscvAsmEmitter.RiscvInstrSelector = (
            RiscvAsmEmitter.RiscvInstrSelector(func.entry)
        )
        for instr in func.getInstrSeq():
            instr.accept(selector)

        info = SubroutineInfo(func)

        return (selector.seq, info)

    # use info to construct a RiscvSubroutineEmitter
    def emitSubroutine(self, info: SubroutineInfo):
        return RiscvSubroutineEmitter(self, info)

    # return all the string stored in asmcodeprinter
    def emitEnd(self):
        return self.printer.close()

    class RiscvInstrSelector(TACVisitor):
        def __init__(self, entry: Label) -> None:
            self.entry = entry
            self.seq = []

        def visitAssign(self, instr: Assign) -> None:
            self.seq.append(Riscv.Move(instr.dst, instr.src))

        # in step11, you need to think about how to deal with globalTemp in almost all the visit functions. 
        def visitReturn(self, instr: Return) -> None:
            if instr.value is not None:
                self.seq.append(Riscv.Move(Riscv.A0, instr.value))
            else:
                self.seq.append(Riscv.LoadImm(Riscv.A0, 0))
            self.seq.append(Riscv.JumpToEpilogue(self.entry))

        def visitMark(self, instr: Mark) -> None:
            self.seq.append(Riscv.RiscvLabel(instr.label))

        def visitLoadImm4(self, instr: LoadImm4) -> None:
            self.seq.append(Riscv.LoadImm(instr.dst, instr.value))

        def visitUnary(self, instr: Unary) -> None:
            self.seq.append(Riscv.Unary(instr.op, instr.dst, instr.operand))
 
        def visitBinary(self, instr: Binary) -> None:
            # Comparison
            if instr.op == BinaryOp.GEQ:
                self.seq.append(Riscv.Binary(BinaryOp.SLT, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
                return
            if instr.op == BinaryOp.LEQ:
                self.seq.append(Riscv.Binary(BinaryOp.SGT, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
                return
            if instr.op == BinaryOp.EQU:
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
                return
            if instr.op == BinaryOp.NEQ:
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
                return
            # Logic
            if instr.op == BinaryOp.AND:
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.lhs))
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, Riscv.ZERO, instr.dst))
                self.seq.append(Riscv.Binary(BinaryOp.AND, instr.dst, instr.dst, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
                return
            if instr.op == BinaryOp.OR:
                self.seq.append(Riscv.Binary(BinaryOp.OR, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
                return
            self.seq.append(Riscv.Binary(instr.op, instr.dst, instr.lhs, instr.rhs))

        def visitCondBranch(self, instr: CondBranch) -> None:
            self.seq.append(Riscv.Branch(instr.cond, instr.label))
        
        def visitBranch(self, instr: Branch) -> None:
            self.seq.append(Riscv.Jump(instr.target))

        # in step9, you need to think about how to pass the parameters and how to store and restore callerSave regs
        def visitCall(self, instr: Call) -> None:
            self.seq.append(Riscv.RCall.fromCall(instr))

        def visitLoadWord(self, instr: LoadWord) -> None:
            self.seq.append(Riscv.LoadWord(instr.dsts[0], instr.srcs[0], instr.offset))

        def visitStoreWord(self, instr: StoreWord) -> None:
            self.seq.append(Riscv.StoreWord(*instr.srcs, instr.offset))

        def visitLoadSymbolAddress(self, instr: LoadSymbolAddress) -> None:
            self.seq.append(Riscv.LoadLabel(instr.dsts[0], instr.symbol.name))

        # in step11, you need to think about how to store the array 
"""
RiscvAsmEmitter: an SubroutineEmitter for RiscV
"""

class RiscvSubroutineEmitter(SubroutineEmitter):
    def __init__(self, emitter: RiscvAsmEmitter, info: SubroutineInfo) -> None:
        super().__init__(emitter, info)
        
        # + 4 is for the RA reg 
        self.nextLocalOffset = 4 * len(Riscv.CalleeSaved) + 4
        
        # the buf which stored all the NativeInstrs in this function
        self.buf: list[NativeInstr] = []

        # from temp to int
        # record where a temp is stored in the stack
        self.offsets: Dict[int, int] = {}

        self.argOffset: Dict[int, int] = {}
        for idx, temp in enumerate(self.info.argTemps[8:]):
            self.argOffset[temp.index] = idx * 4

        self.printer.printLabel(info.funcLabel)
        self.sp_offset = 0

        # in step9, step11 you can compute the offset of local array and parameters here

    def emitComment(self, comment: str) -> None:
        # you can add some log here to help you debug
        # self.printer.printComment(comment)
        self.buf += [comment]
    # store some temp to stack
    # usually happen when reaching the end of a basicblock
    # in step9, you need to think about the function parameters here
    def emitStoreToStack(self, src: Reg) -> None:
        if src.temp.index not in self.offsets:
            self.offsets[src.temp.index] = self.nextLocalOffset
            self.nextLocalOffset += 4
        self.buf.append(
            Riscv.NativeStoreWord(src, Riscv.SP, self.offsets[src.temp.index])
        )

    # load some temp from stack
    # usually happen when using a temp which is stored to stack before
    # in step9, you need to think about the function parameters here
    def emitLoadFromStack(self, dst: Reg, src: Temp):
        if src.index not in self.offsets:
            if src in self.info.argTemps:
                offset = self.argOffset[src.index] - self.sp_offset
                self.buf.append(
                    Riscv.NativeLoadWord(dst, Riscv.SP, offset , src)
                )
                return  # potential assert: the situation can only occur when the temp is first referenced
            raise IllegalArgumentException()
        offset = self.offsets[src.index] - self.sp_offset
        self.buf.append(
            Riscv.NativeLoadWord(dst, Riscv.SP, offset)
        )

    # add a NativeInstr to buf
    # when calling the fuction emitEnd, all the instr in buf will be transformed to RiscV code
    def emitNative(self, instr: NativeInstr):
        self.buf.append(instr)

    def emitLabel(self, label: Label):
        self.buf.append(Riscv.RiscvLabel(label).toNative([], []))

    def adjustSP(self, delta: int):
        self.sp_offset += delta
    
    def emitEnd(self):
        self.printer.printComment("start of prologue")
        self.printer.printInstr(Riscv.SPAdd(-self.nextLocalOffset))

        # Stack Structure
        """
        Arg (len - 1)
        ...
        Arg 8
        ------------- `self.nextLocalOffset`
        SPILL END
        ...
        SPILL BEGIN
        RA
        CALLEE END
        ...
        CALLEE BEGIN
        ------------- SP
        """

        # in step9, you need to think about how to store RA here
        # you can get some ideas from how to save CalleeSaved regs
        for i in range(len(Riscv.CalleeSaved)):
            if Riscv.CalleeSaved[i].isUsed():
                self.printer.printInstr(
                    Riscv.NativeStoreWord(Riscv.CalleeSaved[i], Riscv.SP, 4 * i)
                )
        # store RA
        self.printer.printInstr(
            Riscv.NativeStoreWord(Riscv.RA, Riscv.SP, 4 * len(Riscv.CalleeSaved))
        )

        self.printer.printComment("end of prologue")
        self.printer.println("")

        self.printer.printComment("start of body")

        # in step9, you need to think about how to pass the parameters here
        # you can use the stack or regs

        # using asmcodeprinter to output the RiscV code
        for instr in self.buf:
            # Print comment
            if isinstance(instr, str):
                self.printer.printComment(instr)
                continue

            # Now the nextLocalOffset have been determined (considering possible spills)
            # update the positions of potential arguments
            # well ... if there is too many arguments, we're doomed! (since lw.imm <= 2047)
            if isinstance(instr, Riscv.NativeLoadWord) and instr.temp is not None:
                assert instr.temp.index in self.argOffset
                instr.offset += self.nextLocalOffset

            self.printer.printInstr(instr)

        self.printer.printComment("end of body")
        self.printer.println("")

        self.printer.printLabel(
            Label(LabelKind.TEMP, self.info.funcLabel.name + Riscv.EPILOGUE_SUFFIX)
        )
        self.printer.printComment("start of epilogue")

        # Restore RA
        self.printer.printInstr(
            Riscv.NativeLoadWord(Riscv.RA, Riscv.SP, 4 * len(Riscv.CalleeSaved))
        )

        for i in range(len(Riscv.CalleeSaved)):
            if Riscv.CalleeSaved[i].isUsed():
                self.printer.printInstr(
                    Riscv.NativeLoadWord(Riscv.CalleeSaved[i], Riscv.SP, 4 * i)
                )

        self.printer.printInstr(Riscv.SPAdd(self.nextLocalOffset))
        self.printer.printComment("end of epilogue")
        self.printer.println("")

        self.printer.printInstr(Riscv.NativeReturn())
        self.printer.println("")