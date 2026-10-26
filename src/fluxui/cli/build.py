"""`flux build`: compila todos los componentes del proyecto y guarda el QML generado.

Sirve para validar el proyecto completo (también componentes que todavía no se
usan) y para inspeccionar el QML. **No genera un ejecutable**: empaquetar
aplicaciones para distribuirlas es un paso distinto, previsto para más adelante.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..compiler import CompileSession, CompiledComponent
from ..diagnostics import Diagnostic, FluxError


@dataclass
class BuildResult:
    out_dir: Path
    written: list[Path] = field(default_factory=list)
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def find_source_dir(target: Path) -> Path:
    target = target.resolve()
    if target.is_file():
        return target.parent
    src = target / "src"
    return src if (src / "App.flux").is_file() else target


def build_project(target: Path, out_dir: Path | None = None) -> BuildResult:
    src = find_source_dir(target)
    project = src.parent if src.name == "src" else src
    out = (out_dir or project / "build" / "qml").resolve()
    result = BuildResult(out)

    entry = src / "App.flux"
    files = sorted(src.rglob("*.flux"))
    if not files:
        result.errors.append(Diagnostic(f"no hay archivos .flux en {src}"))
        return result

    session = CompileSession([src])
    compiled: dict[str, CompiledComponent] = {}

    def attempt(path: Path, as_window: bool) -> None:
        try:
            session.compile(path, as_window=as_window)
        except FluxError as exc:
            result.errors.extend(exc.diagnostics)

    if entry.is_file():
        attempt(entry, as_window=True)
    for path in files:
        if str(path.resolve()) not in session.registry and path != entry:
            attempt(path, as_window=False)  # componentes aún sin usar
    compiled.update(session.registry)
    # Un archivo con errores puede intentarse dos veces (como hijo y por sí mismo).
    result.errors = list({(d.message, d.location): d for d in result.errors}.values())

    for key, comp in compiled.items():
        result.warnings.extend(comp.warnings)
        rel = Path(key).relative_to(src) if Path(key).is_relative_to(src) else Path(Path(key).name)
        target_file = out / rel.with_suffix(".qml")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(comp.qml, encoding="utf-8")
        result.written.append(target_file)
    return result
