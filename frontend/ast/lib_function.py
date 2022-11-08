from typing import Dict, Callable

from frontend.ast.tree import Program
from frontend.parser import Parser

lib_funcs: Dict[str, str] = {
    "fill_n": r"""
    int %s(int a[], int n, int v) {
      for (int i = 0; i < n; i = i + 1) {
        a[i] = v;
      }
      return 0;
    }
    """
}

def inject_func(program: Program, func_name: str, parse_func: Callable[[str], Program]):
    func_name_orig = func_name
    func_decl = lib_funcs[func_name]
    while func_name in program.functions():
        func_name += "_"
    lib_program = parse_func(func_decl % func_name)
    program.addLibFunction(func_name_orig, lib_program.children[0])
