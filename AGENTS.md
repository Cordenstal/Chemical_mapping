# AGENTS.md

You are my assistant for creating games and work projects.

## Wiki Policy

- Maintain the root-level wiki in this repository.
- Keep wiki content clean, organized, and linted.
- Update the wiki after any repository change.
- Preserve append-only history in `Wiki/log.md`.
- Keep `Wiki/index.md` synchronized with wiki pages.
- Prefer one canonical page per file, script, or major document.

## Change Control

- Non-wiki changes require a clear plan before editing.
- Wiki-only updates may be made without separate approval.
- When changing files outside `Wiki/`, keep the scope minimal and explicit.
- Record any new source, document, or script page in the wiki in the same task.

## Repo Hygiene

- Keep the repository organized and lint-friendly.
- Avoid orphan files and stale wiki references.
- Add new folders only when they serve a concrete repo purpose.

## Debugging Standards

- Any script or automation added to this repo must include clear progress logging.
- Scripts should expose enough status to identify a hung or slow step.
- Prefer deterministic setup steps and concise, actionable diagnostics.

## Baseline Repo Guidance

- This repository is intended to serve as a baseline template.
- Keep setup files small, readable, and easy to extend.
- Document major repo structure decisions in the wiki.
