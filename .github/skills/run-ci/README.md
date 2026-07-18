# run-ci skill

This directory contains a Copilot Chat skill manifest (`SKILL.md`) and a helper script (`run_ci_helper.py`) to trigger GitHub Actions workflows for a branch using the `gh` CLI.

Quick usage (dry-run by default):

```bash
python .github/skills/run-ci/run_ci_helper.py --branch fix/some-change --workflow docker.yml --dry-run
```

To actually push and run:

```bash
python .github/skills/run-ci/run_ci_helper.py --branch fix/some-change --workflow docker.yml
```

Notes:

- The script defaults to `--dry-run` to avoid accidental pushes. Remove `--dry-run` to execute.
- Running on `main` requires `--allow-main` to prevent accidental destructive runs.
- The script depends on the `gh` CLI being installed and authenticated.

Repository Workflows
--------------------

This repository defines two primary GitHub Actions workflows located in `.github/workflows/`:

- `docker.yml` — Builds, tags, and pushes a Docker image to Artifact Registry and deploys to Cloud Run.
	- Triggers: `workflow_dispatch` (manual) and `push` to `main`.
	- Job guard: the `build-and-push` job runs only when triggered manually or when a commit message contains `--docker`.
	- Use when: you want to publish a new docker image and optionally deploy it to Cloud Run. Good for release commits or manual test deploys.
	- Required secrets/vars: `GCP_SA_KEY`, `GCP_PROJECT_ID`, optional `vars.GCP_REGION`.
	- How to run manually (example):

		```bash
		# dry-run using the helper
		python .github/skills/run-ci/run_ci_helper.py --branch fix/some-change --workflow docker.yml --dry-run

		# real run (push + dispatch):
		python .github/skills/run-ci/run_ci_helper.py --branch fix/some-change --workflow docker.yml

		# or use gh directly to dispatch:
		gh workflow run docker.yml --ref fix/some-change
		```

- `terraform.yml` — Runs `terraform plan` (and optionally `apply`) against `infra/`.
	- Triggers: `workflow_dispatch` with inputs (`action` choice: `plan` or `apply`, and `image_tag`), and `push` to `main`.
	- Job guard: the job runs on manual dispatch, or when a commit message contains `--tf-apply`. The `Apply` step runs only when `action == 'apply'` or the commit message contains `--tf-apply`.
	- Use when: you need to run Terraform plan or apply from CI; prefer `plan` for review and use `apply` only when you intentionally want to mutate infra.
	- Required secrets/vars: `GCP_SA_KEY`, `GCP_PROJECT_ID`, `TF_VAR_SERPAPI_KEY`, `TF_VAR_DASHBOARD_TOTP_SECRET`, optional `vars.GCP_REGION`.
	- How to run manually (example):

		```bash
		# Plan only (via workflow dispatch):
		gh workflow run terraform.yml --ref fix/some-change --field action=plan

		# Apply (requires caution):
		gh workflow run terraform.yml --ref fix/some-change --field action=apply

		# Or use the helper script (dry-run by default):
		python .github/skills/run-ci/run_ci_helper.py --branch fix/some-change --workflow terraform.yml --dry-run
		```

Safety notes
------------

- Both workflows run automatically on `push` to `main`. Use `--docker` or `--tf-apply` in commit messages to trigger the respective jobs from a non-manual push if the job condition is checking commit messages.
- Prefer manual `workflow_dispatch` for destructive operations (deploys, terraform apply). The helper script defaults to dry-run and requires `--allow-main` to operate on `main`.
- Ensure the required secrets are present in repository settings before dispatching workflows.
