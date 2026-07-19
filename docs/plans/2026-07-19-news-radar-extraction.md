# Extract techradar-agent into standalone OSS project `news-radar`

## Context

`scripts/techradar-agent/` in `web-pages` is a mature RSS+Gmail digest pipeline
(fetch → classify/summarize/dedupe via local Ollama → HTML digest + podcast
audio + cover art → publish), but it's tightly coupled to this user/repo:
hardcoded git identity, author name burned into cover art and podcast RSS,
Gmail credential path outside the repo, output dirs/feeds-CSV path/topic list
baked into Python, and `publisher.py` does `git pull/add/commit/push` directly
against this repo plus shells out to `.github/scripts/generate-index.sh`. The
goal is to pull this into a new public repo (`news-radar`, local path
`/Users/keithfry/projects/news-radar`) that anyone can install and run against
their own topics/feeds/credentials, while `web-pages` becomes a thin consumer
of it as an installed dependency.

Survey of current hardcodes (from exploration): `config.py:9` (Gmail env path
`~/keys/kfopenclaw-gmail.env`), `config.py:45-46` (`GIT_USER_NAME`/`GIT_USER_EMAIL`),
`cover_generator.py:140,155` (author text on cover images), `podcast_rss.py:16,129`
(`BASE_URL_ROOT`, `itunes:author`), `main.py` (AI/Robotics topics + keyword
lists hardcoded in argparse/classifier), `publisher.py:49-90` (direct git
publish), `main.py:653-658` (hard call to `generate-index.sh`), the LaunchAgent
plist and `skills/techradar-agent/SKILL.md` (absolute `/Users/keithfry` paths).
Credentials handling is otherwise already sound: `.env`/`token.json`/
`credentials.json` are gitignored and not tracked, Ollama is local-only (no
remote endpoint), no API keys are hardcoded anywhere.

## Decisions locked in during brainstorming

- Target: public OSS repo at `/Users/keithfry/projects/news-radar`.
- Integration: `web-pages` consumes it as an installed package dependency (uv/pip, git URL), no pipeline code stays in `web-pages`.
- Publishing: pluggable — core package only writes files; git commit/push becomes an optional `publish_hook` callable supplied by the consumer.
- Topics: fully config-driven (TOML), no hardcoded AI/Robotics in code — ships as example config only.
- Ad-detector tooling: ported into the package as a core feature, plus a new install step to load the Modelfile into the user's local Ollama.
- Scheduling (LaunchAgent/cron): shipped as templates/docs in `examples/`, not core code.

## New repo layout: `news-radar`

```
src/newsradar/
  cli.py            — argparse entry: --config, --topic, --date, --time, --hours,
                       --dry-run, --no-email, --no-podcast, --refresh-token, etc.
                       (mirrors today's main.py flags, ported from scripts/techradar-agent/main.py)
  config.py         — loads TOML config + .env; zero hardcoded paths/identity/topics
  topics.py         — Topic model: name, classification keywords, feeds-CSV category
                       value, output dir, site metadata overrides
  feed_fetcher.py    — ported from feed_fetcher.py
  email_fetcher.py   — ported from email_fetcher.py; Gmail OAuth stays env/config
                       driven, default token path moves to XDG config dir
                       (e.g. ~/.config/newsradar/token.json) instead of ~/keys/*
  article_fetcher.py — ported from article_fetcher.py
  enricher.py, llm.py — ported from enricher.py/llm.py; all model names
                        (SUMMARIZE_MODEL/RANK_MODEL/DEDUP_MODEL/AD_DETECTOR_MODEL)
                        stay env-overridable as today, just no hardcoded default
                        tied to this project's needs beyond sane defaults
  ad_detector/       — ported compare_models.py, update_modelfile.py,
                        AdDetectorModelfile, AD_DETECTION.md; add
                        `newsradar ad-detector install` command that runs
                        `ollama create` against the packaged Modelfile
  html_generator.py  — ported; site title/base_url/author pulled from config,
                        not hardcoded
  cover_generator.py — ported; author/branding text pulled from config
                        (replace hardcoded "Keith Fry" at cover_generator.py:140,155)
  podcast_generator.py, podcast_rss.py — ported; BASE_URL_ROOT and
                        itunes:author pulled from config (replace hardcodes at
                        podcast_rss.py:16,129)
  output_writer.py   — replaces publisher.py; writes HTML/JSON/MP3/RSS to the
                        configured output dir, then calls an optional
                        `publish_hook(paths, config)` callable if the consumer
                        configured one. No git awareness in core.
examples/
  config.example.toml   — two example topics (ai, robotics) mirroring today's setup
  feeds.example.csv
  launchd/com.example.newsradar.plist.template
  cron/newsradar-cron.example
  hooks/git_publish.py  — reference publish_hook implementation (git pull/add/
                          commit/push), for consumers who want the old behavior
tests/               — ported test_*.py (test_ad_detector, test_classifier,
                        test_enricher, test_podcast_generator, test_podcast_llm,
                        test_podcast_rss), de-hardcoded to use example config
docs/SETUP.md         — credentials/security guide for adopters: Gmail OAuth
                         setup, Ollama install, optional Anthropic API key for
                         DEDUP_MODEL, Kokoro TTS model download
README.md, LICENSE (MIT), .env.example, pyproject.toml, .gitignore
  (mirror web-pages' current .gitignore entries: credentials.json, token.json,
  .env, .venv/, uv.lock)
```

## web-pages side changes (after news-radar exists)

- `scripts/techradar-agent/` shrinks to: `pyproject.toml` depending on
  `news-radar` (git URL or local path during dev), `config/topics.toml`
  (today's AI/Robotics keyword lists + `data/ai-rss-feeds.csv` Category
  mapping), `hooks/publish.py` (today's `publisher.py` git logic + the
  `generate-index.sh` call, now living here as *this repo's* publish hook,
  not package code).
- `scripts/com.keithfry.ai-techradar-agent.plist` stays a real, concrete
  LaunchAgent pointing at the new thin `uv run newsradar` invocation.
- `skills/techradar-agent/SKILL.md` updated to reflect the new CLI invocation
  and config file location.
- `CLAUDE.md` pipeline description updated to describe the package + hook
  split instead of the monolithic pipeline.
- Gmail credential env path (`~/keys/kfopenclaw-gmail.env`) stays this user's
  concern, configured via `web-pages`' own `.env`/config — not baked into the
  package.

## Verification

1. In `news-radar`: `uv run pytest` passes standalone, no reference to any
   `web-pages` path.
2. `uv run newsradar run --config examples/config.example.toml --topic ai --dry-run`
   succeeds with zero `web-pages` checkout present (Ollama must be running
   locally).
3. Pre-push grep of the new repo for `keithfry`, `Keith`, `kfopenclaw`,
   absolute `/Users/` paths — zero hits outside example/template files that
   intentionally use placeholders.
4. Confirm `news-radar`'s `.gitignore` excludes `token.json`/`.env`/
   `credentials.json`, matching `web-pages`' current `.gitignore:5-9`.
5. From `web-pages`: run the new thin wrapper in `--dry-run` against the real
   `config/topics.toml`, diff output against the last real digest
   (`techradar/AI/ai-radar-2026-07-19.html`) for regressions, then do one real
   run to confirm the `publish.py` hook reproduces today's git-commit/
   generate-index behavior end to end.

## Status (as of 2026-07-19, mid-execution)

### Done
- `news-radar` built, tested (33 passed/1 skipped), pushed public at
  https://github.com/keithfry/news-radar. No hardcoded identity (grep-clean).
- `web-pages/scripts/techradar-agent/` got the thin-consumer treatment as
  planned (`pyproject.toml` dep, `config/topics.toml`, `hooks/publish.py`,
  `run.py`) and was verified end-to-end against real feeds/Gmail/Ollama —
  **but this location is now superseded** (see next point) and its own
  `techradar/` publish target is stale/frozen.
- **Architecture changed beyond the original plan**: rather than `web-pages`
  staying the consumer, the runtime consumer moved out to its own repo,
  `~/projects/techradar/` (public, https://github.com/keithfry/techradar),
  which now ALSO hosts the published digest site itself at
  `keithfry.github.io/techradar` (its own `techradar/` subdir + GitHub Actions
  `deploy-pages.yml`), replacing `web-pages/techradar` as the live site.
  `techradar/hooks/publish.py` commits/pushes to the `techradar` repo, not
  `web-pages`, and `config/topics.toml`'s `base_url` points at the new site.
- Fixed a real bug surfaced during this pivot: `news-radar`'s URL construction
  assumed `output_root` was always the published docroot. Added
  `site.public_path_prefix` to `news-radar` config to handle cases where it
  isn't (e.g. the now-stale `web-pages` config, where `output_root` is a
  `techradar/` subdirectory of the site root) — committed/pushed to
  `news-radar`.
- `~/projects/techradar/` committed; small config commit pushed successfully.
  The large second commit (1.5GB, 865 files — `techradar/` seeded from
  `web-pages/techradar`'s existing content) is **still pushing** as of this
  status update (first attempt hit a broken-pipe error partway through;
  retrying now with larger `http.postBuffer`).

### Remaining
1. **Confirm the large push to `keithfry/techradar` lands** (in progress).
2. Enable GitHub Pages on the `techradar` repo (`build_type=workflow`) and
   confirm `deploy-pages.yml` runs successfully and `keithfry.github.io/techradar`
   actually serves content.
3. Repoint the LaunchAgent from `scripts/com.keithfry.ai-techradar-agent.plist`
   (still active, still runs the OLD `web-pages/scripts/techradar-agent/`
   config, still publishes into the now-stale `web-pages/techradar/`) to
   `~/projects/techradar/com.keithfry.ai-techradar-agent.plist` — requires
   `launchctl unload`/`load`, a live system change not yet done.
4. Once the new site is confirmed working: remove `web-pages/techradar/`
   (old published content, breaks old URLs unless redirected — explicitly
   deferred, not forgotten) and remove `web-pages/scripts/techradar-agent/`
   entirely (old dead pipeline files + the now-superseded thin-consumer copy).
   Also remove the old plist.
5. Port `--podcast-only`/`--transcript-only` shortcuts into `news-radar`'s
   `cli.py` (not done — old `main.py` had them, new `cli.py` doesn't yet).
6. Full detail tracked in `web-pages/docs/BACKLOG.md`.
