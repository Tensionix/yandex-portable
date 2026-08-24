---
name: audion-nicegui-gui-layer
description: How an Audion NiceGUI app keeps its stylesheet in .css files beside app.py instead of inside it, and how build_ui is exercised headlessly through NiceGUI's user fixture. Covers the extraction procedure, the equivalence check that proves nothing was lost, and the harness pitfalls that each cost a failure. Use when moving CSS out of app.py, adding or debugging headless GUI tests, or porting the GUI layer into another Audion project.
---

# Audion NiceGUI GUI layer

Two conventions, both proven across the whole NiceGUI fleet in one pass:
the stylesheet lives outside `app.py`, and `build_ui` is actually run by the
tests rather than only compiled.

This project is the reference implementation. Read `AGENTS.md` for the wider
GUI canon — launchers, `window.py`, the Workbench contract, `ui_colors.yaml`.
Nothing here overrides it.

## Where CSS lives

```
CSS приложения      -> .css рядом с app.py, читается через application_css(name)
CSS drop-in модуля  -> внутри модуля (workbench.py), чтобы он оставался одним файлом
```

Derived from what already worked before the clean-up: `workbench.py` is
byte-identical across the fleet precisely because it is one self-contained file
carrying its own CSS, and it must stay that way. An application's own CSS has no
such constraint, and 100 KB of it inside a function is unreadable.

Names: `tokens.css` for the `:root` block when the app has a static one,
`theme.css` for the rules, `base.css` / `base2.css` for earlier runs when module
CSS sits between them.

```python
_application_css_cache: dict[str, str] = {}


def application_css(name: str) -> str:
    """A stylesheet that lives next to this module rather than inside it."""
    if name not in _application_css_cache:
        path = Path(__file__).resolve().with_name(name)
        _application_css_cache[name] = path.read_text(encoding="utf-8")
    return _application_css_cache[name]
```

### Order is load-bearing

Of two rules with equal specificity the later one wins. So:

- never sort, group or tidy a stylesheet by theme — a rule sits where the
  cascade needs it, not next to its relatives;
- split the app's CSS only where module CSS sits between its parts, and keep
  every piece in its original position in the concatenation;
- before moving one rule, check that nothing it crosses sets the same property
  at the same specificity on the same element.

The generated files carry a header saying this. Leave it there.

### Extraction procedure

1. Snapshot first: copy `app.py` to `app.py.before-css-extract`. **The baseline
   is that snapshot, never HEAD** — these repositories carry uncommitted work,
   and comparing against HEAD reports the author's own unfinished changes as
   losses.
2. Parse, don't regex. Find the `ui.add_head_html` calls, flatten `BinOp` and
   `JoinedStr` concatenations into an ordered list of parts, and splice by
   `lineno`/`end_lineno`. Replace the call **before** inserting the accessor
   above the function, so the earlier edit does not shift the later one.
3. Strip any `</style>` that ends up inside a `.css` file.
4. Keep every non-literal part — `WORKBENCH_LAYOUT_CSS`, `WORKBENCH_OVERRIDE_CSS`
   and friends — in its exact position.
5. Verify by declaration multiset: reconstruct what the app hands to
   `add_head_html` before and after, split on `[{};]`, normalise whitespace,
   compare `Counter`s. A clean result loses nothing. The only acceptable
   addition is a second `:root` when a static token block is split out.
6. `py_compile`, then `--smoke`, then the GUI tests. Revert if anything differs.

### What this catches, and what it does not

The declaration check proves the CSS is intact. It says nothing about the Python
around it. Two apps shipped an `add_styles` that raised on the first line —
a call to a function that project does not define, and an f-string naming
`variables_css` where the local is `variables`. Both passed `py_compile` and, at
the time, `--smoke`. Only running `build_ui` found them. Hence the rest of this
skill: the page is now built both by the tests and by `--smoke` itself.

## Headless GUI tests

`tests/test_gui_render.py` runs the real `build_ui` with no browser and no
selenium. The file is identical across the fleet; copy it, don't rewrite it.

Requirements: `pytest` and `beautifulsoup4` in `install/requirements_full.in`
so a rebuilt portable runtime carries them. Without `beautifulsoup4` the module
skips itself and the rest of the suite still runs.

```bat
runtime\python.exe -m pytest tests -q
```

### Seven things that each cost a failure

1. `nicegui.testing.user_plugin`, not `nicegui.testing.plugin`. The umbrella
   plugin pulls in `screen_plugin`, which imports selenium.
2. `pytest.ini` needs an empty `main_file`, or the fixture hunts for a `main.py`.
   These apps hand `build_ui` to `ui.run(root=...)`, so no page exists at import
   time and the test registers one itself.
3. `pytest-asyncio` is not needed. `anyio` ships with NiceGUI, so
   `@pytest.mark.anyio` plus an `anyio_backend` fixture is enough.
4. Module-level state and refreshables outlive a client. With one client in
   production that never shows; across tests a stale refreshable target refreshes
   into a deleted client and raises. Clear `command_tree.targets` and reset
   `state` per test.
5. The fixture matches **declared** text, not what CSS renders. A button reading
   `АРХИВАЦИЯ` on screen is declared `Архивация`; only `text-transform` differs.
6. `user.find(...)` raises on a miss instead of returning nothing, so it cannot
   be used to probe a list of candidates. `user.should_see(x, retries=1)` raises
   too, but one attempt each is cheap and can be caught per candidate.
7. NiceGUI's cleanup pops every page route's module **and all of its parents**
   from `sys.modules` unless the name starts with `tests.`. Registering
   `ui.page("/")(gui.build_ui)` therefore evicts the whole `system_core`
   package, and a sibling test module holding a reference to a submodule then
   fails on `monkeypatch.setattr("system_core.x.y", ...)` with *module
   'system_core' has no attribute 'x'*. Register a local wrapper whose
   `__module__` is set to a `tests.*` name.

Import `app` inside the fixture, not at module scope, for the same reason: at
collection time it drags the whole GUI in ahead of every other test module.

### What the three tests assert

- **shell** — at least one command from the manifest reaches the page. Not the
  roots specifically: an app may open on a landing panel, nest its first level,
  or curate its own entry points, so the check walks the whole tree.
- **Workbench** — the exact RU/EN labels are on screen. They are a public
  contract; skipped where the project has no `workbench.py`.
- **stylesheet** — the tokens and a real rule from every `.css` file beside
  `app.py` arrive in the page head, and the accessor name does not. This is the
  regression guard for the whole convention: delete a `.css` file and it fails.

A project with a richer GUI should add cases beside these — panels opening on
the right step, a mode gate hiding controls, a card showing what it must. Audion
Disk Tools carries six such tests and is the example to copy from.

### Reading the page

Assertions go through `user.should_see` / `should_not_see`. For the page head,
`ui.context` needs a slot and there is none in a test body, so read the client
the fixture opened from `nicegui.client.Client.instances`; `head_html` and
`shared_head_html` are strings, not lists.

## `--smoke` builds the page

`build_ui_once()` sits above `main()` and the `--smoke` branch calls it. There is
no browser and no HTTP request: a bare `nicegui.Client` over a throwaway page
definition gives the slot that `build_ui` needs, and the widgets are constructed
for real. It reports the widget count and the stylesheet size, and exits 1 with
the exception if anything raises.

Three details make it quiet and honest:

- it runs inside `asyncio.run`, with `nicegui.core.loop` set — without a loop the
  first `background_tasks.create` asserts;
- the app starts work that waits for a browser to attach. Nothing will attach, so
  the pending tasks are cancelled deliberately rather than left for the loop to
  close on, and the `nicegui` logger is quieted for the build. An exception from
  `build_ui` itself still propagates — that is the whole point;
- where a project already had a richer `--smoke` (Image Tools walks every command
  variant, Media Tools checks handlers and services, Planning Signals reads its
  registries), the build goes in front of it. Nothing was replaced.

## Verification for the GUI layer

```bat
runtime\python.exe -m py_compile system_core\ui_nicegui\app.py
runtime\python.exe system_core\ui_nicegui\app.py --smoke
runtime\python.exe -m pytest tests -q
```

All three are real gates now. `--smoke` is the one the launcher and the builder
already run, so a page that cannot be built no longer reaches a release.

## The terminal renderer

One module renders the terminal for the whole fleet. It lives beside the rest of
the project's core — `terminal_render.py` — and turns process output into safe
HTML: `ansi_to_html`, `strip_ansi`, `terminal_html`, `terminal_lines_html`, plus
a stateful `AnsiHtmlRenderer` that carries a colour across chunk boundaries.

Three things stay each project's own, because they are identity rather than
behaviour: the sixteen basic colours (`SGR_FG` / `SGR_BG`), the class names
(`TERMINAL_LINE_CLASS`, `TERMINAL_PRE_CLASS` — an empty line class means the
panel builds its own markup), and any name the project's code imports that the
renderer does not provide. `ansi_status` produces ANSI rather than rendering it,
so it belongs to the app.

What the renderer guarantees, and why each clause is there:

- **256 colours**, the standard xterm cube and grey ramp, which is what Windows
  Terminal shows. Indices 0-15 come from the project's own palette because those
  are the terminal's scheme. 24-bit colour maps to the nearest cube entry rather
  than being reproduced.
- **Control characters never reach the page.** Tab and newline are kept: they
  carry layout.
- **A carriage return redraws the line.** A progress bar separates its redraws
  with `\r` and never with a newline, so a whole run arrives as one part; the
  cursor returns without clearing, and a longer tail survives.
- **A table keeps its columns.** `line_holds_a_table` marks a row carrying box
  drawing, two or more bars, or a rule; the stylesheet gives such lines
  `white-space: pre` with no hanging indent, and the panel scrolls sideways only
  while one is wider than it.
- **An orphaned SGR sequence is dropped.** A pipe can swallow the escape and
  leave `[36m` behind; the final `m` is what tells it from `[OK]`.

Changing it is verified by corpus rather than by eye: run one set of probes
through every project's renderer and require the output to agree up to palette
and class names.

## The status row

One line carries state, message, clock and progress, and colour says the state —
grey idle, blue running with the dot pulsing, green done, red failed, with the
tone on the left edge as well. Figures are tabular so they do not jitter.

Two details are worth keeping when this is ported:

- **The clock is kept by the refresh timer**, which notices a run starting rather
  than being told. Several places set `state["running"]`, and none of them has to
  learn about the panel.
- **Every assignment is guarded.** The timer ticks twice a second, so writing
  five fields unconditionally sent ten element updates a second from an idle
  window. Holding the last shown value makes an idle panel free.
