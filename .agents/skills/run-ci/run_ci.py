#!/usr/bin/env python3
# mypy: ignore-errors
"""Helper to trigger a GitHub Actions workflow using the `gh` CLI with safety checks.

Usage example:
  python run_ci.py --branch fix/some-change --workflow deploy.yml --dry-run

This script intentionally defaults to `--dry-run` to avoid accidental pushes.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time


def run(cmd, capture=True, check=False):
    if capture:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        p = subprocess.run(cmd, shell=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{p.stderr}")
    return p


def find_default_workflow():
    wdir = os.path.join(os.getcwd(), ".github", "workflows")
    if not os.path.isdir(wdir):
        return None
    for fn in os.listdir(wdir):
        if fn.endswith(".yml") or fn.endswith(".yaml"):
            return fn
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Trigger a GitHub Actions workflow safely via gh CLI"
    )
    parser.add_argument("--branch", required=True)
    parser.add_argument("--workflow", required=False)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--no-push", action="store_true", default=False)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--allow-main", action="store_true", default=False)
    args = parser.parse_args()

    if not shutil.which("gh"):
        print(
            "gh CLI not found in PATH. Install and `gh auth login` first.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Check auth
    auth = run("gh auth status --hostname github.com", capture=True)
    if auth.returncode != 0:
        print(
            "gh is not authenticated for github.com. Run `gh auth login`.",
            file=sys.stderr,
        )
        print(auth.stderr, file=sys.stderr)
        sys.exit(2)

    branch = args.branch
    if branch == "main" and not args.allow_main:
        print(
            "Refusing to run on `main` without --allow-main. Use --allow-main to override.",
            file=sys.stderr,
        )
        sys.exit(2)

    workflow = args.workflow or find_default_workflow()
    if not workflow:
        print(
            "No workflow specified and no workflow found in .github/workflows",
            file=sys.stderr,
        )
        sys.exit(2)

    print(
        f"Workflow: {workflow}\nBranch: {branch}\nDry run: {args.dry_run}\nNo push: {args.no_push}"
    )

    # Verify branch exists locally
    local_check = run(f"git rev-parse --verify {branch}", capture=True)
    if local_check.returncode != 0:
        # branch might be only on remote
        remote_check = run(f"git ls-remote --heads origin {branch}", capture=True)
        if remote_check.returncode != 0 or not remote_check.stdout.strip():
            print(
                f"Branch {branch} not found locally or on origin. Aborting.",
                file=sys.stderr,
            )
            sys.exit(2)

    if args.dry_run:
        print("\nDRY RUN: the following actions would be taken:")
        if not args.no_push:
            print(f" - git push origin {branch}")
        print(f" - gh workflow run {workflow} --ref {branch}")
        print(
            "\nTo perform the real run, omit --dry-run (or pass --dry-run=False when invoking via a wrapper)."
        )
        sys.exit(0)

    # Push branch unless instructed not to
    if not args.no_push:
        print(f"Pushing branch {branch} to origin...")
        p = run(f"git push origin {branch}", capture=True)
        if p.returncode != 0:
            print("git push failed:", p.stderr, file=sys.stderr)
            sys.exit(3)

    # Trigger the workflow
    print("Triggering workflow...")
    trigger = run(f'gh workflow run "{workflow}" --ref "{branch}"', capture=True)
    if trigger.returncode != 0:
        print(
            "Failed to trigger workflow via `gh workflow run`. Trying API fallback...",
            file=sys.stderr,
        )
        # Try API dispatch fallback
        owner_repo = run(
            "git config --get remote.origin.url", capture=True
        ).stdout.strip()
        # best-effort parse owner/repo from URL
        m = re.search(r"[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:.git)?$", owner_repo)
        if not m:
            print(
                "Could not determine owner/repo from git remote. Aborting.",
                file=sys.stderr,
            )
            sys.exit(4)
        owner = m.group("owner")
        repo = m.group("repo")
        api_cmd = f"gh api repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches -f ref={branch}"
        api = run(api_cmd, capture=True)
        if api.returncode != 0:
            print("API dispatch failed:", api.stderr, file=sys.stderr)
            sys.exit(5)
        print("Workflow dispatch accepted (API fallback).")
        print("No run URL available from fallback. Check repository Actions tab.")
        sys.exit(0)

    # Parse run URL from output
    out = trigger.stdout + "\n" + trigger.stderr
    m = re.search(r"https?://github\.com/.*/actions/runs/(\d+)", out)
    if not m:
        print("Triggered the workflow but could not parse run URL. Output:\n", out)
        sys.exit(0)

    run_id = m.group(1)
    run_url = re.search(r"(https?://github\.com/.*/actions/runs/\d+)", out).group(1)
    print(f"Run queued: {run_url} (id {run_id})")

    # Poll for completion
    deadline = time.time() + args.timeout
    status = None
    conclusion = None
    while time.time() < deadline:
        t = run(f"gh run view {run_id} --json status,conclusion,url", capture=True)
        if t.returncode != 0:
            print("Failed to fetch run status; will retry...")
            time.sleep(5)
            continue
        # parse simple json-like output (gh prints json)
        try:
            import json

            j = json.loads(t.stdout)
            status = j.get("status")
            conclusion = j.get("conclusion")
        except Exception:
            # best-effort parse
            if "completed" in t.stdout:
                status = "completed"
            elif "in_progress" in t.stdout:
                status = "in_progress"
            else:
                status = "queued"

        print(f"Run status: {status} (conclusion: {conclusion})")
        if status == "completed":
            break
        time.sleep(10)

    if status != "completed":
        print(f"Run did not complete within timeout ({args.timeout}s). See {run_url}")
        sys.exit(0)

    print(f"Run completed with conclusion: {conclusion}. See {run_url}")
    if conclusion != "success":
        print("Fetching logs excerpt...")
        logs = run(f"gh run view {run_id} --log", capture=True)
        excerpt = logs.stdout.strip().splitlines()[-200:]
        print("\n".join(excerpt))


if __name__ == "__main__":
    main()
