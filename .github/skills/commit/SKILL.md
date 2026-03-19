---
name: commit
description: "Commit staged files to git. Use when: making a git commit, committing changes, finalizing work. Handles pre-commit hook failures by fixing issues and retrying. Does NOT stage additional files. Expects files to already be staged and a commit message provided."
argument-hint: "The commit message to use, e.g. 'fix: resolve null pointer in user auth'"
---

# Git Commit with Pre-commit Fix Loop

Commit currently staged files. If pre-commit hooks fail, fix the issues and retry — without staging any new files.

## Prerequisites

- Files to commit must already be staged (`git add`) before invoking this skill.
- A commit message must be provided as the argument.

## Procedure

1. **Verify staged files exist.**
   Run `git diff --cached --name-only` to confirm there are staged changes. If nothing is staged, report that and stop.

2. **Record the staged file list.**
   Save the output of `git diff --cached --name-only` — this is the fixed set of files for the commit. No other files should be staged at any point.

3. **Attempt the commit.**
   Run `git commit -m "<message>"` with the provided commit message.

4. **If the commit succeeds**, report success and stop.

5. **If pre-commit hooks fail**, follow the fix loop below.

## Pre-commit Fix Loop (max 3 iterations)

When a commit fails due to pre-commit hooks:

1. **Read the hook output carefully.** Identify which hook failed and which files were modified or flagged.

2. **Check for auto-fixed files.** Some hooks (black, ruff, trailing-whitespace, end-of-file-fixer) modify files in place. Run `git diff --name-only` to see what was changed.

3. **Re-stage ONLY files from the original staged set.** Run `git add` only for files that appear in BOTH the original staged file list AND the auto-modified files. NEVER stage files outside the original set.

4. **Fix lint/type errors manually if needed.** If a hook reports errors that require code changes (ruff lint errors without --fix, mypy type errors), edit the files to resolve them, then re-stage only those files (which must be in the original staged set).

5. **Retry the commit** with the same message.

6. **If it fails again**, repeat from step 1. After 3 failed attempts, stop and report the remaining errors to the user.

## Critical Rules

- **NEVER run `git add .` or `git add` on files not in the original staged set.** Only re-stage files that were part of the initial `git diff --cached --name-only` output.
- **NEVER use `--no-verify`** to bypass pre-commit hooks.
- **NEVER amend or modify commit history.**
- **Do not change the commit message** unless the user explicitly asks.
