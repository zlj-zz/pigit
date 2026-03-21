# -*- coding:utf-8 -*-

import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..cmdparse.parser import Namespace
    from ..context import Context


class RepoCommandHandler:
    """``pigit repo`` / ``pigit open`` — multi-repo registry and bulk git."""

    def __init__(self, ctx: "Context") -> None:
        from plenty import get_console

        self.ctx = ctx
        self.console = get_console()

    @property
    def repo(self):
        return self.ctx.repo

    def add(self, args: "Namespace") -> None:
        if added := self.repo.add_repos(args.paths, args.dry_run):
            self.console.echo(f"Found {len(added)} new repo(s).")
            for path in added:
                self.console.echo(f"\t`{path}`<sky_blue>")
        else:
            self.console.echo("`No new repos found!`<tomato>")

    def rm(self, args: "Namespace") -> None:
        res = self.repo.rm_repos(args.repos, args.path)
        for one in res:
            self.console.echo(f"Deleted repo. name: '{one[0]}', path: {one[1]}")

    def rename(self, args: "Namespace") -> None:
        _ok, msg = self.repo.rename_repo(args.repo, args.new_name)
        self.console.echo(msg)

    def ll(self, args: "Namespace") -> None:
        simple = args.simple
        reverse = args.reverse

        for info in self.repo.ll_repos(reverse=reverse):
            if simple:
                if reverse:
                    self.console.echo(f"{info[0][0]:<20} {info[1][1]:<15}")
                else:
                    self.console.echo(f"{info[0][0]:<20} {info[1][1]:<15} {info[5][1]}")
            else:
                if reverse:
                    summary_string = textwrap.dedent(
                        f"""\
                        b`{info[0][0]}`
                            {info[1][0]}: `{info[1][1]}`<sky_blue>
                        """
                    )
                else:
                    summary_string = textwrap.dedent(
                        f"""\
                        b`{info[0][0]}`
                            {info[1][0]}: {info[1][1]}
                            {info[2][0]}: {info[2][1]}
                            {info[3][0]}: `{info[3][1]}`<khaki>
                            {info[4][0]}: `{info[4][1]}`<ok>
                            {info[5][0]}: `{info[5][1]}`<sky_blue>
                        """
                    )
                self.console.echo(summary_string)

    def clear(self) -> None:
        self.repo.clear_repos()

    def report(self, args: "Namespace") -> None:
        report = self.repo.report_repos(
            author=args.author,
            since=args.since,
            until=args.until,
        )
        self.console.echo(report)

    def cd(self, args: "Namespace") -> None:
        self.repo.cd_repo(args.repo)

    def process_repos_option(self, repos, cmd: str) -> None:
        self.repo.process_repos_option(repos, cmd)

    def open_browser(self, args: "Namespace") -> None:
        _code, msg = self.repo.open_repo_in_browser(
            branch=args.branch,
            issue=args.issue,
            commit=args.commit,
            print=args.print,
        )
        self.console.echo(msg)
