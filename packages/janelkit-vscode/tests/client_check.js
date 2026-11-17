// Prueba del cliente de extension.js fuera de VS Code: un módulo `vscode` de mentira
// y el servidor de verdad (`janel lsp`). Lo lanza test_client.py:
//
//   node client_check.js <python> <archivo.janel>
//
// Abre el archivo con un error, espera sus diagnósticos, lo corrige y espera a que
// se vacíen. Escribe en la salida un JSON con lo que se vio en cada paso.
"use strict";

const Module = require("module");
const path = require("path");

const [python, file] = process.argv.slice(2);
const BAD = "<script>\nfrom janelkit import state\nn = state(0)\n</script>\n<text>{nn}</text>\n";
const GOOD = BAD.replace("{nn}", "{n}");

const listeners = { open: [], change: [], save: [], close: [], config: [] };
const seen = [];
let waiting = null;

const uri = { toString: () => "file:///" + file.replace(/\\/g, "/").replace(/^\//, ""), fsPath: file };
const document = { languageId: "janel", version: 1, uri, text: BAD, getText() { return this.text; } };

const vscode = {
  DiagnosticSeverity: { Error: 0, Warning: 1 },
  Range: class { constructor(a, b, c, d) { Object.assign(this, { a, b, c, d }); } },
  Diagnostic: class { constructor(range, message, severity) { Object.assign(this, { range, message, severity }); } },
  Uri: { parse: (text) => ({ toString: () => text }) },
  languages: {
    createDiagnosticCollection: () => ({
      set(target, items) {
        seen.push({ uri: target.toString(), items });
        if (waiting) waiting();
      },
      clear() {},
      dispose() {},
    }),
  },
  window: {
    createOutputChannel: () => ({ append: (t) => process.stderr.write(t), appendLine: (t) => process.stderr.write(t + "\n"), show() {}, dispose() {} }),
    showWarningMessage: (text) => { process.stderr.write("AVISO: " + text + "\n"); return Promise.resolve(undefined); },
  },
  workspace: {
    workspaceFolders: [{ uri: { fsPath: path.dirname(file) } }],
    textDocuments: [document],
    getConfiguration: (section) => ({ get: (key, fallback) => (section === "janelkit" && key === "pythonPath" ? python : fallback) }),
    onDidOpenTextDocument: (fn) => listeners.open.push(fn),
    onDidChangeTextDocument: (fn) => listeners.change.push(fn),
    onDidSaveTextDocument: (fn) => listeners.save.push(fn),
    onDidCloseTextDocument: (fn) => listeners.close.push(fn),
    onDidChangeConfiguration: (fn) => listeners.config.push(fn),
  },
  commands: { registerCommand: () => ({ dispose() {} }) },
};

const load = Module._load;
Module._load = (request, ...rest) => (request === "vscode" ? vscode : load(request, ...rest));

function next() {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("el servidor no publicó diagnósticos")), 30000);
    waiting = () => { clearTimeout(timer); waiting = null; resolve(seen[seen.length - 1]); };
  });
}

(async () => {
  const extension = require("../extension.js");
  const first = next();
  extension.activate({ subscriptions: [] });
  const bad = await first;                       // al responder a initialize se envían los documentos abiertos
  document.text = GOOD;
  document.version = 2;
  const second = next();
  listeners.change.forEach((fn) => fn({ document }));
  const good = await second;
  extension.deactivate();
  process.stdout.write(JSON.stringify({ bad, good }));
})().catch((error) => {
  process.stderr.write(String(error.stack || error) + "\n");
  process.exit(1);
});
