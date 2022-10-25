# Stage-2

计02 刘明道 2020011156

## 实验内容

### Step-5

在这一步中要实现局部变量声明和赋值的解析操作。

#### 构建符号表

在 `frontend/typecheck/namer.py`

- 访问声明节点时
  - 首先检查 `Identifier` 是否冲突，冲突则报错
  - 然后为 `Identifeir` 在符号表中分配符号，并将符号设为声明的属性
  - 如果有初始化语句，访问它

```python
    def visitDeclaration(self, decl: Declaration, ctx: ScopeStack) -> None:
        if ctx.findConflict(decl.ident.value) is not None:
            raise DecafDeclConflictError(decl.ident.value)
        var = VarSymbol(decl.ident.value, decl.var_t.type)
        ctx.declare(var)
        decl.setattr('symbol', var)
        if decl.init_expr is not NULL:
            decl.init_expr.accept(self, ctx)
```

- 访问赋值节点时
  - 检查左操作数是否为 `Identifier` ，若不是则报错
  - 调用 `visitBinary` 进行访问

```python
    def visitAssignment(self, expr: Assignment, ctx: ScopeStack) -> None:
        if not isinstance(expr.lhs, Identifier):
            raise DecafSyntaxError(f'Cannot assign to value to {type(expr.lhs).__name__}')
        self.visitBinary(expr, ctx)
```

- 访问标识符节点时
  - 检查符号表中该标识符是否被声明过
  - 将声明中分配的符号赋给标识符的属性，便于后续取用

```python
    def visitIdentifier(self, ident: Identifier, ctx: ScopeStack) -> None:
        symbol = ctx.lookup(ident.value)
        if symbol is None:
            raise DecafUndefinedVarError(f'Identifier {ident.value} is not defined')
        ident.setattr('symbol', symbol)
```

#### 将 AST 转换为 TAC

接下来是到 TAC 的转换，在 `frontend/tacgen/tacgen.py` 中

- 访问声明时
  - 为声明的标识符分配临时变量
  - 如果声明有配套的赋值语句，则访问赋值语句进行赋值

```python
    def visitDeclaration(self, decl: Declaration, mv: FuncVisitor) -> None:
        decl.getattr('symbol').temp = mv.freshTemp()
        if decl.init_expr is not NULL:
            decl.init_expr.accept(self, mv)
            mv.visitAssignment(decl.getattr('symbol').temp, decl.init_expr.getattr('val'))
```

- 访问赋值语句、标识符、整数字面量时

  - 访问赋值语句时

    - 访问左操作数，也就是一个标识符，此时会找到将标识符在声明时对应符号的临时变量

    - 访问右操作数，可能是赋值语句、标识符、字面量等。这次访问后，该节点会具有一个 `val` 的属性指向其值所对应的临时变量。
    - 之后调用 `FuncVisitor` 的 `visitAssignment` 生成对应的 `Assign` 指令

```python
    def visitAssignment(self, expr: Assignment, mv: FuncVisitor) -> None:
        expr.rhs.accept(self, mv)
        expr.lhs.accept(self, mv)
        expr.setattr(
            'val',
            mv.visitAssignment(
                expr.lhs.getattr('val'),
                expr.rhs.getattr('val'),
            )
        )
        
    def visitIdentifier(self, ident: Identifier, mv: FuncVisitor) -> None:
        ident.setattr('val', ident.getattr('symbol').temp)    
        
    def visitIntLiteral(self, expr: IntLiteral, mv: FuncVisitor) -> None:
        expr.setattr("val", mv.visitLoad(expr.value))
```

### 将 TAC 转换为 RISCV 指令

在 `backend/riscv/riscvasmemitter.py` 中，新增对 TAC 指令 `Assign` 的访问，将其简单翻译为 RISCV 的 `mv` 指令

```python
        def visitAssign(self, instr: Assign) -> None:
            self.seq.append(Riscv.Move(instr.dst, instr.src))
```

### Step-6

这一步需要照着对 `if` 语句的支持，完成对 `ternary` 的支持

- 首先需要在构造符号表时访问 `ConditionalExpression` 这里由于条件表达式必定有 `otherwise` 语句，因此直接全部访问即可

```python
    def visitCondExpr(self, expr: ConditionExpression, ctx: ScopeStack) -> None:
        expr.cond.accept(self, ctx)
        expr.then.accept(self, ctx)
        expr.otherwise.accept(self, ctx)
```

- 在转换为 TAC 的阶段，同样按照对 `if` 语句的支持完成代码。与 `if` 不同的是，条件表达式需要一个值，此时可以再额外申请一个临时变量 `exprValue` 储存该表达式的值。

```python
    def visitCondExpr(self, expr: ConditionExpression, mv: FuncVisitor) -> None:
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
```



## 思考题

### Step-5

1. 可以使用如下汇编指令

```asm
addi sp, sp, -16
```

2. 

   - 考虑到程序是顺序执行，后面的声明会覆盖前面的，因此只需要记住最后一次的定义并进行使用

   - 可以在标识符表中记录标识符对应符号的名称和计数，如 `{variable_name}_{version_counter}`
   - 在 `visitDeclaration` 中声明标识符时，
     - 如果标识符不存在，则在符号表中新建计数为 0 的符号，记为 `{variable_name}_0` 
     - 此后再次声明时，则为该标识符再另外创建一个符号，但计数器数增加 1
     - 对于重新声明已经存在的变量时，如果声明的同时进行初始化，如 `a=f(a)` ，则应该先访问赋值的右操作数，接着声明新变量（更新符号表中的计数器），然后再访问左操作数。
   - 在 `visitIdentifier` 为标识符节点分配符号时，总是取该标识符在符号表中计数器最大的符号

### Step-6

1. `Python` 编译框架中，`statement` 分为 `statement_matched` 与 `statement_unmatched` 。对于 `if-else` 组合来说，`if` 与 `else` 之间必须为 `statement_matched` 。这样悬吊的 `else` 只能与最近的 `if` 结合，构成 `statement_matched` 后再与外部结合；而假设悬吊 `else ` 与不相邻的 `if` 结合，则会导致 `if-else` 之间出现 `statement_unmatched` ，矛盾。

2. 可以修改生成 TAC 的代码中访问条件表达式的部分。

   - 首先顺序访问 `cond` , `then` 和 `otherwise` 

       ```python
       expr.cond.accept(self, mv)
       expr.then.accept(self, mv)
       expr.otherwise.accept(self, mv)
       ```

   - 然后根据条件进行跳转，给表达式赋值

       ```python
       skipLabel = mv.freshLabel()
       exitLabel = mv.freshLabel()
       exprValue = mv.freshTemp()
       
       mv.visitCondBranch(
           tacop.CondBranchOp.BEQ, expr.cond.getattr("val"), skipLabel
       )
       mv.visitAssignment(exprValue, expr.then.getattr("val"))
       mv.visitBranch(exitLabel)
       
       mv.visitLabel(skipLabel)
       mv.visitAssignment(exprValue, expr.otherwise.getattr("val"))
       mv.visitLabel(exitLabel)
       
       expr.setattr('val', exprValue)
       ```

       
