"""The GUI is exercised here, not just described.

These run headlessly through NiceGUI's `user` fixture: no browser, no selenium.
They cover what `py_compile` and `--smoke` cannot — that `build_ui` actually
produces a shell, that the canonical Workbench vocabulary reaches the screen,
and that the stylesheet still arrives now that it lives outside `app.py`.

Six things about this harness are not obvious, and each one costs a failure:

1. `nicegui.testing.user_plugin`, not `nicegui.testing.plugin`. The umbrella
   plugin pulls in `screen_plugin`, which imports selenium.
2. `pytest.ini` needs an empty `main_file`, or the fixture hunts for a `main.py`.
   This app hands `build_ui` to `ui.run(root=...)`, so no page exists at import
   time and the test registers one itself.
3. `pytest-asyncio` is not needed. `anyio` ships with NiceGUI, so
   `@pytest.mark.anyio` plus an `anyio_backend` fixture is enough.
4. Module-level state and refreshables outlive a client. With one client in
   production that never shows; across tests a stale target refreshes into a
   deleted client and raises. Reset them per test.
5. The fixture matches *declared* text, not what CSS renders. A label that reads
   `ПРОВЕРИТЬ ИСТОЧНИК` on screen is declared as `Проверить источник`; only
   `text-transform` differs.
6. `app` is imported inside the tests, not at module scope. Importing it during
   collection pulls the whole GUI in ahead of every other test module and has
   been seen to break a sibling suite's `monkeypatch.setattr` on a service.

Requires beautifulsoup4 in the runtime; the module skips itself without it so a
runtime that lacks it still runs the rest of the suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("bs4", reason="NiceGUI's user fixture needs beautifulsoup4")

from nicegui import ui  # noqa: E402
from nicegui.client import Client  # noqa: E402
from nicegui.testing import User  # noqa: E402

pytest_plugins = ["nicegui.testing.user_plugin"]

UI_DIR = Path(__file__).resolve().parents[1] / "system_core" / "ui_nicegui"


def gui_module():
    """The GUI module, imported on demand rather than at collection."""
    from system_core.ui_nicegui import app

    return app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fresh_gui():
    """A clean client for each test, and the GUI module to drive it with."""
    gui = gui_module()
    targets = getattr(getattr(gui, "command_tree", None), "targets", None)
    if targets is not None:
        targets.clear()
    state = getattr(gui, "state", None)
    if isinstance(state, dict):
        state["field_values"] = {}
        state["command_path"] = []
        state["pending_command"] = None
    # NiceGUI's cleanup drops every page route's module *and all of its parents*
    # from sys.modules unless the name starts with "tests.". Handing it build_ui
    # directly would therefore evict the whole system_core package, and a later
    # test module that already holds a reference to a submodule would find its
    # parent gone — monkeypatch.setattr("system_core.x.y", ...) then fails. A
    # wrapper that claims a tests.* module keeps the purge away from the product.
    def page() -> None:
        gui.build_ui()

    page.__module__ = "tests.gui_render_page"
    ui.page("/")(page)
    return gui


def ui_language(gui) -> str:
    settings = getattr(gui, "settings", None)
    return getattr(settings, "language", "ru") or "ru"


def command_titles(gui, language: str) -> list[str]:
    """Every command in the tree, at any depth, in the language the GUI is set to."""
    titles: list[str] = []

    def walk(nodes) -> None:
        for node in nodes:
            titles.append(node.display_title(language))
            walk(node.children)

    walk(gui.root_command_nodes())
    return titles


@pytest.mark.anyio
async def test_the_shell_builds_and_shows_its_commands(user: User, fresh_gui) -> None:
    """At least one command from the manifest must be on screen once build_ui has run.

    Not the roots specifically: an app may open on a landing panel, nest its first
    level, or curate its own entry points, so the check walks the whole tree.

    `find` raises on a miss rather than returning nothing, so probing a list with it
    fails on the first absent title. `should_see` raises too, but one attempt each is
    cheap and the exception can be caught per title.
    """
    gui = fresh_gui
    if not hasattr(gui, "root_command_nodes"):
        pytest.skip("this app does not drive a command tree")

    await user.open("/")

    titles = command_titles(gui, ui_language(gui))
    assert titles, "the manifest declares no commands at all"
    for title in titles:
        try:
            await user.should_see(title, retries=1)
        except AssertionError:
            continue
        return
    raise AssertionError(f"none of {len(titles)} commands reached the page; first: {titles[0]!r}")


@pytest.mark.anyio
@pytest.mark.skipif(not (UI_DIR / "workbench.py").is_file(), reason="no canonical Workbench here")
async def test_canonical_workbench_labels_are_on_screen(user: User, fresh_gui) -> None:
    """The Workbench vocabulary is a public contract copied byte-for-byte."""
    await user.open("/")

    labels = (
        ("Источник", "Назначение", "Сбросить", "Удалить", "Список")
        if ui_language(fresh_gui) == "ru"
        else ("Source", "Target", "Reset", "Delete", "List")
    )
    for label in labels:
        await user.should_see(label)


@pytest.mark.anyio
async def test_the_stylesheet_reaches_the_page_from_its_own_file(user: User, fresh_gui) -> None:
    """`add_styles` reads .css files now, so a missing file must fail loudly here."""
    await user.open("/")

    # ui.context needs a slot and there is none out here, so read the client the
    # fixture opened straight from the registry.
    head = "\n".join(
        client.shared_head_html + client.head_html for client in Client.instances.values()
    )
    stylesheets = sorted(path.name for path in UI_DIR.glob("*.css"))
    assert stylesheets, "the app should keep its CSS in files next to app.py"
    # Token prefixes differ between apps — audion-, ats- — so look for any custom
    # property rather than for one project's naming.
    assert re.search(r"--[\w-]+\s*:", head), "the tokens never reached the page"
    assert "application_css" not in head, "the accessor leaked instead of its content"
    for name in stylesheets:
        sample = next(
            (
                line.strip()
                for line in (UI_DIR / name).read_text(encoding="utf-8").splitlines()
                if line.strip().startswith(".") and line.strip().endswith("{")
            ),
            None,
        )
        if sample:
            assert sample[:-1].strip() in head, f"{name} never reached the page"
