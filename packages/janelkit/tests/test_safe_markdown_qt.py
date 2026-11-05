r"""`<Text format="markdown">` no interpreta HTML: el texto de otras personas (un chat) se
muestra tal cual, sin escaparlo a mano. Para HTML, `format="html"`.

La garantía se comprueba con el propio md4c de Qt: el texto que se le pasa se ve igual con
HTML que sin él (`MarkdownNoHTML`).
"""
import random

import pytest
from janelkit.testing import find
from janelkit.runtime.markdown import _md4c_sees_html, safe_markdown


@pytest.fixture(autouse=True)
def qt(janel_app):  # QTextDocument necesita la aplicación
    return janel_app


@pytest.mark.parametrize("source, expected", [
    ("sin etiquetas **negrita**", "sin etiquetas **negrita**"),
    ("hola <b>x</b>", r"hola \<b>x\</b>"),
    ("<img src=https://ejemplo.com/p.png>", r"\<img src=https://ejemplo.com/p.png>"),
    ("<!-- oculto -->", r"\<!-- oculto -->"),
    ("mira `List<int>` y <i>", r"mira `List<int>` y \<i>"),         # en código no se toca
    ("``a ` <b>`` <c>", r"``a ` <b>`` \<c>"),
    ("```py\nif a < b:\n```\n<b>", "```py\nif a < b:\n```\n" + r"\<b>"),
    ("~~~~\n<a>\n~~~\n<b>\n~~~~\n<c>", "~~~~\n<a>\n~~~\n<b>\n~~~~\n" + r"\<c>"),
    ("`sin cerrar <b>", r"`sin cerrar \<b>"),
    (r"ya escapado \<b>", r"ya escapado \<b>"),
])
def test_html_outside_code_is_escaped(source, expected):
    assert safe_markdown(source) == expected


def test_code_that_md4c_reads_differently_falls_back_to_escaping_everything():
    # El ` de la primera línea se cierra con el primero de la segunda: <img> queda fuera de código.
    source = "- \t`\n`-->)|<img src=x>`"
    assert not _md4c_sees_html(safe_markdown(source))
    assert "<img" not in safe_markdown(source).replace(r"\<", "")


def test_md4c_never_sees_html_in_random_input():
    tokens = ["<b>", "</b>", "<img src=x>", "<span style='color:red'>", "<!--", "-->", "<div>", "<?",
              "`", "``", "```", "~~~", "\n", "\n\n", "    ", "- ", "> ", "1. ", "\\", "*", "[a](", ")", "x", "<", " "]
    rng = random.Random(7)
    for _ in range(3000):
        source = "".join(rng.choice(tokens) for _ in range(rng.randint(1, 16)))
        assert not _md4c_sees_html(safe_markdown(source)), source


def shown(m, element_id):
    return find(m, element_id).property("text")


def test_markdown_text_from_data_shows_the_tags(mount):
    m = mount(r"""<script>
from janelkit import state
msg = state("**hola** <b>no</b>")
fmt = state("markdown")
</script>
<Column>
  <Text id="content" format="markdown">{msg}</Text>
  <Text id="attr" format="markdown" text={msg} />
  <Text id="fixed" format="markdown" text="fijo <i>x</i>" />
  <Text id="dynamic" format={fmt}>{msg}</Text>
  <Text id="html" format="html">{msg}</Text>
  <Text id="plain">{msg}</Text>
</Column>
""")
    for element_id in ("content", "attr", "dynamic"):
        assert shown(m, element_id) == r"**hola** \<b>no\</b>", element_id
    assert shown(m, "fixed") == r"fijo \<i>x\</i>"
    assert shown(m, "html") == shown(m, "plain") == "**hola** <b>no</b>"  # sin cambios
    m.instance.namespace["msg"].value = "<span style='color:red'>rojo</span>"
    assert shown(m, "content") == r"\<span style='color:red'>rojo\</span>"
    m.instance.namespace["fmt"].value = "plain"  # el formato cambia: deja de escaparse
    assert shown(m, "dynamic") == "<span style='color:red'>rojo</span>"
