// Errores de los .janel en el editor: lanza `janel lsp` y muestra lo que publica.
//
// Es un cliente mínimo del Language Server Protocol, sin dependencias: solo
// sincroniza los documentos .janel abiertos y recibe sus diagnósticos, que es
// lo que ofrece el servidor. El resaltado sigue siendo la gramática.
"use strict";

const cp = require("child_process");
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");

const LANGUAGE = "janel";

let client = null;

/** El intérprete de Python con el que lanzar el servidor: el del ajuste, el del entorno del proyecto o `python`. */
function findPython(folder) {
  const own = vscode.workspace.getConfiguration("janelkit").get("pythonPath");
  if (own) return own;
  const roots = folder ? [folder] : [];
  const candidates = [".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe", "venv/bin/python"];
  for (const root of roots) {
    for (const candidate of candidates) {
      const file = path.join(root, candidate);
      if (fs.existsSync(file)) return file;
    }
  }
  const shared = vscode.workspace.getConfiguration("python").get("defaultInterpreterPath");
  if (shared && shared !== "python") return shared;
  return process.platform === "win32" ? "python" : "python3";
}

class Client {
  constructor(output) {
    this.output = output;
    this.diagnostics = vscode.languages.createDiagnosticCollection(LANGUAGE);
    this.process = null;
    this.buffer = Buffer.alloc(0);
    this.ready = false;
    this.stopping = false;
    this.warned = false;
    this.nextId = 1;
  }

  start() {
    const folders = vscode.workspace.workspaceFolders || [];
    const folder = folders.length ? folders[0].uri.fsPath : undefined;
    const python = findPython(folder);
    this.output.appendLine(`[janel] ${python} -m janelkit.cli.main lsp`);
    this.stopping = false;
    this.ready = false;
    this.buffer = Buffer.alloc(0);
    let child;
    try {
      child = cp.spawn(python, ["-m", "janelkit.cli.main", "lsp"], { cwd: folder, env: { ...process.env, PYTHONUTF8: "1" } });
    } catch (error) {
      this.failed(`no se pudo lanzar ${python}: ${error.message}`);
      return;
    }
    this.process = child;
    child.stdout.on("data", (chunk) => this.receive(chunk));
    child.stderr.on("data", (chunk) => this.output.append(chunk.toString()));
    child.on("error", (error) => this.failed(`no se pudo lanzar ${python}: ${error.message}`));
    child.on("exit", (code) => {
      if (this.process !== child) return;
      this.process = null;
      this.ready = false;
      this.diagnostics.clear();
      if (!this.stopping) this.failed(`el servidor terminó con código ${code}`);
    });
    this.send({ id: this.nextId++, method: "initialize", params: { processId: process.pid, rootUri: null, capabilities: {} } });
  }

  failed(reason) {
    this.output.appendLine(`[janel] ${reason}`);
    if (this.warned) return;
    this.warned = true;
    vscode.window
      .showWarningMessage(
        "JanelKit: no se pueden mostrar los errores de los .janel. Hace falta janelkit 0.2.1 o posterior en el " +
          "entorno de Python del proyecto (pip install -U janelkit); elige otro intérprete con el ajuste janelkit.pythonPath.",
        "Ver registro"
      )
      .then((choice) => choice && this.output.show());
  }

  stop() {
    this.stopping = true;
    const child = this.process;
    this.process = null;
    this.ready = false;
    this.diagnostics.clear();
    if (!child) return;
    try {
      this.write(child, { id: this.nextId++, method: "shutdown" });
      this.write(child, { method: "exit" });
      child.stdin.end();
    } catch (error) {
      child.kill();
    }
  }

  dispose() {
    this.stop();
    this.diagnostics.dispose();
  }

  // -- transporte ---------------------------------------------------------
  write(child, message) {
    const body = Buffer.from(JSON.stringify({ jsonrpc: "2.0", ...message }), "utf8");
    child.stdin.write(Buffer.concat([Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "ascii"), body]));
  }

  send(message) {
    if (this.process) this.write(this.process, message);
  }

  receive(chunk) {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    for (;;) {
      const end = this.buffer.indexOf("\r\n\r\n");
      if (end < 0) return;
      const match = /content-length:\s*(\d+)/i.exec(this.buffer.slice(0, end).toString("ascii"));
      if (!match) {
        this.buffer = this.buffer.slice(end + 4);
        continue;
      }
      const length = Number(match[1]);
      if (this.buffer.length < end + 4 + length) return;
      const body = this.buffer.slice(end + 4, end + 4 + length).toString("utf8");
      this.buffer = this.buffer.slice(end + 4 + length);
      try {
        this.handle(JSON.parse(body));
      } catch (error) {
        this.output.appendLine(`[janel] mensaje no entendido: ${error.message}`);
      }
    }
  }

  handle(message) {
    if (message.method === "textDocument/publishDiagnostics") {
      this.show(message.params);
    } else if (message.id !== undefined && message.result && message.result.capabilities) {
      // Respuesta a `initialize`: ya se pueden enviar los documentos abiertos.
      this.ready = true;
      this.warned = false;
      this.send({ method: "initialized", params: {} });
      for (const document of vscode.workspace.textDocuments) this.opened(document);
    }
  }

  show(params) {
    const items = params.diagnostics.map((d) => {
      const range = new vscode.Range(d.range.start.line, d.range.start.character, d.range.end.line, d.range.end.character);
      const severity = d.severity === 2 ? vscode.DiagnosticSeverity.Warning : vscode.DiagnosticSeverity.Error;
      const item = new vscode.Diagnostic(range, d.message, severity);
      item.source = d.source || LANGUAGE;
      return item;
    });
    this.diagnostics.set(vscode.Uri.parse(params.uri), items);
  }

  // -- documentos ---------------------------------------------------------
  opened(document) {
    if (!this.ready || document.languageId !== LANGUAGE) return;
    this.send({
      method: "textDocument/didOpen",
      params: { textDocument: { uri: document.uri.toString(), languageId: LANGUAGE, version: document.version, text: document.getText() } },
    });
  }

  changed(document) {
    if (!this.ready || document.languageId !== LANGUAGE) return;
    this.send({
      method: "textDocument/didChange",
      params: { textDocument: { uri: document.uri.toString(), version: document.version }, contentChanges: [{ text: document.getText() }] },
    });
  }

  saved(document) {
    // También al guardar un .py: nada cambia para el compilador, pero cuesta poco y deja todo al día.
    if (!this.ready) return;
    this.send({ method: "textDocument/didSave", params: { textDocument: { uri: document.uri.toString() } } });
  }

  closed(document) {
    if (!this.ready || document.languageId !== LANGUAGE) return;
    this.send({ method: "textDocument/didClose", params: { textDocument: { uri: document.uri.toString() } } });
  }
}

function activate(context) {
  const output = vscode.window.createOutputChannel("JanelKit");
  client = new Client(output);
  const enabled = () => vscode.workspace.getConfiguration("janelkit").get("diagnostics", true);
  if (enabled()) client.start();
  context.subscriptions.push(
    output,
    client,
    vscode.workspace.onDidOpenTextDocument((document) => client.opened(document)),
    vscode.workspace.onDidChangeTextDocument((event) => client.changed(event.document)),
    vscode.workspace.onDidSaveTextDocument((document) => client.saved(document)),
    vscode.workspace.onDidCloseTextDocument((document) => client.closed(document)),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (!event.affectsConfiguration("janelkit")) return;
      client.stop();
      if (enabled()) client.start();
    }),
    vscode.commands.registerCommand("janelkit.restartServer", () => {
      client.stop();
      client.warned = false;
      client.start();
    })
  );
  return client;
}

function deactivate() {
  if (client) client.stop();
}

module.exports = { activate, deactivate };
