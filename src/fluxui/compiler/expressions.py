"""Análisis y compilación de expresiones de plantilla.

Cada nombre libre de una expresión (`count`, `item`, `remove`) se reescribe como
`__fx_get__("count")`. El runtime resuelve ese nombre en la cadena de ámbitos
de la instancia (variables de `{#each}`, script del componente, builtins) y
desenvuelve `state`/`computed`/props. Como la resolución ocurre al evaluarse,
también funciona dentro de `lambda` y comprensiones, incluso más tarde, cuando
un manejador `on:click={lambda: borrar(item["id"])}` se ejecuta.
"""
from __future__ import annotations

import ast
from types import CodeType

from .ast_nodes import Expression

GETTER = "__fx_get__"


def parse_expression(code: str) -> ast.Expression:
    # Los paréntesis permiten expresiones de varias líneas; el salto final evita
    # que un comentario `# ...` se coma el paréntesis de cierre.
    return ast.parse("(" + code.strip() + "\n)", mode="eval")


class _Scoped(ast.NodeTransformer):
    """Recorre la expresión distinguiendo nombres libres de los ligados por lambda o comprensiones."""

    def __init__(self, rewrite: bool):
        self.rewrite = rewrite
        self.bound: list[set[str]] = [set()]
        self.free: list[str] = []

    def _is_bound(self, name: str) -> bool:
        return any(name in scope for scope in self.bound)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load) and not self._is_bound(node.id):
            if node.id not in self.free:
                self.free.append(node.id)
            if self.rewrite:
                call = ast.Call(ast.Name(GETTER, ast.Load()), [ast.Constant(node.id)], [])
                return ast.copy_location(call, node)
        return node

    def visit_NamedExpr(self, node: ast.NamedExpr):
        node.value = self.visit(node.value)
        self.bound[0].add(node.target.id)
        return node

    def visit_Lambda(self, node: ast.Lambda):
        self.generic_visit(node.args)  # valores por defecto: ámbito exterior
        a = node.args
        names = {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
        names |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
        self.bound.append(names)
        node.body = self.visit(node.body)
        self.bound.pop()
        return node

    def _comprehension(self, node, fields: tuple[str, ...]):
        generators = node.generators
        generators[0].iter = self.visit(generators[0].iter)
        self.bound.append(set())
        for i, gen in enumerate(generators):
            if i:
                gen.iter = self.visit(gen.iter)
            self.bound[-1] |= {n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name)}
            gen.ifs = [self.visit(cond) for cond in gen.ifs]
        for name in fields:
            setattr(node, name, self.visit(getattr(node, name)))
        self.bound.pop()
        return node

    def visit_ListComp(self, node):
        return self._comprehension(node, ("elt",))

    def visit_SetComp(self, node):
        return self._comprehension(node, ("elt",))

    def visit_GeneratorExp(self, node):
        return self._comprehension(node, ("elt",))

    def visit_DictComp(self, node):
        return self._comprehension(node, ("key", "value"))


def free_names(code: str) -> list[str]:
    """Nombres que la expresión toma de su entorno, en orden de aparición."""
    walker = _Scoped(rewrite=False)
    walker.visit(parse_expression(code))
    return walker.free


def compile_expression(expression: Expression, file: str) -> CodeType:
    """Código listo para `eval(code, {GETTER: resolver, "__builtins__": ...})`.

    Los números de línea apuntan al `.flux`, de modo que los tracebacks muestran
    la línea real de la plantilla.
    """
    tree = _Scoped(rewrite=True).visit(parse_expression(expression.code))
    ast.fix_missing_locations(tree)
    ast.increment_lineno(tree, expression.loc.line - 1)
    return compile(tree, file, "eval")
