# Command Palette Sheet Polish (Option B)

**Goal:** Keep bottom Sheet; make palette discoverable and only list commands that run.

## Behavior

- Open → context catalog (hide idle sequencer controls); list height from `list_slots_for_term`.
- When matched > slots: sliding window; `↓`/`↑` move through all matches; edge cue `↓N` / `↑N`.
- Type to filter (same budget).
- Sheet: `show_border=True`, `bg=None`; list/input dim rule.
- Unknown typed id → toast.

## Files

- `pigit/termui/widgets/command_palette.py` — slots, scroll window, open(items/list_slots)
- `pigit/app_command_palette.py` — priority catalog + `catalog_for_context`
- `pigit/app.py` — toggle wiring
- tests under `tests/termui/` and `tests/app/`
