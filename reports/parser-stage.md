# Parser-Stage 实验报告

计02 刘明道 2020011156

## 实验内容

在这一节，实现了递归下降的 LL(1) 语法分析。

### 解析 `relational`

`relational` 可以等价地转换为 `relational: additive { '<' additive | '<=' additive | '>' additive | '>=' additive} ` 。这表明开头必定有一个 `additive`。因此解析方式为

- 首先解析一个 `additive` 节点
- 接下来循环
  - 如果 `self.next` 是四种关系算符之一，那么利用之前构造的节点和当前解析的 `expression` ，构造一个相应符号的 `Binary` 节点

### 解析 `logical_and`

`logical_and` 可以等价转换为 `logical_and : equality { '&&' equality }` 。其余的解析方法和 `logical_or` 类似。

### 解析 `assignment`

补全的代码主要包括

- 匹配并消耗 `=`
- 返回一个 由之前解析的节点 `node ` 和 赋值语句右侧的表达式节点构成的 `Assignment `节点

### 解析 `expression`

返回解析 `assignment`

### 解析 `statement`

已经给出了匹配 expression 和 空语句的部分，补全的代码包括

- 如果下一个符号为 `If` 则返回解析 `if` 的节点，如果下一个符号为 `Return` 则返回解析 `return` 的节点

否则抛出异常

### 解析 `declaration`

已经给出了匹配类型和标识符，以及构造节点的部分，补全的代码包括解析初始化语句的部分

- 如果下一个字符为 `=` ，则
  - 匹配并消耗 `=`
  - 解析一个初始化表达式，赋给 `decl.init_expr`

### 解析 `block_item`

- 如果下一个符号属于 `statement` 的 First 集合，则返回解析 `statement`
- 如果下一个符合属于 `declaration` 的 First 集合，则解析 `declaration` ，此后匹配并消耗一个 `;` 然后返回解析到的 `declaration` 节点

### 解析 `if` 

- 匹配并消耗 `if (`
- 解析 `expression` 作为 `if ` 的条件
- 匹配并消耗 `)`
- 解析 `statement` 作为 `if` 的 `then` 部分
- 如果下一个字符为 `else` 
  - 匹配并消耗 `else`
  - 解析 `statement` 作为 `if ` 的 `otherwise` 部分
- 构造并返回 `If` 节点

### 解析 `return` 

- 匹配并消耗 `return`
- 解析 `expression ` 
- 匹配并消耗 `;`
- 构造并返回 `Return` 节点

### 解析 `type`

- 匹配并消耗 `int`
- 构造并返回 `TInt` 节点



## 思考题

### Q1

可以引入新的非终结符 `Q`，消除左递归，转换为

```ebnf
additive : multiplicative Q
Q : '+' multiplicative Q | '-' multiplicative Q | empty
```

### Q2

```c++
int main() {
    int a = 3;
    a = a / ? ;
    a = a + 1;
    return a;
}
```

以这个出错程序为例。第 3 行代码的除数非法。

当语解析到除法的第二个操作数，进行 `p_unary` 时，由于 `?` 不属于 `unary` 的 First 集合，发生错误。

使用课上讲过的短语层恢复试图恢复这个错误。这时我们要跳过不属于集合 $S=\text{BeginSym}\cup\text{EndSym}$ 中的符号。因此我们跳过了 `?` ，遇到 `;`，而 `;` 属于 $S$ （事实上 `;` 属于 $\text{EndSym}$ ）。这时 `p_unary` 返回，可以继续解析后续的输入串。

