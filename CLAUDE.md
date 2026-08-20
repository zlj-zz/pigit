# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Pigit is a Python terminal UI (TUI) for Git, plus CLI short-commands and multi-repo management. It targets Python 3.11+ and is distributed on PyPI.

## Common development commands

Install in editable mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run the test suite:

```bash
make test
# equivalent to:
python -m pytest ./tests
```

Run a single test file or test:

```bash
python -m pytest tests/termui/test_termui_eventloop.py -q
python -m pytest tests/termui/test_termui_eventloop.py::test_add_interval_fires_callback -q
```

Lint:

```bash
make lint
# equivalent to:
python -m flake8 -v --ignore=W503,F403,F405,E501,E402,E203,E741,E401 --show-source ./pigit
```

Run the TUI locally:

```bash
make run
# equivalent to:
python ./tools/run.py
```

Clean build artifacts and caches:

```bash
make del
```

Build and publish (tag-based, uses `python -m build`):

```bash
make release
```

CI runs on `main` and `dev` branches and on version tags `v*.*.*`. It installs with `pip install -e ".[dev]"`, runs flake8, runs `pytest -s ./tests`, and verifies the tag matches `pigit.const.__version__` before publishing to PyPI.

## Architecture

- **Entry points**: `pigit/console_scripts.py` defines `pigit` / `g` entry points → `pigit/entry.py` dispatches to TUI or CLI sub-commands. `pigit/const.py` holds version metadata.
- **CLI**: `pigit/cmdparse/` (short git command aliases), `pigit/repo/` (multi-repo management), `pigit/open/` (browser URLs), `pigit/ext/` (utility extensions).
- **Git**: `pigit/git/api/` (`GitApi`) wraps `git` CLI calls — intentionally omitted from coverage, tested through integration/QA. `pigit/git/managed_repos.py` tracks the multi-repo list; `pigit/git/cmds/` is the `pigit cmd` short-command DSL.
- **TUI framework** (`pigit/termui/`): Custom lightweight framework. Key concepts — `Component` base class owns tree, geometry, bindings, lifecycle; `ComponentRoot` wraps body + `LayerStack` (toasts, sheets, modals) + `FocusManager` and is the single keyboard entry (overlay → app bindings/`handle_key` → focus leaf); `AppEventLoop` runs input polling, `AsyncTask` results, timers, render scheduling; `KeyboardInput` is a daemon-thread stdin reader feeding semantic keys into a queue; `ContextVar`-based runtime context exposes renderer, focus manager, overlay host; `EventBus` for panel pub/sub; `overlay.py` provides `show_toast` / `show_sheet` / `exec_external`; `AsyncTask` wraps `ThreadPoolExecutor`; reusable widgets and containers (Row, Column, TabView) in `widgets/` and `containers/`. Drawing helpers live in `primitives/`; public module names are unprefixed (`component.py`, `root.py`, `segment.py`, …) with engines kept as `_runtime_context` / `_layer` / etc.
- **Application**: `PigitApplication.build_root()` constructs header/body/footer, wires `TabView`, injects `ViewModel` instances. Panels at `pigit/app_*.py`; ViewModels at `pigit/viewmodels/`; `pigit/session_history.py` records undoable actions for `u` / `U`.
- **Config**: `pigit/config_data.py` (dataclasses) and `pigit/config.py` (loading/defaults).
- **Observation**: `pigit/observe/` — StatMtime backends, classify, queue + `RefreshCoordinator`; wired from `PigitApplication` when `repo_observe` is true.

## Style and conventions

The project follows the rules in `.cursor/rules/python-cdoing.mdc`. Important points:

- **Prefer code that stays close to the Zen of Python.** This is the overriding guideline: readability and explicitness beat cleverness; simple and flat beat nested and complex; one function/class should do one thing. When in doubt, choose the more obvious implementation.
- Each file must start with a module header comment in this form:
  ```python
  """
  Module: pigit/module.py
  Description: short description
  Author: Zev
  Date: YYYY-MM-DD
  """
  ```
- Classes and functions must have docstrings (Google style). Complex ones include Args/Returns/Raises/Example.
- Inline comments explain *why*, not *what*.
- Comments must be in English except inside the file header `Description` field.
- Avoid magic values; use named constants.
- Prefer semantic English names; avoid pinyin or opaque abbreviations.

## Design constraints

- **Do not introduce mixins.** The codebase intentionally avoids mixin-based class composition. Prefer explicit composition (delegate objects), helper functions, or small focused base classes instead.

Version bumps and changelog updates live in `pigit/const.py` and `CHANGELOG.md`. PyPI releases require the git tag to match `pigit.const.__version__`.
