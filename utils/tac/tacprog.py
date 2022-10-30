from typing import Any, Optional, Union, List, Tuple

from .tacfunc import TACFunc


# A TAC program consists of several TAC functions.
class TACProg:
    def __init__(self, funcs: list[TACFunc], globalDecls: List[Tuple[str, Optional[int]]]) -> None:
        self.funcs = funcs
        self.globalDecl = globalDecls

    def printTo(self) -> None:
        for name, initial_val in self.globalDecl:
            if initial_val is not None:
                print(f"GLOBAL {name} = {initial_val}")
            else:
                print(f"GLOBAL {name}")

        for func in self.funcs:
            func.printTo()
