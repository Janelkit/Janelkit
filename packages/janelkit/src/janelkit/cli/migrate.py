"""`janel migrate`: actualiza un proyecto a lo que pide esta versión de JanelKit.

Por defecto solo muestra los cambios (un diff); con `--write` los aplica. Cambia lo
que se puede cambiar sin dudas y lista lo que hay que revisar a mano.

Reglas (0.1 → 0.2):

- Elementos del núcleo en minúscula: `<Text>` → `<text>`, también al cerrar y en los
  selectores de tipo de `<style>` (`Text.titulo` → `text.titulo`). Una etiqueta con el
  nombre de un componente que el script importa no se toca.
- Con `--tests`, lo mismo en los `.py` de pruebas: las plantillas dentro de cadenas y
  `find("Text")` / `find_all("Text")`.
- La navegación pasó a janelkit-router: `from janelkit import pages, state` →
  `from janelkit import state` + `from janelkit_router import pages, Pages` (`Pages` y
  `Sections` se añaden si la plantilla los usa). El tipo `Sections` pasa a `SectionSet`.
- `persisted` y `Persisted` pasaron a janelkit-store: `from janelkit_store import persisted`.
- Avisa (sin cambiarlo) de lo que se quitó: `History`.
"""
from __future__ import annotations

import ast
import difflib
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from ..compiler.legacy import LEGACY_TAGS, css_tag_spans, replace_spans

_ALT = "|".join(sorted(LEGACY_TAGS, key=len, reverse=True))
_TAG_RE = re.compile(r"<(/?)(" + _ALT + r")(?=[\s/>])")
_FIND_RE = re.compile(r"""(\.find(?:_all)?\(\s*)(["'])(""" + _ALT + r""")\2""")
_SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script\s*>)", re.DOTALL)
_STYLE_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.DOTALL)
_SKIP_DIRS = {".venv", "venv", ".git", "__pycache__", "build", "dist", "node_modules", "site-packages"}

# Lo que se quitó y no se puede migrar solo: nombre -> qué hacer.
_REMOVED = {
    "History": "History se quitó en la 0.2: anota los pasos de deshacer como pares de funciones en una clase propia",
}
# Lo que pasó a otro paquete: nombre en janelkit -> (paquete, nombre allí).
_MOVED = {
    "pages": ("janelkit_router", "pages"), "sections": ("janelkit_router", "sections"),
    "navigation": ("janelkit_router", "navigation"), "PageStack": ("janelkit_router", "PageStack"),
    "Sections": ("janelkit_router", "SectionSet"),
    "persisted": ("janelkit_store", "persisted"), "Persisted": ("janelkit_store", "Persisted"),
}  # fmt: skip
_ROUTER_TAGS = ("Pages", "Sections")
_FROM_JANELKIT = re.compile(r"^([ \t]*)from janelkit import (\([^)]*\)|[^\n]*)", re.MULTILINE)


@dataclass
class FileResult:
    path: Path
    old: str
    new: str
    notes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.old != self.new


def migrate_janel(text: str) -> tuple[str, list[str]]:
    """Texto de un `.janel` migrado y notas para revisar a mano."""
    imported, notes = _script_names(text)
    script = _SCRIPT_RE.search(text)
    regions: list[tuple[int, int, str]] = []  # (inicio, fin, tipo) de script y style
    if script:
        regions.append((script.start(2), script.end(2), "script"))
    for m in _STYLE_RE.finditer(text):
        regions.append((m.start(2), m.end(2), "style"))
    regions.sort()
    out, last = [], 0
    for start, end, kind in regions:
        out.append(_template(text[last:start], imported))
        body = text[start:end]
        if kind == "style":
            body = replace_spans(body, [(i, w) for i, w in css_tag_spans(body) if w not in imported])
        out.append(body)
        last = end
    out.append(_template(text[last:], imported))
    return _move_imports("".join(out)), notes


def _move_imports(text: str) -> str:
    """Los nombres que pasaron a otro paquete salen de `from janelkit import ...`."""
    out, last = [], 0
    for m in _FROM_JANELKIT.finditer(text):
        body, _, comment = m.group(2).partition("#")
        names = [n.strip() for n in body.strip().strip("()").replace("\n", " ").split(",") if n.strip()]
        moved = [n for n in names if n.split(" as ")[0].strip() in _MOVED]
        if not moved:
            continue
        kept = [n for n in names if n not in moved]
        packages: dict[str, list[str]] = {}
        for n in moved:
            base = n.split(" as ")[0].strip()
            package, new = _MOVED[base]
            packages.setdefault(package, []).append(new + n[len(base):])
        if "janelkit_router" in packages:
            template = _template_after(text, m.end())
            router = packages["janelkit_router"]
            router += [t for t in _ROUTER_TAGS if t not in router and re.search(rf"<{t}\b", template)]
        indent = m.group(1)
        lines = [f"{indent}from janelkit import {', '.join(kept)}"] if kept else []
        lines += [f"{indent}from {package} import {', '.join(names)}" for package, names in packages.items()]
        out += [text[last:m.start()], "\n".join(lines) + (f"  #{comment}" if comment else "")]
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def _template_after(text: str, pos: int) -> str:
    """Si `pos` está dentro de un <script>, la plantilla que lo sigue (hasta otro <script> o el fin de la cadena)."""
    opened = text.rfind("<script", 0, pos)
    if opened < 0 or text.rfind("</script", opened, pos) >= 0:
        return ""
    close = text.find("</script", pos)
    if close < 0:
        return ""
    ends = [i for i in (text.find("<script", close), text.find('"""', close)) if i >= 0]
    return text[close:min(ends) if ends else len(text)]


def migrate_python(text: str) -> tuple[str, list[str]]:
    """Un `.py` de pruebas: plantillas en cadenas y `find("Text")`."""
    new = _move_imports(text)
    new = _TAG_RE.sub(lambda m: "<" + m.group(1) + LEGACY_TAGS[m.group(2)], new)
    new = _STYLE_RE.sub(lambda m: m.group(1) + replace_spans(m.group(2), list(css_tag_spans(m.group(2)))) + m.group(3), new)
    new = _FIND_RE.sub(lambda m: m.group(1) + m.group(2) + LEGACY_TAGS[m.group(3)] + m.group(2), new)
    notes = [
        msg for name, msg in _REMOVED.items()
        if re.search(rf"^\s*from janelkit import [^\n]*\b{name}\b|\bjanelkit\.{name}\b", text, re.MULTILINE)
    ]  # fmt: skip
    return new, notes


def _template(chunk: str, imported: set[str]) -> str:
    return _TAG_RE.sub(lambda m: m.group(0) if m.group(2) in imported else "<" + m.group(1) + LEGACY_TAGS[m.group(2)], chunk)


def _script_names(text: str) -> tuple[set[str], list[str]]:
    """Nombres que importa el script (los componentes) y notas sobre lo que se quitó."""
    m = _SCRIPT_RE.search(text)
    if not m:
        return set(), []
    names: set[str] = set()
    notes: list[str] = []
    try:
        tree = ast.parse(textwrap.dedent(m.group(2)))
    except SyntaxError:
        return set(), ["el <script> tiene un error de sintaxis: revisa a mano las etiquetas con el nombre de un componente"]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if node.module == "janelkit" and alias.name in _REMOVED:
                    notes.append(_REMOVED[alias.name])
                else:
                    names.add(alias.asname or alias.name)
    return names, notes


def migrate_path(root: Path, tests: bool = False) -> list[FileResult]:
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file() and not _skipped(p, root))
    results = []
    for path in files:
        if path.suffix == ".janel" or path.name.endswith(".janel.tmpl"):
            fn = migrate_janel
        elif tests and path.suffix == ".py" and _is_test(path):
            fn = migrate_python
        else:
            continue
        old = path.read_bytes().decode("utf-8")
        new, notes = fn(old)
        results.append(FileResult(path, old, new, notes))
    return results


def _skipped(path: Path, root: Path) -> bool:
    return any(part in _SKIP_DIRS or part.endswith(".egg-info") for part in path.relative_to(root).parts[:-1])


def _is_test(path: Path) -> bool:
    return path.name.startswith("test_") or path.name == "conftest.py" or "tests" in path.parts


def run(root: Path, write: bool, tests: bool, out=print) -> int:
    if not root.exists():
        out(f"error: no existe {root}")
        return 1
    results = migrate_path(root, tests)
    changed = [r for r in results if r.changed]
    for r in changed:
        if write:
            r.path.write_bytes(r.new.encode("utf-8"))
        else:
            diff = difflib.unified_diff(
                r.old.splitlines(keepends=True), r.new.splitlines(keepends=True), str(r.path), str(r.path)
            )
            out("".join(diff).rstrip("\n"))
    for r in results:
        for note in r.notes:
            out(f"{r.path}: revisar a mano: {note}")
    verb = "cambiados" if write else "cambiarían"
    out(f"janel migrate: {len(changed)} de {len(results)} archivo(s) {verb}" + ("" if write else " (usa --write para aplicarlo)"))
    return 0
