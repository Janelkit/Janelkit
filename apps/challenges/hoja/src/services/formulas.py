"""Fórmulas de la hoja: `=A1+B2*2`, `=SUMA(A1:A100)`, `=PROMEDIO(B1:B10; 3)`.

Una fórmula se compila una vez (en caché por texto) a una función `fn(leer)`, donde
`leer(fila, col)` devuelve el valor de otra celda. Quien llama decide cómo se obtiene;
en la hoja, leyendo el `computed` de esa celda, así que las dependencias las registra
JanelKit sin que la fórmula las declare.

Valores: `float`, `str` o `None` (vacía). Un error es un `Error` (subclase de `str`),
que se propaga a las fórmulas que lo usan.
"""
from __future__ import annotations

import operator
import re
from functools import lru_cache
from typing import Any, Callable

Leer = Callable[[int, int], Any]
Nodo = Callable[[Leer], Any]


class Error(str):
    """Valor de error de una celda: `#DIV/0!`, `#VALOR!`, `#REF!`, `#CICLO!`, `#NOMBRE?`, `#ERROR!`."""


class FalloFormula(Exception):
    def __init__(self, codigo: str):
        super().__init__(codigo)
        self.codigo = codigo


def nombre_col(c: int) -> str:
    return chr(ord("A") + c)


def nombre(r: int, c: int) -> str:
    return f"{nombre_col(c)}{r + 1}"


def referencia(texto: str) -> tuple[int, int]:
    """"B12" -> (11, 1)."""
    m = re.fullmatch(r"([A-Za-z])(\d+)", texto.strip())
    if not m or int(m[2]) < 1:
        raise FalloFormula("#REF!")
    return int(m[2]) - 1, ord(m[1].upper()) - ord("A")


def interpretar(texto: str) -> Any:
    """Valor de una celda que no es fórmula: número (con punto o con coma decimal), texto o None."""
    t = texto.strip()
    if not t:
        return None
    for candidato in (t, t.replace(",", ".") if t.count(",") == 1 and "." not in t else None):
        if candidato is not None:
            try:
                return float(candidato)
            except ValueError:
                pass
    return t


def mostrar(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float):
        if valor.is_integer() and abs(valor) < 1e15:
            return str(int(valor))
        return f"{valor:.10g}"
    return str(valor)


def numero(valor: Any) -> float:
    if isinstance(valor, Error):
        raise FalloFormula(valor)
    if valor is None:
        return 0.0
    if isinstance(valor, float):
        return valor
    raise FalloFormula("#VALOR!")


def _numeros(valores: list[Any]) -> list[float]:
    """Como en las hojas de cálculo: en un rango, el texto y las vacías no cuentan; los errores sí."""
    out = []
    for v in valores:
        if isinstance(v, Error):
            raise FalloFormula(v)
        if isinstance(v, float):
            out.append(v)
    return out


def _promedio(xs: list[float]) -> float:
    if not xs:
        raise FalloFormula("#DIV/0!")
    return sum(xs) / len(xs)


FUNCIONES: dict[str, Callable[[list[float]], float]] = {
    "SUMA": sum, "SUM": sum,
    "PROMEDIO": _promedio, "AVERAGE": _promedio,
    "MIN": lambda xs: min(xs, default=0.0),
    "MAX": lambda xs: max(xs, default=0.0),
    "CONTAR": lambda xs: float(len(xs)), "COUNT": lambda xs: float(len(xs)),
}  # fmt: skip


def _dividir(a: float, b: float) -> float:
    if b == 0:
        raise FalloFormula("#DIV/0!")
    return a / b


def _potencia(a: float, b: float) -> float:
    try:
        r = a**b
    except (OverflowError, ZeroDivisionError):
        raise FalloFormula("#VALOR!") from None
    if isinstance(r, complex):
        raise FalloFormula("#VALOR!")
    return r


OPERADORES = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": _dividir, "^": _potencia}

TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
    r"|(?P<rango>[A-Za-z]\d+:[A-Za-z]\d+)"
    r"|(?P<ref>[A-Za-z]\d+)"
    r"|(?P<fn>[A-Za-z]+)(?=\s*\()"
    r"|(?P<txt>\"[^\"]*\")"
    r"|(?P<op>[-+*/^(),;]))"
)


def _tokens(texto: str) -> list[tuple[str, str]]:
    out, pos, texto = [], 0, texto.rstrip()
    while pos < len(texto):
        m = TOKEN.match(texto, pos)
        if not m:
            raise FalloFormula("#ERROR!")
        out.append((m.lastgroup, m[m.lastgroup]))
        pos = m.end()
    return out


def _binario(op: str, a: Nodo, b: Nodo) -> Nodo:
    f = OPERADORES[op]
    return lambda leer: f(numero(a(leer)), numero(b(leer)))


class _Parser:
    """suma := producto (+|- producto)* ; producto := unario (*|/ unario)* ;
    unario := (+|-) unario | potencia ; potencia := atomo (^ unario)?"""

    def __init__(self, tokens: list[tuple[str, str]]):
        self.t, self.i = tokens, 0

    def ver(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def es(self, *ops: str) -> bool:
        tok = self.ver()
        return tok is not None and tok[0] == "op" and tok[1] in ops

    def tomar(self) -> tuple[str, str]:
        tok = self.ver()
        if tok is None:
            raise FalloFormula("#ERROR!")
        self.i += 1
        return tok

    def esperar(self, op: str) -> None:
        if self.tomar() != ("op", op):
            raise FalloFormula("#ERROR!")

    def todo(self) -> Nodo:
        nodo = self.suma()
        if self.ver() is not None:
            raise FalloFormula("#ERROR!")
        return nodo

    def suma(self) -> Nodo:
        nodo = self.producto()
        while self.es("+", "-"):
            nodo = _binario(self.tomar()[1], nodo, self.producto())
        return nodo

    def producto(self) -> Nodo:
        nodo = self.unario()
        while self.es("*", "/"):
            nodo = _binario(self.tomar()[1], nodo, self.unario())
        return nodo

    def unario(self) -> Nodo:
        if self.es("-"):
            self.tomar()
            a = self.unario()
            return lambda leer: -numero(a(leer))
        if self.es("+"):
            self.tomar()
            a = self.unario()
            return lambda leer: numero(a(leer))
        nodo = self.atomo()
        if self.es("^"):
            self.tomar()
            nodo = _binario("^", nodo, self.unario())
        return nodo

    def atomo(self) -> Nodo:
        tipo, texto = self.tomar()
        if tipo == "num":
            valor = float(texto)
            return lambda leer: valor
        if tipo == "txt":
            valor = texto[1:-1]
            return lambda leer: valor
        if tipo == "ref":
            r, c = referencia(texto)
            return lambda leer: leer(r, c)
        if tipo == "fn":
            return self.funcion(texto.upper())
        if (tipo, texto) == ("op", "("):
            nodo = self.suma()
            self.esperar(")")
            return nodo
        raise FalloFormula("#ERROR!")  # un rango suelto (A1:B2) o un operador fuera de sitio

    def funcion(self, nombre_fn: str) -> Nodo:
        f = FUNCIONES.get(nombre_fn)
        self.esperar("(")
        args: list[Callable[[Leer], list[Any]]] = []
        while not self.es(")"):
            tok = self.ver()
            if tok is not None and tok[0] == "rango":
                self.tomar()
                celdas = _rango(tok[1])
                args.append(lambda leer, celdas=celdas: [leer(r, c) for r, c in celdas])
            else:
                nodo = self.suma()
                args.append(lambda leer, nodo=nodo: [numero(nodo(leer))])
            if not self.es(")"):
                if not self.es(";", ","):
                    raise FalloFormula("#ERROR!")
                self.tomar()
        self.esperar(")")
        if f is None:
            return _falla("#NOMBRE?")
        return lambda leer: f(_numeros([v for arg in args for v in arg(leer)]))


def _rango(texto: str) -> list[tuple[int, int]]:
    a, b = texto.split(":")
    (r0, c0), (r1, c1) = referencia(a), referencia(b)
    return [(r, c) for r in range(min(r0, r1), max(r0, r1) + 1) for c in range(min(c0, c1), max(c0, c1) + 1)]


def _falla(codigo: str) -> Nodo:
    def nodo(leer: Leer) -> Any:
        raise FalloFormula(codigo)

    return nodo


@lru_cache(maxsize=4096)
def compilar(formula: str) -> Nodo:
    """`formula` sin el `=` inicial. Una fórmula mal escrita compila a una que da `#ERROR!`."""
    try:
        return _Parser(_tokens(formula)).todo()
    except FalloFormula as e:
        return _falla(e.codigo)


def evaluar(texto: str, leer: Leer) -> Any:
    """Valor de una celda a partir de lo que tiene escrito."""
    if not texto.startswith("="):
        return interpretar(texto)
    try:
        return compilar(texto[1:])(leer)
    except FalloFormula as e:
        return Error(e.codigo)
    except RecursionError:
        return Error("#CICLO!")
