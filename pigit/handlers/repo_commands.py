from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..cmdparse.parser import Namespace
    from ..context import Context


class RepoCommandHandler:
    """``pigit repo`` / ``pigit open`` — multi-repo registry and bulk git."""

    def __init__(self, ctx: "Context") -> None:
        from ..termui.cli_output import get_console

        self.ctx = ctx
        self.console = get_console()

    @property
    def managed_repos(self):
        return self.ctx.managed_repos

    def add(self, args: "Namespace") -> None:
        if added := self.managed_repos.add_repos(args.paths, args.dry_run):
            self.console.echo(f"Found {len(added)} new repo(s).")
            for path in added:
                self.console.echo(f"\t@sky_blue({path})")
        else:
            self.console.echo("@tomato(No new repos found!)")

    def rm(self, args: "Namespace") -> None:
        res = self.managed_repos.rm_repos(args.repos, args.path)
        for one in res:
            self.console.echo(f"Deleted repo. name: '{one[0]}', path: {one[1]}")

    def rename(self, args: "Namespace") -> None:
        _ok, msg = self.managed_repos.rename_repo(args.repo, args.new_name)
        self.console.echo(msg)

    def ll(self, args: "Namespace") -> None:
        simple = args.simple
        reverse = args.reverse
        filter_query = getattr(args, "filter", "")

        for info in self.managed_repos.ll_repos(
            reverse=reverse, filter_query=filter_query
        ):
            if simple:
                if reverse:
                    self.console.echo(f"{info[0][0]:<20} {info[1][1]:<15}")
                else:
                    self.console.echo(f"{info[0][0]:<20} {info[1][1]:<15} {info[6][1]}")
            else:
                if reverse:
                    summary_string = textwrap.dedent(f"""\
                        @bold({info[0][0]})
                            {info[1][0]}: @sky_blue({info[1][1]})
                        """)
                else:
                    summary_string = textwrap.dedent(f"""\
                        @bold({info[0][0]})
                            {info[1][0]}: {info[1][1]}
                            {info[2][0]}: {info[2][1]}
                            {info[3][0]}: @khaki({info[3][1]})
                            {info[4][0]}: @green({info[4][1]})
                            {info[5][0]}: @yellow({info[5][1]})
                            {info[6][0]}: @sky_blue({info[6][1]})
                        """)
                self.console.echo(summary_string)

    def clear(self) -> None:
        self.managed_repos.clear_repos()

    def report(self, args: "Namespace") -> None:
        report = self.managed_repos.report_repos(
            author=args.author,
            since=args.since,
            until=args.until,
        )
        self.console.echo(report)

    def cd(self, args: "Namespace") -> None:
        pick = getattr(args, "repo_cd_pick", False)
        output_file = getattr(args, "repo_cd_output_file", None)
        code, result = self.managed_repos.cd_repo(
            args.repo, pick=pick, output_file=output_file
        )
        if code != 0:
            if result:
                self.console.echo(result)
            raise SystemExit(code)
        if output_file is None and result:
            self.console.echo(result)

    def process_repos_option(self, repos, cmd: str) -> None:
        self.managed_repos.process_repos_option(repos, cmd)

    def open_browser(self, args: "Namespace") -> None:
        _code, msg = self.managed_repos.open_repo_in_browser(
            branch=args.branch,
            issue=args.issue,
            commit=args.commit,
            print=args.print,
        )
        self.console.echo(msg)

    def mkbranch(self, args: "Namespace") -> None:
        from pigit.git.repo_multi_select_picker import (
            EMPTY_MANAGED_REPOS_MSG,
            run_multi_select_picker,
        )
        from pigit.picker_app import PickerRow

        branch_name = args.branch_name
        checkout = getattr(args, "checkout", False)
        base = getattr(args, "base", None)
        force = getattr(args, "force", False)
        dry_run = getattr(args, "dry_run", False)
        filter_regex = getattr(args, "filter_regex", "")

        repo_names: list[str] = []
        if args.repos:
            repo_names = list(args.repos)
        else:
            exist_repos = self.managed_repos.load_repos()
            if not exist_repos:
                self.console.echo(EMPTY_MANAGED_REPOS_MSG)
                return
            rows = [
                PickerRow(
                    title=name, detail=prop.get("path", ""), ref=prop.get("path", "")
                )
                for name, prop in sorted(exist_repos.items())
            ]
            exit_code, selected = run_multi_select_picker(
                rows,
                title=f"pigit repo mkbranch {branch_name}",
                initial_filter=filter_regex,
            )
            if exit_code != 0 or not selected:
                return
            repo_names = selected

        all_ok, blockers, results = self.managed_repos.branch_new_repos(
            branch_name,
            repo_names,
            checkout=checkout,
            base=base,
            force=force,
            dry_run=dry_run,
        )

        if blockers:
            self.console.echo("Pre-flight blocked:")
            for name, reason in blockers:
                self.console.echo(f"  ✗ {name} — {reason}")
            self.console.echo("\nFix the issues and retry.")
            raise SystemExit(1)

        if dry_run:
            self.console.echo(f'Would create branch "{branch_name}" in:')
            for name in repo_names:
                self.console.echo(f"  - {name}")
            return

        for name, code, stderr in results:
            if code == 0:
                self.console.echo(f"✓ {name}")
            else:
                self.console.echo(f"✗ {name} — {stderr or 'unknown error'}")
