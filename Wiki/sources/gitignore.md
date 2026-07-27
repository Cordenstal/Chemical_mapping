# Git Ignore Rules

- Canonical source path: `.gitignore`
- Source type: repository config
- Why it matters: keeps the virtual environment and Python caches out of version control.
- Key points:
  - `.venv/` is ignored.
  - Python bytecode caches are ignored.
  - Common test and lint caches are ignored.
- Update triggers:
  - New generated directories.
  - New tooling that creates local cache or build artifacts.
- Last reviewed date: 2026-06-17
