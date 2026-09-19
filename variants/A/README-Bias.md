- SUBCOMMANDS+SINGLE-JSON: I wanted a compact persistence story, so one file
  captures entries and history together. It simplified saving and load logic
  and made the CLI feel familiar via named verbs.
- LIST-FIXED: Fixed columns kept the listing deterministic and easy to scan in
  smoke tests. The trade-off is aggressive truncation for very long paths, but
  the predictable layout felt worth it here.
