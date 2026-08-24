# Design: Presentation inactive (unfocused body dimming)

> **Date:** 2026-08-24
> **Status:** Revised (review M1/M2 + minors)
> **Scope:** Foreground hierarchy when a MODAL/SHEET steals keyboard; body panels stay visible
> **Principle:** One termui contract for overlay-driven structural dimming; app owns Git semantics and cursor-axis contrast. No row backgrounds.

---

## 0. Problem

When a sheet opens (command palette, commit editor, inspector, …), the body list remains visible but keys go to the sheet. Body panels should read as **inactive** without losing **semantic** color (staged XY, branch refs, unpushed, etc.).

Today inactive dimming is ad hoc and inconsistent:

| Surface | Kind | Current “inactive / dim” behavior |
|---------|------|-----------------------------------|
| Status | Body tab | Often `fg_dim` when `not is_focus_leaf`; semantic XY wiped |
| Commit | Body tab | Refs keep color; message → inactive under steal; graph → `fg_dim`; single active `_row_cache` |
| Branch | Body tab | Mostly no overlay dim (HEAD / remote / primary) |
| Stash | Body tab | Message → muted when not focus leaf |
| Rebase / Recent / LogRef | **Sheet children** | No overlay inactive; Rebase/LogRef dim **non-cursor** rows while focused |
| Palette | Sheet child | Own selection chrome (`bg_active`); out of scope |

`PigitTheme.fg_chrome_inactive` exists and is unused. There is no shared API.

---

## 1. Color roles

```text
┌──────────────────────────────────────────────────────────────┐
│ semantic    │ Git / business meaning (staged, refs, unpushed) │  Never dim for overlay-inactive
├──────────────────────────────────────────────────────────────┤
│ structural  │ Body text, filenames, ordinary branch names     │  → fg_inactive when presentation stolen
├──────────────────────────────────────────────────────────────┤
│ metadata    │ SHA, time, upstream, hints                      │  → fg_inactive (same slot as structural)
└──────────────────────────────────────────────────────────────┘
```

**Two independent axes (must not collapse):**

| Axis | Question | Owner |
|------|----------|--------|
| **Overlay (presentation steal)** | Is a MODAL/SHEET open that owns keys? | `is_presentation_stolen` → `fg_inactive` |
| **Focus (co-visible leaf)** | Is this component the focus leaf? | non-leaf → primary→muted, muted→dim |
| **Cursor** | Is this the list cursor row? | panel `is_cursor` branch (primary vs muted/dim) |

`presentation_fg` owns overlay + focus (steal wins). Cursor muted/dim stays in `describe_row`.

`is_presentation_active` is the combined gate: not stolen, and (no focus manager leaf **or** this is the leaf). Headless tests without a focus manager stay full-strength.

---

## 2. Trigger (M1) — steal ≠ focus leaf

### Why steal must not equal `not is_focus_leaf`

With a sheet open, `ComponentRoot` mouse dispatch (`root.py`) lets clicks miss the sheet and hit the body, then calls `focus_component(target)` → Column may `set_focus_chain` → a body panel becomes focus leaf again while the sheet still intercepts all keys. Keyboard stays on the editor; body would paint as “active” if inactive were keyed only on `is_focus_leaf`.

**Rule:** steal (`fg_inactive`) is decided only by overlay. Focus softening (muted/dim) applies only when **not** stolen. Steal checked first → body click under sheet still paints inactive.

### Correct predicate

```text
presentation_stolen ⇔ top open overlay is MODAL or SHEET
```

Reuse `_top_open_overlay()` (already MODAL then SHEET; **excludes TOAST**). Do **not** use `has_overlay_open()` — toasts (e.g. long spinner) would permanently dim the body.

### API shape

```python
# ComponentRoot
def is_presentation_stolen(self) -> bool:
    """True while an open MODAL or SHEET owns keyboard chrome."""
    return self._top_open_overlay() is not None
```

`Component.presentation_fg` resolves the host via `get_overlay_host()` and calls that. If no host → not stolen (tests / headless).

Unmounted nodes (`_focus_level == -1`) are **not** used as the steal signal; only overlay state.

---

## 3. Theme contract

Add `fg_inactive` on **base** `Theme` (not only `PigitTheme`):

| Slot | Typical value | Use |
|------|---------------|-----|
| `fg_primary` | PEARL / ALMOST_WHITE | Active structural |
| `fg_muted` | MUTED `(150,150,150)` | Active metadata / soft cursor-off |
| `fg_inactive` | SLATE `(120,120,130)` | Overlay-stolen structural + metadata |
| `fg_dim` | Theme: DIM `(100,100,100)`; PigitTheme overrides to SLATE | Decor / chrome rules on transparent bg; **not** the inactive API |

**Notes:**

- Pigit may alias `fg_chrome_inactive` → same as `fg_inactive`, or deprecate the chrome name later.
- Moving Stash/Commit metadata from `fg_muted` (150) to `fg_inactive` (120) under steal is a **visible darkening** — intentional and listed in §8.
- Semantic slots never map through inactive — pass `THEME.fg_*` / helpers to `Segment` directly.
- No `decor` role in `presentation_fg`. Graph rails / dir summary / stash rules keep direct `fg_dim`.

`presentation_fg` always reads structural colors via **`get_theme()`**.

---

## 4. termui API

### 4.1 Naming

Method: **`presentation_fg`**. Shares the `presentation_*` family with `presentation_child` / `is_presentation_*`; the `_fg` suffix marks color resolution (not tree walking).

```python
def presentation_fg(
    self,
    role: Literal["primary", "muted"] = "primary",
) -> tuple[int, int, int]:
    """Structural/metadata fg from presentation state."""
```

Logic:

1. If stolen → `theme.fg_inactive`.
2. Else if focus manager has a leaf and this is not it → primary→muted, muted→dim.
3. Else → `theme.fg_primary` / `theme.fg_muted`.

Git semantic colors (`THEME.fg_local_branch`, `_staged_fg`, `fg_unpushed_commit`, …) are passed **directly** to `Segment` — they never enter `presentation_fg`.

### 4.2 Stays in termui

- `is_presentation_stolen()` on host; `_top_open_overlay` unchanged semantics.
- `Theme.fg_inactive` + `presentation_fg`.
- Tests on ComponentRoot + FocusManager (see Phase A).

### 4.3 Stays in app

- Git → color helpers (`_staged_fg`, …) — **return semantic only**; no steal/dim inside.
- Cursor-axis `is_cursor` primary vs muted/dim.
- Commit `_row_cache` — bake full-strength colors only; steal / non-leaf / cursor rebuild live via `presentation_fg`. No second “inactive” cache (correctness over micro-opt; steal≠focus).

### 4.4 Not in termui

- Post-render Segment dim pass.
- Git color tables.
- Auto-dim Preview/Diff (later decision).

---

## 5. Overlay / sheet scenarios

| Scenario | Body structural | Notes |
|----------|-----------------|-------|
| Sheet open, body visible | inactive | Steal = True |
| Sheet open + click body row | inactive | Focus may move on body; steal still True (M1) |
| Sheet dismissed | primary/muted | Steal = False |
| Toast / spinner only | **not** inactive | TOAST excluded |
| Palette on sheet | body inactive; palette is sheet child | Palette chrome unchanged |
| One-line input sheet | body inactive | InputLine placeholder stays its own `fg_dim` |
| Rebase / Recent / LogRef alone | N/A as body | They **are** the sheet child; steal dims **body** behind them |
| Sheet over sheet (e.g. palette while rebase sheet open) | body inactive; lower sheet’s `presentation_fg` also sees steal | Cursor-axis rules on the focused sheet list still apply |

---

## 6. App migration — delta tables

### 6.1 Overlay axis (body tabs)

| Panel / element | Today (when “unfocused”) | Target when steal |
|-----------------|--------------------------|-------------------|
| Status filename | `fg_dim` | `presentation_fg("primary")` → inactive |
| Status XY / label | wiped to `fg_dim` | direct `_staged_fg` / `_label_fg` (semantic keep) |
| Status multi-select name | `fg_staged_renamed` only if focused | `THEME.fg_staged_renamed` always |
| Status dir summary | `fg_dim` | stay `THEME.fg_dim` (decor; not `presentation_fg`) |
| Status cursor glyph | mixed with dim | `presentation_fg("primary")` (same rule as Commit/Stash) |
| Commit message | `fg_muted` | `presentation_fg("primary")` |
| Commit SHA / meta | muted / dim | `presentation_fg("muted")` |
| Commit refs | keep / sometimes dim | direct `THEME.fg_*` always keep |
| Commit sub-rows (Merge/Author/body) | muted / dim by focus | steal → inactive; active → muted labels + primary values |
| Commit empty / blank | muted / dim | `presentation_fg("muted")` |
| Commit graph rails | dim when inactive | `fg_dim` when not presentation-active |
| Commit unpushed glyph | always yellow | always `THEME.fg_unpushed_commit` (semantic) |
| Branch HEAD | green | `THEME.fg_local_branch` |
| Branch remote | magenta | `THEME.fg_remote_branch` |
| Branch other local | primary | `presentation_fg("primary")` |
| Stash message | muted | `presentation_fg("primary")` |
| Stash ref (right) | muted | `presentation_fg("muted")` |
| Stash header `─` | `fg_dim` | stay `fg_dim` (not steal API) |

### 6.2 Cursor axis (unchanged intent; not “migrate to primary”)

| Panel | Today | Target |
|-------|-------|--------|
| Rebase subject | cursor → primary; else → muted | **same** (do not flatten via `presentation_fg("primary")` alone) |
| Rebase action | action color | semantic; optional bold on cursor |
| LogRef name | cursor → primary; else → dim | **same** cursor contrast; if steal ever applies to this list, compose: steal then cursor |
| Recent description | always primary | primary; timestamp muted; optional cursor bold only |

Compose when both apply (rare for sheet children):

```text
base = presentation_fg("primary") or presentation_fg("muted")   # overlay axis
if not is_cursor:
    base = theme.fg_muted or theme.fg_dim       # cursor axis (panel policy)
```

Prefer: `presentation_fg` first for steal; then if active (not stolen) and not cursor, apply existing muted/dim.

---

## 7. Implementation phases

### Phase A — termui

- [x] `Theme.fg_inactive` on base theme (default SLATE).
- [x] `ComponentRoot.is_presentation_stolen()`.
- [x] `Component.presentation_fg(...)`.
- [x] Tests (drive ComponentRoot + FocusManager):
  - [x] Sheet open → body `presentation_fg("primary")` is `fg_inactive`.
  - [x] Sheet open + `focus_component` on body → still `fg_inactive`.
  - [x] Sheet closed → primary/muted restored.
  - [x] Toast only → not stolen.
  - [x] Semantic colors bypass `presentation_fg` (direct `THEME` / helpers).
  - [x] Unmounted / no host → not stolen.

### Phase B — app body panels

- [x] Status (helpers lose steal-dim; filenames/cursor via `presentation_fg`)
- [x] Commit (+ single active `_row_cache`; steal/cursor live)
- [x] Branch, Stash
- [x] Panel color tests under steal (Status / Commit / Branch / Stash)
- [x] Tests assert theme slots

### Phase C — sheet children (delta only)

- [ ] Rebase / LogRef: document + keep cursor-axis; wire `presentation_fg` only if steal-over-sheet needed
- [ ] Recent: muted timestamp; no false “migration to inactive”

### Phase D — docs (optional)

- [ ] Short pointer in `pigit/termui/DEVELOPMENT.md`

No version bump unless released separately.

---

## 8. Acceptance

- [x] Sheet open: Status filenames inactive; XY still green/red/yellow.
- [ ] Sheet open + click another body panel: still inactive structural; keys still on sheet.
- [x] Toast/spinner alone: body not inactive.
- [x] Sheet closed: primary/muted restored.
- [x] Commit message inactive under steal; refs still colored.
- [x] Branch: HEAD green; other locals inactive under steal; remotes magenta.
- [x] Status↔Stash focus switch: non-leaf softens (muted/dim); semantic kept; steal still darker.
- [ ] Rebase/LogRef: non-cursor rows still softer than cursor while that sheet owns focus.
- [x] No new list row backgrounds.
- [x] Panels do not invent `else fg_dim` / `else fg_muted` for **overlay** steal; use `presentation_fg`. Cursor-axis muted/dim remains allowed.

---

## 9. Trade-offs

| Choice | Rationale |
|--------|-----------|
| Steal = MODAL/SHEET first; then non-leaf soften | Matches keyboard ownership; Status↔Stash feedback without breaking M1 |
| Exclude TOAST | Spinners must not dim forever |
| `presentation_fg` (not `role_fg`) | Names the presentation state machine; `_fg` keeps it distinct from `presentation_child` |
| No `semantic=` on `presentation_fg` | Bypass was a no-op; semantic colors use `THEME` / helpers directly |
| Single active `_row_cache` | Steal≠focus; live rebuild when inactive beats a stale dual cache |
| No decor role | Avoid no-op API; dir summary / graph rails / stash `─` stay explicit `fg_dim` |
| `fg_inactive` = SLATE | Visible on transparent INK; darker than MUTED under steal (accepted) |
| Helper, not render pass | Semantic colors stay explicit |
| Cursor axis separate | Keeps Rebase/LogRef selection affordance |
| Palette `bg_active` untouched | Sheet-child UX; out of scope for body lists |
