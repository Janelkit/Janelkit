"""Ubicaciones de origen y errores con referencia al archivo .flux."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int  # 1-based
    column: int  # 1-based

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


@dataclass
class Diagnostic:
    message: str
    location: SourceLocation | None = None
    hint: str | None = None
    severity: str = "error"  # "error" | "warning"
    source: str | None = field(default=None, repr=False)

    def format(self) -> str:
        head = f"{self.location}: " if self.location else ""
        lines = [f"{head}{self.severity}: {self.message}"]
        snippet = self._snippet()
        if snippet:
            lines.append(snippet)
        if self.hint:
            lines.append(f"  sugerencia: {self.hint}")
        return "\n".join(lines)

    def _snippet(self) -> str | None:
        if not (self.source and self.location):
            return None
        src_lines = self.source.splitlines()
        if not 1 <= self.location.line <= len(src_lines):
            return None
        text = src_lines[self.location.line - 1].expandtabs(1)
        gutter = f"{self.location.line:>4} | "
        caret = " " * (len(gutter) - 2) + "| " + " " * (self.location.column - 1) + "^"
        return f"{gutter}{text}\n{caret}"


class FluxError(Exception):
    """Uno o más diagnósticos de error asociados a archivos .flux."""

    def __init__(self, diagnostics: list[Diagnostic] | Diagnostic):
        if isinstance(diagnostics, Diagnostic):
            diagnostics = [diagnostics]
        self.diagnostics = diagnostics
        super().__init__("\n\n".join(d.format() for d in diagnostics))

    @property
    def first(self) -> Diagnostic:
        return self.diagnostics[0]


def location_at(file: str, text: str, offset: int) -> SourceLocation:
    """Convierte un desplazamiento de caracteres en línea/columna (1-based)."""
    line = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    return SourceLocation(file, line, offset - line_start + 1)
