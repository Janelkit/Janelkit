"""`janel lsp`: los errores del compilador en el editor, mientras se escribe.

Un servidor del Language Server Protocol por la entrada y la salida estándar.
Hace una sola cosa: cada vez que un `.janel` abierto cambia, lo compila (sin
ejecutar su script) y publica los errores y avisos con su línea y columna. Lo
usa la extensión de VS Code y sirve a cualquier editor con cliente LSP.

El texto que se comprueba es el del editor, guardado o no. Los componentes que
importa se leen del disco: un error en uno de ellos aparece en la línea que lo
importa hasta que ese archivo se corrige y se guarda.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from .. import __version__
from ..compiler import CompileSession, parse_sfc
from ..compiler.ast_nodes import Element
from ..diagnostics import Diagnostic, JanelError

ERROR, WARNING = 1, 2
_WORD = re.compile(r"[\w.\-]+")


def path_of(uri: str) -> str:
    """Ruta local de un `file://`; cualquier otro esquema (un archivo sin guardar) se deja como viene."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return uri
    return os.path.abspath(url2pathname(unquote(parsed.path)))


def _same(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def source_root(file: str) -> Path:
    """La carpeta desde la que se resuelven los imports: la de `App.janel` más cercana hacia arriba."""
    folder = Path(file).resolve().parent
    for candidate in (folder, *folder.parents):
        if (candidate / "App.janel").is_file():
            return candidate
    return folder


def _is_window(source: str, file: str) -> bool:
    """Como `janel build`: `App.janel` es la ventana principal; los demás, solo si su raíz es <window>."""
    if Path(file).name == "App.janel":
        return True
    try:
        roots = parse_sfc(source, file).root_elements
    except JanelError:
        return True  # el error lo dará la compilación
    return len(roots) == 1 and isinstance(roots[0], Element) and roots[0].tag == "window"


def check(source: str, file: str) -> list[Diagnostic]:
    """Errores y avisos de `source` (el texto de `file` en el editor) y de lo que importa."""
    try:
        session = CompileSession([source_root(file)])
        return session.compile_source(source, file, as_window=_is_window(source, file)).all_warnings
    except JanelError as exc:
        return list(exc.diagnostics)
    except Exception as exc:  # noqa: BLE001 - un fallo del compilador no debe tumbar el servidor
        return [Diagnostic(f"error interno del compilador: {type(exc).__name__}: {exc}")]


def _range(lines: list[str], line: int, column: int) -> dict[str, Any]:
    """De (línea, columna) a un rango: la palabra que empieza ahí, o un carácter."""
    line = min(max(line, 1), max(len(lines), 1))
    text = lines[line - 1] if lines else ""
    start = min(max(column, 1), len(text) + 1) - 1
    match = _WORD.match(text, start)
    end = match.end() if match else min(start + 1, len(text))
    return {"start": {"line": line - 1, "character": start}, "end": {"line": line - 1, "character": max(end, start)}}


def _import_line(lines: list[str], other: str) -> int:
    """Línea (desde 1) que importa el componente `other`, o la primera."""
    name = re.compile(rf"\bimport\b.*\b{re.escape(Path(other).stem)}\b")
    return next((i for i, text in enumerate(lines, 1) if name.search(text)), 1)


def to_lsp(diagnostics: list[Diagnostic], source: str, file: str) -> list[dict[str, Any]]:
    lines = source.splitlines()
    result = []
    for d in diagnostics:
        message = d.message + (f"\nSugerencia: {d.hint}" if d.hint else "")
        loc = d.location
        if loc is None:
            where = _range(lines, 1, 1)
        elif _same(loc.file, file):
            where = _range(lines, loc.line, loc.column)
        else:  # en un componente importado: se marca la línea que lo importa
            line = _import_line(lines, loc.file)
            text = lines[line - 1] if lines else ""
            where = {"start": {"line": line - 1, "character": 0}, "end": {"line": line - 1, "character": len(text)}}
            message = f"{Path(loc.file).name}:{loc.line}:{loc.column}: {message}"
        result.append({
            "range": where,
            "severity": WARNING if d.severity == "warning" else ERROR,
            "source": "janel",
            "message": message,
        })
    return result


class Server:
    def __init__(self, reader: BinaryIO, writer: BinaryIO):
        self.reader = reader
        self.writer = writer
        self.documents: dict[str, str] = {}  # uri -> texto en el editor
        self.shutdown = False

    # -- transporte ----------------------------------------------------------
    def read(self) -> dict[str, Any] | None:
        length = None
        while True:
            header = self.reader.readline()
            if not header:
                return None
            header = header.strip()
            if not header:
                break
            name, _, value = header.partition(b":")
            if name.lower() == b"content-length":
                length = int(value)
        if length is None:
            return None
        return json.loads(self.reader.read(length).decode("utf-8"))

    def send(self, message: dict[str, Any]) -> None:
        body = json.dumps({"jsonrpc": "2.0", **message}, ensure_ascii=False).encode("utf-8")
        self.writer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        self.writer.flush()

    # -- documentos ----------------------------------------------------------
    def publish(self, uri: str) -> None:
        source = self.documents[uri]
        file = path_of(uri)
        self.send({
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": to_lsp(check(source, file), source, file)},
        })

    def publish_all(self) -> None:
        # Un cambio en un componente puede arreglar o romper a los que lo usan.
        for uri in self.documents:
            self.publish(uri)

    # -- mensajes ------------------------------------------------------------
    def handle(self, message: dict[str, Any]) -> bool:
        """Atiende un mensaje. Devuelve False cuando hay que terminar."""
        method = message.get("method")
        params = message.get("params") or {}
        ident = message.get("id")
        if method == "initialize":
            self.send({"id": ident, "result": {
                "capabilities": {"textDocumentSync": {"openClose": True, "change": 1, "save": True}},
                "serverInfo": {"name": "janel", "version": __version__},
            }})
        elif method == "shutdown":
            self.shutdown = True
            self.send({"id": ident, "result": None})
        elif method == "exit":
            return False
        elif method == "textDocument/didOpen":
            doc = params["textDocument"]
            self.documents[doc["uri"]] = doc["text"]
            self.publish(doc["uri"])
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            changes = params.get("contentChanges") or []
            if changes:
                self.documents[uri] = changes[-1]["text"]  # sincronización completa (change: 1)
                self.publish(uri)
        elif method == "textDocument/didSave":
            self.publish_all()
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            if self.documents.pop(uri, None) is not None:
                self.send({"method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": []}})
        elif ident is not None and method is not None:
            self.send({"id": ident, "error": {"code": -32601, "message": f"método no admitido: {method}"}})
        return True

    def serve(self) -> int:
        while (message := self.read()) is not None:
            if not self.handle(message):
                break
        return 0 if self.shutdown else 1


def run_lsp() -> int:
    return Server(sys.stdin.buffer, sys.stdout.buffer).serve()
