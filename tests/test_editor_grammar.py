"""La gramática de VS Code es JSON válido y sus expresiones regulares compilan."""
import json
import re
from pathlib import Path

VSCODE = Path(__file__).parent.parent / "editors" / "vscode"


def _regexes(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("match", "begin", "end") and isinstance(value, str):
                yield value
            else:
                yield from _regexes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _regexes(item)


def test_grammar_is_valid():
    grammar = json.loads((VSCODE / "syntaxes" / "flux.tmLanguage.json").read_text(encoding="utf-8"))
    assert grammar["scopeName"] == "source.flux"
    patterns = list(_regexes(grammar))
    assert len(patterns) > 10
    for pattern in patterns:
        re.compile(pattern)
    for include in re.findall(r'"#([\w-]+)"', json.dumps(grammar)):
        assert include in grammar["repository"], include


def test_block_pattern_matches_directives():
    grammar = json.loads((VSCODE / "syntaxes" / "flux.tmLanguage.json").read_text(encoding="utf-8"))
    block = re.compile(grammar["repository"]["block"]["begin"])
    for text in ("{#if a}", "{:else if b}", "{:else}", "{/if}", "{#each xs as x}", "{#key k}", "{/key}"):
        assert block.match(text), text
    assert not block.match("{count}")


def test_extension_manifest_points_to_grammar():
    config = json.loads((VSCODE / "language-configuration.json").read_text(encoding="utf-8"))
    for pattern in config["folding"]["markers"].values():
        re.compile(pattern)
    manifest = json.loads((VSCODE / "package.json").read_text(encoding="utf-8"))
    grammar = manifest["contributes"]["grammars"][0]
    assert (VSCODE / grammar["path"]).is_file()
    assert manifest["contributes"]["languages"][0]["extensions"] == [".flux"]
