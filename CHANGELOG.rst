^^^^^^^^^^^^^^^^^^^^^^^^
Changelog of pigit
^^^^^^^^^^^^^^^^^^^^^^^^

v1.5.0 (2022-02-26)
----------
- Refactor code, split sub-command of usage.
- Refactor shell completion.
- Refactor args parser.
- Feat function, add ``repo`` option.
- Feat function, add ``open`` option.
- Fix color error of print original git command.
- Fix some logic bug of TUI.
- Fix can't process chinese error of TUI.
- Update config.
- Remove useless function: ``tomato``.

v1.3.6 (2022-02-10)
----------
- Console add ``--alias`` command.
- Interaction mode add ignore fuc.
- Add new short git command about submodule.
- Update log info more clear.

v1.3.5 (2022-01-15)
----------
- Refactor part of code.
- Fix ``ue`` command about setting global user and email.
- Fix ``--create-config`` command when don't have config.

v1.3.4 (2021-12-26)
----------
- Split TUI module.
- Refactor interaction mode.
- Add branch model of interaction.

v1.3.3 (2021-11-05)
----------
- Optimize CodeCounter.
- Refactor shell completion.
- Dep update to Python3.8
- Optimize shell mode.

v1.3.2 (2021-10-11)
----------
- Fix table class for chinese and color.
- Fix get repo path error when in submodule repo.
- Adjust the command line parameters, ``pigit -h`` to view.
- Simple interactive interface support commit part.

v1.3.1 (2021-09-28)
----------
- Add new git short command (submodule).
- Add new config option.
- Add table class.
- Improve code logic and format.

v1.3.0 (2021-09-09)
----------
- Not continue support Python2.
- Update config and config template.
- Improve code counter running speed.
- Code counter output support icon.
- Fix color command error.
- Add simple shell mode.

v1.0.9 (2021-08-24)
----------
- Update owned commands.
- Supported interaction of windows.
- Improved CodeCounter.
- Fixed some error.
- Update documents.

v1.0.8 (2021-08-18)
----------
- Split package.
- Fixed shell completion.
- Allow setting custom cmds.

v1.0.7 (2021-08-11)
----------
- Refactor config.
- Compat with python2 of interactive mode.
- Add delete and editor in interactive.

v1.0.6 (2021-08-08)
----------
- Rename project, pygittools -> pigit
- Added configuration.
- Added interactive file tree operation.
- Allowed some command combined use, like: ``-if``.
- Optimized ignore matching algorithm of CodeCounter.
- Increase the output mode of CodeCounter. [table, simple]
- Refactor Git command processor.
- Refactor Completion, support fish shell.
- Fix emoji error on windows.

v1.0.4 (2021-08-04)
----------
- Optimized recommendation algorithm.
- Optimize the output of CodeCounter results.
- Repair CodeCounter matching rule.
- Compatible with windows.

v1.0.3 (2021-08-02)
----------
- Support code statistics.
- Support command correction.
- Update completion.

v1.0.2 (2021-07-30)
----------
- Add debug mode.
- Update completion function.
- Support create ``.gitignore`` template according to given type.
- Show runtime.
- Improve print, more color and beautiful.
- Fix color compatibility with python2.

v1.0.1 (2021-07-28)
----------
- Support quick view of GIT config
- Support to display warehouse information
- Improve description.
- Improve help message.

v1.0.0 (2021-07-20)
----------
- Fist release.
- Support Python2.7 and Python3.
- Can use short git command.
- Support shell complete.
- Auto check git version.
