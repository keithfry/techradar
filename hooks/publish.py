"""Publish hook: regenerate this repo's AI/Robotics index.html files, then
git pull/add/commit/push — this repo IS the published GitHub Pages site
(output_root == repo_root/techradar, the Pages docroot).
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from newsradar.config import Config

GIT_USER_NAME = "Keith Fry"
GIT_USER_EMAIL = "keithfry@gmail.com"


def _run(repo_root: Path, args: list[str], check: bool = True, log=print) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True, cwd=repo_root)
    if result.stdout.strip():
        log(f"  [git] {result.stdout.strip()}")
    if result.stderr.strip():
        log(f"  [git] {result.stderr.strip()}")
    if check and result.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(args)}\n{result.stderr}")
    return result


def _commit_message(paths: list[Path]) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_dirs: list[str] = []
    for p in paths:
        parts = p.parts
        if len(parts) >= 3:
            topic_dir = parts[-3]
            if topic_dir not in topic_dirs:
                topic_dirs.append(topic_dir)
    if topic_dirs:
        label = " + ".join(t.capitalize() for t in topic_dirs)
        return f"Add {label} radar for {date_str}"
    return f"Add radar update {date_str}"


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

    _run(repo_root, ["git", "-C", str(repo_root), "pull", "--rebase", "--autostash"], log=log)

    for path in paths:
        rel = path.relative_to(repo_root)
        _run(repo_root, ["git", "-C", str(repo_root), "add", str(rel)], log=log)

    result = _run(
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

    _run(repo_root, ["git", "-C", str(repo_root), "push"], log=log)
    log(f"  pushed: {commit_msg}")
