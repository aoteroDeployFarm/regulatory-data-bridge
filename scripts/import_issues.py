#!/usr/bin/env python3
"""
Bulk-create GitHub issues from JSON using the REST API.

Usage:
  export GITHUB_TOKEN=ghp_xxx   # required
  python scripts/import_issues.py --file data/issues.json --repo owner/name
  # or rely on auto-detect from `git remote`:
  python scripts/import_issues.py --file data/issues.json

JSON format (data/issues.json):
{
  "issues": [
    { "title": "...", "body": "...", "labels": ["a","b"], "milestone": "Phase 1: Core Backend & AI" },
    ...
  ]
}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

import requests


API = "https://api.github.com"


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def get_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        die("GITHUB_TOKEN (or GH_TOKEN) env var is required")
    return token


def detect_repo() -> Optional[str]:
    # 1) GitHub Actions provides GITHUB_REPOSITORY=owner/name
    ga_repo = os.getenv("GITHUB_REPOSITORY")
    if ga_repo:
        return ga_repo

    # 2) Try parsing `git remote get-url origin`
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], stderr=subprocess.DEVNULL
        ).decode().strip()
        # Supports git@github.com:owner/repo.git or https://github.com/owner/repo.git
        m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)", url)
        if m:
            return f"{m.group('owner')}/{m.group('repo')}"
    except Exception:
        pass
    return None


def api_request(
    method: str,
    path: str,
    token: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    paginate: bool = False,
) -> Tuple[int, dict | list]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "issue-importer-python",
    }
    url = f"{API}{path}"

    def do(req_url: str):
        resp = requests.request(method, req_url, headers=headers, params=params, json=json_body, timeout=30)
        # Friendly rate-limit message
        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            reset = resp.headers.get("X-RateLimit-Reset")
            die(f"GitHub API rate limit exceeded. Try again after reset epoch {reset}.")
        return resp

    if not paginate:
        r = do(url)
        try:
            data = r.json()
        except Exception:
            data = {}
        return r.status_code, data

    # Paginate (Link header); collect list results
    results: List = []
    next_url = url
    while next_url:
        r = do(next_url)
        try:
            page = r.json()
        except Exception:
            page = []
        if isinstance(page, list):
            results.extend(page)
        else:
            # Unexpected payload; return as-is
            return r.status_code, page
        # Parse Link header
        link = r.headers.get("Link", "")
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        next_url = m.group(1) if m else None
        if r.status_code >= 400:
            break
    return 200, results


def get_existing_milestones(repo: str, token: str) -> Dict[str, int]:
    code, data = api_request("GET", f"/repos/{repo}/milestones?state=all&per_page=100", token, paginate=True)
    if code >= 400:
        die(f"Failed to list milestones: {data}")
    out: Dict[str, int] = {}
    for m in data:
        out[m["title"]] = int(m["number"])
    return out


def ensure_milestone(repo: str, token: str, title: str) -> int:
    title = title.strip()
    if not title:
        return 0
    existing = get_existing_milestones(repo, token)
    if title in existing:
        return existing[title]
    code, data = api_request("POST", f"/repos/{repo}/milestones", token, json_body={"title": title})
    if code >= 400:
        die(f"Failed to create milestone '{title}': {data}")
    return int(data["number"])


def get_existing_labels(repo: str, token: str) -> Set[str]:
    code, data = api_request("GET", f"/repos/{repo}/labels?per_page=100", token, paginate=True)
    if code >= 400:
        die(f"Failed to list labels: {data}")
    return {lbl["name"] for lbl in data}


def ensure_label(repo: str, token: str, name: str, color: str = "0E8A16") -> None:
    name = name.strip()
    if not name:
        return
    existing = get_existing_labels(repo, token)
    if name in existing:
        return
    code, data = api_request("POST", f"/repos/{repo}/labels", token, json_body={"name": name, "color": color})
    if code >= 400 and not (code == 422 and "already_exists" in str(data)):
        die(f"Failed to create label '{name}': {data}")


def get_existing_issue_titles(repo: str, token: str) -> Set[str]:
    # Pull first 1000 issues (all states); filter out PRs
    titles: Set[str] = set()
    code, data = api_request("GET", f"/repos/{repo}/issues?state=all&per_page=100", token, paginate=True)
    if code >= 400:
        die(f"Failed to list issues: {data}")
    for it in data:
        if "pull_request" in it:
            continue  # skip PRs
        t = it.get("title")
        if t:
            titles.add(t)
    return titles


def create_issue(repo: str, token: str, title: str, body: str, labels: List[str], milestone_num: int) -> str:
    payload = {"title": title, "body": body or ""}
    if labels:
        payload["labels"] = labels
    if milestone_num:
        payload["milestone"] = milestone_num
    code, data = api_request("POST", f"/repos/{repo}/issues", token, json_body=payload)
    if code >= 400:
        die(f"Failed to create issue '{title}': {data}")
    return data.get("html_url", "")


def main():
    ap = argparse.ArgumentParser(description="Import GitHub issues from JSON via REST API.")
    ap.add_argument("--file", "-f", default="data/issues.json", help="Path to issues JSON.")
    ap.add_argument("--repo", "-r", help="owner/name. If omitted, tries to detect from git remote.")
    ap.add_argument("--dry-run", action="store_true", help="Show actions without creating anything.")
    args = ap.parse_args()

    token = get_token()
    repo = args.repo or detect_repo()
    if not repo:
        die("Could not detect repo. Pass --repo owner/name or run inside a git repo with origin set.")

    try:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))  # type: ignore[name-defined]
    except Exception as e:
        die(f"Error reading {args.file}: {e}")

    issues = payload.get("issues", [])
    if not isinstance(issues, list) or not issues:
        die("No issues found in JSON. Expected { 'issues': [ ... ] }")

    print(f"Using repo: {repo}")
    print(f"Total issues to process: {len(issues)}")

    # Ensure milestones & labels
    # Collect unique milestones and labels
    milestones_needed = []
    labels_needed = set()
    for it in issues:
        ms = (it.get("milestone") or "").strip()
        if ms:
            milestones_needed.append(ms)
        for lbl in it.get("labels", []) or []:
            if isinstance(lbl, str) and lbl.strip():
                labels_needed.add(lbl.strip())

    milestones_needed = sorted(set(milestones_needed))
    labels_needed = sorted(labels_needed)

    if args.dry_run:
        print("\n[DRY-RUN] Would ensure milestones:", milestones_needed)
        print("[DRY-RUN] Would ensure labels:", labels_needed)
    else:
        # Create milestones
        milestone_numbers: Dict[str, int] = {}
        for ms in milestones_needed:
            num = ensure_milestone(repo, token, ms)
            milestone_numbers[ms] = num
        # Create labels
        for lbl in labels_needed:
            ensure_label(repo, token, lbl)

    # Cache existing titles to avoid duplicates
    existing_titles = get_existing_issue_titles(repo, token)

    created = 0
    skipped = 0

    for it in issues:
        title = (it.get("title") or "").strip()
        if not title:
            print("Skip: missing title")
            continue
        body = it.get("body") or ""
        labels = [l.strip() for l in (it.get("labels") or []) if isinstance(l, str) and l.strip()]
        ms_title = (it.get("milestone") or "").strip()

        if title in existing_titles:
            print(f"Skip (exists): {title}")
            skipped += 1
            continue

        milestone_num = 0
        if ms_title:
            if args.dry_run:
                milestone_num = 0  # just show the plan
            else:
                # fetch latest milestone map (cheap, but we could cache earlier)
                milestone_num = get_existing_milestones(repo, token).get(ms_title, 0)
                if not milestone_num:
                    milestone_num = ensure_milestone(repo, token, ms_title)

        if args.dry_run:
            print(f"[DRY-RUN] Would create: {title} | labels={labels} | milestone='{ms_title}'")
            created += 1
        else:
            url = create_issue(repo, token, title, body, labels, milestone_num)
            print(f"Created: {title} -> {url}")
            existing_titles.add(title)
            created += 1

    print(f"\nDone. Created: {created}, Skipped (duplicates): {skipped}")


# --- tiny helper to avoid importing pathlib at top just for one call ---
class Path:
    def __init__(self, p: str) -> None:
        self.p = p
    def read_text(self, encoding="utf-8") -> str:
        with open(self.p, "r", encoding=encoding) as f:
            return f.read()


if __name__ == "__main__":
    main()
