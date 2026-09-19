Biases: SUBCOMMANDS+SINGLE-JSON and ENV-MIN.

Why: Subcommands keep the mental model close to git-like tools, and a single JSON file made it easy to snapshot both mappings and history together. Choosing ENV-MIN kept env output predictable for shell wrappers.

Impact: The parser leans on argparse subcommands, resulting in clear help text but slightly more boilerplate. Persisting everything into one JSON simplified truncating history after `back`, though it means larger writes. Minimal env exports made tests and wrapper expectations tight—only PREV/NEXT exports are emitted.
