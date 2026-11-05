"""Control del desplazamiento en <scroll>: follow, on:top/on:bottom/on:scroll y ref.scroll_to_*."""
import pytest
from PySide6.QtCore import QCoreApplication

from janelkit.testing import visual_items

LOG = """<script>
from janelkit import state, ref
lines = state([f"línea {i}" for i in range(%d)])
tops = state(0)
bottoms = state(0)
pos = state({})
zona = ref()
marca = ref()
otro = ref()
</script>
<window width={300} height={200}>
  <scroll %s ref={zona} on:top={tops += 1} on:bottom={bottoms += 1} on:scroll={pos = event}>
    {#each lines as l}
      <text>{l}</text>
    {/each}
    <text ref={marca}>marca</text>
    {#each lines as l}
      <text>{l}</text>
    {/each}
  </scroll>
  <text ref={otro}>fuera</text>
</window>
"""


def flick(m):
    view = next(i for i in visual_items(m) if i.inherits("QQuickScrollView"))
    return view.property("contentItem")


def settle(m):
    for _ in range(4):
        QCoreApplication.processEvents()
    return flick(m)


def test_follow_starts_at_the_end_and_follows_new_content(mount):
    m = mount(LOG % (30, "follow"))
    f = settle(m)
    assert f.property("contentHeight") > f.height()
    assert f.property("atYEnd")
    m.instance.namespace["lines"].value.append("nueva")
    f = settle(m)
    assert f.property("atYEnd")


def test_follow_does_not_jump_when_the_user_scrolled_up(mount):
    m = mount(LOG % (30, "follow"))
    f = settle(m)
    f.setProperty("contentY", f.property("contentY") - 200)
    y = f.property("contentY")
    m.instance.namespace["lines"].value.append("nueva")
    f = settle(m)
    assert f.property("contentY") == y and not f.property("atYEnd")
    m.instance.namespace["zona"].scroll_to_end()  # vuelve a seguir
    m.instance.namespace["lines"].value.append("otra")
    assert settle(m).property("atYEnd")


def test_without_follow_it_stays_at_the_top(mount):
    m = mount(LOG % (30, ""))
    f = settle(m)
    assert f.property("atYBeginning")
    m.instance.namespace["lines"].value.append("nueva")
    assert settle(m).property("atYBeginning")


def test_scroll_to_start_end_and_to_an_inner_element(mount):
    m = mount(LOG % (30, ""))
    ns = m.instance.namespace
    f = settle(m)
    ns["zona"].scroll_to_end()
    f = settle(m)
    assert f.property("atYEnd") and ns["bottoms"].value == 1
    ns["zona"].scroll_to_start()
    f = settle(m)
    assert f.property("atYBeginning") and ns["tops"].value == 1

    ns["zona"].scroll_to(ns["marca"])
    f = settle(m)
    marca = ns["marca"].value
    top = marca.mapToItem(f.property("contentItem"), 0, 0).y()
    y = f.property("contentY")
    assert y <= top and top + marca.height() <= y + f.height()
    assert not f.property("atYBeginning") and not f.property("atYEnd")
    ns["zona"].scroll_to(ns["marca"])  # ya se ve: no se mueve
    assert settle(m).property("contentY") == y


def test_on_scroll_reports_the_position(mount):
    m = mount(LOG % (30, ""))
    ns = m.instance.namespace
    settle(m)
    ns["zona"].scroll_to_end()
    settle(m)
    info = ns["pos"].value
    assert info["bottom"] is True and info["top"] is False
    assert info["y"] > 0 and info["height"] > info["y"]


def test_scroll_to_rejects_what_is_not_inside(mount):
    m = mount(LOG % (5, ""))
    ns = m.instance.namespace
    settle(m)
    with pytest.raises(ValueError, match="no está dentro"):
        ns["zona"].scroll_to(ns["otro"])
    with pytest.raises(TypeError, match="ref de un elemento"):
        ns["zona"].scroll_to(3)
