# Python Byte-Compile Check – Design Note

## Inventory of Existing Integration Points
- **Command-line tooling:** numerous standalone CLIs under `scripts/` symlinked to modules in `src/` (e.g., `fileBackup`, `ff`, `pyZip`).
- **Developer libraries:** reusable helpers in `src/dev_utils/` (logging, argparse registry, dry-run support) imported across scripts.
- **Testing:** `pytest` configured via `pytest.ini` with `src/` on `PYTHONPATH`; no tox/nox environments.
- **Automation:** no Makefile, pre-commit configuration, or CI workflows are present in the repository today.

## Options Considered
1. **Add `dev_utils.compile_check` with an argparse-powered CLI and expose it via the existing `scripts/` symlink pattern.**
   - *Pros:* Matches current layout for utilities, shares logging helpers, gives other modules an importable function; easy to document and discover.
   - *Cons:* Introduces another script entry in `scripts/`, requiring a small amount of plumbing.
2. **Embed the byte-compile step as a pytest helper/fixture invoked via a custom test command.**
   - *Pros:* Reuses the established `pytest` workflow without new scripts; CI could run `pytest` to cover compilation.
   - *Cons:* Harder for other tools to call directly, increases test startup time, and conflates static compilation checks with test execution.

## Chosen Approach
Proceed with **Option 1**. A dedicated module inside `src/dev_utils/` keeps the compile logic importable while the CLI wrapper follows the repo’s existing `scripts/` convention. This separates concerns cleanly (libraries vs. tests), keeps byte-compilation fast and discoverable, and allows future integrations (e.g., CI or Makefile) to call the shared entry point.
