# Backlog

## Done: retire the GitHub Pages deploy (2026-11-12)

The live site moved to https://keithfry.net/techradar/ on 2026-11-11. On 2026-11-12 the Pages workflow (`.github/workflows/deploy-pages.yml`) and the `PAGES_CLEANUP_DUE` reminder in `hooks/publish.py` were removed. `deploy_techradar.sh` is now the only deploy.
