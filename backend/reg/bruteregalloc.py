import random

from backend.dataflow.basicblock import BasicBlock, BlockKind
from backend.dataflow.cfg import CFG
from backend.dataflow.loc import Loc
from backend.reg.regalloc import RegAlloc
from backend.riscv.riscvasmemitter import RiscvAsmEmitter
from backend.subroutineemitter import SubroutineEmitter
from backend.subroutineinfo import SubroutineInfo
from utils.riscv import Riscv
from utils.tac.holeinstr import HoleInstr
from utils.tac.reg import Reg
from utils.tac.temp import Temp

"""
BruteRegAlloc: one kind of RegAlloc

bindings: map from temp.index to Reg

we don't need to take care of GlobalTemp here
because we can remove all the GlobalTemp in selectInstr process

1. accept：根据每个函数的 CFG 进行寄存器分配，寄存器分配结束后生成相应汇编代码
2. bind：将一个 Temp 与寄存器绑定
3. unbind：将一个 Temp 与相应寄存器解绑定
4. localAlloc：根据数据流对一个 BasicBlock 内的指令进行寄存器分配
5. allocForLoc：每一条指令进行寄存器分配
6. allocRegFor：根据数据流决定为当前 Temp 分配哪一个寄存器
"""

class BruteRegAlloc(RegAlloc):
    def __init__(self, emitter: RiscvAsmEmitter) -> None:
        super().__init__(emitter)
        self.bindings = {}

    def clearUsed(self):
        for reg in self.emitter.allocatableRegs:  # init for each subroutine
            reg.used = False

    def accept(self, graph: CFG, info: SubroutineInfo) -> None:
        subEmitter = self.emitter.emitSubroutine(info)
        self.clearUsed()

        # bind (actually stash) A0 ~ A7
        # other args are marked in `RiscvSubroutineEmitter.argOffset`
        for temp, reg in zip(subEmitter.info.argTemps, Riscv.ArgRegs):
            self.bind(temp, reg)
        if len(graph) > 0:
            for tempindex in graph.nodes[0].liveIn:
                if tempindex in self.bindings:
                    subEmitter.emitStoreToStack(self.bindings.get(tempindex))
        self.restoreBindings()

        for bb in graph.iterator():
            # you need to think more here
            # maybe we don't need to alloc regs for all the basic blocks
            if bb.label is not None:
                subEmitter.emitLabel(bb.label)
            self.localAlloc(bb, subEmitter)
        subEmitter.emitEnd()

    def bind(self, temp: Temp, reg: Reg):
        reg.used = True
        self.bindings[temp.index] = reg
        reg.occupied = True
        reg.temp = temp

    def unbind(self, temp: Temp):
        if temp.index in self.bindings:
            self.bindings[temp.index].occupied = False
            self.bindings.pop(temp.index)

    def restoreBindings(self):
        self.bindings.clear()
        for reg in self.emitter.allocatableRegs:
            reg.occupied = False

    def localAlloc(self, bb: BasicBlock, subEmitter: SubroutineEmitter):
        self.restoreBindings()
        # in step9, you may need to think about how to store callersave regs here
        if bb.kind == BlockKind.CALL:
            assert len(bb.locs) == 1
            loc = bb.locs[0]
            call = loc.instr

            # Prepare other arguments
            reg = Riscv.T0
            remain_args_count = len(call.srcs) - 8
            if remain_args_count > 0:
                subEmitter.emitNative(Riscv.SPAdd(-4 * remain_args_count))
                subEmitter.adjustSP(-4 * remain_args_count)
                for idx, temp in enumerate(call.srcs[8:]):  # to regs
                    subEmitter.emitComment(
                        "  PARAM BORROW: allocate {} to {}  (read: {}):".format(
                            str(temp), str(reg), str(True)
                        )
                    )
                    subEmitter.emitLoadFromStack(reg, temp)
                    assert not reg.occupied, f"{reg}, {reg.temp}"
                    self.bind(temp, reg)
                    subEmitter.emitNative(Riscv.NativeStoreWord(reg, Riscv.SP, 4 * idx))
                    self.unbind(temp)

            # Prepare arguments [0, 7]
            for temp, reg in zip(call.srcs, Riscv.ArgRegs):
                subEmitter.emitComment(
                    "  PARAM DIRECT: allocate {} to {}  (read: {}):".format(
                        str(temp), str(reg), str(True)
                    )
                )
                subEmitter.emitLoadFromStack(reg, temp)
                assert not reg.occupied
                self.bind(temp, reg)

            # Function call
            subEmitter.emitComment(str(call))
            subEmitter.emitNative(call.toNative(call.dsts, call.dsts))

            # Clean up stack
            if remain_args_count > 0:
                subEmitter.emitNative(Riscv.SPAdd(4 * remain_args_count))
                subEmitter.adjustSP(4 * remain_args_count)

            # Store return value
            if len(call.srcs) > 0:
                self.unbind(call.srcs[0])
            self.bind(call.dsts[0], Riscv.A0)
            subEmitter.emitStoreToStack(Riscv.A0)
        else:
            for loc in bb.allSeq():
                subEmitter.emitComment(str(loc.instr))

                self.allocForLoc(loc, subEmitter)

            for tempindex in bb.liveOut:
                if tempindex in self.bindings:
                    subEmitter.emitStoreToStack(self.bindings.get(tempindex))

            if (not bb.isEmpty()) and (bb.kind not in {BlockKind.CONTINUOUS, BlockKind.CALL}):
                self.allocForLoc(bb.locs[len(bb.locs) - 1], subEmitter)

    def allocForLoc(self, loc: Loc, subEmitter: SubroutineEmitter):
        instr = loc.instr
        srcRegs: list[Reg] = []
        dstRegs: list[Reg] = []

        for i in range(len(instr.srcs)):
            temp = instr.srcs[i]
            if isinstance(temp, Reg):
                srcRegs.append(temp)
            else:
                srcRegs.append(self.allocRegFor(temp, True, loc.liveIn, subEmitter))

        for i in range(len(instr.dsts)):
            temp = instr.dsts[i]
            if isinstance(temp, Reg):
                dstRegs.append(temp)
            else:
                dstRegs.append(self.allocRegFor(temp, False, loc.liveIn, subEmitter))

        subEmitter.emitNative(instr.toNative(dstRegs, srcRegs))

    def allocRegFor(
        self, temp: Temp, isRead: bool, live: set[int], subEmitter: SubroutineEmitter
    ):
        if temp.index in self.bindings:
            return self.bindings[temp.index]

        for reg in self.emitter.allocatableRegs:
            if (not reg.occupied) or (not reg.temp.index in live):
                subEmitter.emitComment(
                    "  allocate {} to {}  (read: {}):".format(
                        str(temp), str(reg), str(isRead)
                    )
                )
                if isRead:
                    subEmitter.emitLoadFromStack(reg, temp)
                if reg.occupied:
                    self.unbind(reg.temp)
                self.bind(temp, reg)
                return reg

        reg = self.emitter.allocatableRegs[
            random.randint(0, len(self.emitter.allocatableRegs) - 1)
        ]
        subEmitter.emitStoreToStack(reg)
        subEmitter.emitComment("  spill {} ({})".format(str(reg), str(reg.temp)))
        self.unbind(reg.temp)
        self.bind(temp, reg)
        subEmitter.emitComment(
            "  allocate {} to {} (read: {})".format(str(temp), str(reg), str(isRead))
        )
        if isRead:
            subEmitter.emitLoadFromStack(reg, temp)
        return reg
