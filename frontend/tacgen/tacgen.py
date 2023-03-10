import utils.riscv as riscv
from frontend.ast import node
from frontend.ast.tree import *
from frontend.ast.visitor import Visitor
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from frontend.type.builtin_type import BuiltinType
from utils.tac import tacop
from utils.tac.funcvisitor import FuncVisitor
from utils.tac.programwriter import ProgramWriter
from utils.tac.tacprog import TACProg
from utils.tac.temp import Temp

"""
The TAC generation phase: translate the abstract syntax tree into three-address code.
"""


class TACGen(Visitor[FuncVisitor, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> TACProg:

        pw = ProgramWriter(
            program.functions().values(),
            program.globalDecls().values(),
            program.lib_function,
        )



        for name, func in program.functions().items():
            if func.body is NULL:
                continue
            mv = pw.visitFunc(name, len(func.param_list), func.local_arrays, func.param_arrays)
            func.accept(self, mv)
            mv.visitEnd()

        # Remember to call pw.visitEnd before finishing the translation phase.
        return pw.visitEnd()

    def visitBlock(self, block: Block, mv: FuncVisitor) -> None:
        for child in block:
            child.accept(self, mv)

    def visitReturn(self, stmt: Return, mv: FuncVisitor) -> None:
        stmt.expr.accept(self, mv)
        mv.visitReturn(stmt.expr.getattr("val"))

    def visitBreak(self, stmt: Break, mv: FuncVisitor) -> None:
        mv.visitBranch(mv.getBreakLabel())

    def visitIdentifier(self, ident: Identifier, mv: FuncVisitor) -> None:
        """
        1. Set the 'val' attribute of ident as the temp variable of the 'symbol' attribute of ident.
        """
        sym: VarSymbol = ident.getattr('symbol')
        if isinstance(sym.type, ArrayType):
            addr_temp = mv.visitLoadSymbolAddress(sym)
            ident.setattr('addr', addr_temp)
            return

        if sym.isGlobal:
            global_val = mv.visitLoadFromSymbol(sym)
            ident.setattr('val', global_val)
        else:
            ident.setattr('val', ident.getattr('symbol').temp)

    def visitDeclaration(self, decl: Declaration, mv: FuncVisitor) -> Optional[Temp]:
        """
        1. Get the 'symbol' attribute of decl.
        2. Use mv.freshTemp to get a new temp variable for this symbol.
        3. If the declaration has an initial value, use mv.visitAssignment to set it.
        """
        # Note that global declaration will not be visited here
        sym: VarSymbol = decl.getattr('symbol')
        # if sym.type is ArrayType:
        #
        if sym.isGlobal:
            sym.initValue = decl.init_expr.value
            return
        temp = mv.freshTemp()
        sym.temp = temp
        if decl.init_expr is not NULL:
            if isinstance(decl.init_expr, InitializerList):
                # Call `fill_n` to clear array if not all element are defined in initializer list
                addr = mv.visitLoadSymbolAddress(sym)
                value_temp = mv.visitLoad(0)
                dummy = mv.freshTemp()
                if len(decl.init_expr.value) < sym.type.element_count:
                    const_temp = mv.visitLoad(sym.type.size)
                    mv.visitCall(
                        mv.ctx.getFuncLabel(mv.lib_function["fill_n"].ident.value),
                        dummy,  # dummy, store return value
                        [addr, value_temp, const_temp]
                    )
                # Initialize elements specified in initializer list
                const_temp = mv.visitLoad(sym.type.full_indexed.size)
                for val in decl.init_expr.value:
                    mv.visitLoad(val, value_temp)
                    mv.visitStoreToAddress(value_temp, addr)
                    mv.visitBinarySelf(tacop.BinaryOp.ADD, addr, const_temp)
            else:
                decl.init_expr.accept(self, mv)
                mv.visitAssignment(temp, decl.init_expr.getattr('val'))
        return temp

    def visitAssignment(self, expr: Assignment, mv: FuncVisitor) -> None:
        """
        1. Visit the right hand side of expr, and get the temp variable of left hand side.
        2. Use mv.visitAssignment to emit an assignment instruction.
        3. Set the 'val' attribute of expr as the value of assignment instruction.
        """
        expr.rhs.accept(self, mv)
        rhs_val = expr.rhs.getattr('val')
        expr.setattr('val', rhs_val)

        if isinstance(expr.lhs, Subscription):
            expr.lhs.setattr('addr_only', True)
            expr.lhs.accept(self, mv)
            mv.visitStoreToAddress(
                rhs_val,
                expr.lhs.getattr('addr')
            )
            return

        assert isinstance(expr.lhs, Identifier)
        lhs_symbol = expr.lhs.getattr('symbol')
        if lhs_symbol.isGlobal:
            mv.visitStoreToSymbol(lhs_symbol, rhs_val)
        else:
            expr.lhs.accept(self, mv)
            lhs_val = expr.lhs.getattr('val')
            mv.visitAssignment(lhs_val, rhs_val)

    def visitIf(self, stmt: If, mv: FuncVisitor) -> None:
        stmt.cond.accept(self, mv)

        if stmt.otherwise is NULL:
            skipLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitLabel(skipLabel)
        else:
            skipLabel = mv.freshLabel()
            exitLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitBranch(exitLabel)
            mv.visitLabel(skipLabel)
            stmt.otherwise.accept(self, mv)
            mv.visitLabel(exitLabel)

    def visitWhile(self, stmt: While, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        mv.visitLabel(beginLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitUnary(self, expr: Unary, mv: FuncVisitor) -> None:
        expr.operand.accept(self, mv)

        op = {
            node.UnaryOp.Neg: tacop.UnaryOp.NEG,
            node.UnaryOp.BitNot: tacop.UnaryOp.NOT,
            node.UnaryOp.LogicNot: tacop.UnaryOp.SEQZ,
            # You can add unary operations here.
        }[expr.op]
        expr.setattr("val", mv.visitUnary(op, expr.operand.getattr("val")))

    def visitBinary(self, expr: Binary, mv: FuncVisitor) -> None:
        expr.lhs.accept(self, mv)
        expr.rhs.accept(self, mv)

        op = {
            node.BinaryOp.Add: tacop.BinaryOp.ADD,
            node.BinaryOp.Sub: tacop.BinaryOp.SUB,
            node.BinaryOp.Mul: tacop.BinaryOp.MUL,
            node.BinaryOp.Div: tacop.BinaryOp.DIV,
            node.BinaryOp.Mod: tacop.BinaryOp.REM,
            # Comparison
            node.BinaryOp.LT: tacop.BinaryOp.SLT,
            node.BinaryOp.LE: tacop.BinaryOp.LEQ,
            node.BinaryOp.GE: tacop.BinaryOp.GEQ,
            node.BinaryOp.GT: tacop.BinaryOp.SGT,
            node.BinaryOp.EQ: tacop.BinaryOp.EQU,
            node.BinaryOp.NE: tacop.BinaryOp.NEQ,
            # Logic
            node.BinaryOp.LogicAnd: tacop.BinaryOp.AND,
            node.BinaryOp.LogicOr: tacop.BinaryOp.OR,
        }[expr.op]
        expr.setattr(
            "val", mv.visitBinary(op, expr.lhs.getattr("val"), expr.rhs.getattr("val"))
        )

    def visitCondExpr(self, expr: ConditionExpression, mv: FuncVisitor) -> None:
        """
        1. Refer to the implementation of visitIf and visitBinary.
        """
        expr.cond.accept(self, mv)
        skipLabel = mv.freshLabel()
        exitLabel = mv.freshLabel()
        exprValue = mv.freshTemp()

        mv.visitCondBranch(
            tacop.CondBranchOp.BEQ, expr.cond.getattr("val"), skipLabel
        )
        expr.then.accept(self, mv)
        mv.visitAssignment(exprValue, expr.then.getattr("val"))
        mv.visitBranch(exitLabel)
        mv.visitLabel(skipLabel)
        expr.otherwise.accept(self, mv)
        mv.visitAssignment(exprValue, expr.otherwise.getattr("val"))
        mv.visitLabel(exitLabel)

        expr.setattr('val', exprValue)

    def visitIntLiteral(self, expr: IntLiteral, mv: FuncVisitor) -> None:
        expr.setattr("val", mv.visitLoad(expr.value))

    def visitContinue(self, stmt: Continue, mv: FuncVisitor) -> None:
        mv.visitBranch(mv.getContinueLabel())

    def visitFor(self, stmt: For, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()

        # init
        stmt.init.accept(self, mv)

        # begin loop
        mv.openLoop(breakLabel, loopLabel)
        mv.visitLabel(beginLabel)

        # cond, can be NULL
        stmt.cond.accept(self, mv)
        if stmt.cond.getattr("val") is not None:
            mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        # body
        stmt.body.accept(self, mv)

        # update
        mv.visitLabel(loopLabel)
        stmt.update.accept(self, mv)
        mv.visitBranch(beginLabel)

        # end
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitDoWhile(self, stmt: DoWhile, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        bodyLabel = mv.freshLabel()

        mv.openLoop(breakLabel, loopLabel)
        mv.visitBranch(bodyLabel)  # skip the first condition check
        mv.visitLabel(beginLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)
        mv.visitLabel(bodyLabel)
        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitFunction(self, func: Function, mv: FuncVisitor) -> None:
        for p in func.param_list:
            p.accept(self, mv)
        func.body.accept(self, mv)

    def visitParameter(self, that: Parameter, mv: FuncVisitor) -> None:
        temp = self.visitDeclaration(that, mv)
        mv.func.addArgTemp(temp)

    def visitCall(self, call: Call, mv: FuncVisitor) -> None:
        # Evaluate Argument Expressions
        param_temp = []
        for arg_expr in call.arg_list:
            arg_expr.accept(self, mv)
            if isinstance(arg_expr.getattr('type'), ArrayType):
                assert arg_expr.getattr('addr')
                param_temp += [arg_expr.getattr('addr')]
            else:
                assert isinstance(arg_expr.getattr('type'), BuiltinType)
                assert arg_expr.getattr('val')
                param_temp += [arg_expr.getattr('val')]

        # Assign Return Value
        ret = mv.freshTemp()
        call.setattr('val', ret)
        func_label = mv.ctx.getFuncLabel(call.ident.value)
        mv.visitCall(func_label, ret, param_temp)

    def visitSubscription(self, sub: Subscription, mv: FuncVisitor) -> None:
        sub.base.setattr('addr_only', True)
        sub.base.accept(self, mv)
        sub.index.accept(self, mv)
        assert sub.index.getattr('val')

        # determine expression address
        base_offset_temp = sub.base.getattr('addr')
        offset_temp = mv.visitLoad(sub.getattr('type').size)
        mv.visitBinarySelf(tacop.BinaryOp.MUL, offset_temp, sub.index.getattr('val'))
        mv.visitBinarySelf(tacop.BinaryOp.ADD, offset_temp, base_offset_temp)
        sub.setattr('addr', offset_temp)

        # determine expression value,
        if sub.getattr('addr_only') is None:
            sub.setattr(
                'val',
                mv.visitLoadFromAddress(offset_temp)
            )