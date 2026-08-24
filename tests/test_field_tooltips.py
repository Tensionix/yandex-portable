"""Every field says what it is when the pointer rests on it.

The tooltip is attached to the field container rather than to each widget: one
place covers every field kind, and a branch added later cannot forget it.

The canon is background rgb(23, 33, 43) and a 1500 ms delay — long enough that a
pointer crossing a dense panel does not set off a flicker of popups, short enough
that someone who stopped to ask gets an answer.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UI_DIR = ROOT / "system_core" / "ui_nicegui"
APP = UI_DIR / "app.py"


def app_source() -> str:
    return APP.read_text(encoding="utf-8")


def stylesheets() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(UI_DIR.glob("*.css")))


def test_the_field_container_carries_the_tooltip() -> None:
    source = app_source()
    tree = ast.parse(source)
    render = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render_field")
    body = "\n".join(source.splitlines()[render.lineno - 1 : render.end_lineno])

    assert "attach_field_tooltip(field_container, field)" in body, (
        "the container is where a tooltip covers every field kind at once"
    )
    assert "with field_container:" in body


def test_the_tooltip_text_falls_back_from_hint_to_label() -> None:
    from system_core.ui_nicegui import app as gui

    assert gui.field_control_tooltip({"label": "Источник", "hint": "Откуда читать"}) == "Откуда читать"
    assert gui.field_control_tooltip({"label": "Источник"}) == "Источник"
    assert gui.field_control_tooltip({}) == ""


def test_the_canonical_timing_is_installed() -> None:
    source = app_source()
    assert "AUDION_CANONICAL_TOOLTIP_DELAY_MS = 1500" in source
    assert "install_audion_canonical_tooltip_defaults()" in source


def test_the_canonical_background_is_in_the_stylesheet() -> None:
    assert "rgb(23, 33, 43)" in stylesheets()


def test_every_helper_the_field_branches_call_exists() -> None:
    """A branch calling a name this module never defines fails only when opened.

    The template shipped `normalize_selected_list` unresolved, so any panel with a
    checkbox group raised on render while the shell and its root panel looked fine.
    """
    source = app_source()
    tree = ast.parse(source)
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = [statement.target] if isinstance(statement, ast.AnnAssign) else statement.targets
            defined.update(t.id for t in targets if isinstance(t, ast.Name))
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            defined.update((a.asname or a.name).split(".")[0] for a in statement.names)

    import builtins

    render = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render_field")
    local = {c.id for c in ast.walk(render) if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Store)}
    local |= {c.name for c in ast.walk(render) if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))}
    local |= {
        a.arg
        for c in ast.walk(render)
        if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
        for a in c.args.args
    }
    local |= {a.arg for a in render.args.args}
    for c in ast.walk(render):
        if isinstance(c, ast.ExceptHandler) and c.name:
            local.add(c.name)
        elif isinstance(c, ast.With):
            local.update(i.optional_vars.id for i in c.items if isinstance(i.optional_vars, ast.Name))

    unresolved = sorted(
        {
            node.func.id
            for node in ast.walk(render)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id not in defined
            and node.func.id not in local
            and not hasattr(builtins, node.func.id)
        }
    )
    assert not unresolved, f"render_field calls names this module never defines: {unresolved}"


@pytest.mark.parametrize("name", ["field_control_tooltip", "attach_field_tooltip", "normalize_selected_list"])
def test_the_field_helpers_are_present(name: str) -> None:
    assert f"def {name}(" in app_source()
