"""
Module that defines all AST nodes.
Reading this file to grasp the basic method of defining a new AST node is recommended.
Modify this file if you want to add a new AST node.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar, Union, List, Tuple, Dict

from frontend.type import INT, DecafType
from utils import T, U

from .node import NULL, BinaryOp, Node, UnaryOp
from .visitor import Visitor, accept
from utils.error import *

_T = TypeVar("_T", bound=Node)
U = TypeVar("U", covariant=True)


def _index_len_err(i: int, node: Node):
    return IndexError(
        f"you are trying to index the #{i} child of node {node.name}, which has only {len(node)} children"
    )


class ListNode(Node, Generic[_T]):
    """
    Abstract node type that represents a node sequence.
    E.g. `Block` (sequence of statements).
    """

    def __init__(self, name: str, children: list[_T]) -> None:
        super().__init__(name)
        self.children = children

    def __getitem__(self, key: int) -> Node:
        return self.children.__getitem__(key)

    def __len__(self) -> int:
        return len(self.children)

    def accept(self, v: Visitor[T, U], ctx: T):
        ret = tuple(map(accept(v, ctx), self))
        return None if ret.count(None) == len(ret) else ret


class Program(ListNode["Function"]):
    """
    AST root. It should have only one children before step9.
    """

    def __init__(self, *children: Function) -> None:
        super().__init__("program", list(children))
        self.lib_function: Dict[str, Function] = {}

    def functions(self) -> dict[str, Function]:
        return {func.ident.value: func for func in self if isinstance(func, Function)}

    def globalDecls(self) -> dict[str, Declaration]:
        return {decl.ident.value: decl for decl in self if isinstance(decl, Declaration)}

    def hasMainFunc(self) -> bool:
        return "main" in self.functions()

    def mainFunc(self) -> Function:
        return self.functions()["main"]

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitProgram(self, ctx)

    def addLibFunction(self, lib_name: str, func: Function):
        self.lib_function[lib_name] = func
        self.children.insert(0, func)

    def __iadd__(self, other: List[Union[Function, Declaration]]):
        self.children += other
        return self

class Function(Node):
    """
    AST node that represents a function.
    """

    def __init__(
        self,
        ret_t: TypeLiteral,
        ident: Identifier,
        body: Block,
        param_list: List[Parameter],
    ) -> None:
        super().__init__("function")
        self.ret_t = ret_t
        self.ident = ident
        self.body = body
        self.param_list = param_list
        self.local_arrays = None
        self.param_arrays = None

    def __getitem__(self, key: int) -> Node:
        return (
            self.ret_t,
            self.ident,
            self.body,
            *self.param_list,
        )[key]

    def __len__(self) -> int:
        return 3 + len(self.param_list)

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitFunction(self, ctx)


class Statement(Node):
    """
    Abstract type that represents a statement.
    """

    def is_block(self) -> bool:
        """
        Determine if this type of statement is `Block`.
        """
        return False


class Return(Statement):
    """
    AST node of return statement.
    """

    def __init__(self, expr: Expression) -> None:
        super().__init__("return")
        self.expr = expr

    def __getitem__(self, key: Union[int, str]) -> Node:
        if isinstance(key, int):
            return (self.expr,)[key]
        return self.__dict__[key]

    def __len__(self) -> int:
        return 1

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitReturn(self, ctx)


class If(Statement):
    """
    AST node of if statement.
    """

    def __init__(
        self, cond: Expression, then: Statement, otherwise: Optional[Statement] = None
    ) -> None:
        super().__init__("if")
        self.cond = cond
        self.then = then
        self.otherwise = otherwise or NULL

    def __getitem__(self, key: int) -> Node:
        return (self.cond, self.then, self.otherwise)[key]

    def __len__(self) -> int:
        return 3

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIf(self, ctx)


class While(Statement):
    """
    AST node of while statement.
    """

    def __init__(self, cond: Expression, body: Statement) -> None:
        super().__init__("while")
        self.cond = cond
        self.body = body

    def __getitem__(self, key: int) -> Node:
        return (self.cond, self.body)[key]

    def __len__(self) -> int:
        return 2

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitWhile(self, ctx)


class Break(Statement):
    """
    AST node of break statement.
    """

    def __init__(self) -> None:
        super().__init__("break")

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitBreak(self, ctx)

    def is_leaf(self):
        return True


class Block(Statement, ListNode[Union["Statement", "Declaration"]]):
    """
    AST node of block "statement".
    """

    def __init__(self, *children: Union[Statement, Declaration]) -> None:
        super().__init__("block", list(children))

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitBlock(self, ctx)

    def is_block(self) -> bool:
        return True


class Declaration(Node):
    """
    AST node of declaration.
    """

    def __init__(
        self,
        var_t: TypeLiteral,
        ident: Identifier,
        init_expr: Optional[Expression] = None,
        array_dim: Optional[List[IntLiteral]] = None,
    ) -> None:
        super().__init__("declaration")
        self.var_t = var_t
        self.ident = ident
        self.init_expr = init_expr or NULL
        if isinstance(self, Parameter):
            if array_dim is not None:
                for idx, dim_literal in enumerate(array_dim):
                    if idx == 0 and dim_literal is NULL:
                        continue
                    if dim_literal.value <= 0:
                        raise DecafBadArraySizeError()
        else:
            if array_dim is not None:
                for dim_literal in array_dim:
                    if dim_literal.value <= 0:
                        raise DecafBadArraySizeError()
        self.array_dim = array_dim or NULL

    def __getitem__(self, key: int) -> Node:
        return (self.var_t, self.ident, self.init_expr, self.array_dim)[key]

    def __len__(self) -> int:
        return 4

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitDeclaration(self, ctx)

class Parameter(Declaration):
    def __init__(self, var_t: TypeLiteral, ident: Identifier, array_dim: Optional[List[IntLiteral]] = None):
        super().__init__(var_t, ident, array_dim=array_dim)
        self.var_t = var_t
        self.ident = ident

    def accept(self, v: Visitor[T, U], ctx: T) -> Optional[U]:
        return v.visitParameter(self, ctx)

class Expression(Node):
    """
    Abstract type that represents an evaluable expression.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.type: Optional[DecafType] = None

class Call(Expression):
    def __init__(self, ident: Identifier, arg_list: List[Expression]):
        super(Call, self).__init__("call")
        self.ident = ident
        self.arg_list = arg_list

    def __len__(self):
        return 1 + len(self.arg_list)

    def __getitem__(self, item):
        return (
            self.ident,
            *self.arg_list
        )[item]

    def accept(self, v: Visitor[T, U], ctx: T) -> Optional[U]:
        return v.visitCall(self, ctx)

class Unary(Expression):
    """
    AST node of unary expression.
    Note that the operation type (like negative) is not among its children.
    """

    def __init__(self, op: UnaryOp, operand: Expression) -> None:
        super().__init__(f"unary({op.value})")
        self.op = op
        self.operand = operand

    def __getitem__(self, key: int) -> Node:
        return (self.operand,)[key]

    def __len__(self) -> int:
        return 1

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitUnary(self, ctx)

    def __str__(self) -> str:
        return "{}({})".format(
            self.op.value,
            self.operand,
        )


class Binary(Expression):
    """
    AST node of binary expression.
    Note that the operation type (like plus or subtract) is not among its children.
    """

    def __init__(self, op: BinaryOp, lhs: Expression, rhs: Expression) -> None:
        super().__init__(f"binary({op.value})")
        self.lhs = lhs
        self.op = op
        self.rhs = rhs

    def __getitem__(self, key: int) -> Node:
        return (self.lhs, self.rhs)[key]

    def __len__(self) -> int:
        return 2

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitBinary(self, ctx)

    def __str__(self) -> str:
        return "({}){}({})".format(
            self.lhs,
            self.op.value,
            self.rhs,
        )


class Assignment(Binary):
    """
    AST node of assignment expression.
    It's actually a kind of binary expression, but it'll make things easier if we use another accept method to handle it.
    """

    def __init__(self, lhs: Identifier, rhs: Expression) -> None:
        super().__init__(BinaryOp.Assign, lhs, rhs)

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitAssignment(self, ctx)


class ConditionExpression(Expression):
    """
    AST node of condition expression (`?:`).
    """

    def __init__(
        self, cond: Expression, then: Expression, otherwise: Expression
    ) -> None:
        super().__init__("cond_expr")
        self.cond = cond
        self.then = then
        self.otherwise = otherwise

    def __getitem__(self, key: Union[int, str]) -> Node:
        if isinstance(key, int):
            return (self.cond, self.then, self.otherwise)[key]
        return self.__dict__[key]

    def __len__(self) -> int:
        return 3

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitCondExpr(self, ctx)

    def __str__(self) -> str:
        return "({})?({}):({})".format(
            self.cond,
            self.then,
            self.otherwise,
        )


class Identifier(Expression):
    """
    AST node of identifier "expression".
    """

    def __init__(self, value: str) -> None:
        super().__init__("identifier")
        self.value = value

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIdentifier(self, ctx)

    def __str__(self) -> str:
        return f"identifier({self.value})"

    def is_leaf(self):
        return True


class IntLiteral(Expression):
    """
    AST node of int literal like `0`.
    """

    def __init__(self, value: Union[int, str]) -> None:
        super().__init__("int_literal")
        self.value = int(value)

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIntLiteral(self, ctx)

    def __str__(self) -> str:
        return f"int({self.value})"

    def is_leaf(self):
        return True


class TypeLiteral(Node):
    """
    Abstract node type that represents a type literal like `int`.
    """

    def __init__(self, name: str, _type: DecafType) -> None:
        super().__init__(name)
        self.type = _type

    def __str__(self) -> str:
        return f"type({self.type})"

    def is_leaf(self):
        return True


class TInt(TypeLiteral):
    "AST node of type `int`."

    def __init__(self) -> None:
        super().__init__("type_int", INT)

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitTInt(self, ctx)

class For(Statement):
    def __init__(
            self,
            init: Expression,
            cond: Expression,
            update: Expression,
            body: Statement,
    ):
        super().__init__("for")
        self.init = init
        self.cond = cond
        self.update = update
        self.body = body

    def __getitem__(self, key: int) -> Node:
        return (self.init, self.cond, self.update, self.body)[key]

    def __len__(self) -> int:
        return 4

    def accept(self, v: Visitor[T, U], ctx: T) -> Optional[U]:
        return v.visitFor(self, ctx)

class DoWhile(Statement):
    def __init__(
            self,
            cond: Expression,
            body: Statement,
    ):
        super().__init__("d_while")
        self.cond = cond
        self.body = body

    def __getitem__(self, key: int) -> Node:
        return (self.cond, self.body)[key]

    def __len__(self) -> int:
        return 2

    def accept(self, v: Visitor[T, U], ctx: T) -> Optional[U]:
        return v.visitDoWhile(self, ctx)


class Continue(Statement):
    def __init__(self) -> None:
        super().__init__("continue")

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitContinue(self, ctx)

    def is_leaf(self):
        return True

class Subscription(Expression):
    def __init__(self, base: Expression, index: Expression):
        super(Subscription, self).__init__("subscription")
        self.base = base
        self.index = index

    def __len__(self):
        return 2

    def __getitem__(self, item):
        return (
            self.base,
            self.index
        )[item]

    def accept(self, v: Visitor[T, U], ctx: T) -> Optional[U]:
        return v.visitSubscription(self, ctx)

class InitializerList(Node):
    def __init__(self, initializer_list: List[IntLiteral]):
        super().__init__("initializer_list")
        self.initializer_list = initializer_list
        self.value = [x.value for x in initializer_list]

    def __len__(self):
        return len(self.initializer_list)

    def __getitem__(self, item):
        return self.initializer_list[item]

    def accept(self, v: Visitor[T, U], ctx: T) -> None:
        pass
