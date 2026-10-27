"""Análisis y compilación de expresiones de plantilla.

Cada nombre libre de una expresión (`count`, `item`, `remove`) se reescribe como
`__fx_get__("count")`. El runtime resuelve ese nombre en la cadena de ámbitos
de la instancia (variables de `{#each}`, script del componente, builtins) y
desenvuelve `state`/`computed`/props. Como la resolución ocurre al evaluarse,
también funciona dentro de `lambda` y comprensiones, incluso más tarde, cuando
un manejador `on:click={lambda: borrar(item["id"])}` se ejecuta.

Los manejadores `on:` admiten además código *en línea*: una llamada
(`on:click={borrar(item["id"])}`) o sentencias simples (`on:click={n += 1}`).
Las asignaciones a nombres se reescriben como `__fx_set__("n", valor)`, que
el runtime aplica al `state` correspondiente.
"""
from __future__ import annotations

import ast
import textwrap
from types import CodeType

from .ast_nodes import Expression

GETTER = "__fx_get__"
SETTER = "__fx_set__"
RUNNER = "__fx_run__"  # recibe el valor de cada sentencia-expresión (lanza corrutinas)
EVENT_NAME = "event"  # en un manejador en línea: el argumento del evento

SIMPLE_STATEMENTS = (ast.Expr, ast.Assign, ast.AugAssign, ast.Pass)
# Un manejador cuyo valor es una función (se llama con los argumentos del evento).
_REFERENCE_NODES = (ast.Name, ast.Attribute, ast.Subscript, ast.Lambda, ast.IfExp)


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


# -- manejadores -------------------------------------------------------------------
def parse_statements(code: str) -> ast.Module:
    code = code.strip("\n")
    return ast.parse(textwrap.dedent(code) if "\n" in code else code.strip())


def is_inline_handler(code: str) -> bool:
    """`on:x={f}` o `{lambda: ...}` dan una función; una llamada o sentencias se ejecutan en línea."""
    try:
        tree = parse_expression(code)
    except SyntaxError:
        return True
    return not isinstance(tree.body, _REFERENCE_NODES)


def _handler_module(code: str) -> ast.Module:
    try:
        tree = parse_expression(code)
    except SyntaxError:
        return parse_statements(code)
    return ast.Module([ast.Expr(tree.body)], [])


def _store_names(module: ast.Module) -> list[str]:
    names: list[str] = []
    for st in module.body:
        targets = st.targets if isinstance(st, ast.Assign) else [st.target] if isinstance(st, ast.AugAssign) else []
        for target in targets:
            for node in ast.walk(target):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id not in names:
                    names.append(node.id)
    return names


def handler_names(code: str) -> tuple[list[str], list[str]]:
    """(nombres leídos, nombres asignados) de un manejador en línea."""
    module = _handler_module(code)
    stores = _store_names(module)
    walker = _Scoped(rewrite=False)
    walker.bound[0].add(EVENT_NAME)
    walker.visit(module)
    return walker.free, stores


def _getter(name: str) -> ast.Call:
    return ast.Call(ast.Name(GETTER, ast.Load()), [ast.Constant(name)], [])


def _setter(name: str, value: ast.expr) -> ast.Expr:
    return ast.Expr(ast.Call(ast.Name(SETTER, ast.Load()), [ast.Constant(name), value], []))


def _rewrite_assignments(module: ast.Module) -> ast.Module:
    """`n += 1` → `__fx_set__("n", __fx_get__("n") + 1)`; `a, b = x` pasa por variables temporales."""
    body: list[ast.stmt] = []
    for st in module.body:
        if isinstance(st, ast.AugAssign) and isinstance(st.target, ast.Name):
            value = ast.BinOp(_getter(st.target.id), st.op, st.value)
            body.append(ast.copy_location(_setter(st.target.id, value), st))
        elif isinstance(st, ast.Expr):
            call = ast.Call(ast.Name(RUNNER, ast.Load()), [st.value], [])
            body.append(ast.copy_location(ast.Expr(call), st))
        elif isinstance(st, ast.Assign):
            sets: list[tuple[str, str]] = []
            for target in st.targets:
                for node in ast.walk(target):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                        temp = f"__fx_t{len(sets)}"
                        sets.append((node.id, temp))
                        node.id = temp
            body.append(st)
            body.extend(ast.copy_location(_setter(name, ast.Name(temp, ast.Load())), st) for name, temp in sets)
        else:
            body.append(st)
    module.body = body
    return module


def compile_handler(expression: Expression, file: str) -> CodeType:
    """Código de un manejador en línea, listo para `exec` con `GETTER` y `SETTER` en el entorno."""
    module = _handler_module(expression.code)
    walker = _Scoped(rewrite=True)
    walker.bound[0].add(EVENT_NAME)
    module = _rewrite_assignments(walker.visit(module))
    ast.fix_missing_locations(module)
    ast.increment_lineno(module, expression.loc.line - 1)
    return compile(module, file, "exec")
