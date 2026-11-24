"""Lo que `css.SUPPORTED` dice que admite cada elemento funciona de verdad: compila sin avisos y
Qt acepta el QML. La tabla «CSS por elemento» de docs/estilos.md se genera desde SUPPORTED
(tools/css_table.py), así que esta prueba es la que hace que la documentación diga la verdad."""
import pytest

from janelkit.compiler import compile_source
from janelkit.compiler.css import SUPPORTED, _WINDOW_OVERRIDES
from janelkit.compiler.elements import BASE_ELEMENTS

SAMPLE = {
    "color": "#123456", "background": "#123456", "background-color": "#123456", "border": "1px solid #123456",
    "border-color": "#123456", "border-width": "2px", "border-radius": "4px", "overflow": "hidden", "padding": "3px",
    "gap": "3px", "row-gap": "3px", "column-gap": "3px", "flex-direction": "row", "direction": "row",
    "flex-wrap": "wrap", "align-items": "center", "justify-content": "center", "align-content": "center",
    "font-size": "15px", "font-weight": "bold", "font-family": "Arial", "font-style": "italic",
    "letter-spacing": "1px", "text-transform": "uppercase", "text-align": "center", "line-height": "1.4",
    "white-space": "nowrap", "text-overflow": "ellipsis", "user-select": "text", "flex": "1", "flex-grow": "1",
    "flex-shrink": "0", "flex-basis": "10px", "order": "1", "margin": "2px", "position": "relative",
    "top": "1px", "right": "1px", "bottom": "1px", "left": "1px", "inset": "1px", "z-index": "1",
    "align-self": "center", "width": "100px", "height": "40px", "min-width": "10px", "max-width": "300px",
    "min-height": "10px", "max-height": "300px", "opacity": "0.9", "transition": "all 100ms",
    "transform": "scale(1.1)", "cursor": "pointer", "box-shadow": "0 2px 4px #000", "outline": "1px solid #000",
    "outline-width": "1px", "outline-color": "#000", "outline-offset": "1px", "pointer-events": "none",
    "visibility": "visible",
    **{f"padding-{s}": "1px" for s in ("top", "right", "bottom", "left")},
    **{f"margin-{s}": "1px" for s in ("top", "right", "bottom", "left")},
    **{f"border-{s}": "1px solid #000" for s in ("top", "right", "bottom", "left")},
    **{f"border-{s}-width": "1px" for s in ("top", "right", "bottom", "left")},
    **{f"border-{s}-color": "#000" for s in ("top", "right", "bottom", "left")},
}  # fmt: skip

ELEMENT = {
    "text": "<text class='x'>hola</text>",
    "button": "<button class='x'>b</button>",
    "checkbox": "<checkbox class='x'>c</checkbox>",
    "switch": "<switch class='x'>s</switch>",
    "select": "<select class='x' options={['a']} />",
    "radiogroup": "<radiogroup class='x' options={['a']} />",
    "tabs": "<tabs class='x' options={['a']} />",
    "list": "<list class='x'>{#each [1] as i}<row><text>{i}</text></row>{/each}</list>",
    "image": "<image class='x' src='' />",
    "shortcut": "<shortcut class='x' keys='Ctrl+K' />",
}


def supported_by(tag: str) -> list[str]:
    names = {name for name, (tags, _) in SUPPORTED.items() if tag in tags}
    return sorted(names | set(_WINDOW_OVERRIDES) if tag == "window" else names)


def test_every_supported_property_has_a_sample():
    assert set(SUPPORTED) <= set(SAMPLE)


@pytest.mark.parametrize("tag", BASE_ELEMENTS)
def test_every_property_an_element_admits_works_on_it(mount, caplog, tag):
    """Todas a la vez (también `transition: all`, que anima lo que el elemento tiene)."""
    style = "; ".join(f"{name}: {SAMPLE[name]}" for name in supported_by(tag))
    if tag == "window":
        source = f"<window class='x'><column /></window>\n<style>.x {{ {style} }}</style>"
    else:
        source = f"<column>{ELEMENT.get(tag, f'<{tag} class={chr(39)}x{chr(39)} />')}</column>\n<style>.x {{ {style} }}</style>"
    if not style:
        assert tag == "shortcut"  # no se dibuja: ningún estilo le afecta
        return
    assert [w.message for w in compile_source(source).warnings] == []
    mount(source)
    assert caplog.text == ""


def test_a_property_an_element_lacks_warns_instead_of_breaking_the_app():
    for source, expected in (
        ("<column><checkbox class='x'>c</checkbox></column>\n<style>.x { transition: border-radius 1s }</style>",
         "transition: 'border-radius' no tiene efecto en <checkbox>"),
        ("<column><shortcut class='x' keys='Ctrl+K' /></column>\n<style>.x { flex: 1 }</style>",
         "'flex' no tiene efecto en <shortcut>"),
    ):
        assert [w.message for w in compile_source(source).warnings] == [expected]


def test_the_font_of_a_radiogroup_follows_the_window_and_its_own_style(mount):
    m = mount(
        "<window style='font-size: 20px'><column>"
        "<radiogroup id='a' options={['uno']} /><radiogroup id='b' class='x' options={['dos']} />"
        "</column></window>\n<style>.x { font-size: 30px; font-weight: bold }</style>"
    )
    from janelkit.testing import find

    def font(group_id):
        radio = next(c for c in find(m, group_id).childItems() if c.inherits("QQuickRadioButton"))
        return radio.property("font")

    assert font("a").pixelSize() == 20
    assert font("b").pixelSize() == 30 and font("b").bold()
