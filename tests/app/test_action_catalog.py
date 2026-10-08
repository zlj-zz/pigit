# -*- coding: utf-8 -*-
"""
Module: tests/app/test_action_catalog.py
Description: The catalog holds exactly the actions reachable on screen now.
Author: Zev
Date: 2026-10-08
"""

from __future__ import annotations

from itertools import islice
from unittest.mock import patch

import pytest

from pigit.app import PigitApplication
from pigit.app_keybindings import collect_all_action_bindings
from pigit.config_data import AppConfig
from pigit.termui import Component, bind_action
from pigit.termui.bindings import ExecutableBinding
from pigit.termui.root import ComponentRoot
from pigit.termui.widgets.command_palette import _default_match
from pigit.termui._runtime_context import RuntimeContext, _runtime_ctx


@pytest.fixture
def runtime():
    ctx = RuntimeContext()
    token = _runtime_ctx.set(ctx)
    yield ctx
    _runtime_ctx.reset(token)


@pytest.fixture
def app(runtime: RuntimeContext) -> PigitApplication:
    """A real app with its real root, mounted and sized."""
    application = PigitApplication(config=AppConfig())
    root = ComponentRoot(
        application.build_root(),
        runtime.registry,
        event_bus=application._event_bus,
        key_handlers=application._key_handlers,
    )
    runtime.overlay_host = root
    runtime.focus_manager = root._focus_manager
    root._app_on_event = application.on_event
    application._root = root
    application.setup_root(root)
    root.mount()
    root.resize((100, 30))
    return application


def _titles(app: PigitApplication) -> list[str]:
    return [title for title, _ in app.collect_binding_groups()]


def _actions(app: PigitApplication) -> list[str]:
    return [row.action for _, rows in app.collect_binding_groups() for row in rows]


def _binding(desc: str) -> ExecutableBinding:
    """A catalog row with only the field the label rule reads."""
    return ExecutableBinding(
        keys_display="", desc=desc, action="", owner=None, invoke=lambda: None
    )


class TestOnlyWhatIsOnScreen:
    """Actions are offered for components the user can act on right now.

    Both halves matter. ``TabView`` cold-unmounts the panel you leave and it
    never reloads, so its list is still ``[]``; a mounted-but-unpainted panel
    keeps stale content for a cursor nobody can see. Either way the action
    would quietly do nothing, or act on something invisible.
    """

    def test_the_start_tab_offers_its_own_actions(self, app):
        assert _titles(app) == ["Global", "Status"]

    def test_switching_tabs_swaps_which_actions_are_offered(self, app):
        """Every panel is reachable -- the walk is not stuck on the start tab."""
        app._tab_view.route_to("branch")
        assert _titles(app) == ["Global", "Branch"]
        assert "branch.checkout" in _actions(app)

    def test_the_panel_left_behind_is_no_longer_offered(self, app):
        app._tab_view.route_to("graph")
        assert _titles(app) == ["Global", "ContributionPanel"]
        assert not [a for a in _actions(app) if a.startswith(("status.", "stash."))]

    def test_the_diff_viewer_is_offered_only_while_it_is_painted(self, app):
        """It stays mounted behind the split pane, so mounting alone would
        offer diff actions for a cursor nobody can see."""
        assert "diff.discard_hunk" not in _actions(app)
        app._body_view.show(app._diff_panel)
        assert "diff.discard_hunk" in _actions(app)

    def test_a_focused_but_unmounted_panel_is_not_offered(self, app):
        """The other half of the rule: mounting alone is not enough either."""
        app._tab_view.route_to("branch")
        assert "branch.checkout" in _actions(app)
        app._branch_panel.unmount()
        assert not [a for a in _actions(app) if a.startswith("branch.")]

    def test_a_panel_that_has_never_been_focused_contributes_nothing(self, app):
        """Stash is mounted and painted as Status's sibling, but it loads its
        list in ``on_focus`` -- so at startup its actions would be silent
        no-ops. Focus, not visibility, is what makes them real."""
        assert app._stash_panel.is_mounted()
        assert not [a for a in _actions(app) if a.startswith("stash.")]
        app.goto_stash()
        assert [a for a in _actions(app) if a.startswith("stash.")]

    def test_a_cycle_in_the_parent_chain_ends_the_walk(self, app):
        """The walk climbs parents, so it has to be cycle-guarded like the
        framework's own leaf resolvers. ``islice`` bounds the read: without the
        guard this fails on an unbounded walk instead of hanging the suite."""
        leaf = app._focused_component()
        original = leaf.parent
        leaf.parent = leaf
        try:
            owners = list(islice(app.iter_action_owners(), 10))
        finally:
            leaf.parent = original
        assert len(owners) < 10



class TestTheCatalogHoldsDeclaredActions:
    def test_every_listed_action_is_declared_somewhere(self, app):
        declared = {binding.action for _, binding in collect_all_action_bindings()}
        assert set(_actions(app)) <= declared

    def test_the_app_always_contributes_its_own(self, app):
        assert "universal.palette" in _actions(app)
        assert "universal.quit" in _actions(app)

    def test_no_action_is_listed_twice(self, app):
        actions = _actions(app)
        assert len(actions) == len(set(actions))

    def test_two_rows_never_read_the_same(self, app):
        """Descriptions repeat across panels -- ``Next row`` exists in several,
        and ``status.next``/``status.previous`` share one -- so a colliding row
        names its action."""
        labels = [item.label for item in app.palette_catalog()]
        assert len(labels) == len(set(labels))
        assert "Navigate file list · next" in labels

    def test_a_description_that_looks_disambiguated_is_still_separated(self, app):
        """Appending the action's tail cannot promise uniqueness on its own:
        another row's description may already read that way."""
        rows = {
            "x.alpha": _binding("Close"),
            "y.beta": _binding("Close"),
            "z.quit": _binding("Close · alpha"),
        }
        with patch.object(app, "palette_rows", return_value=rows):
            labels = [item.label for item in app.palette_catalog()]
        assert sorted(labels) == sorted(set(labels))
        assert len(labels) == 3

    def test_every_panel_has_a_title(self, app):
        assert all(title for title, _ in app.collect_binding_groups())


class TestTheNamedCommandsHaveNoKey:
    """Fetch and the sequencer controls are reached by name only. They are
    bindings like any other, so they land in the palette and in Help."""

    def test_the_argument_free_sequencer_controls_are_offered(self, app):
        assert {
            "universal.fetch",
            "universal.continue_merge",
            "universal.rebase_continue",
            "universal.rebase_abort",
            "universal.rebase_skip",
            "universal.cherry_pick_continue",
            "universal.cherry_pick_abort",
            "universal.cherry_pick_skip",
        } <= set(_actions(app))

    def test_they_carry_a_description_and_no_keys(self, app):
        rows = app.palette_rows()
        row = rows["universal.fetch"]
        assert row.desc == "Fetch from remote"
        assert row.keys_display == ""


class TestTheOldWordsStillFindTheirAction:
    """The palette used to be typed as bare words. The ids are now action ids
    (``universal.goto_status``), so the match has to come from the description
    -- which is where the word already was."""

    @pytest.mark.parametrize(
        ("word", "action"),
        [
            ("status", "universal.goto_status"),
            ("branch", "universal.goto_branch"),
            ("commit", "universal.goto_commit"),
            ("stash", "universal.goto_stash"),
            ("quit", "universal.quit"),
            ("push", "universal.push"),
            ("pull", "universal.pull"),
        ],
    )
    def test_typing_the_word_still_finds_the_action(self, app, word, action):
        matched = [
            item.id
            for item in app.palette_catalog()
            if _default_match(word, item)
        ]
        assert action in matched


class TestTheParameterizedIds:
    def test_they_are_distinct_from_the_binding_ids(self, app):
        """A parameterized id is bare (``merge``) and a binding id is namespaced
        (``branch.merge``); the dispatcher checks the bare ones first."""
        from pigit.app_command_palette import with_parameterized

        app._tab_view.route_to("branch")
        items = with_parameterized(
            app.palette_catalog(),
            branch_names=lambda: [],
            file_names=lambda: [],
        )
        ids = [item.id for item in items]
        assert len(ids) == len(set(ids))
        assert "merge" in ids
        assert "branch.merge" in ids


class TestHelpAndTheCatalogAgree:
    def test_help_reports_the_same_description_and_keys(self, app):
        """Both read the same rows, so a binding cannot be described one way
        in Help and another in the palette."""
        catalog = {
            row.action: row
            for _, rows in app.collect_binding_groups()
            for row in rows
        }
        groups = app.get_help_groups()
        assert groups
        for _title, rows in groups:
            for row in rows:
                assert row.action in catalog
                assert (
                    catalog[row.action].desc,
                    catalog[row.action].keys_display,
                ) == (row.desc, row.keys_display)

    def test_help_narrows_to_the_panel_you_are_on(self, app):
        app._tab_view.route_to("commit")
        assert [title for title, _ in app.get_help_groups()] == ["Commit", "Global"]


class _SheetProbe(Component):
    """A component that exists only inside a sheet -- never in the body tree."""

    keymap_namespace = "sheetprobe"

    @bind_action("probe", "p", desc="Probe from a sheet")
    def do_probe(self) -> None:
        pass

    def paint(self, surface) -> None:
        pass


class TestAnOpenOverlay:
    def test_a_sheeted_component_contributes_its_actions(self, app):
        assert "sheetprobe.probe" not in _actions(app)
        app._root.show_sheet(_SheetProbe())
        assert "sheetprobe.probe" in _actions(app)


class TestDispatchingAnAction:
    def test_an_action_id_runs_the_bound_method(self, app):
        """The id is what the palette hands back; dispatch is a lookup into the
        same rows the catalog was built from."""
        with patch.object(app, "goto_stash") as goto:
            app._on_palette_execute("universal.goto_stash")
        goto.assert_called_once()

    def test_an_action_that_is_not_on_screen_cannot_be_run_by_name(self, app):
        """Not merely unlisted: Branch is cold-unmounted, so its actions are
        not in the catalog and the id does not resolve."""
        with patch("pigit.app.show_toast") as toast:
            app._on_palette_execute("branch.delete")
        assert "Unknown command" in toast.call_args[0][0]
