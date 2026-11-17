"""`janel lsp`: los errores del compilador llegan al editor con su sitio."""
import io
import json
import subprocess
import sys
from pathlib import Path

from janelkit.cli.lsp import Server, check, path_of, source_root, to_lsp

GOOD = "<script>\nfrom janelkit import state\nn = state(0)\n</script>\n<text>{n}</text>\n"
BAD = GOOD.replace("{n}", "{nn}")


def frame(message):
    body = json.dumps({"jsonrpc": "2.0", **message}).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def frames(data):
    out = []
    while data:
        header, _, rest = data.partition(b"\r\n\r\n")
        length = int(header.split(b":")[1])
        out.append(json.loads(rest[:length]))
        data = rest[length:]
    return out


def talk(*messages):
    """Lo que responde el servidor a una conversación completa."""
    writer = io.BytesIO()
    code = Server(io.BytesIO(b"".join(frame(m) for m in messages)), writer).serve()
    return code, frames(writer.getvalue())


def opened(uri, text):
    return {"method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "languageId": "janel", "version": 1, "text": text}}}


def changed(uri, text):
    return {"method": "textDocument/didChange", "params": {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": text}]}}


def test_an_error_is_published_where_it_is_and_cleared_when_fixed(tmp_path):
    uri = (tmp_path / "App.janel").as_uri()
    code, out = talk(
        {"id": 1, "method": "initialize", "params": {}},
        {"method": "initialized", "params": {}},
        opened(uri, BAD),
        changed(uri, GOOD),
        {"method": "textDocument/didClose", "params": {"textDocument": {"uri": uri}}},
        {"id": 2, "method": "shutdown"},
        {"method": "exit"},
    )
    assert code == 0
    assert out[0]["result"]["capabilities"]["textDocumentSync"]["change"] == 1
    first, fixed, closed = (m["params"] for m in out[1:4])
    assert first["uri"] == uri
    (diag,) = first["diagnostics"]
    assert diag["severity"] == 1 and "nn" in diag["message"] and diag["source"] == "janel"
    # El texto no está en el disco: se comprueba lo que hay en el editor. El rango cubre el nombre.
    assert diag["range"] == {"start": {"line": 4, "character": 7}, "end": {"line": 4, "character": 9}}
    assert fixed["diagnostics"] == [] and closed["diagnostics"] == []
    assert out[4] == {"jsonrpc": "2.0", "id": 2, "result": None}


def test_imports_resolve_from_the_folder_of_app_janel(tmp_path):
    src = tmp_path / "src"
    (src / "components").mkdir(parents=True)
    (src / "App.janel").write_text("<text>app</text>", encoding="utf-8")
    (src / "components" / "Hijo.janel").write_text("<text>hijo</text>", encoding="utf-8")
    page = src / "pages" / "Pagina.janel"
    page.parent.mkdir()
    source = "<script>\nfrom components.Hijo import Hijo\n</script>\n<column><Hijo /></column>"
    assert source_root(str(page)) == src.resolve()
    assert check(source, str(page)) == []


def test_an_error_in_an_imported_component_is_shown_on_the_import_line(tmp_path):
    (tmp_path / "Hijo.janel").write_text("<text>{nada}</text>", encoding="utf-8")
    app = tmp_path / "App.janel"
    source = "<script>\nfrom Hijo import Hijo\n</script>\n<column><Hijo /></column>"
    (diag,) = to_lsp(check(source, str(app)), source, str(app))
    assert diag["range"]["start"] == {"line": 1, "character": 0}
    assert diag["message"].startswith("Hijo.janel:1:") and "nada" in diag["message"]


def test_saving_rechecks_every_open_document(tmp_path):
    child = tmp_path / "Hijo.janel"
    child.write_text("<text>{nada}</text>", encoding="utf-8")
    app = (tmp_path / "App.janel").as_uri()
    source = "<script>\nfrom Hijo import Hijo\n</script>\n<column><Hijo /></column>"
    server = Server(io.BytesIO(), io.BytesIO())
    server.handle(opened(app, source))
    child.write_text("<text>bien</text>", encoding="utf-8")
    server.handle({"method": "textDocument/didSave", "params": {"textDocument": {"uri": child.as_uri()}}})
    before, after = frames(server.writer.getvalue())
    assert len(before["params"]["diagnostics"]) == 1 and after["params"] == {"uri": app, "diagnostics": []}


def test_uris_become_local_paths(tmp_path):
    file = tmp_path / "con espacio" / "App.janel"
    assert Path(path_of(file.as_uri())) == file
    assert path_of("untitled:Untitled-1") == "untitled:Untitled-1"


def test_janel_lsp_speaks_over_stdio(tmp_path):
    uri = (tmp_path / "App.janel").as_uri()
    data = b"".join(frame(m) for m in ({"id": 1, "method": "initialize", "params": {}}, opened(uri, BAD), {"id": 2, "method": "shutdown"}, {"method": "exit"}))
    proc = subprocess.run([sys.executable, "-m", "janelkit.cli.main", "lsp"], input=data, capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    out = frames(proc.stdout)
    assert out[0]["result"]["serverInfo"]["name"] == "janel"
    assert len(out[1]["params"]["diagnostics"]) == 1
