"""La API pública es explícita: cambiarla obliga a actualizar esta prueba y docs/api.md."""
import re
from pathlib import Path

import janelkit
import janelkit.compiler
import janelkit.diagnostics
import janelkit.ext
import janelkit.inspect

API_DOC = (Path(__file__).resolve().parents[3] / "docs" / "api.md").read_text(encoding="utf-8")

PUBLIC = {
    "janelkit": [
        "Computed", "DragEvent", "Effect", "Event", "FocusEvent", "Frames", "KeyEvent", "Persisted", "PointerEvent", "ResizeEvent", "WheelEvent", "Prop", "PropError", "Ref", "Screen", "State", "Task", "Timer", "__version__", "background",
        "batch", "before_leave", "computed", "effect", "event", "inject", "interval", "is_visible", "locale", "on_destroy", "on_mount", "open_window", "persisted", "prop", "provide", "ref", "run", "screens",
        "spawn", "state", "task", "theme", "timeout", "untracked",
    ],
    "janelkit.compiler": ["CompiledComponent", "FORMAT_VERSION", "check_file", "check_source", "compile_file", "compile_source"],
    "janelkit.diagnostics": ["Diagnostic", "JanelError", "SourceLocation"],
    "janelkit.inspect": ["Element", "InspectError", "MountedApp", "mount"],
    "janelkit.ext": ["Child", "Container", "Gate", "Host", "Session", "app", "ask_to_leave", "inspector", "is_component", "session"],
}  # fmt: skip


def documented() -> set[str]:
    """Nombres de la primera columna de las tablas de docs/api.md."""
    return set(re.findall(r"^\| `([\w.]+)` \|", API_DOC, re.MULTILINE))


def test_top_level_exports_are_exactly_the_public_api():
    assert sorted(janelkit.__all__) == sorted(PUBLIC["janelkit"])


def test_public_names_exist():
    for module_name, names in PUBLIC.items():
        module = {
            "janelkit": janelkit,
            "janelkit.compiler": janelkit.compiler,
            "janelkit.diagnostics": janelkit.diagnostics,
            "janelkit.inspect": janelkit.inspect,
            "janelkit.ext": janelkit.ext,
        }[module_name]
        for name in names:
            assert hasattr(module, name), f"{module_name}.{name}"


def test_removed_names_say_what_happened():
    import pytest

    with pytest.raises(ImportError, match="History se quitó en JanelKit 0.2.0"):
        exec("from janelkit import History")
    with pytest.raises(ImportError, match="pip install janelkit-router"):
        exec("from janelkit import pages")


def test_every_public_name_is_documented_and_nothing_else():
    public = {name for names in PUBLIC.values() for name in names}
    assert documented() == public


def test_check_source_reports_without_raising():
    assert janelkit.compiler.check_source("<text>hola</text>") == []
    diags = janelkit.compiler.check_source("<script>\nx = 1\n</script>\n<text>{y}</text>")
    assert len(diags) == 1 and diags[0].severity == "error" and "'y' no está definido" in diags[0].message
