# Bias Choices

- **SUBCOMMANDS+SINGLE-JSON** — I leaned into a subcommand-oriented UX so each action is explicit and argparse can emit rich help. Consolidating everything into one JSON file made state saves straightforward and kept persistence easy to inspect.
- **LIST-ADAPTIVE** — Adaptive column widths with mid-ellipsis keep `gdir list` readable even when paths are long, while still showing distinguishing prefixes/suffixes. It nudged me to separate presentation concerns from the storage layer.
