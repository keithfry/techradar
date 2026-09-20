# Retention Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually-triggered retention job that calls `newsradar`'s retention purge logic per topic, regenerates the RSS/index files, and commits+pushes (unless `--dry-run`).

**Prerequisite:** Tasks 1–2 (shared filename-date helper, `newsradar.retention` purge logic) live in the `news-radar` repo — execute `news-radar/docs/plans/2026-08-06-retention.md` first. The purge requirements (what gets deleted, and the 90/150-day default thresholds) are specified there, in `news-radar/docs/plans/2026-08-06-retention-design.md`. Task numbering below continues from that plan.

**Architecture:** A thin orchestrator script in the `techradar` repo (mirroring the existing `run.py`/`run-agent.sh` pair) wires config, calls the `newsradar.retention` purge functions per topic with the package's default thresholds, regenerates `podcast.rss` and `index.html`, and handles git commit/push.

**Tech Stack:** Python 3.13, bash, existing `newsradar` config/topics/podcast_rss/retention modules, existing `.github/scripts/generate-index.sh`.

## Global Constraints

- Purge thresholds are not defined here — use `DEFAULT_AUDIO_MAX_AGE_DAYS` / `DEFAULT_EPISODE_MAX_AGE_DAYS` imported from `newsradar.retention`.
- `--dry-run` still performs all file deletions/edits on disk (so `git status`/`git diff` show the real effect) — it only skips the final `git commit`/`git push`.
- Follow existing code style: type-hinted Python.

---

### Task 3: Rename `hooks/publish.py`'s `_run` to a reusable `run_git`

**Files:**
- Modify: `techradar/hooks/publish.py` (whole file — renames `_run` to `run_git`, no behavior change)

**Interfaces:**
- Produces: `run_git(repo_root: Path, args: list[str], check: bool = True, log=print) -> subprocess.CompletedProcess` — same signature as the old `_run`, just public so Task 4's `retention.py` can import it without reaching into a private name.

This repo has no test suite (confirmed: `find techradar -iname "*test*"` turns up nothing) — `run.py` and `hooks/publish.py` are both validated by manual runs today, so this task's validation step is the same: a manual smoke check, not a new pytest run.

- [ ] **Step 1: Rename every occurrence**

In `techradar/hooks/publish.py`, rename the function definition and all 5 call sites from `_run` to `run_git`. The function body is unchanged — only the name.

```python
def run_git(repo_root: Path, args: list[str], check: bool = True, log=print) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True, cwd=repo_root)
    if result.stdout.strip():
        log(f"  [git] {result.stdout.strip()}")
    if result.stderr.strip():
        log(f"  [git] {result.stderr.strip()}")
    if check and result.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(args)}\n{result.stderr}")
    return result
```

And update the 5 call sites inside `publish_hook` (the ones currently reading `_run(repo_root, [...], ...)`) to `run_git(repo_root, [...], ...)`.

- [ ] **Step 2: Verify the rename is complete**

Run: `grep -n "_run(" techradar/hooks/publish.py`
Expected: no matches (everything renamed to `run_git`)

Run: `grep -n "def run_git\|run_git(" techradar/hooks/publish.py`
Expected: 1 definition + 5 call sites, all using `run_git`

- [ ] **Step 3: Commit**

```bash
cd /Users/keithfry/projects/techradar
git add hooks/publish.py
git commit -m "Rename publish.py's _run to run_git so retention.py can reuse it"
```

---

### Task 4: `techradar/retention.py` orchestrator script

**Files:**
- Create: `techradar/retention.py`

**Interfaces:**
- Consumes:
  - `newsradar.config.load_config(path: str | Path) -> Config` (existing)
  - `newsradar.podcast_rss.generate_podcast_rss(output_dir, topic, base_url, author_name, output_dir_rel, log=print) -> Path` (existing)
  - `newsradar.retention.purge_audio(output_dir, file_prefix, max_age_days, now, log=print) -> list[Path]` (news-radar plan, Task 2)
  - `newsradar.retention.purge_episodes(output_dir, file_prefix, max_age_days, now, log=print) -> list[Path]` (news-radar plan, Task 2)
  - `newsradar.retention.DEFAULT_AUDIO_MAX_AGE_DAYS`, `DEFAULT_EPISODE_MAX_AGE_DAYS` (news-radar plan, Task 2)
  - `hooks.publish.run_git(repo_root, args, check=True, log=print) -> subprocess.CompletedProcess` (Task 3)
- Produces: a runnable script — no other file imports this one.

No automated tests for this task (matches `run.py`'s existing zero-test-coverage pattern in this repo) — validated in Task 6 by a manual dry-run against real data plus a manual full run against a scratch copy.

- [ ] **Step 1: Write the script**

Create `techradar/retention.py`:

```python
#!/usr/bin/env python3
"""Manually-run retention job: purges old AI/Robotics radar episodes.

    uv run retention.py --config config/config.toml [--dry-run]

Two tiers, thresholds defaulted by newsradar.retention (see
news-radar/docs/plans/2026-08-06-retention-design.md):
  - audio artifacts (mp3/chapters/transcript/covers) purged after 90 days
  - full episodes (html/json + any leftovers) purged after 150 days

Regenerates podcast.rss and index.html for anything touched, then commits
and pushes — unless --dry-run, which stops after regeneration so the
changes can be inspected with `git status`/`git diff` before committing
manually.
"""

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from newsradar.config import load_config
from newsradar.podcast_rss import generate_podcast_rss
from newsradar.retention import (
    DEFAULT_AUDIO_MAX_AGE_DAYS,
    DEFAULT_EPISODE_MAX_AGE_DAYS,
    purge_audio,
    purge_episodes,
)

from hooks.publish import run_git

GIT_USER_NAME = "Keith Fry"
GIT_USER_EMAIL = "keithfry@gmail.com"


def log(msg: str) -> None:
    print(msg, flush=True)


def _regenerate_index(repo_root: Path, touched_dirs: set[Path]) -> list[Path]:
    """Delete stale index.html under touched dirs (+ the repo-root techradar/ index,
    which lists the topic dirs) and rebuild via generate-index.sh. Returns rewritten index paths.
    """
    top_dir = repo_root / "techradar"
    all_dirs = set(touched_dirs) | {top_dir}

    for output_dir in all_dirs:
        index_path = output_dir / "index.html"
        if index_path.exists():
            index_path.unlink()

    rel_dirs = [str(d.relative_to(repo_root)) for d in sorted(all_dirs)]
    result = subprocess.run(
        ["bash", str(repo_root / ".github" / "scripts" / "generate-index.sh"), *rel_dirs],
        capture_output=True, text=True, cwd=repo_root,
    )
    if result.stdout.strip():
        log(f"  {result.stdout.strip()}")
    if result.returncode != 0:
        log(f"  WARNING: generate-index.sh failed: {result.stderr.strip()}")
        return []

    return [d / "index.html" for d in all_dirs if (d / "index.html").exists()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to config.toml")
    parser.add_argument("--dry-run", action="store_true", help="Skip the final git commit/push")
    args = parser.parse_args()

    config = load_config(args.config)
    repo_root = config.repo_root.parent
    now = datetime.now(timezone.utc)

    all_changed: list[Path] = []
    touched_dirs: set[Path] = set()
    summary: list[str] = []

    for topic in config.topics.values():
        output_dir = config.output_root / topic.output_dir
        log(f"── {topic.display_name} ──")

        audio_changed = purge_audio(output_dir, topic.file_prefix, DEFAULT_AUDIO_MAX_AGE_DAYS, now, log=log)
        episode_changed = purge_episodes(output_dir, topic.file_prefix, DEFAULT_EPISODE_MAX_AGE_DAYS, now, log=log)
        changed = audio_changed + episode_changed
        all_changed.extend(changed)
        if changed:
            touched_dirs.add(output_dir)

        summary.append(
            f"{topic.display_name}: {len(audio_changed)} audio file(s) purged, "
            f"{len(episode_changed)} episode file(s) purged"
        )

        rss_output_dir_rel = (
            f"{config.site.public_path_prefix}/{topic.output_dir}"
            if config.site.public_path_prefix else topic.output_dir
        )
        rss_path = generate_podcast_rss(
            output_dir=output_dir,
            topic=topic,
            base_url=config.site.base_url,
            author_name=config.site.author_name,
            output_dir_rel=rss_output_dir_rel,
            log=log,
        )
        all_changed.append(rss_path)

    if touched_dirs:
        log("Regenerating index.html...")
        all_changed.extend(_regenerate_index(repo_root, touched_dirs))

    log("")
    log("=== Retention summary ===")
    for line in summary:
        log(f"  {line}")

    if not all_changed:
        log("Nothing changed, skipping commit.")
        return

    if args.dry_run:
        log(f"--dry-run: {len(all_changed)} path(s) changed, skipping commit/push. Review with git status/diff.")
        return

    lock = repo_root / ".git" / "index.lock"
    if lock.exists():
        lock.unlink()
        log("  removed stale .git/index.lock")

    run_git(repo_root, ["git", "-C", str(repo_root), "pull", "--rebase", "--autostash"], log=log)

    for path in all_changed:
        rel = path.relative_to(repo_root)
        run_git(repo_root, ["git", "-C", str(repo_root), "add", "--", str(rel)], log=log)

    date_str = now.strftime("%Y-%m-%d")
    commit_lines = "\n".join(f"- {line}" for line in summary)
    commit_msg = f"Retention: prune old AI/Robotics radar files ({date_str})\n\n{commit_lines}"

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
    log(f"  pushed: {commit_msg.splitlines()[0]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make it executable and verify it parses**

```bash
cd /Users/keithfry/projects/techradar
chmod +x retention.py
source .venv/bin/activate
python3 -c "import ast; ast.parse(open('retention.py').read())"
python3 retention.py --help
```
Expected: `--help` prints the usage/description without error.

- [ ] **Step 3: Commit**

```bash
cd /Users/keithfry/projects/techradar
git add retention.py
git commit -m "Add retention.py orchestrator script"
```

---

### Task 5: `techradar/retention-agent.sh` wrapper

**Files:**
- Create: `techradar/retention-agent.sh`

**Interfaces:**
- Consumes: `techradar/retention.py` (Task 4) via `uv run`
- Produces: a runnable wrapper — nothing else depends on it.

- [ ] **Step 1: Write the script**

Create `techradar/retention-agent.sh`:

```bash
#!/bin/bash
# Manual wrapper for retention.py — mirrors run-agent.sh's launchd-safe
# log-filename stamping, but this one's meant to be run by hand:
#   ./retention-agent.sh              # purge + regenerate + commit + push
#   ./retention-agent.sh --dry-run    # purge + regenerate only, no commit/push
set -euo pipefail

cd /Users/keithfry/projects/techradar
mkdir -p logs

LOG_FILE="logs/techradar-retention-$(date +%Y-%m-%d).log"

exec /opt/homebrew/bin/uv run retention.py --config config/config.toml "$@" >>"$LOG_FILE" 2>&1
```

- [ ] **Step 2: Make it executable**

```bash
cd /Users/keithfry/projects/techradar
chmod +x retention-agent.sh
```

- [ ] **Step 3: Verify permissions**

Run: `ls -l retention-agent.sh`
Expected: permissions include `x` (e.g. `-rwxr-xr-x`)

- [ ] **Step 4: Commit**

```bash
cd /Users/keithfry/projects/techradar
git add retention-agent.sh
git commit -m "Add retention-agent.sh wrapper"
```

---

### Task 6: Manual acceptance run

**Files:** none created/modified — this is a verification-only task.

**Interfaces:** none — exercises Tasks 1-5 end to end against real data.

- [ ] **Step 1: Dry-run against the real repo**

```bash
cd /Users/keithfry/projects/techradar
./retention-agent.sh --dry-run
tail -60 logs/techradar-retention-$(date +%Y-%m-%d).log
```

Confirm the log shows per-topic purge counts and, if anything was old enough to purge, a "Regenerating index.html..." line — with no commit/push lines (dry-run stops before those).

- [ ] **Step 2: Inspect what actually changed on disk**

```bash
git status
git diff --stat
```

Confirm: any deleted files are audio artifacts (mp3/chapters/transcript/jpg/og.jpg) from episodes older than 90 days, or full episode files from episodes older than 150 days — nothing recent got touched. If `git diff` shows a modified `.html` file, confirm the podcast player and og:image tags are gone but the rest of the article content is intact (`git diff path/to/that.html`).

- [ ] **Step 3: Revert the dry-run's disk changes before doing a real run**

Since this was a dry run intended only to verify behavior, discard it before deciding whether to do a real run:

```bash
git checkout -- .
git clean -fd techradar/
```

- [ ] **Step 4: Decide on a real run**

If step 2's inspection looked correct, either wait for enough episodes to actually age past the thresholds, or run `./retention-agent.sh` (no `--dry-run`) when ready. This step has no fixed pass/fail — it's a judgment call by the person running the job, not part of the automated implementation.
