from utils.tac.tacfunc import TACFunc

"""
SubroutineInfo: collect some info when selecting instr which will be used in SubroutineEmitter
"""


class SubroutineInfo:
    def __init__(self, func: TACFunc) -> None:
        self.funcLabel = func.entry
        self.argTemps = func.argTemps

    def __str__(self) -> str:
        return "funcLabel: {}{}".format(
            self.funcLabel.name,
            str(self.argTemps),
        )
