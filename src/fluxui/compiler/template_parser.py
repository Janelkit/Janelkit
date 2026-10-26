"""Parser de la plantilla: elementos, atributos, texto, `{expresiones}` y bloques.

No es un parser XML: admite expresiones Python entre llaves (con cadenas que
pueden contener llaves) y los bloques `{#if}`/`{:else}`/`{/if}`,
`{#each}`/`{:else}`/`{/each}` y `{#key}`/`{/key}`.
"""
from __future__ import annotations

import ast
import re

from ..diagnostics import Diagnostic, FluxError, SourceLocation, location_at
from .ast_nodes import (
    Attribute,
    EachBlock,
    Element,
    Expression,
    IfBlock,
    IfBranch,
    Interpolation,
    KeyBlock,
    Node,
    Text,
)

_TAG_RE = re.compile(r"[A-Za-z][\w.]*")
_ATTR_NAME_RE = re.compile(r"[A-Za-z_][\w:.-]*")
_EACH_RE = re.compile(
    r"^(?P<iter>.+?)\s+as\s+(?P<item>[A-Za-z_]\w*)"
    r"(?:\s*,\s*(?P<index>[A-Za-z_]\w*))?\s*(?:\((?P<key>.*)\))?\s*$",
    re.DOTALL,
)


class _Stop(Exception):
    """Señal interna: se encontró `{:...}` o `{/...}` que cierra un bloque."""

    def __init__(self, nodes: list[Node]):
        self.nodes = nodes


def parse_template(text: str, file: str, source: str | None = None) -> list[Node]:
    return _TemplateParser(text, file, source if source is not None else text).parse()


def validate_expression(code: str, loc: SourceLocation, source: str) -> None:
    """Comprueba que `code` sea una expresión Python válida."""
    if not code.strip():
        raise FluxError(Diagnostic("expresión vacía", loc, "escribe una expresión entre las llaves", source=source))
    stripped = code.lstrip()
    multiline = "\n" in stripped.rstrip()
    # Entre paréntesis se admiten expresiones repartidas en varias líneas.
    candidate = "(" + stripped + "\n)" if multiline else stripped
    try:
        ast.parse(candidate, mode="eval")
        return
    except SyntaxError as e:
        err = e
    # Ubicación del error relativa al texto sin espacios iniciales.
    skipped = code[: len(code) - len(stripped)]
    start_line = loc.line + skipped.count("\n")
    start_col = (len(skipped) - skipped.rfind("\n")) if "\n" in skipped else loc.column + len(skipped)
    err_line = err.lineno or 1
    err_col = (err.offset or 1) - (1 if multiline and err_line == 1 else 0)
    line = start_line + err_line - 1
    col = start_col + err_col - 1 if err_line == 1 else err_col
    last_line = loc.line + code.rstrip().count("\n")
    if line > last_line:  # error en el paréntesis de cierre añadido: señalar el final real
        line = last_line
        tail = code.rstrip()
        col = len(tail) - tail.rfind("\n") if "\n" in tail else loc.column + len(tail)
    raise FluxError(
        Diagnostic(
            f"expresión Python no válida: {err.msg}",
            SourceLocation(loc.file, line, max(col, 1)),
            "las llaves de la plantilla aceptan expresiones, no sentencias",
            source=source,
        )
    )


class _TemplateParser:
    def __init__(self, text: str, file: str, source: str):
        self.text = text
        self.file = file
        self.source = source
        self.pos = 0

    # -- utilidades ---------------------------------------------------------
    def loc(self, offset: int | None = None) -> SourceLocation:
        return location_at(self.file, self.text, self.pos if offset is None else offset)

    def error(self, msg: str, offset: int | None = None, hint: str | None = None) -> FluxError:
        return FluxError(Diagnostic(msg, self.loc(offset), hint, source=self.source))

    def startswith(self, s: str) -> bool:
        return self.text.startswith(s, self.pos)

    def skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def eof(self) -> bool:
        return self.pos >= len(self.text)

    # -- entrada ------------------------------------------------------------
    def parse(self) -> list[Node]:
        try:
            return self.parse_children(closing=None)
        except _Stop:
            raise self.error(f"directiva {self._peek_directive()} sin bloque abierto") from None

    def parse_children(self, closing: Element | None, block: tuple[str, int] | None = None) -> list[Node]:
        """Analiza hijos hasta el cierre de `closing`, o hasta `{:..}`/`{/..}` si hay un bloque abierto."""
        nodes: list[Node] = []
        while True:
            if self.eof():
                if closing is not None:
                    raise FluxError(
                        Diagnostic(
                            f"el elemento <{closing.tag}> no está cerrado",
                            closing.loc,
                            f"añade </{closing.tag}> o usa <{closing.tag} />",
                            source=self.source,
                        )
                    )
                return nodes
            if self.startswith("<!--"):
                end = self.text.find("-->", self.pos)
                if end < 0:
                    raise self.error("comentario sin cerrar", hint="cierra el comentario con -->")
                self.pos = end + 3
            elif self.startswith("</"):
                start = self.pos
                self.pos += 2
                m = _TAG_RE.match(self.text, self.pos)
                name = m.group(0) if m else ""
                self.pos += len(name)
                self.skip_ws()
                if not self.startswith(">"):
                    raise self.error(f"cierre </{name}> mal formado", start)
                self.pos += 1
                if block is not None:
                    kind, bstart = block
                    raise self.error(
                        f"se encontró </{name}> antes de cerrar el bloque {{#{kind}}}",
                        start,
                        f"el bloque se abrió en la línea {self.loc(bstart).line}; añade {{/{kind}}}",
                    )
                if closing is None:
                    raise self.error(f"cierre </{name}> sin elemento abierto", start)
                if name != closing.tag:
                    raise self.error(
                        f"se esperaba </{closing.tag}> pero se encontró </{name}>",
                        start,
                        f"<{closing.tag}> se abrió en la línea {closing.loc.line}",
                    )
                return nodes
            elif self.startswith("<") and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isalpha():
                nodes.append(self.parse_element())
            elif self.startswith("{#"):
                nodes.append(self.parse_block())
            elif self.startswith("{:") or self.startswith("{/"):
                if block is not None:
                    raise _Stop(nodes)
                if closing is not None:
                    raise self.error(
                        f"directiva {self._peek_directive()} inesperada dentro de <{closing.tag}>",
                        hint=f"cierra </{closing.tag}> antes de terminar el bloque",
                    )
                raise self.error(f"directiva {self._peek_directive()} sin bloque abierto")
            elif self.startswith("{"):
                start = self.pos
                expr = self.read_braced()
                nodes.append(Interpolation(expr, self.loc(start)))
            elif self.startswith("<"):
                raise self.error("carácter '<' inesperado", hint="los nombres de elemento empiezan con una letra")
            else:
                start = self.pos
                while not self.eof() and self.text[self.pos] not in "<{":
                    self.pos += 1
                nodes.append(Text(self.text[start:self.pos], self.loc(start)))

    def _peek_directive(self) -> str:
        end = self.text.find("}", self.pos)
        return self.text[self.pos:end + 1] if end >= 0 else self.text[self.pos:self.pos + 10]

    # -- elementos ----------------------------------------------------------
    def parse_element(self) -> Element:
        start = self.pos
        self.pos += 1
        tag = _TAG_RE.match(self.text, self.pos).group(0)
        self.pos += len(tag)
        element = Element(tag, [], [], self.loc(start))
        seen: set[str] = set()
        while True:
            self.skip_ws()
            if self.eof():
                raise self.error(f"la etiqueta <{tag}> no está cerrada", start, "falta '>' o '/>'")
            if self.startswith("/>"):
                self.pos += 2
                return element
            if self.startswith(">"):
                self.pos += 1
                element.children = self.parse_children(closing=element)
                return element
            attr = self.parse_attribute()
            if attr.name in seen:
                raise FluxError(Diagnostic(f"atributo duplicado '{attr.name}'", attr.loc, source=self.source))
            seen.add(attr.name)
            element.attributes.append(attr)

    def parse_attribute(self) -> Attribute:
        start = self.pos
        if self.startswith("{"):
            # Forma abreviada {name} equivalente a name={name}
            expr = self.read_braced()
            name = expr.code.strip()
            if not name.isidentifier():
                raise FluxError(
                    Diagnostic("la forma abreviada {nombre} solo admite un identificador", expr.loc, source=self.source)
                )
            return Attribute(name, expr, self.loc(start))
        m = _ATTR_NAME_RE.match(self.text, self.pos)
        if not m:
            raise self.error(f"atributo no válido cerca de {self.text[self.pos:self.pos + 10]!r}")
        name = m.group(0)
        self.pos = m.end()
        self.skip_ws()
        if not self.startswith("="):
            return Attribute(name, True, self.loc(start))
        self.pos += 1
        self.skip_ws()
        if self.startswith("{"):
            return Attribute(name, self.read_braced(), self.loc(start))
        quote = self.text[self.pos] if not self.eof() else ""
        if quote not in "\"'" or not quote:
            raise self.error(f"valor del atributo '{name}' no válido", hint='usa comillas "..." o llaves {...}')
        end = self.text.find(quote, self.pos + 1)
        if end < 0:
            raise self.error(f"falta la comilla de cierre en el atributo '{name}'")
        value = self.text[self.pos + 1:end]
        self.pos = end + 1
        return Attribute(name, value, self.loc(start))

    # -- expresiones --------------------------------------------------------
    def read_braced(self, validate: bool = True) -> Expression:
        """Lee `{...}` respetando llaves anidadas y cadenas Python."""
        open_pos = self.pos
        self.pos += 1
        depth = 1
        text = self.text
        while self.pos < len(text):
            ch = text[self.pos]
            if ch in "\"'":
                triple = text.startswith(ch * 3, self.pos)
                delim = ch * 3 if triple else ch
                end = self.pos + len(delim)
                while True:
                    end = text.find(delim, end)
                    if end < 0:
                        raise self.error("cadena sin cerrar dentro de la expresión", self.pos)
                    if text[end - 1] != "\\":
                        break
                    end += 1
                self.pos = end + len(delim)
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    code = text[open_pos + 1:self.pos]
                    self.pos += 1
                    expr = Expression(code, self.loc(open_pos + 1))
                    if validate:
                        validate_expression(code, expr.loc, self.source)
                    return expr
            self.pos += 1
        raise self.error("falta '}' para cerrar la expresión", open_pos)

    # -- bloques --------------------------------------------------------------
    def parse_block(self) -> Node:
        start = self.pos
        raw = self.read_braced(validate=False)
        content = raw.code
        keyword = content[1:].split(None, 1)[0] if len(content) > 1 else ""
        rest = content[1 + len(keyword):]
        rest_loc = self.loc(start + 2 + len(keyword))
        if keyword == "if":
            cond = self._expr(rest, rest_loc, "{#if condición}")
            return self.parse_if(start, cond)
        if keyword == "each":
            return self.parse_each(start, rest, rest_loc)
        if keyword == "key":
            expr = self._expr(rest, rest_loc, "{#key expresión}")
            return self.parse_key(start, expr)
        raise self.error(
            f"bloque desconocido '{{#{keyword}}}'", start, "los bloques disponibles son {#if}, {#each} y {#key}"
        )

    def parse_key(self, start: int, expr: Expression) -> KeyBlock:
        block = KeyBlock(expr, [], self.loc(start))
        try:
            self.parse_children(closing=None, block=("key", start))
        except _Stop as stop:
            block.children = stop.nodes
        else:
            raise self.error("el bloque {#key} no está cerrado", start, "añade {/key}")
        dstart = self.pos
        directive = self.read_braced(validate=False).code.strip()
        if directive != "/key":
            raise self.error(f"directiva {{{directive}}} inesperada dentro de {{#key}}", dstart, "cierra el bloque con {/key}")
        return block

    def _expr(self, code: str, loc: SourceLocation, form: str) -> Expression:
        if not code.strip():
            raise FluxError(Diagnostic(f"falta la expresión en {form}", loc, source=self.source))
        # Ajustar ubicación al primer carácter no blanco.
        stripped = code.lstrip()
        loc = SourceLocation(loc.file, loc.line, loc.column + len(code) - len(stripped))
        validate_expression(stripped, loc, self.source)
        return Expression(stripped, loc)

    def parse_if(self, start: int, cond: Expression) -> IfBlock:
        block = IfBlock([], self.loc(start))
        branch = IfBranch(cond, [], self.loc(start))
        while True:
            try:
                self.parse_children(closing=None, block=("if", start))
            except _Stop as stop:
                branch.children = stop.nodes
            else:
                raise self.error("el bloque {#if} no está cerrado", start, "añade {/if}")
            block.branches.append(branch)
            dstart = self.pos
            directive = self.read_braced(validate=False).code.strip()
            if directive == "/if":
                return block
            if directive == ":else":
                if branch.condition is None:
                    raise self.error("{:else} repetido en el mismo bloque {#if}", dstart)
                branch = IfBranch(None, [], self.loc(dstart))
                continue
            if directive.startswith(":else if"):
                if branch.condition is None:
                    raise self.error("{:else if} después de {:else}", dstart)
                code = self.text[dstart + 1:self.pos - 1]
                offset = code.index("if") + 2
                cond = self._expr(code[offset:], self.loc(dstart + 1 + offset), "{:else if condición}")
                branch = IfBranch(cond, [], self.loc(dstart))
                continue
            raise self.error(f"directiva {{{directive}}} inesperada dentro de {{#if}}", dstart, "cierra el bloque con {/if}")

    def parse_each(self, start: int, rest: str, rest_loc: SourceLocation) -> EachBlock:
        m = _EACH_RE.match(rest.strip())
        if not m:
            raise self.error(
                "sintaxis de {#each} no válida",
                start,
                "usa {#each elementos as elemento (clave)}",
            )
        lead = len(rest) - len(rest.lstrip())
        base = SourceLocation(rest_loc.file, rest_loc.line, rest_loc.column + lead)
        iterable = self._expr(m.group("iter"), base, "{#each}")
        key = None
        if m.group("key") is not None:
            key_off = rest.strip().rfind("(") + 1
            key = self._expr(
                m.group("key"), SourceLocation(base.file, base.line, base.column + key_off), "clave de {#each}"
            )
        block = EachBlock(iterable, m.group("item"), m.group("index"), key, [], self.loc(start))
        try:
            self.parse_children(closing=None, block=("each", start))
        except _Stop as stop:
            block.children = stop.nodes
        else:
            raise self.error("el bloque {#each} no está cerrado", start, "añade {/each}")
        dstart = self.pos
        directive = self.read_braced(validate=False).code.strip()
        if directive == ":else":
            try:
                self.parse_children(closing=None, block=("each", start))
            except _Stop as stop:
                block.else_children = stop.nodes
            else:
                raise self.error("el bloque {#each} no está cerrado", start, "añade {/each}")
            dstart = self.pos
            directive = self.read_braced(validate=False).code.strip()
        if directive != "/each":
            raise self.error(f"directiva {{{directive}}} inesperada dentro de {{#each}}", dstart, "cierra el bloque con {/each}")
        return block
