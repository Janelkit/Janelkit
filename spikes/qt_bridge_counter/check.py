"""Verificación automática del spike (plataforma offscreen)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from PySide6.QtCore import QMetaObject, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine
sys.path.insert(0, os.path.dirname(__file__))
from main import Model, load

app = QGuiApplication(sys.argv)
engine = QQmlEngine()
m = Model()
w = load(engine, m)
label = w.findChild(QObject, "label"); button = w.findChild(QObject, "button")
field = w.findChild(QObject, "field"); echo = w.findChild(QObject, "echo")
assert label.property("text") == "Clicks: 0"
QMetaObject.invokeMethod(button, "click"); app.processEvents()
assert m.count == 1 and label.property("text") == "Clicks: 1", label.property("text")
m.count = 41; m.sync(); assert label.property("text") == "Clicks: 41"
field.setProperty("text", "Ana"); QMetaObject.invokeMethod(field, "textEdited"); app.processEvents()
assert m.name == "Ana" and echo.property("text") == "Hola, Ana", (m.name, echo.property("text"))
assert m.writes == 1, m.writes  # sin bucle: una sola escritura
m.name = "Bea"; m.sync()
assert field.property("text") == "Bea" and echo.property("text") == "Hola, Bea"
# el binding text: jk.name sigue vivo tras una edición del usuario
field.setProperty("text", "Bea2"); QMetaObject.invokeMethod(field, "textEdited")
m.name = "Carla"; m.sync()
assert field.property("text") == "Carla", field.property("text")
print("spike OK")
