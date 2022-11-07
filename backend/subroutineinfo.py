from frontend.symbol.varsymbol import VarSymbol
from utils.tac.tacfunc import TACFunc
from frontend.ast.tree import Declaration
from typing import List, Dict

"""
SubroutineInfo: collect some info when selecting instr which will be used in SubroutineEmitter
"""


class SubroutineInfo:
    def __init__(self, func: TACFunc) -> None:
        self.funcLabel = func.entry
        self.argTemps = func.argTemps
        self.localArrays = func.local_arrays

        # stack space for all local arrays
        self.array_offsets: Dict[VarSymbol, int] = {}
        alloc_ptr = 0
        for var in self.localArrays:
            self.array_offsets[var] = alloc_ptr
            alloc_ptr += var.type.size
        self.localArraySize = alloc_ptr

    def __str__(self) -> str:
        return "funcLabel: {}{}".format(
            self.funcLabel.name,
            str(self.argTemps),
        )
