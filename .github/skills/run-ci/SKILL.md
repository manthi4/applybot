---
name: run-ci
description: "Trigger a GitHub Actions workflow on a specified branch for testing. Use when: you want to run CI on a branch or deploy a test branch without manual GitHub UI steps."
argument-hint: "(Required) branch. Optional: workflow filename or id, --dry-run, --no-push, --timeout=seconds, --allow-main"
---

# Run CI / Trigger Workflow Skill

Trigger a GitHub Actions workflow for a given branch using the `gh` CLI. This skill is intended for safe, auditable CI runs from the developer environment.

## Prerequisites

- `gh` CLI installed and authenticated with sufficient scopes (`repo`, `workflow`).
- Local git repository in a clean state (no unfinished merges or unresolved conflicts) when pushing.

## Inputs

- `branch` (required): branch name to run the workflow on.
- `workflow` (optional): workflow filename (e.g. `deploy.yml`) or workflow id. If omitted, the default repo workflow (or a configured default) will be used.
- `dry_run` (optional, default true): do not perform destructive actions (no push/dispatch) when true.
- `no_push` (optional): do not push the local branch to origin before triggering the workflow.
- `timeout` (optional): how long to wait for the run to complete, in seconds (default 1800 / 30m).
- `allow_main` (flag): explicit flag required to run workflows on the `main` branch.

## Procedure

1. Validate `gh` CLI availability and authentication.
2. Confirm the target branch exists locally or on remote. If missing and `no_push` is false, refuse.
3. Require explicit confirmation if the target branch is `main` unless `allow_main` is provided.
4. If `dry_run` is false and `no_push` is false, push the branch to `origin`.
5. Trigger the workflow using `gh workflow run <workflow> --ref <branch>` when available, otherwise call the Actions API via `gh api`.
6. Return the run URL and run id. Optionally poll for status until `timeout` or completion. On failure, fetch and return a trimmed log excerpt.

## Safety Rules

- **Always** require an explicit `allow_main` flag to run on `main`.
- **Never** embed secrets in the skill file. Use environment variables or the `gh` auth store.
- Default to `dry_run=true` to avoid accidental pushes or dispatches.

## Outputs

- `run_url`: URL to the workflow run on GitHub.
- `run_id`: numeric run id (if available).
- `status`: `queued`/`in_progress`/`completed` and `conclusion` when completed.
- `logs`: short excerpt if the run failed.

## Implementation

See `run_ci_helper.py` in the same directory for a `gh`-based helper script that implements the steps above.
