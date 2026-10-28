"""Instancias de componentes y fragmentos: ejecutan el script, evalúan bindings y gestionan regiones dinámicas.

- `ComponentInstance` ejecuta el `<script>` en un espacio de nombres propio,
  de modo que dos instancias del mismo componente nunca comparten estado local.
- `TemplateInstance` da vida a una plantilla: el componente completo o una
  fila de `{#each}` / rama de `{#if}`. Tiene su propio puente `jk` y su propio
  ámbito reactivo, que se libera al desmontarla.
- Una fila que sale de un `{#each}` con clave y entra, en el mismo cambio, en otra
  instancia de la misma declaración con la misma clave se *traslada*: sus
  componentes (con su estado) pasan a la fila nueva en vez de crearse otra vez.
- Los nombres de las expresiones se resuelven en cadena: variables de la fila
  (`item`, `i`), luego las de los fragmentos que la contienen, luego el script
  y por último los builtins. `state`, `computed` y props se desenvuelven.
"""
from __future__ import annotations

import bisect
import builtins
import inspect
import logging
import types
import typing
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType
from typing import Any, Protocol

from PySide6.QtCore import QObject, QTimer
from shiboken6 import Shiboken

from ..compiler import CompiledComponent
from ..compiler.ast_nodes import Expression, FormattedExpression
from ..compiler.expressions import EVENT_NAME, GETTER, RUNNER, SETTER, compile_expression, compile_handler
from ..compiler.ir import (
    Binding,
    ComponentSlot,
    ComponentUse,
    ConstArg,
    EachSlot,
    ExprBinding,
    Fragment,
    Handler,
    IfSlot,
    IRTemplate,
    KeySlot,
    SlotOutlet,
    TextBinding,
)
from ..compiler.script_analysis import EVENT_FACTORY, PROP_FACTORY
from ..diagnostics import Diagnostic, SourceLocation
from ..lifecycle import Ref, _setup
from ..pages import PageStack, Sections
from ..tasks import spawn
from ..reactivity import Computed, Effect, Event, Prop, PropError, Scope, State, batch, untracked
from ..reactivity.props import REQUIRED
from ..reactivity.collections import to_plain
from ..reactivity.effects import Gate, when_settled
from ..reactivity.state import _same
from .list_model import LazySlotModel, SlotModel
from .qt_bridge import make_bridge_class

log = logging.getLogger("janelkit")
_NO_KIND: Any = object()  # prop sin anotación de tipo


class Host(Protocol):
    """Lo que el runtime necesita del motor Qt: el componente QML de un hijo."""

    def delegate_for(self, compiled: CompiledComponent) -> QObject: ...
    def fragment_delegate(self, compiled: CompiledComponent, template_id: str) -> QObject: ...


@dataclass(frozen=True)
class ComponentRef:
    """Valor que recibe el script al importar un componente .janel (se usa con `open_window`)."""

    name: str
    path: str
    owner: "ComponentInstance | None" = field(default=None, compare=False, repr=False)

    def __repr__(self) -> str:
        return f"<componente {self.name} ({Path(self.path).name})>"


# -- tablas compiladas una vez por componente -----------------------------------
def _code(compiled: CompiledComponent, expr: Expression) -> CodeType:
    table = compiled.cache.setdefault("code", {})
    code = table.get(id(expr))
    if code is None:
        code = table[id(expr)] = compile_expression(expr, compiled.file)
    return code


def _handler_code(compiled: CompiledComponent, expr: Expression) -> CodeType:
    table = compiled.cache.setdefault("handlers", {})
    code = table.get(id(expr))
    if code is None:
        code = table[id(expr)] = compile_handler(expr, compiled.file)
    return code


def _bridge_class(compiled: CompiledComponent, template: IRTemplate) -> type[QObject]:
    table = compiled.cache.setdefault("bridges", {})
    cls = table.get(template.id)
    if cls is None:
        cls = table[template.id] = make_bridge_class(
            [b.id for b in template.bindings],
            template.model_ids,
            f"JanelBridge_{Path(compiled.file).stem}_{template.id}",
        )
    return cls


def _script_code(compiled: CompiledComponent) -> CodeType | None:
    if "script" not in compiled.cache:
        info = compiled.ir.script_info
        tree = info.tree if info is not None else None
        compiled.cache["script"] = compile(tree, compiled.file, "exec") if tree is not None else None
    return compiled.cache["script"]


def _unwrap(value: Any) -> Any:
    return value.value if isinstance(value, (State, Computed, Prop)) else value


def _display(value: Any) -> str:
    return "" if value is None else str(value)


_CONVERSIONS = {"r": repr, "s": str, "a": ascii}


def _formatted(value: Any, expr: FormattedExpression) -> str:
    """`{valor!r:.1f}`: conversión y después formato, como en un f-string (None sigue siendo "")."""
    if value is None:
        return ""
    if expr.conversion:
        value = _CONVERSIONS[expr.conversion](value)
    return format(value, expr.spec)


# -- plantillas ------------------------------------------------------------------
class TemplateInstance:
    def __init__(
        self,
        component: "ComponentInstance",
        template: IRTemplate,
        names: dict[str, Any],
        parent: "TemplateInstance | None",
        bridge_parent: QObject | None = None,
        scope: Scope | None = None,
        with_bridge: bool = True,
        gate: "Gate | None | object" = ...,
        ungated: frozenset[str] = frozenset(),
    ):
        self.component = component
        self.template = template
        # Compuerta de visibilidad de lo que muestra esta plantilla (ver Gate): la del sitio
        # donde se monta. `ungated`: bindings que no se aplazan (el que muestra un {#hidden}).
        self.gate: Gate | None = (parent.gate if parent is not None else None) if gate is ... else gate  # type: ignore[assignment]
        self._ungated = ungated
        self.names = names
        self.row_key: Any = None  # clave de la fila de {#each} que crea esta plantilla (si la hay)
        self.view_gate: Gate | None = None  # fila de <List>: abierta solo mientras se ve
        self._views = 0
        self.parent = parent
        self.scope = scope if scope is not None else Scope()
        self._globals = {GETTER: self._get, "__builtins__": builtins}
        self._handlers = {h.id: h for h in template.handlers}
        self._writes = {w.binding_id: w for w in template.writes}
        self._refs = {r.id: r for r in template.refs}
        self.bridge = _bridge_class(component.compiled, template)(self, bridge_parent) if with_bridge else None
        self.regions: list[_Region] = []
        self._attached: list[tuple[Ref, QObject]] = []
        # Filas de {#each}: componentes creados directamente en la fila (por ordinal), para
        # poder trasladarlos, y los que llegan de otra fila para adoptarlos en vez de crearlos.
        self.created: dict[int, ComponentInstance] | None = None
        self.adopt: dict[int, ComponentInstance] | None = None

    def start(self) -> None:
        if self._refs:
            self.scope.add(_Release(self._release_refs))
        with self.scope.active():
            for binding in self.template.bindings:
                self._bind(binding)
            for slot in self.template.slots:
                if isinstance(slot, EachSlot):
                    self.regions.append((_LazyEachRegion if slot.lazy else _EachRegion)(self, slot))
                elif isinstance(slot, IfSlot):
                    self.regions.append(_IfRegion(self, slot))
                elif isinstance(slot, KeySlot):
                    self.regions.append(_KeyRegion(self, slot))
                elif isinstance(slot, SlotOutlet):
                    self.regions.append(_SlotRegion(self, slot))
                else:
                    self.regions.append(_ComponentRegion(self, slot))

    @property
    def disposed(self) -> bool:
        return self.scope.disposed

    def dispose(self) -> None:
        self.scope.dispose()

    # -- nombres y expresiones ------------------------------------------------
    def resolve(self, name: str) -> Any:
        """Valor sin desenvolver de `name` en la cadena de ámbitos."""
        inst: TemplateInstance | None = self
        while inst is not None:
            if name in inst.names:
                return inst.names[name]
            inst = inst.parent
        try:
            return getattr(builtins, name)
        except AttributeError:
            raise NameError(f"name {name!r} is not defined") from None

    def _get(self, name: str) -> Any:
        return _unwrap(self.resolve(name))

    def eval(self, expression: Expression, extra: dict[str, Any] | None = None) -> Any:
        """Evalúa una expresión de plantilla; `extra` añade nombres temporales (p. ej. la clave de una fila)."""
        code = _code(self.component.compiled, expression)
        if not extra:
            return eval(code, self._globals)

        def get(name: str) -> Any:
            return _unwrap(extra[name]) if name in extra else self._get(name)

        return eval(code, {GETTER: get, "__builtins__": builtins})

    # -- bindings ------------------------------------------------------------
    def _bind(self, binding: Binding) -> None:
        bridge = self.bridge

        def update() -> None:
            # QML recibe una copia: el binding depende también del contenido de las colecciones.
            bridge.set_value(binding.id, to_plain(self._evaluate(binding), track=True))

        def on_error(exc: BaseException) -> None:
            self.report(f"error al evaluar el binding: {type(exc).__name__}: {exc}", binding.loc, exc)
            if bridge.value(binding.id) is None and isinstance(binding, TextBinding):
                bridge.set_value(binding.id, "")

        effect = Effect(update, on_error=on_error)
        if binding.id not in self._ungated:
            effect.gate = self.gate

    def _evaluate(self, binding: Binding) -> Any:
        if isinstance(binding, ExprBinding):
            value = self.eval(binding.expression)
            if binding.id in self._writes:  # bind:value={prefs.tema}: el atributo es el state, no su valor
                value = _unwrap(value)
            return self._class_string(value, binding) if binding.classes else value
        return "".join(
            p if isinstance(p, str) else _formatted(self.eval(p), p) if isinstance(p, FormattedExpression) else _display(self.eval(p))
            for p in binding.parts
        )

    def _class_string(self, value: Any, binding: ExprBinding) -> str:
        """class={expr}: texto, lista/tupla/conjunto (se ignoran los vacíos) o dict {clase: condición}."""
        names = _class_names(value)
        known = set(self.component.compiled.ir.class_names)
        warned = self.component.compiled.cache.setdefault("unknown_classes", set())
        for name in names:
            if name not in known and name not in warned:
                warned.add(name)
                self.component.warn(f"la clase '{name}' no tiene reglas en <style>", binding.loc)
        return " " + " ".join(names) + " "

    # -- eventos desde Qt ----------------------------------------------------
    def bridge_invoke(self, handler_id: str, args: list) -> None:
        self.call_handler(self._handlers[handler_id], args)

    def bridge_write(self, binding_id: str, value: Any) -> None:
        self._write(binding_id, value)

    def bridge_shown(self, shown: bool) -> None:
        """Fila de <List>: abre su compuerta mientras tiene alguna vista (ver _LazyEachRegion)."""
        if self.view_gate is None:
            return
        self._views += 1 if shown else -1
        self.view_gate.set_open(self._views > 0)

    def bridge_mounted(self, item: QObject) -> None:
        if self.parent is None and not self.disposed:
            self.component.view_created(item)

    def bridge_ref(self, ref_id: str, item: QObject, attached: bool) -> None:
        use = self._refs[ref_id]
        if attached and self.disposed:
            return
        try:
            target = self.resolve(use.name)
        except NameError:
            target = None
        if isinstance(target, (PageStack, Sections)):  # <Pages stack={nav}>, <Sections of={...}>
            if attached:
                target._attach(item, self)
                self._attached.append((target, item))
            else:
                target._detach(item)
            return
        if not isinstance(target, Ref):
            if attached:
                kind = "no está definido" if target is None else f"es {type(target).__name__}"
                self.report(f"ref: '{use.name}' {kind}; declara {use.name} = ref() en el script", use.loc)
            return
        if attached:
            target._attach(item)
            self._attached.append((target, item))
        else:
            target._detach(item)

    def _release_refs(self) -> None:
        attached, self._attached = self._attached, []
        for target, item in attached:
            target._detach(item)

    def call_handler(self, handler: Handler, args: list, kwargs: dict[str, Any] | None = None) -> None:
        if self.disposed:
            return
        try:
            if handler.inline:
                self.run_inline(handler, args, kwargs)
                return
            with untracked():
                fn = self.eval(handler.expression)
            if not callable(fn):
                self.report(f"on:{handler.event} debe recibir una función, se obtuvo {type(fn).__name__}", handler.loc)
                return
            with self.scope.active(), batch():
                result = fn(*_fit_args(fn, args), **(kwargs or {}))
                self.start_async(result, handler)
        except Exception as exc:  # noqa: BLE001 - un error del usuario no debe cerrar la app
            hint = None
            if isinstance(exc, AttributeError) and any(f"'{m}'" in str(exc) for m in ("set", "value", "update")):
                hint = (
                    "en la plantilla los state ya están desenvueltos; asígnalos directamente "
                    "(on:click={n = 1}, on:click={n += 1}) o usa una función del script"
                )
            self.report(f"error en el manejador on:{handler.event}: {type(exc).__name__}: {exc}", handler.loc, exc, hint)

    def run_inline(self, handler: Handler, args: list, kwargs: dict[str, Any] | None) -> None:
        """Ejecuta `on:x={n += 1}` o `on:x={borrar(i)}`. `event` es el argumento del evento."""
        if kwargs:
            event = kwargs if not args else (*args, kwargs)
        else:
            event = args[0] if len(args) == 1 else tuple(args) if args else None
        env = {
            GETTER: self._get,
            SETTER: self.assign,
            RUNNER: lambda value: self.start_async(value, handler),
            EVENT_NAME: event,
            "__builtins__": builtins,
        }
        with untracked(), self.scope.active(), batch():
            exec(_handler_code(self.component.compiled, handler.expression), env)

    def start_async(self, result: Any, handler: Handler) -> None:
        """Si un manejador devolvió una corrutina (`async def`), la lanza ligada a esta plantilla."""
        if inspect.isawaitable(result):

            def on_error(exc: BaseException) -> None:
                self.report(f"error en el manejador on:{handler.event}: {type(exc).__name__}: {exc}", handler.loc, exc)

            spawn(result, on_error=on_error)

    def assign(self, name: str, value: Any) -> None:
        """Asignación desde un manejador en línea: solo a `state` del script."""
        inst: TemplateInstance | None = self
        while inst is not None and name not in inst.names:
            inst = inst.parent
        if inst is None:
            raise NameError(f"'{name}' no está definido")
        target = inst.names[name]
        if inst.parent is not None:
            raise TypeError(f"no se puede asignar a la variable de bloque '{name}'")
        if isinstance(target, Prop):
            target.value = value  # PropError con explicación
        if not isinstance(target, State):
            raise TypeError(f"'{name}' es {type(target).__name__}, no un state: declara {name} = state(...) para poder asignarlo")
        target.value = value

    def _write(self, binding_id: str, value: Any) -> None:
        if self.disposed:
            return
        write = self._writes[binding_id]
        name = write.target.code.strip()
        root, *attrs = [part.strip() for part in name.split(".")]
        try:
            target = self.resolve(root)
            if attrs:  # como al leer: el nombre se desenvuelve, los atributos no
                target = _unwrap(target)
            for attr in attrs:
                target = getattr(target, attr)
        except (NameError, AttributeError):
            target = None
        if isinstance(target, State):
            target.value = value
        elif isinstance(target, Prop):
            self.report(f"bind: la prop '{name}' es de solo lectura", write.loc)
        else:
            kind = "no está definido" if target is None else f"es {type(target).__name__}, no un state"
            self.report(f"bind: '{name}' {kind}", write.loc)

    # -- componentes hijos ---------------------------------------------------
    def delegate_for(self, fragment: Fragment | None) -> QObject | None:
        if fragment is None or fragment.component is None:
            return None
        return self.component.require_host().delegate_for(self.component.compiled.component(fragment.component.path))

    def slot_delegate(self, fragment: Fragment) -> QObject | None:
        """Delegado del contenido de slot `fragment`, escrito en la plantilla de este componente."""
        if fragment.component is not None:
            return self.delegate_for(fragment)
        return self.component.require_host().fragment_delegate(self.component.compiled, fragment.template.id)

    def create_child(self, use: ComponentUse, bridge_parent: QObject | None) -> "ComponentInstance":
        compiled = self.component.compiled.component(use.path)
        adopted = self.adopt.pop(use.ordinal, None) if self.adopt else None
        if adopted is not None and (adopted.compiled is not compiled or use.slots or adopted.disposed):
            _discard_children({0: adopted})  # el contenido de un slot vive en la fila vieja: no se traslada
            adopted = None
        # Un componente trasladado conserva sus fuentes de props: los efectos de esta
        # fila empiezan a escribir en ellas (con los nombres de su nuevo padre).
        incoming: dict[str, State] = adopted._incoming if adopted is not None else {}
        with self.scope.active():
            for name, arg in use.props.items():
                if isinstance(arg, ConstArg):
                    if name in incoming:
                        incoming[name].value = arg.value
                    else:
                        incoming[name] = State(arg.value)
                    continue
                source: State | None = incoming.get(name)
                if source is None:
                    source = State(None)

                def push(arg: Expression = arg, source: State = source) -> None:
                    source.value = self.eval(arg)

                def on_error(exc: BaseException, name: str = name, arg: Expression = arg) -> None:
                    self.report(f"error al evaluar la prop '{name}' de <{use.tag}>: {type(exc).__name__}: {exc}", arg.loc, exc)

                Effect(push, on_error=on_error).gate = self.gate
                incoming[name] = source
            events = {
                name: (lambda *args, _h=handler, **kwargs: self.call_handler(_h, list(args), kwargs))
                for name, handler in use.events.items()
            }
            slots = {name: (fragment, self) for name, fragment in use.slots.items()}
            locs = {name: arg.loc if isinstance(arg, Expression) else use.loc for name, arg in use.props.items()}
            rows, inst = [], self
            while inst is not None and inst.component is self.component:
                if inst.row_key is not None:
                    rows.append(inst.row_key)
                inst = inst.parent
            hmr_key = (use.tag, use.ordinal, tuple(reversed(rows)))
            if adopted is not None:
                adopted.adopt(self.component, events, hmr_key, bridge_parent)
                child = adopted
            else:
                child = ComponentInstance(
                    compiled, self.component.host, incoming, events, bridge_parent, parent=self.component, slots=slots,
                    prop_locs=locs, hmr_key=hmr_key, gate=self.gate,
                )  # fmt: skip
        self.scope.add(child.scope)
        if self.row_key is not None:
            if self.created is None:
                self.created = {}
            self.created[use.ordinal] = child
        return child

    def report(self, message: str, loc: SourceLocation | None, exc: BaseException | None = None, hint: str | None = None) -> None:
        self.component.report(message, loc, exc, hint)


# -- regiones dinámicas ----------------------------------------------------------
@dataclass
class _Row:
    key: Any
    item: State | None
    index: State | None
    instance: TemplateInstance
    bridge: QObject
    child: "ComponentInstance | None" = None  # si el fragmento es un único componente
    leave_ms: int = 0  # duración de su animación de salida (out:/transition:)
    carried: "dict[int, ComponentInstance] | None" = None  # trasladados, esperando a que <List> cree la fila


class _Region:
    """Base de las regiones: monta y desmonta fragmentos en un modelo."""

    def __init__(self, owner: TemplateInstance):
        self.owner = owner

    def new_model(self, model_id: str, fragment: Fragment | None) -> SlotModel:
        model = SlotModel(self.owner.delegate_for(fragment), parent=self.owner.bridge)
        self.owner.bridge.set_model(model_id, model)
        return model

    def mount(
        self,
        fragment: Fragment,
        model: SlotModel,
        position: int,
        names: dict[str, Any],
        key: Any = None,
        origin: TemplateInstance | None = None,
        adopt: "dict[int, ComponentInstance] | None" = None,
        gate: "Gate | None | object" = ...,
        ungated: frozenset[str] = frozenset(),
    ) -> _Row | None:
        """Crea el fragmento en `model`. `origin` es la plantilla donde se escribió (otra, si es contenido de un slot);
        `gate`, su compuerta de visibilidad (por defecto, la del sitio donde se muestra)."""
        owner = self.owner
        origin = origin or owner
        inst = TemplateInstance(
            origin.component,
            fragment.template,
            names,
            parent=origin,
            bridge_parent=model,
            with_bridge=fragment.root is not None,
            gate=owner.gate if gate is ... else gate,
            ungated=ungated,
        )
        inst.row_key = key
        inst.adopt = adopt
        owner.scope.add(inst.scope)
        child = None
        try:
            inst.start()
            if fragment.component is not None:
                child = inst.create_child(fragment.component, bridge_parent=model)
                bridge = child.bridge
            else:
                bridge = inst.bridge
        except Exception as exc:  # noqa: BLE001 - p. ej. un error en el script de un hijo
            _discard_children(inst.adopt)
            inst.dispose()
            owner.scope.discard(inst.scope)
            loc = fragment.component.loc if fragment.component else (fragment.root.loc if fragment.root else None)
            origin.report(f"no se pudo crear el contenido: {type(exc).__name__}: {exc}", loc, exc)
            return None
        _discard_children(inst.adopt)
        inst.adopt = None
        model.insert(position, bridge)
        flush_mounts()
        return _Row(key, None, None, inst, bridge, child, fragment.leave_ms)

    def unmount(self, model: SlotModel, position: int, row: _Row) -> None:
        if row.leave_ms > 0 and not self.owner.disposed:
            # Salida animada: la fila deja de contar ya, pero su vista y sus bindings siguen
            # vivos hasta que termina la animación; entonces se retira de verdad.
            bridge = model.start_leaving(position)
            bridge.leave.emit()
            QTimer.singleShot(row.leave_ms + 20, lambda: self._finish_leaving(model, row))
            return
        # Primero la vista (QML deja de leer el puente), después efectos y puente.
        model.remove(position)
        self._release(row)

    def _finish_leaving(self, model: SlotModel, row: _Row) -> None:
        if Shiboken.isValid(model):
            model.finish_leaving(row.bridge)
        self._release(row)

    def _release(self, row: _Row) -> None:
        if not row.instance.disposed:
            row.instance.dispose()
        self.owner.scope.discard(row.instance.scope)
        if row.bridge is not None and Shiboken.isValid(row.bridge):
            row.bridge.deleteLater()


class _EachRegion(_Region):
    def __init__(self, owner: TemplateInstance, slot: EachSlot):
        super().__init__(owner)
        self.slot = slot
        self.rows: list[_Row] = []
        self.model = self.new_model(slot.model_id, slot.fragment)
        self.empty_model = self.new_model(slot.empty_model_id, slot.empty_fragment) if slot.empty_model_id else None
        self.empty_row: _Row | None = None
        self._reported_keys = False
        self.started = False  # la primera reconciliación (al montar) no busca traslados
        self.by_key: dict[Any, _Row] = {}
        if slot.key is not None:
            _each_regions.setdefault(id(slot), weakref.WeakSet()).add(self)

        def on_error(exc: BaseException) -> None:
            owner.report(f"error en {{#each}}: {type(exc).__name__}: {exc}", slot.iterable.loc, exc)

        Effect(self.update, on_error=on_error).gate = owner.gate

    def update(self) -> None:
        value = self.owner.eval(self.slot.iterable)
        items = [] if value is None else list(value)
        with untracked():
            if not self.slot.fragment.empty:
                self.reconcile(items)
                if self.slot.key is not None:
                    self.by_key = {row.key: row for row in self.rows}
            self.update_empty(not items)
        self.started = True

    def keys_for(self, items: list) -> list:
        slot = self.slot
        if slot.key is None:
            return list(range(len(items)))
        keys: list = []
        seen: set = set()
        problem: str | None = None
        for i, value in enumerate(items):
            extra = {slot.item: value}
            if slot.index:
                extra[slot.index] = i
            key = self.owner.eval(slot.key, extra)
            try:
                hash(key)
            except TypeError:
                problem = problem or f"la clave de {{#each}} debe ser hashable (número, texto o tupla), se obtuvo {type(key).__name__}"
                key = ("__jk_index__", i)
            if key in seen:
                problem = problem or f"clave repetida en {{#each}}: {key!r}; cada elemento necesita una clave única"
                key = ("__jk_dup__", key, i)
            seen.add(key)
            keys.append(key)
        if problem and not self._reported_keys:
            self._reported_keys = True
            self.owner.report(problem, slot.key.loc)
        return keys

    def reconcile(self, items: list) -> None:
        self.apply_reconcile(self.keys_for(items), items)

    def apply_reconcile(self, keys: list, items: list) -> None:
        """Elimina, mueve e inserta filas una a una (los delegados movidos se conservan)."""
        wanted = set(keys)
        for pos in range(len(self.rows) - 1, -1, -1):
            if self.rows[pos].key not in wanted:
                self.unmount(self.model, pos, self.rows.pop(pos))

        pos = 0
        for index, (key, value) in enumerate(zip(keys, items)):
            if pos < len(self.rows) and self.rows[pos].key == key:
                row = self.rows[pos]
            else:
                found = next((p for p in range(pos + 1, len(self.rows)) if self.rows[p].key == key), None)
                if found is None:
                    row = self.create(key, value, index, pos)
                    if row is not None:
                        self.rows.insert(pos, row)
                        pos += 1
                    continue
                self.model.move(found, pos)
                self.rows.insert(pos, self.rows.pop(found))
                row = self.rows[pos]
            row.item.value = value
            if row.index is not None:
                row.index.value = index
            pos += 1

    def create(self, key: Any, value: Any, index: int, pos: int) -> _Row | None:
        slot = self.slot
        item = State(value)
        names: dict[str, Any] = {slot.item: item}
        index_state = None
        if slot.index:
            index_state = names[slot.index] = State(index)
        row = self.mount(slot.fragment, self.model, pos, names, key, adopt=self.arriving(key))
        if row is not None:
            row.item, row.index = item, index_state
        return row

    # -- traslados entre instancias de la misma declaración ------------------------
    def arriving(self, key: Any) -> "dict[int, ComponentInstance] | None":
        """Componentes de una fila con esta clave que sale, en este mismo cambio, de otra
        lista de la misma declaración: aparcada (ya salió) o aún en su lista, si esta ya no la quiere."""
        if self.slot.key is None or not self.started:
            return None
        carried = _parked.pop((id(self.slot), key), None)
        if carried is not None:
            return carried
        for region in list(_each_regions.get(id(self.slot), ())):
            if region is self or region.slot is not self.slot or region.owner.disposed:
                continue
            row = region.by_key.get(key)
            if row is not None and (row.instance is not None or row.carried):
                return region.give(row)
        return None

    def give(self, row: _Row) -> "dict[int, ComponentInstance] | None":
        """Otra lista reclama `row` antes de que esta se actualice: se la cede si ya no está en sus datos."""
        with untracked():
            value = self.owner.eval(self.slot.iterable)
            if row.key in set(self.keys_for([] if value is None else list(value))):
                return None  # la misma clave en dos listas a la vez: son dos filas
        carried = self.carry(row)
        if not carried:
            return None
        position = self.rows.index(row)
        self.rows.pop(position)
        self.by_key.pop(row.key, None)
        self.model.remove(position)
        if row.instance is not None:
            self._release(row)
        return carried

    def carry(self, row: _Row) -> "dict[int, ComponentInstance] | None":
        """Separa de la fila sus componentes para trasladarlos (antes de quitar su vista)."""
        if row.instance is None:
            carried, row.carried = row.carried, None
            return carried
        carried, row.instance.created = row.instance.created, None
        for child in (carried or {}).values():
            child.remember_focus()
            row.instance.scope.discard(child.scope)
            child.bridge.setParent(self.model)  # la fila vieja se libera: su puente no debe arrastrarlo
            if row.bridge is child.bridge:
                row.bridge = None
        return carried

    def park(self, model: SlotModel, position: int, row: _Row) -> bool:
        """Al quitar una fila con clave, sus componentes esperan hasta el final del cambio
        por si otra lista de la misma declaración la recibe."""
        if model is not self.model or self.slot.key is None or self.owner.disposed:
            return False
        carried = self.carry(row)
        if not carried:
            return False
        model.remove(position)
        if row.instance is not None:
            self._release(row)
        _park((id(self.slot), row.key), carried)
        return True

    def unmount(self, model: SlotModel, position: int, row: _Row) -> None:
        if not self.park(model, position, row):
            super().unmount(model, position, row)

    def update_empty(self, is_empty: bool) -> None:
        if self.empty_model is None:
            return
        if is_empty and self.empty_row is None:
            self.empty_row = self.mount(self.slot.empty_fragment, self.empty_model, 0, {})
        elif not is_empty and self.empty_row is not None:
            self.unmount(self.empty_model, 0, self.empty_row)
            self.empty_row = None


class _LazyEachRegion(_EachRegion):
    """`{#each}` dentro de `<List>`: la reconciliación por clave es la misma, pero
    cada fila se crea (script, bindings, puente) solo cuando el ListView la pide."""

    def new_model(self, model_id: str, fragment: Fragment | None) -> SlotModel:
        if model_id != self.slot.model_id:
            return super().new_model(model_id, fragment)
        model = LazySlotModel(self.materialize, None, parent=self.owner.bridge)
        self.owner.bridge.set_model(model_id, model)
        return model

    BULK = 64  # a partir de tantos cambios, se aplican todos de una vez (reinicio del modelo)

    def create(self, key: Any, value: Any, index: int, pos: int) -> _Row | None:
        row = self.placeholder(key, value, index)
        self.model.insert(pos, row)  # hueco: el puente se crea al pedirlo Qt
        return row

    def placeholder(self, key: Any, value: Any, index: int) -> _Row:
        row = _Row(key, State(value), State(index) if self.slot.index else None, None, None)  # type: ignore[arg-type]
        row.carried = self.arriving(key)
        for child in (row.carried or {}).values():
            child.bridge.setParent(self.model)  # espera aquí hasta que ListView pida la fila
        return row

    def reconcile(self, items: list) -> None:
        keys = self.keys_for(items)
        old = {row.key: row for row in self.rows}
        wanted = set(keys)
        removed = sum(k not in wanted for k in old)
        position = {row.key: i for i, row in enumerate(self.rows)}
        survivors = [position[k] for k in keys if k in old]
        moves = len(survivors) - _longest_increasing(survivors)  # filas que hay que mover
        if not removed and not moves:
            return self.insert_runs(keys, items, old)
        changes = sum(k not in old for k in keys) + removed + moves
        if changes <= self.BULK:
            return self.apply_reconcile(keys, items)
        # Muchos cambios: un solo reinicio del modelo. Las filas que siguen conservan
        # su instancia; Qt solo vuelve a crear los delegados visibles.
        rows = [old.pop(key, None) or self.placeholder(key, value, i) for i, (key, value) in enumerate(zip(keys, items))]
        self.rows = rows
        self.model.reset([row.bridge if row.bridge is not None else row for row in rows])
        for row in old.values():
            if self.slot.key is not None and (carried := self.carry(row)):
                _park((id(self.slot), row.key), carried)
            if row.instance is not None:
                row.instance.dispose()
                self.owner.scope.discard(row.instance.scope)
                row.bridge.deleteLater()
        for index, (row, value) in enumerate(zip(rows, items)):
            row.item.value = value
            if row.index is not None:
                row.index.value = index

    def insert_runs(self, keys: list, items: list, old: dict) -> None:
        """Solo hay filas nuevas (añadir al final, cargar historial arriba...): se insertan
        por bloques contiguos, sin reiniciar el modelo, así la vista conserva su posición."""
        rows: list[_Row] = []
        run_start, run = 0, []
        for index, (key, value) in enumerate(zip(keys, items)):
            row = old.get(key)
            if row is None:
                if not run:
                    run_start = index
                run.append(self.placeholder(key, value, index))
                continue
            if run:
                self.model.insert_many(run_start, run)
                rows.extend(run)
                run = []
            row.item.value = value
            if row.index is not None:
                row.index.value = index
            rows.append(row)
        if run:
            self.model.insert_many(run_start, run)
            rows.extend(run)
        self.rows = rows

    def materialize(self, row: _Row) -> QObject | None:
        if self.owner.disposed:
            return None
        slot, owner = self.slot, self.owner
        names: dict[str, Any] = {slot.item: row.item}
        if slot.index:
            names[slot.index] = row.index
        # Su compuerta se cierra cuando Qt destruye la vista de la fila (fuera de pantalla):
        # la parte Python se conserva, pero lo que muestra deja de recalcularse hasta volver.
        gate = Gate(owner.gate)
        inst = TemplateInstance(
            owner.component, slot.fragment.template, names, parent=owner, bridge_parent=self.model, gate=gate
        )
        inst.view_gate = gate
        inst.row_key = row.key
        inst.adopt, row.carried = row.carried, None
        owner.scope.add(inst.scope)
        try:
            inst.start()
        except Exception as exc:  # noqa: BLE001
            _discard_children(inst.adopt)
            inst.dispose()
            owner.scope.discard(inst.scope)
            owner.report(f"no se pudo crear la fila: {type(exc).__name__}: {exc}", slot.fragment.root.loc, exc)
            return None
        _discard_children(inst.adopt)
        inst.adopt = None
        row.instance, row.bridge = inst, inst.bridge
        _schedule_flush()
        return inst.bridge

    LEAVE_MS = 220  # algo más que la animación de salida de <List animate> (JkList.jkAnimMs)

    def unmount(self, model: SlotModel, position: int, row: _Row) -> None:
        if self.park(model, position, row):
            return
        model.remove(position)
        if row.instance is None:
            return
        if self.slot.animated and not self.owner.disposed:
            # ListView anima la salida con el delegado aún vivo: liberar después.
            QTimer.singleShot(self.LEAVE_MS, lambda: self._release(row))
        else:
            self._release(row)


class _IfRegion(_Region):
    def __init__(self, owner: TemplateInstance, slot: IfSlot):
        super().__init__(owner)
        self.slot = slot
        self.models = [self.new_model(b.model_id, b.fragment) if b.model_id else None for b in slot.branches]
        self.active: int | None = None
        self.row: _Row | None = None

        def on_error(exc: BaseException) -> None:
            owner.report(f"error al evaluar la condición de {{#if}}: {type(exc).__name__}: {exc}", slot.loc, exc)

        Effect(self.update, on_error=on_error).gate = owner.gate

    def update(self) -> None:
        index = None
        for i, branch in enumerate(self.slot.branches):
            if branch.condition is None or self.owner.eval(branch.condition):
                index = i
                break
        if index == self.active:
            return
        with untracked():
            if self.row is not None:
                self.unmount(self.models[self.active], 0, self.row)
                self.row = None
            self.active = index
            if index is not None and self.models[index] is not None:
                self.row = self.mount(self.slot.branches[index].fragment, self.models[index], 0, {})


class _KeyRegion(_Region):
    _UNSET = object()

    def __init__(self, owner: TemplateInstance, slot: KeySlot):
        super().__init__(owner)
        self.slot = slot
        self.model = self.new_model(slot.model_id, slot.fragment)
        self.value: Any = self._UNSET
        self.row: _Row | None = None
        # {#hidden}: mientras está oculto, lo que muestra no se recalcula (se pone al día al verse).
        self.gate = Gate(owner.gate) if slot.hidden else None

        def on_error(exc: BaseException) -> None:
            word = "hidden" if slot.hidden else "key"
            owner.report(f"error al evaluar {{#{word}}}: {type(exc).__name__}: {exc}", slot.expression.loc, exc)

        Effect(self.update, on_error=on_error).gate = owner.gate

    def update(self) -> None:
        value = self.owner.eval(self.slot.expression)
        if self.slot.hidden:  # se crea la primera vez que se muestra; su `visible` hace el resto
            with untracked():
                self.gate.set_open(not value)
                if self.row is None and not value:
                    shown = frozenset((self.slot.shown_id,)) if self.slot.shown_id else frozenset()
                    self.row = self.mount(self.slot.fragment, self.model, 0, {}, gate=self.gate, ungated=shown)
            return
        if self.value is not self._UNSET and _same(value, self.value):
            return
        self.value = value
        with untracked():
            if self.row is not None:
                self.unmount(self.model, 0, self.row)
            self.row = self.mount(self.slot.fragment, self.model, 0, {})


class _SlotRegion(_Region):
    """`<Slot>`: muestra el contenido que pasó el componente padre, o la reserva."""

    def __init__(self, owner: TemplateInstance, slot: SlotOutlet):
        super().__init__(owner)
        content = owner.component.slot_content.get(slot.name)
        delegate = content[1].slot_delegate(content[0]) if content else None
        self.model = SlotModel(delegate, parent=owner.bridge)
        owner.bridge.set_model(slot.model_id, self.model)
        if slot.fallback_model_id:
            fallback_model = self.new_model(slot.fallback_model_id, slot.fallback)
        if content:
            self.mount(content[0], self.model, 0, {}, origin=content[1])
        elif slot.fallback is not None:
            self.mount(slot.fallback, fallback_model, 0, {})


class _ComponentRegion(_Region):
    def __init__(self, owner: TemplateInstance, slot: ComponentSlot):
        super().__init__(owner)
        compiled = owner.component.compiled.component(slot.use.path)
        self.model = SlotModel(owner.component.require_host().delegate_for(compiled), parent=owner.bridge)
        owner.bridge.set_model(slot.model_id, self.model)
        self.child = owner.create_child(slot.use, bridge_parent=self.model)
        self.model.insert(0, self.child.bridge)
        flush_mounts()


# -- traslados ---------------------------------------------------------------------
# Regiones {#each} con clave por declaración (id del EachSlot), y componentes de filas
# quitadas en el cambio en curso: si ninguna lista los recibe, se liberan al terminar.
_each_regions: dict[int, "weakref.WeakSet[_EachRegion]"] = {}
_parked: dict[tuple[int, Any], dict[int, "ComponentInstance"]] = {}


def _park(key: tuple[int, Any], carried: dict[int, "ComponentInstance"]) -> None:
    first = not _parked
    _discard_children(_parked.pop(key, None))
    _parked[key] = carried
    if first:
        when_settled(_release_parked)


def _release_parked() -> None:
    parked = list(_parked.values())
    _parked.clear()
    for carried in parked:
        _discard_children(carried)


def _discard_children(children: "dict[int, ComponentInstance] | None") -> None:
    for child in (children or {}).values():
        child.dispose()
        if Shiboken.isValid(child.bridge):
            child.bridge.deleteLater()


def _restore_focus(root: Any, path: list[int]) -> None:
    """Da el foco al elemento que lo tenía en la vista anterior (mismo camino desde la raíz)."""
    if not Shiboken.isValid(root):
        return
    target = root
    for i in path:
        children = target.childItems()
        if i >= len(children):
            break
        target = children[i]
    target.forceActiveFocus()


# -- ciclo de vida ----------------------------------------------------------------
# Componentes cuya vista QML ya existe y aún no han ejecutado on_mount. QML avisa
# (Component.onCompleted de la raíz) en un orden no garantizado; los callbacks se
# ejecutan después, al terminar de crear la vista, de los más profundos a la raíz.
_pending_mounts: list["ComponentInstance"] = []
_flush_scheduled = False


def flush_mounts() -> None:
    """Ejecuta on_mount de los componentes cuya vista ya se creó."""
    global _flush_scheduled
    _flush_scheduled = False
    while _pending_mounts:
        ready = sorted(_pending_mounts, key=lambda c: -c.depth)
        _pending_mounts.clear()
        for component in ready:
            component.run_mounted()


def _schedule_flush() -> None:
    global _flush_scheduled
    if not _flush_scheduled:
        _flush_scheduled = True
        QTimer.singleShot(0, flush_mounts)


class HotReload:
    """Estado guardado de una vista para volver a montarla (janel dev) sin perderlo.

    Cada componente se identifica por su ruta en el árbol (`hmr_path`). Si su
    script no cambió, sus `state` recuperan el valor que tenían.
    """

    def __init__(self, root: "ComponentInstance"):
        self.saved: dict[tuple, tuple[str, dict[str, Any]]] = {}
        self.restored = 0
        self.reset_files: set[str] = set()
        self._collect(root)

    def _collect(self, instance: "ComponentInstance") -> None:
        if instance.disposed:
            return
        values = {
            name: to_plain(value.peek())
            for name, value in instance.namespace.items()
            if type(value) is State and not name.startswith("__")
        }
        self.saved[instance.hmr_path] = (_script_source(instance.compiled), values)
        for child in instance.children:
            self._collect(child)

    def restore(self, instance: "ComponentInstance") -> None:
        entry = self.saved.get(instance.hmr_path)
        if entry is None:
            return
        script, values = entry
        if script != _script_source(instance.compiled):
            self.reset_files.add(Path(instance.compiled.file).name)
            return
        for name, value in values.items():
            current = instance.namespace.get(name)
            if type(current) is State and (current.peek() is None or value is None or type(to_plain(current.peek())) is type(value)):
                current.value = value
        self.restored += 1


hot_reload: HotReload | None = None  # lo activa DevReloader mientras vuelve a montar


def _script_source(compiled: CompiledComponent) -> str:
    script = compiled.ir.script
    return script.content if script is not None else ""


class _Release:
    def __init__(self, fn: Any):
        self.fn = fn

    def dispose(self) -> None:
        fn, self.fn = self.fn, None
        if fn is not None:
            fn()


class _Callback:
    """Función que se ejecuta al liberar un ámbito (on_destroy, limpieza de on_mount)."""

    def __init__(self, component: "ComponentInstance", fn: Any, what: str):
        self.component, self.fn, self.what = component, fn, what

    def dispose(self) -> None:
        fn, self.fn = self.fn, None
        if fn is not None:
            self.component.run_callback(fn, self.what)


def _longest_increasing(values: list[int]) -> int:
    """Longitud de la subsecuencia creciente más larga (filas que no hace falta mover)."""
    tails: list[int] = []
    for v in values:
        i = bisect.bisect_left(tails, v)
        if i == len(tails):
            tails.append(v)
        else:
            tails[i] = v
    return len(tails)


# -- componentes -----------------------------------------------------------------
class ComponentInstance:
    def __init__(
        self,
        compiled: CompiledComponent,
        host: Host | None = None,
        props: dict[str, State] | None = None,
        events: dict[str, Any] | None = None,
        bridge_parent: QObject | None = None,
        parent: "ComponentInstance | None" = None,
        slots: dict[str, tuple[Fragment, TemplateInstance]] | None = None,
        prop_locs: dict[str, SourceLocation] | None = None,
        hmr_key: Any = None,
        gate: Gate | None = None,
    ):
        self.compiled = compiled
        self._prop_locs = prop_locs or {}
        # Identidad estable en el árbol (para conservar el estado al recargar en janel dev).
        own_key = hmr_key if hmr_key is not None else Path(compiled.file).name
        self.hmr_path: tuple = (parent.hmr_path if parent is not None and hmr_key is not None else ()) + (own_key,)
        self.children: list[ComponentInstance] = []
        self.parent = parent
        self.scope = Scope()
        if parent is not None:
            parent.children.append(self)
            self.scope.add(_Release(lambda: self.parent.children.remove(self) if self in self.parent.children else None))
        self.slot_content = slots or {}
        self.host = host
        self.depth = 0 if parent is None else parent.depth + 1
        self.provided: dict[Any, Any] = {}
        self.mounted = False
        self.view_item: QObject | None = None  # raíz de su vista QML (cambia si la fila se traslada)
        self._refocus: list[int] | None = None
        self._on_mount: list[Any] = []
        self.leave_guards: list[Any] = []  # before_leave
        self.page_stack: Any = None  # la pila de pages() si es una página
        self._incoming = props or {}
        self._event_handlers = events or {}
        self.props: dict[str, Prop] = {}
        self.events: dict[str, Event] = {}
        self.namespace: dict[str, Any] = {
            "__name__": f"janelkit.components.{Path(compiled.file).stem}",
            "__file__": compiled.file,
            "__builtins__": builtins,
            PROP_FACTORY: self._make_prop,
            EVENT_FACTORY: self._make_event,
        }
        info = compiled.ir.script_info
        if info is not None:
            for name, imp in info.components.items():
                self.namespace[name] = ComponentRef(name, str(imp.path), self)
        code = _script_code(compiled)
        with self.scope.active():
            if code is not None:
                with _setup(self):
                    exec(code, self.namespace)
                if hot_reload is not None:
                    hot_reload.restore(self)
            self.root = TemplateInstance(self, compiled.ir.template, self.namespace, None, bridge_parent, scope=self.scope, gate=gate)
            self.root.start()

    @property
    def bridge(self) -> QObject:
        return self.root.bridge

    @property
    def disposed(self) -> bool:
        return self.scope.disposed

    def eval(self, expression: Expression) -> Any:
        return self.root.eval(expression)

    def dispose(self) -> None:
        """Libera bindings, efectos, filas e hijos: el estado deja de notificar a esta instancia."""
        self.scope.dispose()

    # -- preparación (lo llaman on_mount, on_destroy, provide e inject) -----------
    def add_mount(self, fn: Any) -> None:
        self._on_mount.append(fn)

    def add_destroy(self, fn: Any) -> None:
        self.scope.add(_Callback(self, fn, "on_destroy"))

    def add_leave(self, fn: Any) -> None:
        self.leave_guards.append(fn)

    def provide(self, key: Any, value: Any) -> None:
        self.provided[key] = value

    def inject(self, key: Any) -> Any:
        ancestor = self.parent
        while ancestor is not None:
            if key in ancestor.provided:
                return ancestor.provided[key]
            ancestor = ancestor.parent
        raise LookupError(key)

    # -- traslado entre filas de {#each} -----------------------------------------
    def adopt(self, parent: "ComponentInstance", events: dict[str, Any], hmr_key: Any, bridge_parent: QObject | None) -> None:
        """Pasa a una fila de otra lista: nuevo padre, manejadores de sus eventos y puente.
        Su estado, efectos y lo obtenido con `inject` se conservan; on_mount no se repite."""
        if self in self.parent.children:
            self.parent.children.remove(self)
        self.parent = parent
        parent.children.append(self)
        self._event_handlers = events
        for name, event in self.events.items():
            event._handler = events.get(name)
        self._rebase(parent.hmr_path + (hmr_key,))
        self.bridge.setParent(bridge_parent)

    def _rebase(self, path: tuple) -> None:
        old, self.hmr_path = self.hmr_path, path
        for child in self.children:
            child._rebase(path + child.hmr_path[len(old):])

    def remember_focus(self) -> None:
        """Si el foco está en su vista, guarda dónde, para devolverlo en la vista nueva."""
        # Se baja por la cadena de foco (sin root.window(): Shiboken ataría la ventana a
        # la raíz vieja y la invalidaría al soltarla).
        item = self.view_item
        if item is None or not Shiboken.isValid(item) or not item.hasActiveFocus():
            return
        path: list[int] = []
        while True:
            step = next((i for i, c in enumerate(item.childItems()) if c.hasActiveFocus()), None)
            if step is None:
                break
            path.append(step)
            item = item.childItems()[step]
        self._refocus = path

    # -- montaje ------------------------------------------------------------
    def view_created(self, item: QObject | None = None) -> None:
        """La vista QML de este componente existe: on_mount se ejecutará al terminar de crearla."""
        if item is not None:
            self.view_item = item
            if self._refocus is not None:
                path, self._refocus = self._refocus, None
                QTimer.singleShot(0, lambda: _restore_focus(item, path))
        if not self.mounted and self not in _pending_mounts:
            _pending_mounts.append(self)
            _schedule_flush()

    def run_mounted(self) -> None:
        if self.mounted or self.disposed:
            return
        self.mounted = True
        callbacks, self._on_mount = self._on_mount, []
        for fn in callbacks:
            cleanup = self.run_callback(fn, "on_mount")
            if callable(cleanup):
                self.scope.add(_Callback(self, cleanup, "la limpieza de on_mount"))

    def run_callback(self, fn: Any, what: str) -> Any:
        name = getattr(fn, "__name__", "función")

        def on_error(exc: BaseException) -> None:
            self.report(f"error en {what} ({name}): {type(exc).__name__}: {exc}", None, exc)

        try:
            with untracked(), batch():
                if self.scope.disposed:
                    result = fn()
                else:
                    with self.scope.active():
                        result = fn()
                if inspect.isawaitable(result):  # async def en on_mount
                    if self.scope.disposed:
                        if inspect.iscoroutine(result):
                            result.close()
                        return None
                    with self.scope.active():
                        spawn(result, on_error=on_error)
                    return None
                return result
        except Exception as exc:  # noqa: BLE001 - un error del usuario no debe cerrar la app
            on_error(exc)
            return None

    def require_host(self) -> Host:
        if self.host is None:
            raise RuntimeError("los componentes hijos necesitan un motor Qt (Application) para crearse")
        return self.host

    def _make_prop(self, name: str, default: Any = REQUIRED, kind: Any = _NO_KIND) -> Prop:
        if name in self._incoming:
            source = self._incoming[name]
            if kind is not _NO_KIND:
                self._check_prop_type(name, source, kind)
        elif default is REQUIRED:
            raise PropError(f"la prop '{name}' es obligatoria y nadie la ha pasado (¿es el componente raíz?)")
        else:
            source = State(default)
        prop = self.props[name] = Prop(name, source)
        return prop

    def _check_prop_type(self, name: str, source: State, kind: Any) -> None:
        """Comprueba cada valor que recibe una prop anotada (`edad: int = prop(0)`)."""
        if isinstance(kind, str):  # anotación entre comillas: se resuelve en el script
            try:
                kind = eval(kind, self.namespace)
            except Exception:  # noqa: BLE001 - un tipo que no se puede resolver no se comprueba
                return
        tag = Path(self.compiled.file).stem
        loc = self._prop_locs.get(name)

        def check() -> None:
            value = source.value
            if not _matches(value, kind):
                shown = repr(value) if len(repr(value)) <= 40 else repr(value)[:37] + "..."
                self.report(
                    f"la prop '{name}' de <{tag}> espera {_type_name(kind)} y recibió {type(value).__name__} ({shown})",
                    loc,
                )

        Effect(check)

    def _make_event(self, name: str) -> Event:
        event = self.events[name] = Event(name, self._event_handlers.get(name))
        return event

    def warn(self, message: str, loc: SourceLocation | None) -> None:
        diag = Diagnostic(message, loc, severity="warning", source=self.compiled.ir.source)
        log.warning(diag.format())

    def report(self, message: str, loc: SourceLocation | None, exc: BaseException | None = None, hint: str | None = None) -> None:
        source = self.compiled.ir.source if loc is None or loc.file == self.compiled.file else None
        if source is None and loc is not None:
            other = next((c for c in self.compiled.registry.values() if c.file == loc.file), None)
            source = other.ir.source if other else None
        diag = Diagnostic(message, loc, hint, source=source)
        log.error(diag.format(), exc_info=exc if exc is not None and log.isEnabledFor(logging.DEBUG) else None)


def _class_names(value: Any) -> list[str]:
    """Nombres de clase de un valor de class={...}: texto, colecciones (anidables) o {clase: condición}."""
    if value is None or value is False or value is True:
        return []
    if isinstance(value, str):
        return value.split()
    if isinstance(value, dict):
        return [n for k, on in value.items() if on for n in str(k).split()]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [n for item in value for n in _class_names(item)]
    return str(value).split()


def _matches(value: Any, kind: Any) -> bool:
    """¿`value` es del tipo anotado? Los tipos que no se saben comprobar se aceptan."""
    if kind is typing.Any or kind is object:
        return True
    if kind is None or kind is type(None):
        return value is None
    origin = typing.get_origin(kind)
    if origin is typing.Union or origin is types.UnionType:
        return any(_matches(value, arg) for arg in typing.get_args(kind))
    if origin is typing.Literal:
        return value in typing.get_args(kind)
    if origin is not None:
        kind = origin  # list[str] -> list (el contenido no se comprueba)
    if kind is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(kind, type):
        return isinstance(value, kind)
    return True


def _type_name(kind: Any) -> str:
    if kind is None or kind is type(None):
        return "None"
    if isinstance(kind, type) and typing.get_origin(kind) is None:
        return kind.__name__
    return str(kind).replace("typing.", "")


def _fit_args(fn: Any, args: list) -> list:
    """Pasa al manejador solo los argumentos que acepta (`def guardar():` o `def guardar(texto):`)."""
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return args
    if any(p.kind is p.VAR_POSITIONAL for p in params):
        return args
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return args[: len(positional)]
