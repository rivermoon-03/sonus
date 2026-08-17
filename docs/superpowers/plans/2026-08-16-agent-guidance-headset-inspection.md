# Agent Guidance and Headset Inspection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Codex and Claude repository guidance synchronized, update it to the current Sonus implementation, and safely inspect the connected WH-1000XM6.

**Architecture:** `CLAUDE.md` remains the single source of truth and `AGENTS.md` is a relative symbolic link to it. Documentation reflects the current CLI and safety boundary without duplicating detailed protocol tables. Headset inspection uses only BlueZ metadata and Sonus read-only commands.

**Tech Stack:** Markdown, POSIX symbolic links, Git, BlueZ `bluetoothctl`, Python 3.11+, Sonus CLI, pytest

## Global Constraints

- Keep `AGENTS.md` as a relative symbolic link to `CLAUDE.md`.
- Do not run `set`, raw `send`, long-running `sniff`, or power/reset/pairing/firmware operations during inspection.
- Preserve the existing package layering and protocol safety rules.
- Treat only DSEE as a verified writable setting.

---

### Task 1: Shared Agent Guidance

- Create the relative `AGENTS.md -> CLAUDE.md` symbolic link.
- Update `CLAUDE.md` with current implementation, CLI, test, observation, and hardware safety guidance.
- Verify the link, command list, and Markdown whitespace.

### Task 2: Regression Verification

- Run `uv run pytest -q` and confirm the default suite passes with hardware tests excluded.
- Review the exact worktree diff.

### Task 3: Connected XM6 Read-Only Inspection

- Read BlueZ metadata with `bluetoothctl info 58:18:62:1F:C9:CB`.
- Run Sonus `status`, `settings`, and `discover` with `--channel 9 --json`.
- Summarize current values, retrievable data, failures, and safe future implementation candidates.
- Do not run mutating or experimental commands.

### Task 4: Commit the Guidance Change

- Stage only `AGENTS.md`, `CLAUDE.md`, and this plan.
- Check the staged diff and commit as `docs: refresh shared agent guidance`.
