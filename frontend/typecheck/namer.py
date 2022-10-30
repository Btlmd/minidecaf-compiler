from typing import Protocol, TypeVar, cast

from frontend.ast.node import Node, NullType
from frontend.ast.tree import *
from frontend.ast.visitor import RecursiveVisitor, Visitor
from frontend.scope.globalscope import GlobalScope
from frontend.scope.scope import Scope, ScopeKind
from frontend.scope.scopestack import ScopeStack
from frontend.symbol.funcsymbol import FuncSymbol
from frontend.symbol.symbol import Symbol
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from frontend.type.type import DecafType
from utils.error import *
from utils.riscv import MAX_INT

"""
The namer phase: resolve all symbols defined in the abstract syntax tree and store them in symbol tables (i.e. scopes).
"""


class Namer(Visitor[ScopeStack, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> Program:
        # Global scope. You don't have to consider it until Step 9.
        program.globalScope = GlobalScope
        ctx = ScopeStack(program.globalScope)

        program.accept(self, ctx)
        return program

    def visitProgram(self, program: Program, ctx: ScopeStack) -> None:
        # Check if the 'main' function is missing
        if not program.hasMainFunc():
            raise DecafNoMainFuncError

        for component in program:
            assert ctx.isGlobalScope()
            component.accept(self, ctx)

    def visitParameter(self, that: Parameter, ctx: T) -> None:
        return self.visitDeclaration(that, ctx)

    def visitFunction(self, func: Function, ctx: ScopeStack) -> None:
        # Check identifier conflict
        if ctx.findConflict(func.ident.value):
            raise DecafDeclConflictError(func.ident.value)
        sym = FuncSymbol(func.ident.value, func.ret_t.type, ctx.currentScope())
        ctx.declare(sym)
        func.setattr('symbol', sym)
        assert ctx.isGlobalScope()
        with ctx.local():
            for param in func.param_list:
                sym.addParaType(param.var_t.type)
                param.accept(self, ctx)
            # Visit body statements.
            # Note that visit the block directly will generate a new scope
            for stmt in func.body.children:
                stmt.accept(self, ctx)

    def visitBlock(self, block: Block, ctx: ScopeStack) -> None:
        with ctx.local():
            for child in block:
                child.accept(self, ctx)

    def visitReturn(self, stmt: Return, ctx: ScopeStack) -> None:
        stmt.expr.accept(self, ctx)

        """
        def visitFor(self, stmt: For, ctx: ScopeStack) -> None:

        1. Open a local scope for stmt.init.
        2. Visit stmt.init, stmt.cond, stmt.update.
        3. Open a loop in ctx (for validity checking of break/continue)
        4. Visit body of the loop.
        5. Close the loop and the local scope.
        """

    def visitFor(self, stmt: For, ctx: ScopeStack) -> None:
        with ctx.local():
            stmt.init.accept(self, ctx)
            stmt.cond.accept(self, ctx)
            stmt.update.accept(self, ctx)
            with ctx.loop():
                stmt.body.accept(self, ctx)

    def visitIf(self, stmt: If, ctx: ScopeStack) -> None:
        stmt.cond.accept(self, ctx)
        stmt.then.accept(self, ctx)

        # check if the else branch exists
        if not stmt.otherwise is NULL:
            stmt.otherwise.accept(self, ctx)

    def visitWhile(self, stmt: While, ctx: ScopeStack) -> None:
        stmt.cond.accept(self, ctx)
        ctx.openLoop()
        stmt.body.accept(self, ctx)
        ctx.closeLoop()

        """
        def visitDoWhile(self, stmt: DoWhile, ctx: ScopeStack) -> None:

        1. Open a loop in ctx (for validity checking of break/continue)
        2. Visit body of the loop.
        3. Close the loop.
        4. Visit the condition of the loop.
        """
    def visitDoWhile(self, stmt: DoWhile, ctx: ScopeStack) -> None:
        with ctx.loop():
            stmt.body.accept(self, ctx)
        stmt.cond.accept(self, ctx)

    def visitBreak(self, stmt: Break, ctx: ScopeStack) -> None:
        if not ctx.inLoop():
            raise DecafBreakOutsideLoopError()

    def visitContinue(self, stmt: Continue, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBreak.
        """
        if not ctx.inLoop():
            raise DecafBreakOutsideLoopError()

    def visitDeclaration(self, decl: Declaration, ctx: ScopeStack) -> None:
        """
        1. Use ctx.findConflict to find if a variable with the same name has been declared.
        2. If not, build a new VarSymbol, and put it into the current scope using ctx.declare.
        3. Set the 'symbol' attribute of decl.
        4. If there is an initial value, visit it.
        """
        if ctx.findConflict(decl.ident.value) is not None:
            raise DecafDeclConflictError(decl.ident.value)
        var = VarSymbol(decl.ident.value, decl.var_t.type)
        if ctx.isGlobalScope():
            var.isGlobal = True
            if decl.init_expr is not NULL:
                assert isinstance(decl.init_expr, IntLiteral)
                var.initValue = decl.init_expr.value
        ctx.declare(var)
        decl.setattr('symbol', var)
        if decl.init_expr is not NULL:
            decl.init_expr.accept(self, ctx)

    def visitAssignment(self, expr: Assignment, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        if not isinstance(expr.lhs, Identifier):
            raise DecafSyntaxError(f'Cannot assign to value to {type(expr.lhs).__name__}')
        self.visitBinary(expr, ctx)

    def visitUnary(self, expr: Unary, ctx: ScopeStack) -> None:
        expr.operand.accept(self, ctx)

    def visitBinary(self, expr: Binary, ctx: ScopeStack) -> None:
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)

    def visitCondExpr(self, expr: ConditionExpression, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.cond.accept(self, ctx)
        expr.then.accept(self, ctx)
        expr.otherwise.accept(self, ctx)

    def visitIdentifier(self, ident: Identifier, ctx: ScopeStack) -> None:
        """
        1. Use ctx.lookup to find the symbol corresponding to ident.
        2. If it has not been declared, raise a DecafUndefinedVarError.
        3. Set the 'symbol' attribute of ident.
        """
        symbol = ctx.lookup(ident.value)
        if symbol is None:
            raise DecafUndefinedVarError(f'Identifier {ident.value} is not defined')
        ident.setattr('symbol', symbol)

    def visitIntLiteral(self, expr: IntLiteral, ctx: ScopeStack) -> None:
        value = expr.value
        if value > MAX_INT:
            raise DecafBadIntValueError(value)

    def visitCall(self, call: Call, ctx: ScopeStack) -> None:
        func: FuncSymbol = ctx.lookup(call.ident.value)
        # Check if function is defined
        if func is None or func.isFunc is False:
            raise DecafUndefinedFuncError(call.ident.value)

        # Check if param_list match
        if len(call.arg_list) != func.parameterNum:
            raise DecafBadFuncCallError(f"Expecting {func.parameterNum} parameters, got {len(call.arg_list)}")

        call.ident.setattr('symbol', func)
        for arg in call.arg_list:
            arg.accept(self, ctx)
