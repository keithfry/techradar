#!/usr/bin/env python3
"""Manually-run retention job: purges old radar episodes for every configured topic (AI, Robotics).

    uv run retention.py --config config/config.toml [--dry-run]

Two tiers, thresholds defaulted by newsradar.retention (see
news-radar/docs/plans/2026-08-06-retention-design.md):
  - audio artifacts (mp3/chapters/transcript/covers) purged after 90 days
  - full episodes (html/json + any leftovers) purged after 150 days

Regenerates podcast.rss and index.html for anything touched, then commits
and pushes.

--dry-run skips ONLY the commit/push. Files are still deleted and edited on
disk, so the real effect can be reviewed with `git status`/`git diff` and
then either committed or reverted.
"""

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path

from newsradar.config import load_config
from newsradar.podcast_rss import generate_podcast_rss
from newsradar.retention import (
    DEFAULT_AUDIO_MAX_AGE_DAYS,
    DEFAULT_EPISODE_MAX_AGE_DAYS,
    purge_audio,
    purge_episodes,
)

from hooks.publish import GIT_USER_EMAIL, GIT_USER_NAME, run_git

_YM_DIR_RE = re.compile(r"^\d{4}-\d{2}$")


def log(msg: str) -> None:
    print(msg, flush=True)


def _remove_index_only_month_dirs(output_dir: Path) -> None:
    """Remove YYYY-MM dirs whose only remaining file is our generated index.html.

    newsradar's purge_episodes only removes a month dir once it's truly empty;
    generate-index.sh leaves an index.html in each one, so finish the job here.
    """
    for month_dir in sorted(output_dir.iterdir()):
        if not month_dir.is_dir() or not _YM_DIR_RE.match(month_dir.name):
            continue
        if [f.name for f in month_dir.iterdir()] == ["index.html"]:
            (month_dir / "index.html").unlink()
            month_dir.rmdir()
            log(f"    removed empty dir: {month_dir}")


def _regenerate_index(repo_root: Path, touched_dirs: set[Path]) -> None:
    """Rebuild every index.html under the touched topic dirs via generate-index.sh.

    The script skips an index unless some sibling file is newer than it, which a
    deletion never produces — so delete the stale indexes first to force a rebuild.
    """
    for output_dir in touched_dirs:
        for index_path in output_dir.rglob("index.html"):
            index_path.unlink()

    rel_dirs = [str(d.relative_to(repo_root)) for d in sorted(touched_dirs)]
    result = subprocess.run(
        ["bash", str(repo_root / ".github" / "scripts" / "generate-index.sh"), *rel_dirs],
        capture_output=True, text=True, cwd=repo_root,
    )
    if result.stdout.strip():
        log(f"  {result.stdout.strip()}")
    if result.returncode != 0:
        log(f"  WARNING: generate-index.sh failed: {result.stderr.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", required=True, help="Path to config.toml")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip the final git commit/push (files ARE still changed on disk)",
    )
    parser.add_argument(
        "--audio-days", type=int, default=DEFAULT_AUDIO_MAX_AGE_DAYS,
        help=f"Purge audio artifacts older than this many days (default: {DEFAULT_AUDIO_MAX_AGE_DAYS})",
    )
    parser.add_argument(
        "--episode-days", type=int, default=DEFAULT_EPISODE_MAX_AGE_DAYS,
        help=f"Purge whole episodes older than this many days (default: {DEFAULT_EPISODE_MAX_AGE_DAYS})",
    )
    args = parser.parse_args()
    if args.episode_days < args.audio_days:
        parser.error("--episode-days must be >= --audio-days")

    config = load_config(args.config)
    # Resolved: output_root comes through as config/../techradar, and both the
    # index script's title lookup and our repo-relative paths need the clean form.
    repo_root = config.repo_root.parent.resolve()  # config/ -> repo root (output_root's parent)
    # Local time, not UTC — episode filename dates are local, and a UTC "today"
    # would purge a day early every evening.
    now = datetime.now()

    log(f"=== Retention run {now:%Y-%m-%d %H:%M}{' (DRY RUN — no commit/push)' if args.dry_run else ''} ===")
    log(f"  audio artifacts older than {args.audio_days} days, episodes older than {args.episode_days} days")

    touched_dirs: set[Path] = set()
    summary: list[str] = []

    for topic in config.topics.values():
        output_dir = (config.output_root / topic.output_dir).resolve()
        log(f"── {topic.display_name} ──")

        audio_changed = purge_audio(output_dir, topic.file_prefix, args.audio_days, now, log=log)
        episode_changed = purge_episodes(output_dir, topic.file_prefix, args.episode_days, now, log=log)
        summary.append(
            f"{topic.display_name}: {len(audio_changed)} audio-tier path(s) changed, "
            f"{len(episode_changed)} episode-tier file(s) deleted"
        )
        if not audio_changed and not episode_changed:
            log("    nothing to purge")
            continue

        touched_dirs.add(output_dir)
        _remove_index_only_month_dirs(output_dir)

        # Only for touched topics: the feed carries a lastBuildDate, so
        # regenerating an untouched one would produce a no-op commit every run.
        generate_podcast_rss(
            output_dir=output_dir,
            topic=topic,
            base_url=config.site.base_url,
            author_name=config.site.author_name,
            output_dir_rel=(
                f"{config.site.public_path_prefix}/{topic.output_dir}"
                if config.site.public_path_prefix else topic.output_dir
            ),
            log=log,
        )

    if touched_dirs:
        log("Regenerating index.html...")
        _regenerate_index(repo_root, touched_dirs)

    log("")
    log("=== Retention summary ===")
    for line in summary:
        log(f"  {line}")

    if not touched_dirs:
        log("Nothing changed, skipping commit.")
        return

    rel_dirs = [str(d.relative_to(repo_root)) for d in sorted(touched_dirs)]

    if args.dry_run:
        log("--dry-run: skipping commit/push. Changes are on disk — review with:")
        log("    git status --short | head; git diff --stat")
        log("  then either rerun without --dry-run to publish, or revert with:")
        log(f"    git checkout -- {' '.join(rel_dirs)} && git clean -fd {' '.join(rel_dirs)}")
        return

    lock = repo_root / ".git" / "index.lock"
    if lock.exists():
        lock.unlink()
        log("  removed stale .git/index.lock")

    run_git(repo_root, ["git", "-C", str(repo_root), "pull", "--rebase", "--autostash"], log=log)
    run_git(repo_root, ["git", "-C", str(repo_root), "add", "-A", "--", *rel_dirs], log=log)

    commit_lines = "\n".join(f"- {line}" for line in summary)
    commit_msg = f"Retention: prune old radar files ({now:%Y-%m-%d})\n\n{commit_lines}"

    staged = run_git(
        repo_root, ["git", "-C", str(repo_root), "diff", "--cached", "--quiet"], check=False, log=log
    )
    if staged.returncode == 0:
        log("  nothing to commit, skipping push")
        return

    # -q: a first run deletes 1000+ files; don't echo every "delete mode" line.
    run_git(
        repo_root,
        [
            "git", "-C", str(repo_root),
            "-c", f"user.name={GIT_USER_NAME}",
            "-c", f"user.email={GIT_USER_EMAIL}",
            "commit", "-q", "-m", commit_msg,
        ],
        log=log,
    )

    run_git(repo_root, ["git", "-C", str(repo_root), "push"], log=log)
    log(f"  pushed: {commit_msg.splitlines()[0]}")


if __name__ == "__main__":
    main()
