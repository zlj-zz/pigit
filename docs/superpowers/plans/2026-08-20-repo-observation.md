# Repo observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace blind `auto_refresh_interval` with a virgin observation pipeline so panel lists, Status/Branch side previews, and Header tracking stay fresh when the repo changes.

**Architecture:** Injectable `ObservationBackend` (Phase A: `StatMtimeBackend`) enqueues `PathSignal`s; UI-thread drain merges/debounces into `ChangeBatch`; `RefreshCoordinator` dispatches typed sinks. Optional later `WatchdogBackend` via `pigit[watch]` is out of this plan’s commits but must not be blocked by the interface. Spec: `docs/superpowers/specs/2026-08-20-repo-observation-design.md`.

**Tech Stack:** Python 3.10+, pytest, existing `AppEventLoop.add_interval` / `run_async`, zero new core dependencies.

## Global Constraints

- Spec locked: B1=c StatMtime; B2 queue+UI drain; B3 `Application.on_exit`; remove `auto_refresh_interval` entirely; no blind-timer fallback.
- Dual git roots: `--git-dir` and `--git-common-dir` (M1).
- Defer refresh only for MODAL|SHEET, never TOAST (M4).
- Header ahead/behind via new Git API + async stale-guard (M2); Status preview async (M3).
- No mixins; file headers + Google docstrings; English comments; date `2026-08-20` on new files.
- Core `dependencies = []`; do not add watchdog in this plan.
- Partner rule: **do not auto-commit** unless explicitly asked; stop after each phase for ACK.
- After each phase: `python3 -m pytest ./tests -q` green.
- Keep imperative `_refresh_active_panel()` (or rename) for merge/rebase completion call sites.

---

## File map

| Path | Role |
|------|------|
| `pigit/observe/__init__.py` | Package exports for types used by app |
| `pigit/observe/types.py` | `PathSignal`, `WatchRoot`, `ChangeKind`, `ChangeBatch`, `BackendHealth`, `ObserveContext` |
| `pigit/observe/clock.py` | `MonotonicClock` protocol + `SystemClock` + test `FakeClock` |
| `pigit/observe/classify.py` | Pure `classify_path_signal(...)` |
| `pigit/observe/backend.py` | `ObservationBackend` protocol, `StatMtimeBackend`, test `FakeBackend` |
| `pigit/observe/paths.py` | Build metadata path list from git_dir + common_dir |
| `pigit/observe/observer.py` | Queue + optional producer; `poll_backend_once` for StatMtime |
| `pigit/observe/coordinator.py` | Drain, debounce, defer predicate, flush → sink callbacks |
| `pigit/observe/overlay.py` | `should_defer_repo_refresh(root)` MODAL\|SHEET only |
| `pigit/termui/application.py` | `on_exit()` hook in `_run_body` finally |
| `pigit/git/api/_core.py` (+ façade) | `get_git_common_dir`, `get_head_tracking` |
| `pigit/config_data.py` / `config.py` | Remove `auto_refresh_interval`; add `repo_observe`, `observe_worktree` |
| `pigit/app.py` | Wire observer, coordinator, remove interval timer; `reload_header`; `on_exit` |
| `pigit/app_status.py` / `app_preview.py` / `app_log_graph_preview.py` | Preview reload APIs (Phase C / Branch in A) |
| `tests/observe/` | Unit tests (fake backend, clock, classifier, coordinator) |
| `README.md` / `CHANGELOG.md` / `examples/pigit.toml` | Docs for observe; remove interval |

---

### Phase 0: Core observe types, clock, classifier (tests first)

**Suggested commit:** `feat(observe): add change kinds, clock, and path classifier`

**Files:**
- Create: `pigit/observe/types.py`, `clock.py`, `classify.py`, `__init__.py`
- Create: `tests/observe/test_classify.py`, `tests/observe/test_clock.py`

**Produces:**
- `ChangeKind`, `ChangeBatch`, `PathSignal`, `WatchRoot`, `BackendHealth`, `ObserveContext`
- `classify_path_signal(signal: PathSignal, ctx: ObserveContext) -> frozenset[ChangeKind]` and optional rel path
- `FakeClock` with `advance(seconds: float)`

- [ ] **Step 1: Add failing classifier tests**

```python
# tests/observe/test_classify.py
from pigit.observe.classify import classify_path_signal
from pigit.observe.types import ChangeKind, ObserveContext, PathSignal

def _ctx(**kwargs):
    base = dict(
        repo_root="/repo",
        git_dir="/repo/.git",
        common_dir="/repo/.git",
        preview_target=None,
    )
    base.update(kwargs)
    return ObserveContext(**base)

def test_head_file_maps_to_head():
    kinds, paths = classify_path_signal(
        PathSignal(path="/repo/.git/HEAD", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.HEAD in kinds

def test_refs_heads_maps_to_refs():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/refs/heads/main", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.REFS in kinds

def test_stash_ref_maps_to_stash_and_refs():
    kinds, _ = classify_path_signal(
        PathSignal(path="/repo/.git/refs/stash", mtime_ns=1),
        _ctx(),
    )
    assert ChangeKind.STASH in kinds
    assert ChangeKind.REFS in kinds

def test_preview_target_maps_to_preview_file():
    kinds, paths = classify_path_signal(
        PathSignal(path="/repo/foo.py", mtime_ns=1),
        _ctx(preview_target="foo.py"),
    )
    assert ChangeKind.PREVIEW_FILE in kinds
    assert "foo.py" in paths
```

- [ ] **Step 2: Run — expect FAIL (import/module missing)**

```bash
python3 -m pytest tests/observe/test_classify.py -q
```

- [ ] **Step 3: Implement `types.py`, `clock.py`, `classify.py`**

`ObserveContext` fields: `repo_root`, `git_dir`, `common_dir` (abs), `preview_target: str | None` (repo-relative).  
Classifier normalizes signal path to abs, then matches under `git_dir` / `common_dir` / worktree; returns `(frozenset[ChangeKind], frozenset[str])`.

- [ ] **Step 4: Tests pass**

```bash
python3 -m pytest tests/observe/ -q
```

- [ ] **Step 5: Stop for partner** (commit only if asked)

---

### Phase 1: Backend protocol + StatMtime + FakeBackend

**Suggested commit:** `feat(observe): add StatMtimeBackend and fake test backend`

**Files:**
- Create: `pigit/observe/backend.py`, `pigit/observe/paths.py`
- Create: `tests/observe/test_stat_mtime_backend.py`

**Produces:**
- `ObservationBackend` with `start(roots)`, `stop()`, `health()`, and for StatMtime also `tick(out_queue)` or observer calls `collect_signals() -> list[PathSignal]`
- Prefer **pull style for StatMtime**: UI/observer calls `backend.poll() -> list[PathSignal]` so no mandatory backend thread in Phase A. Protocol:

```python
class ObservationBackend(Protocol):
    def start(self, roots: Sequence[WatchRoot]) -> None: ...
    def stop(self) -> None: ...
    def health(self) -> BackendHealth: ...
    def poll(self) -> list[PathSignal]:
        """Return new signals since last poll (StatMtime/Fake). Watch backends may return []."""
```

Watchdog later can push to the same `queue.Queue` from a thread **and** leave `poll()` empty — document in `backend.py` docstring.

- [ ] **Step 1: Failing test — mtime change emits signal**

```python
def test_stat_mtime_emits_when_file_changes(tmp_path):
    target = tmp_path / "HEAD"
    target.write_text("ref: refs/heads/main\n")
    q_signals = []
    backend = StatMtimeBackend(paths=[str(target)])
    backend.start([])
    assert backend.poll() == []  # baseline
    target.write_text("ref: refs/heads/other\n")
    signals = backend.poll()
    assert len(signals) == 1
    assert signals[0].path == str(target.resolve())
```

- [ ] **Step 2: Implement `StatMtimeBackend` + `FakeBackend` (scripted signal list)**
- [ ] **Step 3: `build_git_metadata_paths(git_dir, common_dir) -> list[str]`**  
  common: `packed-refs`, walk `refs/`, `logs/refs/` if present; git_dir: `HEAD`, `index`, `logs/HEAD`. Skip missing paths. No `objects/`.
- [ ] **Step 4: Tests green; stop**

---

### Phase 2: Observer queue + coordinator drain/debounce/defer

**Suggested commit:** `feat(observe): observer queue and refresh coordinator`

**Files:**
- Create: `pigit/observe/observer.py`, `coordinator.py`, `overlay.py`
- Create: `tests/observe/test_coordinator.py`

**Produces:**
- `RepoObserver(backend, queue, ctx_provider)` with `poll_into_queue()` calling `backend.poll()` then `queue.put`
- `RefreshCoordinator(queue, clock, debounce_s=0.3, defer_fn, on_batch)` with `drain()`
- `should_defer_repo_refresh(root)` → True iff MODAL or SHEET top is open

- [ ] **Step 1: Coordinator tests with FakeClock**

```python
def test_debounce_merges_bursts():
    batches = []
    clock = FakeClock()
    q = queue.Queue()
    coord = RefreshCoordinator(
        q, clock=clock, debounce_s=0.3,
        defer_fn=lambda: False,
        on_batch=batches.append,
        classify_ctx=...,
    )
    q.put(PathSignal(path="/repo/.git/HEAD", mtime_ns=1))
    coord.drain()
    assert batches == []  # waiting debounce
    clock.advance(0.3)
    q.put(PathSignal(path="/repo/.git/index", mtime_ns=2))
    coord.drain()
    clock.advance(0.3)
    coord.drain()
    assert len(batches) == 1
    assert ChangeKind.HEAD in batches[0].kinds
    assert ChangeKind.INDEX in batches[0].kinds

def test_defer_while_modal_then_flush():
    ...
```

- [ ] **Step 2: Implement coordinator + overlay helper**
- [ ] **Step 3: Tests green; stop**

**Interfaces for later phases:**
- `on_batch: Callable[[ChangeBatch], None]`
- Coordinator must not import `pigit.app`

---

### Phase 3: Framework `on_exit` + config removal of interval

**Suggested commit:** `feat(termui): Application.on_exit; remove auto_refresh_interval`

**Files:**
- Modify: `pigit/termui/application.py` — call `self.on_exit()` in `_run_body` finally before destroy
- Modify: `pigit/config_data.py`, `pigit/config.py`, `examples/pigit.toml`, `README.md`
- Modify: `tests/test_auto_refresh.py` → replace with observe config tests or delete interval cases
- Modify: `pigit/app.py` — **remove** timer registration only in this phase if wiring not ready; if observer not wired yet, removing timer means **no** auto refresh until Phase 4 — **acceptable** if Phase 4 follows immediately in the same working session. Prefer combining “remove timer + wire observe” in Phase 4 if partner wants zero gap; otherwise document the brief gap.

**Partner preference:** Implement Phase 3 config + `on_exit` without removing the timer until Phase 4 wires observe, **or** do Phase 3+4 in one stop. **Plan default: Phase 3 adds `on_exit` + config fields + ignore legacy key; Phase 4 removes timer and starts observer in one stop** so users never lose auto-refresh without replacement.

Revised Phase 3 scope:
- `on_exit` hook only + add `repo_observe`/`observe_worktree` to config (defaults true) while **still reading** `auto_refresh_interval` until Phase 4 deletes it.

- [ ] **Step 1: Test `on_exit` called before destroy** (mock Application subclass)
- [ ] **Step 2: Implement hook**
- [ ] **Step 3: Add config fields (keep interval field until Phase 4)**
- [ ] **Step 4: Stop**

---

### Phase 4: Git dirs + head tracking + wire Phase A in app

**Suggested commit:** `feat(app): wire repo observation; drop auto_refresh_interval`

**Files:**
- Modify: `pigit/git/api/_core.py`, `pigit/git/api/__init__.py` — `get_git_common_dir`, `get_head_tracking() -> tuple[str, int, int]`
- Create: `tests/git/` or extend existing git tests with mocks for tracking
- Modify: `pigit/app.py` — start observer, drain interval 0.15s, coordinator sinks, `reload_header`, `on_exit`, remove auto_refresh timer + config field
- Modify: `pigit/app_log_graph_preview.py` — public `reload()` for current selection (reuse async path)
- Modify: Commit panel refresh path — if not `viewing_checkout_log()`, still refresh pinned ref log (call existing refresh without resetting pin)
- Update CHANGELOG / README / examples

**Sinks in `on_batch`:**

```python
def _on_observe_batch(self, batch: ChangeBatch) -> None:
    if ChangeKind.HEAD in batch.kinds or ChangeKind.REFS in batch.kinds:
        self._schedule_reload_header()
    active = resolve_presentation_leaf(self._tab_view.active)
    # list refresh by panel type + kinds (see spec §6)
    # if Branch + log graph wanted: log_graph_preview.reload()
```

`_schedule_reload_header`: bump generation; `run_async(self._git.get_head_tracking, callback)`.

`get_head_tracking` sketch:

```python
def get_head_tracking(self, path=None) -> tuple[str, int, int]:
    """Return (branch_or_sha, ahead, behind) for the current HEAD."""
    # branch name from get_head(); ahead/behind via
    # git rev-list --left-right --count @{upstream}...HEAD when upstream exists
    # else ahead=0, behind=0
```

- [ ] **Step 1: Unit/mock tests for `get_head_tracking`**
- [ ] **Step 2: Implement Git APIs**
- [ ] **Step 3: Wire observe in `setup_root` / after loop start; remove interval config + timer**
- [ ] **Step 4: `on_exit` stops observe**
- [ ] **Step 5: Full suite; stop**

**Verify:**

```bash
# no auto_refresh_interval in AppConfig
rg "auto_refresh_interval" pigit examples README.md
python3 -m pytest ./tests -q
```

---

### Phase 5: Worktree observation (Status list)

**Suggested commit:** `feat(observe): worktree meta signals for Status list`

**Files:**
- Extend: `StatMtimeBackend` / path builder for worktree files with denylist
- Modify: `classify.py` — worktree → `WORKTREE_META`
- Modify: `app.py` — when Status focused and `observe_worktree`, include worktree roots/files strategy

**Strategy (keep Phase A simple):** Phase 5 may start with **stat of `git status --porcelain` paths only** refreshed periodically via metadata poll trigger, **or** shallow walk with denylist. Spec prefers watch/stat worktree with denylist. For StatMtime: maintain a set of paths from last status load + top-level dirs excluding denylist; update set when Status list refreshes.

- [ ] **Step 1: Denylist helper tests**
- [ ] **Step 2: When Status active, `WORKTREE_META` → status `refresh()`**
- [ ] **Step 3: Full suite; stop**

---

### Phase 6: Status preview file + async preview

**Suggested commit:** `feat(app): async Status preview reload on file observe`

**Files:**
- Modify: `app_status.py` / `app_preview.py` — async load_diff + generation; `reload_preview()`
- Modify: observe ctx `set_preview_target` from Status selection
- Classify already maps preview path → `PREVIEW_FILE`

- [ ] **Step 1: Test stale-guard drops outdated preview apply**
- [ ] **Step 2: Implement async preview path (fix sync `preview_lines` load)**
- [ ] **Step 3: Wire `PREVIEW_FILE` → `reload_preview()`**
- [ ] **Step 4: Full suite; stop — v1 Done**

---

## Out of scope (this plan)

- `WatchdogBackend` / `pigit[watch]` extra (document stub in `observe/backend.py` docstring only)
- Stash side preview sink
- TUI repo switch
- Contribution graph

---

## Spec coverage

| Spec item | Phase |
|-----------|-------|
| Types, classifier, clock | 0 |
| StatMtime + Fake backend | 1 |
| Queue, debounce, defer MODAL\|SHEET | 2 |
| `on_exit` | 3 |
| Dual git roots, head tracking, wire A sinks, remove interval | 4 |
| Worktree / Status list | 5 |
| Preview file + async Status preview | 6 |
| No watchdog in core | all |

## Execution note

Between phases: stop for partner. Commits only when partner says「提交」. Suggested messages are above each phase.
