# App-global Push/Pull Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add app-global `P`/`F` push/pull for the current repo with a real center-anchored spinning toast, shared with the command palette, without calling `exec_external` from worker threads.

**Architecture:** Extend `ToastPosition` + Toast frame animation on the existing 0.05s timer; add `GitApi.push()` and non-interactive env on push/pull; run captured-output git on `AsyncTask` with an explicit `_network_sync_busy` flag; deliver outcomes via a result object (AsyncTask swallows exceptions); wire conflict UX and merge-finish checkout through an `on_success` callback.

**Tech Stack:** Python 3.11+, existing `pigit.termui` (Toast, AsyncTask, overlay), `pigit.git.api`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-21-push-pull-global-design.md`

## Global Constraints

- Worker threads must never call `exec_external` or touch TUI session/TTY.
- v1 credentials: `GIT_TERMINAL_PROMPT=0` (merged into subprocess env); auth failures → ERROR toast only.
- v1 dirty worktree: no porcelain preflight; rely on git errors.
- “Global” = app keybindings on the **current** repo only (not multi-repo batch).
- Push/Pull spinner position: `ToastPosition.CENTER`.
- Busy guard is an app bool (`_network_sync_busy`), not `AsyncTask.cancel` alone.
- Observe may refresh while TOAST is open (intentional).

---

## File map

| File | Responsibility |
|------|----------------|
| `pigit/termui/types.py` | Add `ToastPosition.CENTER` |
| `pigit/termui/widgets/toast.py` | CENTER layout/slide; optional spinning frame on existing timer |
| `pigit/termui/overlay.py` | `show_spinner(..., position=)` |
| `pigit/git/api/_merge.py` | `push()`; non-interactive env; pull conflict messages |
| `pigit/git/api/__init__.py` | Facade `push()` |
| `pigit/app.py` | `_network_sync_busy`, `_run_network_git`, `P`/`F`, palette + merge wiring |
| `tests/termui/test_components_overlay.py` | CENTER + spinner frames |
| `tests/termui/test_overlay_api.py` | `show_spinner` position |
| `tests/app/test_network_sync.py` | **Create** — busy, bindings path, conflict, merge callback (mocked GitApi) |

---

### Task 1: `ToastPosition.CENTER` layout

**Files:**
- Modify: `pigit/termui/types.py`
- Modify: `pigit/termui/widgets/toast.py` (`_compute_base_position`, `_compute_slide_offset`)
- Test: `tests/termui/test_components_overlay.py`

**Interfaces:**
- Produces: `ToastPosition.CENTER`; center base `(row, col)` = vertical/horizontal midpoint; slide offset `0` for CENTER

- [ ] **Step 1: Write failing CENTER position test**

Add to `TestToast` in `tests/termui/test_components_overlay.py`:

```python
def test_toast_position_center(self):
    toast = Toast("Hi", duration=5.0, position=ToastPosition.CENTER)
    toast._rebuild_frame()
    surface = Surface(80, 24)
    row, col = toast._compute_base_position(surface)
    assert abs(row - (24 - toast.outer_row_count) // 2) <= 1
    assert abs(col - (80 - toast._outer_w) // 2) <= 1
    assert toast._compute_slide_offset(0.0) == 0
    assert toast._compute_slide_offset(0.1) == 0
```

- [ ] **Step 2: Run test — expect fail** (`ToastPosition.CENTER` missing or wrong layout)

```bash
python3 -m pytest tests/termui/test_components_overlay.py::TestToast::test_toast_position_center -v
```

- [ ] **Step 3: Implement**

In `pigit/termui/types.py`, add `CENTER = auto()` to `ToastPosition`.

In `toast.py` `_compute_base_position`:

```python
if self._position is ToastPosition.CENTER:
    base_row = max(0, (surface.height - self.outer_row_count) // 2)
    base_col = max(0, (surface.width - self._outer_w) // 2)
    return base_row, base_col
# existing top/bottom + left/right branches unchanged
```

In `_compute_slide_offset`, early-return `0` when `self._position is ToastPosition.CENTER`.

- [ ] **Step 4: Run test — expect pass**

```bash
python3 -m pytest tests/termui/test_components_overlay.py::TestToast::test_toast_position_center -v
```

- [ ] **Step 5: Commit**

```bash
git add pigit/termui/types.py pigit/termui/widgets/toast.py tests/termui/test_components_overlay.py
git commit -m "$(cat <<'EOF'
feat(termui): add ToastPosition.CENTER anchor

EOF
)"
```

---

### Task 2: Animated `show_spinner` (reuse Toast timer)

**Files:**
- Modify: `pigit/termui/widgets/toast.py`
- Modify: `pigit/termui/overlay.py` (`show_spinner`)
- Test: `tests/termui/test_components_overlay.py`, `tests/termui/test_overlay_api.py`

**Interfaces:**
- Consumes: Task 1 `CENTER`
- Produces: `Toast(..., spin=True)` or equivalent; `show_spinner(message, *, position=ToastPosition.BOTTOM_LEFT)`; frames advance inside existing `_tick`

**Design note:** Prefer a boolean/`spin` flag + message template on Toast rather than a free-form callback, unless a callback is clearly cleaner in-tree. Frames: `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` (or `|/-\\`). Display `{frame} {message}…`.

- [ ] **Step 1: Write failing spinner frame test**

```python
def test_toast_spin_advances_frame_on_timer_tick(self):
    clock = {"t": 0.0}
    toast = Toast(
        "Pushing",
        duration=3600.0,
        position=ToastPosition.CENTER,
        clock=lambda: clock["t"],
        spin=True,  # or whatever API Task 2 settles on
        enter_duration=0.0,
        exit_duration=0.0,
    )
    toast._rebuild_frame()
    first = "".join(s.text for s in toast._line_segments[0])
    # Simulate one animation tick’s frame advance (call the same helper _tick uses)
    toast._advance_spin_frame()
    toast._rebuild_frame()
    second = "".join(s.text for s in toast._line_segments[0])
    assert first != second
    assert "Pushing" in second
```

Also update `test_show_spinner` to assert default position and that optional `position=ToastPosition.CENTER` is stored.

- [ ] **Step 2: Run — expect fail**

```bash
python3 -m pytest tests/termui/test_components_overlay.py::TestToast::test_toast_spin_advances_frame_on_timer_tick tests/termui/test_overlay_api.py::TestOverlayAPI::test_show_spinner -v
```

- [ ] **Step 3: Implement**

- Toast: store `_spin`, `_spin_message`, `_spin_frame_i`, `_SPIN_FRAMES`.
- On `_tick` (existing timer): if spinning, `_advance_spin_frame()`, rebuild segments, then `request_render()`.
- `show_spinner`:

```python
def show_spinner(
    message: str,
    *,
    position: ToastPosition = ToastPosition.BOTTOM_LEFT,
) -> Toast | None:
    return show_toast(
        "",
        segments=None,  # or build initial frame segments inside Toast(spin=...)
        duration=3600.0,
        position=position,
        # pass spin=True, spin_message=message through show_toast → Toast
    )
```

Wire new kwargs through `show_toast` only as needed (keep API minimal).

- [ ] **Step 4: Run — expect pass**

```bash
python3 -m pytest tests/termui/test_components_overlay.py::TestToast tests/termui/test_overlay_api.py::TestOverlayAPI::test_show_spinner -v
```

- [ ] **Step 5: Commit**

```bash
git add pigit/termui/widgets/toast.py pigit/termui/overlay.py tests/termui/test_components_overlay.py tests/termui/test_overlay_api.py
git commit -m "$(cat <<'EOF'
feat(termui): animate show_spinner frames on toast timer

EOF
)"
```

---

### Task 3: `GitApi.push` + non-interactive push/pull

**Files:**
- Modify: `pigit/git/api/_merge.py`
- Modify: `pigit/git/api/__init__.py`
- Test: `tests/git/` — add or extend a focused unit test with mocked executor (if no existing merge API tests, create `tests/git/test_merge_ops_network.py` with a fake executor)

**Interfaces:**
- Produces: `GitApi.push(path=None) -> None` raises `GitError`
- Produces: `pull`/`push` pass `env` with `GIT_TERMINAL_PROMPT=0` (copy of `os.environ` + override)
- Produces: `pull` on conflict raises `GitError` whose message contains `"conflict"` (same idea as `merge`)

**Important:** Do not use `exec_external` here.

- [ ] **Step 1: Write failing tests**

```python
def test_push_runs_git_push_with_terminal_prompt_disabled(fake_executor, merge_ops):
    fake_executor.last_env = None
    def exec_capture(cmd, *, flags=0, **kws):
        fake_executor.last_env = kws.get("env")
        return 0, "", ""
    fake_executor.exec = exec_capture
    merge_ops.push()
    assert fake_executor.last_env["GIT_TERMINAL_PROMPT"] == "0"

def test_pull_conflict_raises_git_error_with_conflict_word(fake_executor, merge_ops):
    fake_executor.exec = lambda *a, **k: (1, "CONFLICT (content): merge conflict in a", "")
    with pytest.raises(GitError, match="[Cc]onflict"):
        merge_ops.pull()
```

Adapt fixture style to whatever the repo already uses for executor fakes; if none, build a minimal stub object with `.exec`.

- [ ] **Step 2: Run — expect fail**

```bash
python3 -m pytest tests/git/test_merge_ops_network.py -v
```

- [ ] **Step 3: Implement**

Shared helper inside `_merge.py`:

```python
def _noninteractive_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env
```

```python
def push(self, path: str | None = None) -> None:
    path = path or self.path
    code, err, _out = self.executor.exec(
        "git push",
        cwd=path,
        flags=WAITING | REPLY | DECODE,
        env=self._noninteractive_env(),
    )
    if code != 0:
        raise GitError(err or "Push failed")
```

Update `pull` similarly for `env=...`, and on `code != 0` if `"conflict" in (err or "").lower()` raise `GitError(f"Merge conflict: {err}")` (or keep wording consistent with `merge`).

Facade:

```python
def push(self, path=None):
    return self._merge.push(path)
```

- [ ] **Step 4: Run — expect pass**

```bash
python3 -m pytest tests/git/test_merge_ops_network.py -v
```

- [ ] **Step 5: Commit**

```bash
git add pigit/git/api/_merge.py pigit/git/api/__init__.py tests/git/test_merge_ops_network.py
git commit -m "$(cat <<'EOF'
feat(git): add non-interactive GitApi.push and conflict-aware pull

EOF
)"
```

---

### Task 4: App `_run_network_git` + `P` / `F` + palette

**Files:**
- Modify: `pigit/app.py`
- Create: `tests/app/test_network_sync.py`

**Interfaces:**
- Consumes: `GitApi.push`/`pull`, `show_spinner(..., CENTER)`, `AsyncTask` / `run_async`
- Produces: `_network_sync_busy: bool`; `_network_sync_task: AsyncTask`; `_run_network_git(action: Literal["push","pull"], *, on_success: Callable[[], None] | None = None) -> None`
- **AsyncTask swallows exceptions** — worker must return a result object, not raise:

```python
@dataclass(frozen=True)
class _NetworkGitOutcome:
    ok: bool
    message: str = ""
    conflict: bool = False
```

- [ ] **Step 1: Write failing app tests** (mock `_git`, capture spinner/toast, drive callback synchronously)

```python
def test_busy_guard_blocks_second_sync(app, monkeypatch):
    app._network_sync_busy = True
    calls = []
    monkeypatch.setattr(app, "_git", ...)
    app._run_network_git("push")
    # assert no new AsyncTask start / push not called

def test_palette_push_dismisses_sheet_before_spinner(app, monkeypatch):
    # open palette mock; execute "push"; assert dismiss/close ordered before show_spinner
```

Keep first tests focused on busy + that worker callable is `self._git.push` not `exec_external`.

- [ ] **Step 2: Run — expect fail**

```bash
python3 -m pytest tests/app/test_network_sync.py -v
```

- [ ] **Step 3: Implement helper + bindings**

Sketch:

```python
@bind_action("push", "P", desc="Push current branch to upstream", tip="Push")
def push_upstream(self) -> None:
    self._run_network_git("push")

@bind_action("pull", "F", desc="Pull current branch from upstream", tip="Pull")
def pull_upstream(self) -> None:
    self._run_network_git("pull")

def _run_network_git(self, action: str, *, on_success=None) -> None:
    if self._network_sync_busy:
        show_toast("Push/Pull already in progress", duration=1.5, kind=FeedbackKind.INFO)
        return
    if self._palette.is_active:
        self._palette.close()  # or existing dismiss path used elsewhere
    self._network_sync_busy = True
    label = "Pushing" if action == "push" else "Pulling"
    show_spinner(label, position=ToastPosition.CENTER)

    def work() -> _NetworkGitOutcome:
        try:
            if action == "push":
                self._git.push()
            else:
                self._git.pull()
            return _NetworkGitOutcome(ok=True)
        except GitError as e:
            msg = str(e)
            conflict = "conflict" in msg.lower()
            return _NetworkGitOutcome(ok=False, message=msg, conflict=conflict)

    def done(outcome: _NetworkGitOutcome) -> None:
        self._network_sync_busy = False
        hide_spinner()
        if outcome.conflict:
            self._handle_pull_conflict(outcome.message)  # Task 5 may stub then fill
            return
        if not outcome.ok:
            show_toast(outcome.message or f"Git {action} failed", duration=3.0, kind=FeedbackKind.ERROR)
            return
        show_toast(f"Git {action} completed", duration=1.5, kind=FeedbackKind.SUCCESS)
        self._refresh_git_vms()
        self._schedule_reload_header()
        if on_success is not None:
            on_success()

    self._network_sync_task.start(work, done)
```

Route palette:

```python
if lower in ("pull", "push"):
    self._run_network_git(lower)
    return
# leave fetch on old path or also document fetch stays sync exec_external for now
```

**Fetch:** Spec non-goal for keys; palette `fetch` may remain on `_run_git_action` / `exec_external` until a follow-up — do not silently break fetch. Keep:

```python
if lower == "fetch":
    self._run_git_action("fetch")
    return
if lower in ("pull", "push"):
    self._run_network_git(lower)
    return
```

- [ ] **Step 4: Run — expect pass**

```bash
python3 -m pytest tests/app/test_network_sync.py -v
```

- [ ] **Step 5: Commit**

```bash
git add pigit/app.py tests/app/test_network_sync.py
git commit -m "$(cat <<'EOF'
feat(app): add global P/F push-pull via async GitApi

EOF
)"
```

---

### Task 5: Pull conflict UX

**Files:**
- Modify: `pigit/app.py` (`_handle_pull_conflict` or inline in `done`)
- Test: `tests/app/test_network_sync.py`

**Interfaces:**
- Consumes: `_NetworkGitOutcome.conflict`, `sequencer_in_progress` / `has_unmerged_paths`, `_save_merge_state` only if a source/target pair is known — for plain `git pull`, there is often **no** pigit merge-state file; route Status + toast for `continue-merge` when `MERGE_HEAD` exists, matching cherry-pick style messaging.

- [ ] **Step 1: Failing test**

```python
def test_pull_conflict_routes_to_status(app, monkeypatch):
    # make work return conflict outcome (or call done handler directly)
    # assert route_to("status") and toast mentions continue-merge / Resolve
```

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Implement**

```python
def _handle_pull_conflict(self, message: str) -> None:
    show_toast(
        "Conflict! Resolve in Status, then ';' → continue-merge",
        duration=3.0,
        kind=FeedbackKind.WARNING,
    )
    self._tab_view.route_to("status")
    self._refresh_git_vms()
```

If `continue-merge` requires `_merge_state`, either (a) document that pull conflicts use git’s MERGE_HEAD and `continue-merge` only when pigit state exists, or (b) set a minimal state from current branch + upstream when detectable. Prefer (a) unless `continue-merge` already works with MERGE_HEAD alone — **read `_continue_merge` before coding** and match reality; do not invent a second state machine.

- [ ] **Step 4: Run — expect pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix(app): route pull conflicts to Status like merge UX

EOF
)"
```

---

### Task 6: Merge-workflow push completion chain

**Files:**
- Modify: `pigit/app.py` (`_confirm_push_and_finish`)
- Test: `tests/app/test_network_sync.py` (or existing merge tests if present)

**Interfaces:**
- Consumes: `_run_network_git(..., on_success=...)`
- Produces: checkout-back / clear merge state **only** inside `on_success`; failures do not run success cleanup; never `finally: hide_spinner()` around async start

- [ ] **Step 1: Failing test** — assert when push outcome ok, checkout_back called after done; when push starts, checkout not called yet

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Replace sync body**

```python
def on_push_confirmed(confirmed: bool) -> None:
    if not confirmed:
        # keep today’s cancel behavior (still checkout-back? match existing)
        ...
        return

    def after_push() -> None:
        try:
            self._git.checkout_branch(source)
        except GitError as e:
            show_toast(f"Checkout back failed: {e}", ..., kind=FeedbackKind.ERROR)
            return
        self._merge_state = None
        ...
        show_toast(f"Merged into {target}", ..., kind=FeedbackKind.SUCCESS)

    self._run_network_git("push", on_success=after_push)
```

Re-read current cancel/decline path and preserve it.

- [ ] **Step 4: Run — expect pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix(app): chain merge finish checkout after async push

EOF
)"
```

---

### Task 7: Regression sweep

**Files:** none new

- [ ] **Step 1: Run focused suites**

```bash
python3 -m pytest tests/termui/test_components_overlay.py tests/termui/test_overlay_api.py tests/git/test_merge_ops_network.py tests/app/test_network_sync.py tests/app/test_header_state.py -q
```

Expected: all pass.

- [ ] **Step 2: Run broader app/termui if time**

```bash
python3 -m pytest tests/app tests/termui -q --tb=line
```

- [ ] **Step 3: Manual smoke** (implementer): `P`/`F` show center spinner animation; palette push dismisses sheet; second `P` while busy toasts; no TTY suspend.

- [ ] **Step 4: Commit only if Task 7 produced fixes**; otherwise stop.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| `P`/`F` global bindings | 4 |
| Palette shares path; dismiss sheet first | 4 |
| No `exec_external` in worker | 3–4 |
| `GitApi.push` + non-interactive env | 3 |
| Credential policy v1 | 3 |
| Busy flag | 4 |
| CENTER position | 1 |
| Animated spinner via existing timer | 2 |
| Pull conflict → Status UX | 5 |
| Merge push `on_success` chain | 6 |
| No dirty preflight (explicit) | 4 (no preflight code) |
| Fetch unchanged on palette | 4 |
| Observe/TOAST allowed | (no code; do not defer on TOAST) |

## Placeholder scan

No TBD steps; AsyncTask exception swallowing called out with `_NetworkGitOutcome`; merge conflict/`continue-merge` dependency requires reading `_continue_merge` in Task 5 before choosing state persistence.
