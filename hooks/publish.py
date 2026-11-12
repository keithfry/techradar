"""Publish hook: regenerate this repo's AI/Robotics index.html files,
git pull/add/commit/push to GitHub (history), then run deploy_techradar.sh to
rsync techradar/ to https://keithfry.net/techradar/ (the live site).
"""

from __future__ import annotations

import re
import subprocess
from datetime import date, datetime
from pathlib import Path

from newsradar.config import Config

GIT_USER_NAME = "Keith Fry"
GIT_USER_EMAIL = "keithfry@gmail.com"


def run_git(repo_root: Path, args: list[str], check: bool = True, log=print) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True, cwd=repo_root)
    if result.stdout.strip():
        log(f"  [git] {result.stdout.strip()}")
    if result.stderr.strip():
        log(f"  [git] {result.stderr.strip()}")
    if check and result.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(args)}\n{result.stderr}")
    return result


_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _commit_message(paths: list[Path]) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_dirs: list[str] = []
    for p in paths:
        m = _DATE_RE.search(p.stem)
        if m:
            date_str = m.group(1)
        parts = p.parts
        if len(parts) >= 3:
            topic_dir = parts[-3]
            if topic_dir not in topic_dirs:
                topic_dirs.append(topic_dir)
    if topic_dirs:
        label = " + ".join(t.capitalize() for t in topic_dirs)
        return f"Add {label} radar for {date_str}"
    return f"Add radar update {date_str}"


# Backlog reminder (docs/BACKLOG.md): GitHub Pages still deploys on push during
# the move to keithfry.net. Delete this check when the workflow is removed.
PAGES_CLEANUP_DUE = date(2026, 12, 1)


def _warn_pages_cleanup_due(log=print) -> None:
    if date.today() < PAGES_CLEANUP_DUE:
        return
    msg = "Remove the GitHub Pages deploy workflow (see docs/BACKLOG.md)"
    log(f"  REMINDER: {msg}")
    subprocess.run(
        ["osascript", "-e", f'display notification "{msg}" with title "Techradar backlog"'],
        capture_output=True,
    )


def deploy_site(repo_root: Path, log=print) -> None:
    """Mirror techradar/ to keithfry.net via deploy_techradar.sh (rsync over ssh)."""
    _warn_pages_cleanup_due(log=log)
    log("  Deploying to keithfry.net...")
    result = subprocess.run(
        ["bash", str(repo_root / "deploy_techradar.sh")], capture_output=True, text=True, cwd=repo_root
    )
    if result.stdout.strip():
        log(f"  [deploy] {result.stdout.strip()}")
    if result.stderr.strip():
        log(f"  [deploy] {result.stderr.strip()}")
    if result.returncode != 0:
        raise RuntimeError(f"deploy_techradar.sh failed (exit {result.returncode}):\n{result.stderr}")
    log("  deployed")


def publish_hook(paths: list[Path], config: Config, log=print) -> None:
    if not paths:
        log("  no paths to publish, skipping")
        return

    repo_root = config.repo_root.parent  # config/ -> repo root (output_root's parent)

    log("  Regenerating techradar index...")
    index_script = repo_root / ".github" / "scripts" / "generate-index.sh"
    result = subprocess.run(
        ["bash", str(index_script), "techradar"], capture_output=True, text=True, cwd=repo_root
    )
    if result.stdout.strip():
        log(f"  {result.stdout.strip()}")
    if result.returncode != 0:
        log(f"  WARNING: generate-index.sh failed: {result.stderr.strip()}")
    else:
        for idx_path in (repo_root / "techradar").rglob("index.html"):
            paths.append(idx_path)
        log("  index regenerated")

    commit_msg = _commit_message(paths)

    lock = repo_root / ".git" / "index.lock"
    if lock.exists():
        lock.unlink()
        log("  removed stale .git/index.lock")

    run_git(repo_root, ["git", "-C", str(repo_root), "pull", "--rebase", "--autostash"], log=log)

    for path in paths:
        rel = path.relative_to(repo_root)
        run_git(repo_root, ["git", "-C", str(repo_root), "add", str(rel)], log=log)

    result = run_git(
        repo_root,
        [
            "git", "-C", str(repo_root),
            "-c", f"user.name={GIT_USER_NAME}",
            "-c", f"user.email={GIT_USER_EMAIL}",
            "commit", "-m", commit_msg,
        ],
        check=False,
        log=log,
    )
    if result.returncode != 0:
        if "nothing to commit" in result.stdout + result.stderr:
            log("  nothing to commit, skipping push")
            return
        raise RuntimeError(f"git commit failed:\n{result.stderr}")

    run_git(repo_root, ["git", "-C", str(repo_root), "push"], log=log)
    log(f"  pushed: {commit_msg}")

    deploy_site(repo_root, log=log)
