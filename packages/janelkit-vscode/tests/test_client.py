"""El cliente de extension.js habla con `janel lsp`: un error llega al editor y se va al corregirlo.

Se prueba fuera de VS Code, con un módulo `vscode` de mentira (client_check.js) y el servidor de verdad.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

VSCODE = Path(__file__).resolve().parents[1]


def test_manifest_declares_the_client():
    manifest = json.loads((VSCODE / "package.json").read_text(encoding="utf-8"))
    assert (VSCODE / manifest["main"]).is_file()
    assert manifest["activationEvents"] == ["onLanguage:janel"]
    source = (VSCODE / "extension.js").read_text(encoding="utf-8")
    for setting in manifest["contributes"]["configuration"]["properties"]:
        section, key = setting.split(".")
        assert f'getConfiguration("{section}").get("{key}"' in source, setting
    for command in manifest["contributes"]["commands"]:
        assert f'registerCommand("{command["command"]}"' in source


def test_client_shows_and_clears_the_compiler_errors(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("necesita Node.js")
    pytest.importorskip("janelkit.cli.lsp")
    file = tmp_path / "App.janel"
    proc = subprocess.run([node, str(VSCODE / "tests" / "client_check.js"), sys.executable, str(file)], capture_output=True, timeout=90)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    result = json.loads(proc.stdout)
    (diag,) = result["bad"]["items"]
    assert "nn" in diag["message"] and diag["severity"] == 0
    assert diag["range"] == {"a": 4, "b": 7, "c": 4, "d": 9}
    assert result["good"]["items"] == [] and result["good"]["uri"] == result["bad"]["uri"]
