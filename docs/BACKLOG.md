# Backlog

## Retire the GitHub Pages deploy (due 2026-12-01)

The live site moved to https://keithfry.net/techradar/ on 2026-11-11. `deploy_techradar.sh` rsyncs `techradar/` there after each push. `.github/workflows/deploy-pages.yml` still publishes the same files to https://keithfry.github.io/techradar/ on every push to `main`, so the old feed URLs keep working during the switch.

Starting 2026-12-01, every publish (daily run and retention) writes a warning to the run log and shows a macOS notification. `PAGES_CLEANUP_DUE` in `hooks/publish.py` sets the date.

To clean up:

1. Delete `.github/workflows/deploy-pages.yml`.
2. Turn off Pages in the GitHub repo settings (Settings > Pages).
3. Delete the `PAGES_CLEANUP_DUE` check (`_warn_pages_cleanup_due`) from `hooks/publish.py`.
4. Mark this item done.
