"""GitHub PR creation for approved remediation patches.

This is the only place ExecutionNode is allowed to touch the real
repository: it creates a branch and opens a pull request. It never merges
and never pushes to the base branch — Sentinel's own approval gate
authorizes *proposing* the change, and GitHub's PR review remains the
second, independent checkpoint before anything reaches the base branch.

Falls back to a local `.sentinel/patches/` artifact (see app/agents/triage.py)
when GITHUB_TOKEN / TRIAGE_GITHUB_REPO aren't configured, so the feature
works out of the box on a fresh clone without secrets.

Uses raw httpx against the GitHub REST API rather than a GitHub SDK,
matching the rest of Sentinel's dependency-light style.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

import httpx
from unidiff import PatchSet  # type: ignore[attr-defined]

from app.config import settings

if TYPE_CHECKING:
    from app.agents.prompts import FileChange

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def github_configured() -> bool:
    return bool(settings.github_token and settings.triage_github_repo)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _apply_unified_diff(original: str, diff_text: str) -> str:
    """Apply a single-file unified diff to `original`.

    unidiff parses the diff into a hunk model (it doesn't ship a patcher);
    this walks that model to rebuild the file content, which keeps us out
    of hand-parsing the fragile `@@ -a,b +c,d @@` text format ourselves.
    """
    patch = PatchSet(diff_text)
    if not patch:
        return original
    patched_file = patch[0]
    orig_lines = original.splitlines(keepends=True)
    result: list[str] = []
    cursor = 0
    for hunk in patched_file:
        src_start = max(hunk.source_start - 1, 0)
        result.extend(orig_lines[cursor:src_start])
        cursor = src_start
        for line in hunk:
            text = line.value if line.value.endswith("\n") else line.value + "\n"
            if line.is_context:
                result.append(text)
                cursor += 1
            elif line.is_removed:
                cursor += 1
            elif line.is_added:
                result.append(text)
    result.extend(orig_lines[cursor:])
    return "".join(result)


def open_remediation_pr(
    *, execution_id: str, summary: str, patch_kind: str, files: list[FileChange]
) -> str:
    """Create a branch, commit each file's patched content, and open a PR.

    Returns the PR URL. Raises on any GitHub API failure — the caller marks
    the execution failed rather than reporting a partial success as done.
    """
    repo = settings.triage_github_repo
    base_branch = settings.triage_github_base_branch
    branch_name = f"sentinel-triage/{execution_id}"

    with httpx.Client(timeout=30.0) as client:
        ref_resp = client.get(
            f"{GITHUB_API}/repos/{repo}/git/ref/heads/{base_branch}", headers=_headers()
        )
        ref_resp.raise_for_status()
        base_sha = ref_resp.json()["object"]["sha"]

        client.post(
            f"{GITHUB_API}/repos/{repo}/git/refs",
            headers=_headers(),
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        ).raise_for_status()

        skipped: list[str] = []
        for file in files:
            get_resp = client.get(
                f"{GITHUB_API}/repos/{repo}/contents/{file.path}",
                headers=_headers(),
                params={"ref": branch_name},
            )
            existing_sha: str | None = None
            original = ""
            if get_resp.status_code == 200:
                body = get_resp.json()
                existing_sha = body["sha"]
                original = base64.b64decode(body["content"]).decode("utf-8", errors="ignore")
            elif get_resp.status_code != 404:
                get_resp.raise_for_status()

            try:
                new_content = _apply_unified_diff(original, file.diff)
            except Exception as exc:
                logger.warning("Failed to apply diff for %s: %s", file.path, exc)
                skipped.append(file.path)
                continue

            put_body: dict[str, object] = {
                "message": f"Sentinel triage: {summary[:200]}",
                "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
                "branch": branch_name,
            }
            if existing_sha:
                put_body["sha"] = existing_sha
            client.put(
                f"{GITHUB_API}/repos/{repo}/contents/{file.path}",
                headers=_headers(),
                json=put_body,
            ).raise_for_status()

        pr_body = summary
        if skipped:
            pr_body += "\n\n**Skipped (diff failed to apply, needs manual review):** " + ", ".join(
                skipped
            )
        pr_resp = client.post(
            f"{GITHUB_API}/repos/{repo}/pulls",
            headers=_headers(),
            json={
                "title": f"Sentinel triage: {summary[:120]}",
                "head": branch_name,
                "base": base_branch,
                "body": pr_body,
            },
        )
        pr_resp.raise_for_status()
        return str(pr_resp.json()["html_url"])
