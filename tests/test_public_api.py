"""La API pública es explícita: cambiarla obliga a actualizar esta prueba y docs/api.md."""
import re
from pathlib import Path

import fluxui
import fluxui.compiler
import fluxui.diagnostics
import fluxui.inspect

API_DOC = (Path(__file__).parent.parent / "docs" / "api.md").read_text(encoding="utf-8")

PUBLIC = {
    "fluxui": [
        "Computed", "Effect", "Event", "FocusEvent", "KeyEvent", "PageStack", "PointerEvent", "ResizeEvent", "WheelEvent", "Prop", "PropError", "Ref", "State", "Task", "Timer", "__version__", "background",
        "batch", "computed", "dialogs", "effect", "event", "i18n", "inject", "interval", "notify", "on_destroy", "on_mount", "open_window", "pages", "prop", "provide", "ref", "run",
        "spawn", "state", "t", "task", "theme", "timeout", "untracked",
    ],
    "fluxui.compiler": ["CompiledComponent", "FORMAT_VERSION", "check_file", "check_source", "compile_file", "compile_source"],
    "fluxui.diagnostics": ["Diagnostic", "FluxError", "SourceLocation"],
    "fluxui.inspect": ["Element", "InspectError", "MountedApp", "mount"],
}  # fmt: skip


def documented() -> set[str]:
    """Nombres de la primera columna de las tablas de docs/api.md."""
    return set(re.findall(r"^\| `([\w.]+)` \|", API_DOC, re.MULTILINE))


def test_top_level_exports_are_exactly_the_public_api():
    assert sorted(fluxui.__all__) == sorted(PUBLIC["fluxui"])


def test_public_names_exist():
    for module_name, names in PUBLIC.items():
        module = {
            "fluxui": fluxui,
            "fluxui.compiler": fluxui.compiler,
            "fluxui.diagnostics": fluxui.diagnostics,
            "fluxui.inspect": fluxui.inspect,
        }[module_name]
        for name in names:
            assert hasattr(module, name), f"{module_name}.{name}"


def test_every_public_name_is_documented_and_nothing_else():
    public = {name for names in PUBLIC.values() for name in names}
    assert documented() == public


def test_check_source_reports_without_raising():
    assert fluxui.compiler.check_source("<Text>hola</Text>") == []
    diags = fluxui.compiler.check_source("<script>\nx = 1\n</script>\n<Text>{y}</Text>")
    assert len(diags) == 1 and diags[0].severity == "error" and "'y' no está definido" in diags[0].message
