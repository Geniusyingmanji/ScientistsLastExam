"""Make the repository's own ``scripts`` package win over an installed distribution's.

Without this file the directory is only a PEP 420 namespace portion, and a *regular* package of
the same name anywhere on ``sys.path`` shadows it outright. ``pyarrow`` and ``gguf`` both ship
one into dist-packages, so on this host ``from scripts.repo_paths import ...`` raised
``No module named 'scripts.repo_paths'`` and the documented ``pytest tests/ -q`` command died in
collection with 39 errors - the repository's own scripts were not importable by name from the
repository root. A regular package here ends the search here, which is what every
``python scripts/<name>.py`` invocation and every ``from scripts.<name> import ...`` in ``tests/``
already assumes.

Deliberately empty beyond this docstring: the modules are still run as files, and re-exporting
from here would make importing any one of them import the other forty.
"""
