# Stage-1 实验报告

计02 刘明道 2020011156

## 实验内容

### Step-2

在这一节中，模仿对取负节点的处理方法，将取反与逻辑非这两个一元操作的 AST 节点对应到相应的 TAC。

```diff
+++ b/frontend/tacgen/tacgen.py
@@ -109,6 +109,8 @@ class TACGen(Visitor[FuncVisitor, None]):

         op = {
             node.UnaryOp.Neg: tacop.UnaryOp.NEG,
+            node.UnaryOp.BitNot: tacop.UnaryOp.NOT,
+            node.UnaryOp.LogicNot: tacop.UnaryOp.SEQZ,
             # You can add unary operations here.
         }[expr.op]
         expr.setattr("val", mv.visitUnary(op, expr.operand.getattr("val")))
```

### Step-3

类似 Step-2，仿照对 ADD 节点的处理方法，将其余 4 种二元运算符映射到对应的 TAC。

```diff
+++ b/frontend/tacgen/tacgen.py
@@ -121,7 +121,10 @@ class TACGen(Visitor[FuncVisitor, None]):

         op = {
             node.BinaryOp.Add: tacop.BinaryOp.ADD,
-            # You can add binary operations here.
+            node.BinaryOp.Sub: tacop.BinaryOp.SUB,
+            node.BinaryOp.Mul: tacop.BinaryOp.MUL,
+            node.BinaryOp.Div: tacop.BinaryOp.DIV,
+            node.BinaryOp.Mod: tacop.BinaryOp.REM,
         }[expr.op]
         expr.setattr(
             "val", mv.visitBinary(op, expr.lhs.getattr("val"), expr.rhs.getattr("val"))
```

### Step-4

在这一节我们需要实现对 `<`, `<=`, `>=`, `>`, `==`, `!=` 这 6 种比较操作和 `&&` , `||` 这两种二元逻辑操作的支持。

与之前两步类似，首先添加相应 AST 节点到 TAC 的映射关系

```diff
+++ b/frontend/tacgen/tacgen.py
@@ -125,6 +125,16 @@ class TACGen(Visitor[FuncVisitor, None]):
             node.BinaryOp.Mul: tacop.BinaryOp.MUL,
             node.BinaryOp.Div: tacop.BinaryOp.DIV,
             node.BinaryOp.Mod: tacop.BinaryOp.REM,
+            # Comparison
+            node.BinaryOp.LT: tacop.BinaryOp.SLT,
+            node.BinaryOp.LE: tacop.BinaryOp.LEQ,
+            node.BinaryOp.GE: tacop.BinaryOp.GEQ,
+            node.BinaryOp.GT: tacop.BinaryOp.SGT,
+            node.BinaryOp.EQ: tacop.BinaryOp.EQU,
+            node.BinaryOp.NE: tacop.BinaryOp.NEQ,
+            # Logic
+            node.BinaryOp.LogicAnd: tacop.BinaryOp.AND,
+            node.BinaryOp.LogicOr: tacop.BinaryOp.OR,
         }[expr.op]
         expr.setattr(
             "val", mv.visitBinary(op, expr.lhs.getattr("val"), expr.rhs.getattr("val"))
```

由于其中的一些操作在 RISVC 中并没有单一指令的支持，还需要继续添加从 TAC 生成 RISCV 汇编的代码

```diff
+++ b/backend/riscv/riscvasmemitter.py                                                       
@@ -77,6 +77,34 @@ class RiscvAsmEmitter(AsmEmitter):                                     
...
         def visitBinary(self, instr: Binary) -> None:                                       
+            # Comparison                                                                 
+            if instr.op == BinaryOp.GEQ:                                                 
+                self.seq.append(Riscv.Binary(BinaryOp.SLT, instr.dst, instr.lhs, instr.rhs))
+                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))         
+                return                                                                   
+            if instr.op == BinaryOp.LEQ:                   
+                self.seq.append(Riscv.Binary(BinaryOp.SGT, instr.dst, instr.lhs, instr.rhs))
+                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
+                return
+            if instr.op == BinaryOp.EQU:
+                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
+                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
+                return
+            if instr.op == BinaryOp.NEQ:
+                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
+                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
+                return
+            # Logic
+            if instr.op == BinaryOp.AND:
+                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.lhs))
+                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, Riscv.ZERO, instr.dst))
+                self.seq.append(Riscv.Binary(BinaryOp.AND, instr.dst, instr.dst, instr.rhs))
+                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
+                return
+            if instr.op == BinaryOp.OR:
+                self.seq.append(Riscv.Binary(BinaryOp.OR, instr.dst, instr.lhs, instr.rhs))
+                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
+                return
             self.seq.append(Riscv.Binary(instr.op, instr.dst, instr.lhs, instr.rhs))
```

具体来说，

- `>=` 用 小于与取反表示；`<=` 用 大于与取反表示
- `==` , `!=` 用两操作数相减再判断是否为零表示
- `&&` 与 `||` 参考实验指导书中给出的汇编代码实现
- 其余操作在 RISCV 中可以使用单条指令直接实现，所以使用默认的转换规则即可

## 思考题

### Step-2

设计的表达式为 

```c
-~2147483647
```

`2147483647` 取反后变成了 `-2147483648`， 再取负后数学上应为 `2147483648` 。这超出了 $32$ 位有符号整数的表示范围。

### Step-3

如果除法的结果超出了字宽的表示范围，则也会有未定义行为。例如 $-2147483648 \div(-1)=2147483648>2147483647$

取左右操作分别为 `-2147483648` , `-1`，相应的代码为

```c
#include <stdio.h>

int main() {
  int a = -2147483648;
  int b = -1;
  printf("%d\n", a / b);
  return 0;
}
```

#### WSL x86-64 

```bash
$ gcc test.c -O0 -o test.out && ./test.out
[1]    13990 floating point exception  ./test.out
```

此时产生了一个异常

#### Qemu RISCV-32

```bash
$ riscv64-unknown-elf-gcc -std=c17 -march=rv32im -mabi=ilp32 -O0 test.c -o test.o && \
  qemu-riscv32 test.o
-2147483648
```

此时输出了溢出后的结果

### Step-4

- 短路求值可以避免无用的计算，例如在表达式

  ```c
  Exp_1 && Exp_2 && ... && Exp_i
  ```

  如果 `Exp_1` 为假，则其余表达式的值与最终结果无关，此时短路求值可以减少一些不必要的计算量

- 短路求值可以简化代码，形成简洁的 idiom。例如使用 `condition_1()` 保护另一个需要判断的 `condition_2()` 的代码可以是

  ```c
  if (condition1()) {
      if (condition2()){
          // conditional operations
      }
  }
  ```

  而使用短路求值可以等价转换成 

  ```c
  if (condition_1() && condition_2()) {
      // conditional operations
  }
  ```

  这种行为是常见的，例如 `condition_1()` 检查某个数组下标的合法性，而 `condition_2()` 的判断则会利用下标访问数组元素。使用短路求值可以让这些代码变得简洁优雅。

