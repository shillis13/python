# Bias Choices

- **Bias 1 – Subcommand CLI & single JSON file**: Chosen to keep the UX explicit and centralize persistence. This led to a straightforward argparse setup and all state (entries, history, cursor) living together.
- **Bias 3 – Minimal env export**: Limited the `env` output to only `PREV` and `NEXT`, keeping integration simple and avoiding extra shell noise.
