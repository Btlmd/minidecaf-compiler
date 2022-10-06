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

## 思考题

### Step-5

1. 可以使用如下汇编指令

```asm
addi sp, sp, -16
```

2. 可以在进行符号表构建的过程中进行如下修改

   - 在标识符表中记录标识符对应符号的名称和版本，如 `{variable_name}_{version_counter}`

   - 在 `visitDeclaration` 中声明标识符时，
     - 如果标识符不存在，则在符号表中新建第 0 版，记为 `{variable_name}_0` 
     - 此后再次声明时，则为该标识符再另外创建一个符号，但版本数增加 1
   - 在 `visitIdentifier` 为标识符节点分配符号时，总是该标识符在符号表中版本数最大的符号

### Step-6

