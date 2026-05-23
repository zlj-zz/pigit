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

    def update(self, args: "Namespace") -> None:
        names = getattr(args, "repos", None) or None
        repos = self.managed_repos.load_repos()
        targets = [n for n in repos if names is None or n in names] if repos else []
        if not targets:
            self.console.echo("No repos found to refresh.")
            return
        self.console.echo(f"Refreshing {len(targets)} repo(s)...")
        count = 0
        for name in self.managed_repos.refresh_meta(names, force=True):
            self.console.echo(f"  ✓ {name}")
            count += 1
        if count == 0:
            self.console.echo("All repos are up to date.")

    def rename(self, args: "Namespace") -> None:
        _, msg = self.managed_repos.rename_repo(args.repo, args.new_name)
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

    @staticmethod
    def _write_path_or_echo(path: str, output_file: str | None, console) -> None:
        """Write path to file when given, otherwise echo to console."""
        if output_file is not None:
            with open(output_file, "w") as f:
                f.write(path)
        else:
            console.echo(path)

    def _cd_with_picker(
        self, repo_name: str | None, output_file: str | None, exist: dict
    ) -> None:
        from .repo_picker import run_repo_cd_picker
        from pigit.picker_app import PickerRow
        from pigit.git.managed_repos import iter_managed_repo_names
        from .repo_picker import EMPTY_MANAGED_REPOS_MSG

        if not exist:
            self.console.echo(EMPTY_MANAGED_REPOS_MSG)
            raise SystemExit(1)
        if repo_name and repo_name in exist:
            self._write_path_or_echo(
                exist[repo_name]["path"], output_file, self.console
            )
            return

        rows = [
            PickerRow(title=name, detail=exist[name]["path"], ref=exist[name]["path"])
            for name in iter_managed_repo_names(exist)
        ]
        exit_code, result = run_repo_cd_picker(rows, initial_filter=repo_name or "")
        if exit_code == 0 and result is not None:
            self._write_path_or_echo(result, output_file, self.console)
        elif exit_code != 0:
            if result:
                self.console.echo(result)
            raise SystemExit(exit_code)

    def _cd_by_name(self, repo_name: str, output_file: str | None, exist: dict) -> None:
        path = exist.get(repo_name, {}).get("path")
        if path:
            self._write_path_or_echo(path, output_file, self.console)
            return
        self.console.echo(f"@tomato(Unknown repo: {repo_name})")
        raise SystemExit(1)

    def _cd_interactive(self, output_file: str | None, exist: dict) -> None:
        from pigit.git.managed_repos import iter_managed_repo_names
        from .repo_picker import EMPTY_MANAGED_REPOS_MSG

        names = iter_managed_repo_names(exist)
        if not names:
            self.console.echo(EMPTY_MANAGED_REPOS_MSG)
            raise SystemExit(1)

        self.console.echo("Managed repos include the following:")
        for i, name in enumerate(names):
            self.console.echo(f"  {i}. {name}")
        try:
            idx = int(input("Please input the index:"))
            path = exist[names[idx]]["path"]
            self._write_path_or_echo(path, output_file, self.console)
        except (ValueError, IndexError):
            self.console.echo("@tomato(Error: invalid index.)")
            raise SystemExit(1)

    def cd(self, args: "Namespace") -> None:
        pick = getattr(args, "repo_cd_pick", False)
        output_file = getattr(args, "repo_cd_output_file", None)
        repo_name = args.repo
        exist = self.managed_repos.load_repos()

        if pick:
            self._cd_with_picker(repo_name, output_file, exist)
            return

        if repo_name:
            self._cd_by_name(repo_name, output_file, exist)
            return

        self._cd_interactive(output_file, exist)

    def _pick_repos(
        self,
        explicit: list[str],
        title: str,
        filter_regex: str = "",
    ) -> list[str] | None:
        """Return explicit repo names, or let the user pick via TUI."""
        from pigit.picker_app import PickerRow
        from pigit.git.managed_repos import iter_managed_repo_names
        from .repo_picker import EMPTY_MANAGED_REPOS_MSG, run_multi_select_picker

        if explicit:
            return list(explicit)

        exist_repos = self.managed_repos.load_repos()
        if not exist_repos:
            self.console.echo(EMPTY_MANAGED_REPOS_MSG)
            return None

        rows = [
            PickerRow(
                title=name,
                detail=exist_repos[name].get("path", ""),
                ref=exist_repos[name].get("path", ""),
            )
            for name in iter_managed_repo_names(exist_repos)
        ]
        exit_code, selected = run_multi_select_picker(
            rows,
            title=title,
            initial_filter=filter_regex,
        )
        if exit_code != 0 or not selected:
            return None
        return selected

    def bulk_cmd(self, args: "Namespace", cmd: str) -> None:
        repo_names = self._pick_repos(
            getattr(args, "repos", []),
            title=f"pigit repo {cmd}",
        )
        if repo_names is None:
            return

        results = self.managed_repos.process_repos_option(repo_names, cmd)
        if not results:
            self.console.echo("No repos to process.")
            return

        for name, code, err, out in results:
            if out:
                self.console.echo(out)
            if err:
                self.console.echo(f"@tomato({err})")
            if code != 0:
                self.console.echo(f"@tomato(✗) {name} — exited {code}")

        success = sum(1 for _, code, _, _ in results if code == 0)
        total = len(results)
        if success == total:
            self.console.echo(f"@green(✓) {success}/{total} succeeded")
        else:
            self.console.echo(
                f"@green(✓) @yellow({success})/{total} succeeded, @tomato({total - success}) failed"
            )

    def mkbranch(self, args: "Namespace") -> None:
        branch_name = args.branch_name
        checkout = getattr(args, "checkout", False)
        base = getattr(args, "base", None)
        force = getattr(args, "force", False)
        dry_run = getattr(args, "dry_run", False)

        repo_names = self._pick_repos(
            getattr(args, "repos", []),
            title=f"pigit repo mkbranch {branch_name}",
            filter_regex=getattr(args, "filter_regex", ""),
        )
        if repo_names is None:
            return

        _, blockers, results = self.managed_repos.branch_new_repos(
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

    def switch(self, args: "Namespace") -> None:
        branch = args.branch_name
        create = getattr(args, "create", False)
        force = getattr(args, "force", False)
        dry_run = getattr(args, "dry_run", False)

        repo_names = self._pick_repos(
            getattr(args, "repos", []),
            title=f"pigit repo switch {branch}",
            filter_regex=getattr(args, "filter_regex", ""),
        )
        if repo_names is None:
            return

        _, blockers, results = self.managed_repos.switch_repos(
            branch,
            repo_names,
            create=create,
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
            self.console.echo(f'Would switch to branch "{branch}" in:')
            for name in repo_names:
                self.console.echo(f"  - {name}")
            return

        for name, code, stderr in results:
            if code == 0:
                self.console.echo(f"✓ {name}")
            else:
                self.console.echo(f"✗ {name} — {stderr or 'unknown error'}")
