# Python Byte-Compile Check – Design Note

## Inventory of integration points
- **Scripts directory (`scripts/`)** – Existing developer CLIs are thin wrappers over modules in `src/`. Tools typically live alongside reusable libraries and expose a `main()` that can run via `python -m ...`.
- **`dev_utils` package** – Hosts shared developer helpers (`lib_logging`, `lib_argparse_registry`, etc.) that other modules import for cross-cutting concerns.
- **`pytest` test suite** – Primary automation in the repo; no tox/nox configuration found.
- **Makefile / pre-commit / CI** – No Makefile, `.pre-commit-config.yaml`, tox/nox, or GitHub Actions workflows are present in the repository.

## Options considered
1. **New utility module in `dev_utils` with CLI entry via `python -m dev_utils.compile_check`**
   - *Pros*: Reuses the existing argparse registry and logging conventions, keeps functionality importable without side effects, no new top-level script required.
   - *Cons*: Requires users to know the module path instead of a short alias in `scripts/`.
2. **Standalone script under `scripts/` invoking a helper in `src/utils`**
   - *Pros*: Matches the executable helpers listed in `scripts/README.md` and gives a short command name.
   - *Cons*: Introduces another top-level entry point and duplicates argument parsing unless we thread it through `dev_utils` helpers; less convenient for other Python code to import directly.

## Chosen approach
Adopt **Option 1**: implement a reusable library function inside `dev_utils` (e.g., `dev_utils.compile_check.run`) and expose a CLI through the same module so it is runnable via `python -m dev_utils.compile_check`. This keeps the checker colocated with other developer utilities, shares the argument registry/logging style, and avoids introducing a new standalone script while remaining easy to import from other tools.
