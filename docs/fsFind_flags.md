# fsFind output controls and gitignore stacking

This change introduces default inclusion of **both files and directories** and two opt-out switches:

- `--no-files` / `-nf` — suppress file output (filters still evaluate)
- `--no-dirs`  / `-nd` — suppress directory output (filters still evaluate)

### Examples

```bash
# Directories only (but file filters still decide which dirs count)
fsFind.py . --no-files --file-pattern '*.py'

# Files only under directories matching a pattern
fsFind.py . --no-dirs --dir-pattern src
```

### Gitignore stacking
`.gitignore` rules are evaluated from the repo root down to the current directory.
Child rules override parent rules; negations (e.g., `!keep.log`) un-ignore specific paths.

### Notes
- Help text updated for clarity and parity with behavior.
- Tests cover defaults and cross-type filtering behavior.
