## 声明

**如果您是选报了清华大学计算机系《编译原理》选课同学，请立即关闭此页面，[禁止抄袭](hhttps://decaf-lang.github.io/minidecaf-tutorial/#%E8%AF%9A%E4%BF%A1%E5%AE%88%E5%88%99)。**

**注：《学生纪律处分管理规定实施细则》节选：**

>**第六章 学术不端、违反学习纪律的行为与处分**
>
>**第二十一条 有下列违反课程学习纪律情形之一的，给予警告以上、留校察看以下处分：**
>
> **（一）课程作业抄袭严重的；**
>
> **（二）实验报告抄袭严重或者篡改实验数据的；**
>
> **（三）期中、期末课程论文抄袭严重的；**
>
> **（四）在课程学习过程中严重弄虚作假的其他情形。**

---

[2023-11-19] This repository is reset subject to complaints about plagiarism.

# MiniDecaf Python 框架

## 依赖

- **Python >= 3.9**
- requirements.txt 里的 python 库，包括 ply 和 argparse。
- RISC-V 运行环境（参见实验指导书）

## 运行

```
python3 main.py --input <testcase.c> [--riscv/--tac/--parse]
```

各参数意义如下：

| 参数 | 含义 |
| --- | --- |
| `input` | 输入的 Minidecaf 代码位置 |
| `riscv` | 输出 RISC-V 汇编 |
| `tac` | 输出三地址码 |
| `parse` | 输出抽象语法树 |

## 代码结构

```
minidecaf/
    frontend/       前端（与中端）
        ast/        语法树定义
        lexer/      词法分析
        parser/     语法分析
        type/       类型定义
        symbol/     符号定义
        scope/      作用域定义
        typecheck/  语义分析（符号表构建、类型检查）
        tacgen/     中间代码 TAC 生成
    backend/        后端
        dataflow/   数据流分析
        reg/        寄存器分配
        riscv/      RISC-V 平台相关
    utils/          底层类
        label/      标签定义
        tac/        TAC 定义和基本类
```
