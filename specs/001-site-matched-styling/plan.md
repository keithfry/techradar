# Techradar site-matched styling implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every techradar page (daily digests, topic and month indexes, landing page) use keithfry.net's colors and font from one shared stylesheet, add a slim "Keith Fry / Tech Radar" bar, and convert the 331 archived digests once.

**Architecture:** `news-radar` gains four opt-in `[site]` settings. When they are set, the generator writes a `<link>` to a shared stylesheet in place of its inline `<style>` block and adds the bar. When they are unset, output stays byte-for-byte the same. This repo adds `techradar/radar.css`, teaches `generate-index.sh` to link it and add the same bar, adds a one-time archive rewrite script that reuses news-radar's bar function, and sets the four settings in `config/config.toml`.

**Tech stack:** Python 3.13 (stdlib plus `newsradar`), bash, plain CSS. pytest for tests. `uv` runs everything.

**Spec:** [spec.md](spec.md)

## Global constraints

- `news-radar` with no new `[site]` keys MUST produce the same bytes as before (SC-005).
- Pages link the stylesheet by relative path only, never `/techradar/radar.css` or an absolute URL (FR-009).
- Pages MUST NOT load keithfry.net's Astra or Elementor CSS (FR-009). The only keithfry.net request is the font CSS at `https://keithfry.net/wp-content/astra-local-fonts/astra-local-fonts.css`.
- Every text and background pair in `radar.css` passes WCAG AA, 4.5:1 (FR-004, FR-005).
- No horizontal scroll at 375px width (FR-007).
- Output stays static HTML. `deploy_techradar.sh` is unchanged (FR-012).
- The bar markup is identical in digests and index pages. Its exact form is in Task 2.
- Bar text: home label `Keith Fry`, home URL `https://keithfry.net/`, section label `Tech Radar`.

## Where the work happens

The daily 08:00 run imports `../news-radar` as an editable install and commits generated output to whatever branch this checkout has. So:

- Do news-radar work (Tasks 1 and 2) in a worktree at `/Users/keithfry/projects/news-radar-site-style` on branch `site-style`. Merge it to news-radar `main` when Task 2 is done. This is safe to merge any time because the new behavior is off until this repo's config opts in.
- Do techradar work (Tasks 3 to 6) in a worktree at `/Users/keithfry/projects/techradar-site-style` on branch `site-style`. A sibling folder keeps `pyproject.toml`'s `../news-radar` path pointing at the real news-radar checkout. Start these tasks after news-radar `main` has Task 2 merged, because Task 5 imports from it.
- Task 7 (rollout) runs in the main techradar checkout, outside the 07:55 to 08:30 window.

## Review focus

1. **An archived digest whose `<style>` block differs from today's.** The archive has three CSS versions (June 14, June 15 to September, October onward). The rewrite matches the block by tags, not by content. Task 5 tests a page with a short custom block.
2. **Running the archive rewrite twice.** The second run must change nothing and report the files as already converted, not as errors. Task 5 tests it.
3. **The sticky filter bar and the new site bar on a scrolled digest.** The site bar is not sticky, so it scrolls away and the filter bar keeps `top: 0`. Task 7 checks it manually.
4. **keithfry.net fonts blocked or the site down.** Pages fall back to the system sans stack and stay readable (SC-004). Task 7 checks it with DevTools request blocking.
5. **A digest title or topic label containing `&` or `<`.** `site_bar_html` escapes labels. Task 2 tests `R&D <Lab>`.

---

### Task 1: news-radar `[site]` settings

Repo: news-radar worktree.

**Files:**
- Modify: `src/newsradar/config.py` (`SiteConfig` at line 33, `load_config` at line 177)
- Modify: `examples/config.example.toml` (`[site]` table, commented-out keys only)
- Test: `tests/test_site_config.py` (new)

**Interfaces:**
- Produces: `SiteConfig.stylesheet: str = ""`, `SiteConfig.home_url: str = ""`, `SiteConfig.home_label: str = ""`, `SiteConfig.section_label: str = ""`, each read from the `[site]` key of the same name.

- [ ] **Step 1: Write the failing tests**

```python
def test_example_config_leaves_site_chrome_off():
    site = load_config(EXAMPLE_CONFIG).site
    assert (site.stylesheet, site.home_url, site.home_label, site.section_label) == ("", "", "", "")

def test_site_chrome_keys_load(tmp_path):
    # copy EXAMPLE_CONFIG's text, append to its [site] table:
    # stylesheet = "radar.css", home_url = "https://keithfry.net/",
    # home_label = "Keith Fry", section_label = "Tech Radar"
    site = load_config(cfg).site
    assert site.stylesheet == "radar.css"
    assert site.home_url == "https://keithfry.net/"
    assert site.home_label == "Keith Fry"
    assert site.section_label == "Tech Radar"
```

The example config refers to its topic files by relative path, so write the modified copy next to the original or copy `examples/topics/` into `tmp_path` as well.

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/test_site_config.py -v`
Expected: FAIL with `AttributeError: 'SiteConfig' object has no attribute 'stylesheet'`

- [ ] **Step 3: Add the four fields and load them**

Add them to `SiteConfig` with a comment saying they are opt-in and that `stylesheet` is a path relative to `output_root`. Read them in `load_config` with `site_raw.get(key, "")`. In `examples/config.example.toml`, add the four keys commented out, with a one-line note each.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest tests/test_site_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/newsradar/config.py examples/config.example.toml tests/test_site_config.py
git commit -m "Add opt-in [site] keys for a shared stylesheet and site bar"
```

---

### Task 2: news-radar digest links the stylesheet and shows the bar

Repo: news-radar worktree.

**Files:**
- Modify: `src/newsradar/html_generator.py`
- Modify: `src/newsradar/cli.py` (the `generate_html(...)` call at line 539)
- Create: `tests/test_data/digest_default.html` (golden file)
- Test: `tests/test_site_chrome.py` (new), `tests/test_retention.py` (one added test)

**Interfaces:**
- Consumes: the `SiteConfig` fields from Task 1.
- Produces:
  - `site_bar_html(home_url: str, home_label: str, crumbs: list[tuple[str, str | None]]) -> str`. Returns `""` when `home_url` is empty. Each crumb is `(label, href)`. `href=None` marks the current page. The function escapes labels.
  - `digest_page_chrome(site: SiteConfig, topic_output_dir: str, topic_label: str, date: datetime) -> tuple[str | None, str]`. Returns `(stylesheet_href, site_bar)`. Task 5 calls this.
  - `generate_html(..., stylesheet_href: str | None = None, site_bar: str = "")`

Exact bar markup, which Task 4's shell script must also produce:

```html
<nav class="site-bar" aria-label="Site">
  <a class="site-bar-home" href="https://keithfry.net/">Keith Fry</a>
  <ol class="site-bar-crumbs">
    <li><a href="../../">Tech Radar</a></li>
    <li><a href="../">AI</a></li>
    <li aria-current="page">November 12, 2026</li>
  </ol>
</nav>
```

- [ ] **Step 1: Capture the golden file on the unchanged code**

Write a `sample_digest_html(**kwargs) -> str` helper in `tests/test_site_chrome.py`. It calls `generate_html` with fixed inputs: one newsletter, two articles (one tagged `robotics`), one paper, one error, one removed item, `date=datetime(2026, 11, 12, 8, 0, tzinfo=ZoneInfo("America/New_York"))`, `topic_label="AI"`, and fixed `mp3_url`, `podcast_rss_url` and `og_image_url` strings. Then run:

```bash
uv run python -c "import sys; sys.path.insert(0, 'tests'); from test_site_chrome import sample_digest_html; open('tests/test_data/digest_default.html', 'w').write(sample_digest_html())"
```

Expected: the file exists, and `grep -c '<style>' tests/test_data/digest_default.html` prints `1`.

- [ ] **Step 2: Write the failing tests**

```python
def test_default_output_is_unchanged():  # SC-005
    assert sample_digest_html() == Path("tests/test_data/digest_default.html").read_text()

def test_stylesheet_href_replaces_inline_style():
    html = sample_digest_html(stylesheet_href="../../radar.css")
    assert '<link rel="stylesheet" href="../../radar.css">' in html
    assert "<style>" not in html

def test_site_bar_follows_body():
    bar = site_bar_html("https://keithfry.net/", "Keith Fry", [("Tech Radar", "../../"), ("AI", "../"), ("November 12, 2026", None)])
    html = sample_digest_html(site_bar=bar)
    assert html.index("<body>") < html.index('<nav class="site-bar"') < html.index('<div class="page-header">')

def test_site_bar_markup():
    # assert equality with the exact markup block in this task's Interfaces

def test_site_bar_empty_without_home_url():
    assert site_bar_html("", "Keith Fry", [("Tech Radar", "../")]) == ""

def test_site_bar_escapes_labels():
    bar = site_bar_html("https://keithfry.net/", "Keith Fry", [("R&D <Lab>", None)])
    assert "R&amp;D &lt;Lab&gt;" in bar

def test_digest_page_chrome_for_top_level_topic():
    site = SiteConfig(stylesheet="radar.css", home_url="https://keithfry.net/", home_label="Keith Fry", section_label="Tech Radar")
    href, bar = digest_page_chrome(site, "AI", "AI", datetime(2026, 11, 12))
    assert href == "../../radar.css"
    assert '<li><a href="../../">Tech Radar</a></li>' in bar
    assert '<li aria-current="page">November 12, 2026</li>' in bar

def test_digest_page_chrome_for_nested_topic():
    href, bar = digest_page_chrome(site, "news/ai", "AI", datetime(2026, 11, 12))
    assert href == "../../../radar.css"
    assert '<li><a href="../../../">Tech Radar</a></li>' in bar

def test_digest_page_chrome_off_by_default():
    assert digest_page_chrome(SiteConfig(), "AI", "AI", datetime(2026, 11, 12)) == (None, "")

def test_section_label_falls_back_to_site_title():
    site = SiteConfig(title="My Radar", home_url="https://example.com/", home_label="Home")
    _, bar = digest_page_chrome(site, "AI", "AI", datetime(2026, 11, 12))
    assert '<li><a href="../../">My Radar</a></li>' in bar
```

In `tests/test_retention.py`, add a test for FR-014. It runs `purge_episodes(root / "AI", "ai-radar", 30, now)` on a tree that has an old episode plus `root / "radar.css"`, and asserts that `radar.css` still exists.

- [ ] **Step 3: Run them and confirm the new ones fail**

Run: `uv run pytest tests/test_site_chrome.py tests/test_retention.py -v`
Expected: `test_default_output_is_unchanged` and the retention test PASS. The rest FAIL with `ImportError` for `site_bar_html`.

- [ ] **Step 4: Implement**

In `html_generator.py`:
- Add `site_bar_html` and `digest_page_chrome`. In `digest_page_chrome`, `up = "../" * (len(PurePosixPath(topic_output_dir).parts) + 1)`. The crumbs are `(site.section_label or site.title, up)`, `(topic_label, "../")`, and `(date.strftime("%B %-d, %Y"), None)`.
- In `generate_html`, write `<link rel="stylesheet" href="{stylesheet_href}">` in place of `<style>\n{_CSS}\n</style>` when `stylesheet_href` is set. Insert `site_bar` plus a newline right after `<body>\n` when it is non-empty. With both at their defaults, the output must not change by a single byte.

In `cli.py`, compute `stylesheet_href, site_bar = digest_page_chrome(config.site, topic.output_dir, topic.display_name, as_of)` inside `_gen_html` and pass both to `generate_html`.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS, including the existing tests. Tests that need Ollama skip as before.

- [ ] **Step 6: Commit, then merge to news-radar main**

```bash
git add src/newsradar/html_generator.py src/newsradar/cli.py tests/test_site_chrome.py tests/test_data/digest_default.html tests/test_retention.py
git commit -m "Link a shared stylesheet and add a site bar when [site] opts in"
```

Merge `site-style` into news-radar `main`. Because of `test_default_output_is_unchanged`, this is safe before the 08:00 run.

---

### Task 3: `techradar/radar.css`

Repo: techradar worktree.

**Files:**
- Create: `techradar/radar.css`
- Create: `tests/conftest.py` (adds the repo root to `sys.path`), `tests/test_radar_css.py`

**Interfaces:**
- Produces: the stylesheet that Tasks 2, 4 and 5 link. It styles every class in news-radar's `_CSS` (in `html_generator.py`), plus `.site-bar`, `.site-bar-home`, `.site-bar-crumbs`, `.index-title`, `.digest-list`, `.topic-list`, `.podcast-bar` and `.copy-btn`.

Tokens. Define them on `:root` with exactly these names and values:

| Token | Value | Token | Value |
|---|---|---|---|
| `--kf-bg` | `#0f172a` | `--kf-link` | `#748ffc` |
| `--kf-surface` | `#162032` | `--kf-link-hover` | `#a5b4fc` |
| `--kf-surface-2` | `#1e293b` | `--kf-accent` | `#4361ee` |
| `--kf-footer` | `#080b14` | `--kf-on-accent` | `#ffffff` |
| `--kf-border` | `#334155` | `--kf-danger` | `#f87171` |
| `--kf-heading` | `#f1f5f9` | `--kf-arxiv` | `#a78bfa` |
| `--kf-text` | `#cbd5e1` | `--kf-robotics` | `#34d399` |
| `--kf-muted` | `#94a3b8` | `--kf-font` | `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` |

Tag pills, as `--tag-<key>-bg` and `--tag-<key>-fg`:

| Key | bg | fg | Key | bg | fg |
|---|---|---|---|---|---|
| policy | `#3f1d24` | `#fca5a5` | voice | `#3d2614` | `#fdba74` |
| model | `#1e2a5a` | `#93c5fd` | health | `#123840` | `#67e8f9` |
| agents | `#163a2a` | `#86efac` | research | `#263244` | `#cbd5e1` |
| safety | `#3a3015` | `#fde047` | ethics | `#3d1a33` | `#f9a8d4` |
| robotics | `#2e2350` | `#c4b5fd` | | | |

How to port `_CSS`: keep its layout rules, and swap colors as follows.

| Old value | New value |
|---|---|
| Body background `#f4f6f9`, body text `#1a1d23` | `--kf-bg`, `--kf-text` |
| White card, removed-items and filter-bar backgrounds | `--kf-surface` for cards and removed items, `--kf-surface-2` for the filter bar |
| Borders `#e8edf3`, `#e2e8f0` | `--kf-border` |
| Headings `#0f172a` | `--kf-heading` |
| Card paragraph `#475569` | `--kf-text` |
| Meta and subsection text `#64748b`, `#94a3b8` | `--kf-muted` |
| Links and "via" `#3b82f6`, `#2563eb`, `#60a5fa` | `--kf-link`, hover `--kf-link-hover` |
| `.card.arxiv`, `.card.robotics` accents | `--kf-arxiv`, `--kf-robotics` |
| Problem-feeds pink box | `--kf-surface` background, `--kf-danger` border and heading |
| Footer | `--kf-footer` background, `--kf-muted` text |
| Header gradient | `--kf-bg` to `--kf-surface-2`, with a `--kf-border` bottom border |
| Active filter chip | border `--kf-accent` |

Start the file with `@import url("https://keithfry.net/wp-content/astra-local-fonts/astra-local-fonts.css");` and set `font-family: var(--kf-font)` on `body`. The site bar is `--kf-surface-2` with a bottom border. It is not sticky. Separate the crumbs with `li + li::before { content: "/"; }`. `.copy-btn` uses `--kf-accent` with `--kf-on-accent` text. Long URLs in `.problem-feeds` and `.removed-items` get `overflow-wrap: anywhere`.

- [ ] **Step 1: Write the failing contrast test**

`tests/test_radar_css.py` parses `--name: #hex;` pairs from `techradar/radar.css`. It computes the WCAG relative-luminance contrast ratio and asserts `>= 4.5` for each pair:

```python
PAIRS = [
    ("--kf-text", "--kf-bg"), ("--kf-text", "--kf-surface"), ("--kf-muted", "--kf-bg"),
    ("--kf-muted", "--kf-surface"), ("--kf-muted", "--kf-surface-2"), ("--kf-muted", "--kf-footer"),
    ("--kf-heading", "--kf-surface"), ("--kf-link", "--kf-bg"), ("--kf-link", "--kf-surface"),
    ("--kf-link", "--kf-surface-2"), ("--kf-link-hover", "--kf-surface"), ("--kf-on-accent", "--kf-accent"),
    ("--kf-danger", "--kf-surface"), ("--kf-arxiv", "--kf-surface"), ("--kf-robotics", "--kf-surface"),
] + [(f"--tag-{k}-fg", f"--tag-{k}-bg") for k in
     ("policy", "model", "agents", "safety", "robotics", "voice", "health", "research", "ethics")]
```

Add `test_no_root_relative_or_wordpress_urls`. It asserts the file contains no `url(/`, no `astra/assets`, and no `elementor`.

Add `test_styles_every_generator_class`. It imports `_CSS` from `newsradar.html_generator`, collects each `.class-name` token with a regex, and asserts every one appears in `radar.css`.

- [ ] **Step 2: Run it and confirm it fails**

Run: `uv run --with pytest pytest tests/test_radar_css.py -v`
Expected: FAIL with `FileNotFoundError` for `techradar/radar.css`.

- [ ] **Step 3: Write `techradar/radar.css`** using the token tables and porting rules above.

- [ ] **Step 4: Run it and confirm it passes**

Run: `uv run --with pytest pytest tests/test_radar_css.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

`radar.css` is hand-written, so it belongs in a manual commit even though it lives in `techradar/`.

```bash
git add techradar/radar.css tests/conftest.py tests/test_radar_css.py
git commit -m "Add radar.css with keithfry.net colors and font"
```

---

### Task 4: Index pages link the stylesheet and show the bar

Repo: techradar worktree.

**Files:**
- Modify: `.github/scripts/generate-index.sh`
- Test: `tests/test_generate_index.py` (new)

**Interfaces:**
- Consumes: the bar markup from Task 2 and the class names from Task 3.
- Produces: `_radar_prefix DIR`, a shell function that prints `""`, `"../"` or `"../../"` for `techradar`, `techradar/AI` or `techradar/AI/2026-11`, with or without a leading `./`, and returns 1 for a directory outside `techradar`.

Behavior for directories under `techradar/`:
- Write `<!DOCTYPE html>`, `<html lang="en">`, a viewport meta tag, and `<link rel="stylesheet" href="${prefix}radar.css">` in the head. Keep the cache meta tags and the reload script.
- Put the bar right after `<body>`, using the Task 2 markup and the constants `HOME_URL="https://keithfry.net/"`, `HOME_LABEL="Keith Fry"` and `SECTION_LABEL="Tech Radar"` at the top of the script. Crumbs:
  - landing page: `Tech Radar` (current)
  - topic index: `Tech Radar` linking to `../`, then `AI` (current)
  - month index: `Tech Radar` linking to `../../`, then `AI` linking to `../`, then `November 2026` (current)
- Wrap the content in `<main class="container">`, use `<h1 class="index-title">` for the page title, `<ul class="digest-list">` for month groups, and `<ul class="topic-list">` for the landing page's undated entries.
- `_dir_title` returns `Tech Radar` for `techradar` and `./techradar`.
- Undated entries get no `<h2>Other</h2>` heading and are sorted by name, A to Z (FR-011).
- Drop the inline `<style>` from the podcast bar. `radar.css` now styles `.podcast-bar` and `.copy-btn`.

Leave directories outside `techradar/` as they are today.

- [ ] **Step 1: Write the failing tests**

Each test builds a tree in `tmp_path`: `techradar/AI/2026-11/ai-radar-2026-11-12.html`, `ai-radar-2026-11-12.mp3`, `techradar/AI/podcast.rss`, and `techradar/Research/` and `techradar/Robotics/` with one digest each. It then runs `bash <repo>/.github/scripts/generate-index.sh techradar` with `cwd=tmp_path`.

```python
def test_landing_page_links_stylesheet_and_lists_topics():
    html = (root / "techradar/index.html").read_text()
    assert '<link rel="stylesheet" href="radar.css">' in html
    assert "<h2>Other</h2>" not in html
    assert html.index('href="./AI"') < html.index('href="./Research"') < html.index('href="./Robotics"')
    assert '<li aria-current="page">Tech Radar</li>' in html

def test_topic_index_bar_and_stylesheet():
    html = (root / "techradar/AI/index.html").read_text()
    assert '<link rel="stylesheet" href="../radar.css">' in html
    assert '<a class="site-bar-home" href="https://keithfry.net/">Keith Fry</a>' in html
    assert '<li><a href="../">Tech Radar</a></li>' in html
    assert '<li aria-current="page">AI</li>' in html

def test_month_index_crumbs():
    html = (root / "techradar/AI/2026-11/index.html").read_text()
    assert '<link rel="stylesheet" href="../../radar.css">' in html
    assert '<li aria-current="page">November 2026</li>' in html

def test_topic_index_keeps_podcast_and_listen_link():
    html = (root / "techradar/AI/index.html").read_text()
    assert 'class="copy-btn"' in html and "<style>" not in html
    assert 'href="./2026-11/ai-radar-2026-11-12.mp3"' in html

def test_viewport_and_doctype():
    html = (root / "techradar/AI/index.html").read_text()
    assert html.startswith("<!DOCTYPE html>")
    assert 'name="viewport"' in html
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run --with pytest pytest tests/test_generate_index.py -v`
Expected: FAIL. The first assertion about `radar.css` fails.

- [ ] **Step 3: Update `generate-index.sh`** as described above.

- [ ] **Step 4: Run them and confirm they pass**

Run: `uv run --with pytest pytest tests/test_generate_index.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/generate-index.sh tests/test_generate_index.py
git commit -m "Style index pages with radar.css and add the site bar"
```

---

### Task 5: Archive rewrite script and config opt-in

Repo: techradar worktree.

**Files:**
- Create: `scripts/restyle_archive.py`
- Modify: `config/config.toml` (`[site]` table)
- Test: `tests/test_restyle_archive.py` (new)

**Interfaces:**
- Consumes: `digest_page_chrome` from Task 2, the `SiteConfig` fields from Task 1, and `newsradar.config.load_config`.
- Produces:
  - `restyle_digest(html: str, stylesheet_href: str, site_bar: str) -> str`. It replaces the single `<style>...</style>` block (matched by tags, `re.DOTALL`) with `<link rel="stylesheet" href="...">`, and inserts `site_bar` plus a newline after `<body>\n`. It raises `AlreadyRestyled` (a `ValueError` subclass) when the page has no `<style>` block and already contains `class="site-bar"`. It raises `ValueError` when there is not exactly one `<style>` block or no `<body>` tag.
  - `restyle_tree(config: Config, dry_run: bool = False, log=print) -> tuple[list[Path], list[tuple[Path, str]]]`. It walks `config.output_root / topic.output_dir / "YYYY-MM" / "<file_prefix>-YYYY-MM-DD.html"` for each `topic` in `config.topics.values()`, takes the date from the filename, and calls `digest_page_chrome(config.site, topic.output_dir, topic.display_name, date)`. Tests build `cfg` with `dataclasses.replace(load_config(Path("config/config.toml")), output_root=tmp_path)`. It returns `(changed, skipped)`, where `skipped` holds `(path, reason)` pairs. It does not write files when `dry_run` is true.
  - CLI: `uv run scripts/restyle_archive.py --config config/config.toml [--dry-run]`. It prints `changed: N, already restyled: N, skipped: N`, then each skipped path with its reason. It exits with 1 if anything was skipped for a reason other than "already restyled".

Add these lines to `config/config.toml` under `[site]`:

```toml
stylesheet = "radar.css"
home_url = "https://keithfry.net/"
home_label = "Keith Fry"
section_label = "Tech Radar"
```

- [ ] **Step 1: Write the failing tests**

```python
def test_replaces_style_and_adds_bar():
    out = restyle_digest(SAMPLE, "../../radar.css", BAR)
    assert "<style>" not in out
    assert '<link rel="stylesheet" href="../../radar.css">' in out
    assert out.index("<body>") < out.index(BAR) < out.index('<div class="page-header">')

def test_handles_short_old_style_block():   # review focus 1
    old = SAMPLE.replace(FULL_STYLE_BLOCK, "<style>\n  body { color: red; }\n</style>")
    assert "<style>" not in restyle_digest(old, "../../radar.css", BAR)

def test_leaves_content_untouched():   # FR-010
    out = restyle_digest(SAMPLE, "../../radar.css", BAR)
    for fragment in ('<meta property="og:image"', '<audio controls', 'data-tags="model"', 'id="removed-items"'):
        assert fragment in out

def test_second_run_raises_already_restyled():   # review focus 2
    once = restyle_digest(SAMPLE, "../../radar.css", BAR)
    with pytest.raises(AlreadyRestyled):
        restyle_digest(once, "../../radar.css", BAR)

def test_two_style_blocks_rejected():
    with pytest.raises(ValueError):
        restyle_digest(SAMPLE.replace("</head>", "<style></style></head>"), "../../radar.css", BAR)

def test_restyle_tree_counts_and_dates(tmp_path):
    # config with output_root=tmp_path, one AI topic; two digests plus one already restyled
    changed, skipped = restyle_tree(cfg)
    assert len(changed) == 2
    assert [r for _, r in skipped] == ["already restyled"]
    assert '<li aria-current="page">November 12, 2026</li>' in changed_page_text

def test_dry_run_writes_nothing(tmp_path):
    before = page.read_text()
    restyle_tree(cfg, dry_run=True)
    assert page.read_text() == before

def test_repo_config_opts_in():
    site = load_config(Path("config/config.toml")).site
    assert (site.stylesheet, site.home_url, site.home_label, site.section_label) == (
        "radar.css", "https://keithfry.net/", "Keith Fry", "Tech Radar")
```

`SAMPLE` comes from `newsradar.html_generator.generate_html` called with fixed inputs. `FULL_STYLE_BLOCK` is the `<style>…</style>` substring cut from `SAMPLE`.

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run --with pytest pytest tests/test_restyle_archive.py -v`
Expected: FAIL with `ModuleNotFoundError: scripts.restyle_archive`

- [ ] **Step 3: Write `scripts/restyle_archive.py` and add the config keys.** `load_config` requires no environment variables, so the script needs no secrets.

- [ ] **Step 4: Run them and confirm they pass**

Run: `uv run --with pytest pytest tests/ -v`
Expected: all techradar tests PASS.

- [ ] **Step 5: Check the real archive without writing**

Run: `uv run scripts/restyle_archive.py --config config/config.toml --dry-run`
Expected: `already restyled: 0, skipped: 0`, and `changed` equal to the output of `ls techradar/*/*/*-radar-*.html | wc -l` (331 on 2026-11-12).

- [ ] **Step 6: Commit**

```bash
git add scripts/restyle_archive.py tests/test_restyle_archive.py config/config.toml
git commit -m "Add one-time archive restyle script and opt in to the site styling"
```

---

### Task 6: Pre-merge review

Run the whole-branch review across both repos' `site-style` branches against the spec, before rollout. Fix findings on the branches.

- [ ] **Step 1:** In news-radar, `uv run pytest -v`. Expected: all PASS.
- [ ] **Step 2:** In techradar, `uv run --with pytest pytest tests/ -v`. Expected: all PASS.

---

### Task 7: Rollout

Runs in `/Users/keithfry/projects/techradar` on `main`. Steps 6 and 7 publish, so get Keith's go-ahead before each.

The 08:00 job's publish hook pushes local `main` and rsyncs the working tree of `techradar/` to keithfry.net. So once Step 1 lands, the next run would publish the merge and any uncommitted restyled files without the Step 6 and 7 go-ahead. Do Steps 1 to 7 in one sitting, or pause the job first and resume it after Step 7:

```bash
launchctl unload ~/Library/LaunchAgents/com.keithfry.ai-techradar-agent.plist
```

```bash
launchctl load ~/Library/LaunchAgents/com.keithfry.ai-techradar-agent.plist
```

- [ ] **Step 0: Merge news-radar first.** Merge news-radar `site-style` into news-radar `main`. This is safe at any time because `test_default_output_is_unchanged` pins the default output. If techradar merged first, new digests would stay light with no bar while the indexes turned dark, and `restyle_archive.py` would fail with ImportError.

- [ ] **Step 1: Merge** techradar `site-style` into `main`. Delete the untracked `specs/001-site-matched-styling/` copy in the main checkout first, or git refuses the merge. Confirm news-radar `main` has Task 2 by checking that `grep -n "def digest_page_chrome" ../news-radar/src/newsradar/html_generator.py` prints a line.

- [ ] **Step 2: Rebuild every index.** The script skips any index newer than its siblings, so delete them first:

```bash
find techradar -name index.html -delete && bash .github/scripts/generate-index.sh techradar
```

Expected: `grep -L 'radar.css' $(find techradar -name index.html)` prints nothing.

- [ ] **Step 3: Restyle the archive**

```bash
uv run scripts/restyle_archive.py --config config/config.toml
```

Expected: `skipped: 0`, and `grep -l '<style>' techradar/*/*/*-radar-*.html` prints nothing (SC-007).

- [ ] **Step 4: Check the pages locally** with `python3 -m http.server 8000 -d techradar` in the browser pane. Check:
  - the landing page, `/AI/`, `/AI/2026-11/`, today's AI, Research and Robotics digests, and the oldest digest in each topic (`/AI/2026-06/ai-radar-2026-06-14.html` uses the oldest CSS)
  - that tag filtering, the Removed pill, the audio player, Subscribe, Copy URL and the listen links all work (SC-003)
  - the same pages at 375px width, with no horizontal scroll (FR-007)
  - a digest scrolled down, where the filter bar stays visible and the site bar does not cover it (review focus 3)
  - computed `background-color`, `color` and `font-family` on `body`, compared with keithfry.net (SC-001)
  - `keithfry.net` blocked in DevTools, where the text should be readable in the fallback font (SC-004)
  - one color variable changed in `radar.css`, which should change on an archived digest after a reload. Revert the change afterward (SC-008).

- [ ] **Step 5: Commit the regenerated output on its own.** This is the one manual commit of generated `techradar/` files, as FR-010 approves. Keep it separate from code commits.

```bash
git add techradar/
git commit -m "Restyle archived radar pages to match keithfry.net"
```

- [ ] **Step 6 (needs Keith's go-ahead): Push**, `git push`. This also updates the GitHub Pages copy.

- [ ] **Step 7 (needs Keith's go-ahead): Deploy**, `./deploy_techradar.sh`. Then load `https://keithfry.net/techradar/` and one digest, and confirm `radar.css` returns 200.

- [ ] **Step 8: The next morning,** check `logs/techradar-agent-<date>.log` and the new AI, Research and Robotics digests. They should link `../../radar.css` and show the bar, with no manual steps (SC-006).
