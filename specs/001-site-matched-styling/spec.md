# Feature specification: Techradar pages match keithfry.net styling

**Feature branch**: none yet (see "Branching note" under Assumptions)
**Created**: 2026-11-12
**Status**: Clarified, ready for planning
**Input**: "I want to have the techradar generated pages have a similar style to my web pages on keithfry.net, possibly by re-using the same style sheet."

## Background

keithfry.net is a WordPress site on the Astra theme with Elementor page layouts. Its main navigation already has a "Tech Radar" item that links to `/techradar/`. Clicking it today drops the visitor onto a page that looks unrelated to the rest of the site.

The site's look, read from the live homepage on 2026-11-12:

| Element | keithfry.net value |
|---|---|
| Page background | `#0f172a` (Astra global color 5), footer `#080b14` (global color 8) |
| Raised surfaces | `#162032` and `#1e293b` (global colors 6 and 7) |
| Body text | `#cbd5e1` (global color 3), headings and site title `#f1f5f9` (global color 2) |
| Muted text | `#94a3b8` (global color 4) |
| Links and accent | `#4361ee` (global color 0), hover `#748ffc` (global color 1) |
| Typeface | Inter, served from `keithfry.net/wp-content/astra-local-fonts/`, 17px body, line height 1.7 |
| Content width | About 1100 to 1200px |
| Top navigation | Home, Resume, Services, Build (Open Source, Maker), Blog, Tech Radar |

The techradar output has three kinds of pages, built by two different programs:

1. **Daily digest pages** (for example `techradar/AI/2026-11/ai-radar-2026-11-12.html`). The `news-radar` package (`../news-radar/src/newsradar/html_generator.py`) writes these with its own inline stylesheet: a light gray body, a dark navy gradient header, white cards, and colored tag pills.
2. **Topic index pages** (`techradar/AI/index.html`, `techradar/Robotics/index.html`, `techradar/Research/index.html`). This repo's `.github/scripts/generate-index.sh` writes these as unstyled HTML with browser-default fonts, plus a small orange podcast bar.
3. **The landing page** (`techradar/index.html`). The same script writes it. It lists the three topics under a heading that reads "Other".

## Clarifications

### Session 2026-11-12

- Q: Should techradar pages carry keithfry.net's header and footer, or only match its colors and font? → A: A slim bar. "Keith Fry" links to keithfry.net, followed by a "Tech Radar" breadcrumb. No copy of the WordPress menu or footer.
- Q: Where should the techradar pages get their styling? → A: One shared techradar stylesheet that holds the site's colors and font as named variables. It is published under `/techradar/` and every page links to it. Pages do not load the WordPress theme CSS.
- Q: Should the already-published digest pages get the new look too? → A: Yes. A one-time rewrite converts every existing digest to the new styling.

## User scenarios and testing *(mandatory)*

### User story 1: Daily digest reads as part of keithfry.net (priority: P1)

A visitor on keithfry.net clicks "Tech Radar", picks a topic, and opens today's digest. The digest uses the site's dark background, Inter type, text colors, and blue link color, so the visitor can tell they are still on Keith's site.

**Why this priority**: Digest pages are where visitors spend their time and are the pages that get shared (they carry Open Graph previews). They are also the furthest from the site's look today, since they use a light theme.

**Independent test**: Generate one digest for a fixed date and open it next to keithfry.net. Compare background, body text, heading text, link color, and font family.

**Acceptance scenarios**:

1. **Given** a newly generated AI digest, **When** a visitor opens it, **Then** the page background, text colors, link color, and typeface match the values in the background table.
2. **Given** a digest with tagged cards, **When** a visitor clicks a tag filter chip, **Then** filtering works as it does today and each tag stays visually distinct from the others on the dark background.
3. **Given** a digest with a podcast episode, **When** a visitor views the header, **Then** the audio player and the Subscribe link are visible and usable on the dark background.
4. **Given** a digest with feed errors and removed items, **When** a visitor expands "Removed Items", **Then** the problem-feeds and removed-items blocks are readable and use the site's colors rather than the current pink and white boxes.

---

### User story 2: Topic index pages match the site (priority: P2)

A visitor lands on `/techradar/AI/` and sees the archive of past digests, grouped by month, styled like the rest of keithfry.net instead of as a bare browser-default list.

**Why this priority**: The index is the first techradar page a visitor sees after clicking the nav link. It is a small amount of markup, so restyling it costs little.

**Independent test**: Run `generate-index.sh` against `techradar/` and open each topic index.

**Acceptance scenarios**:

1. **Given** a topic index page, **When** a visitor opens it, **Then** it uses the site's background, typeface, text colors, and link color.
2. **Given** a topic with a podcast feed, **When** a visitor clicks "Copy URL", **Then** the feed URL is copied as it is today, and the podcast bar uses the site's accent color in place of the current orange `#d4561d`.
3. **Given** a digest that has an MP3, **When** the index lists it, **Then** the listen link still appears next to that entry.

---

### User story 3: Landing page introduces the three radars (priority: P3)

A visitor opens `/techradar/` and sees a titled page that names the AI, Research, and Robotics radars, styled like the site. The stray "Other" heading is gone.

**Why this priority**: It is the target of the site's nav link, but it is a single page with three links.

**Independent test**: Open `techradar/index.html` after the index script runs.

**Acceptance scenarios**:

1. **Given** the landing page, **When** a visitor opens it, **Then** it shows a page title and one entry per topic, with no "Other" group heading.
2. **Given** a new topic folder is added under `techradar/`, **When** the index script runs, **Then** the landing page lists it without code changes.

---

### User story 4: Visitor can get back to the main site (priority: P3)

A visitor reading a digest wants to go to the Blog or Resume. Every techradar page has a slim bar at the top. "Keith Fry" links to `https://keithfry.net/`, followed by a breadcrumb: "Tech Radar" on the landing page, "Tech Radar / AI" on the AI index, and "Tech Radar / AI / November 12, 2026" on a digest. Each breadcrumb part except the last links to its page.

**Independent test**: From any techradar page, follow the link to keithfry.net in one click, and follow the breadcrumb back to the topic index and the landing page.

**Acceptance scenarios**:

1. **Given** any techradar page, **When** a visitor looks for a way back to keithfry.net, **Then** the bar is visible at the top without scrolling and "Keith Fry" links to the site.
2. **Given** a digest page, **When** a visitor clicks the topic name in the breadcrumb, **Then** the topic index opens.
3. **Given** a digest page with tag filters, **When** the visitor scrolls, **Then** the bar and the sticky filter bar do not overlap or hide each other.

---

### Edge cases

- **keithfry.net is down or slow.** The digest and index pages must still render readable content. A failed font or stylesheet request from keithfry.net may change the typeface but must not leave the page unstyled or unreadable.
- **The WordPress theme changes.** If Keith changes Astra's global colors or swaps the theme, techradar pages keep the old colors until someone edits the variables in the shared stylesheet. Because every page links that one file, one edit restyles the whole archive.
- **Older digest markup.** Digests from June 2026 may use earlier markup than today's generator writes. The archive rewrite must handle every variant present in `techradar/`, or report the files it skipped.
- **The shared stylesheet fails to load.** If the stylesheet request fails, pages fall back to browser defaults. The content stays readable, so this is acceptable for a file served from the same host as the page.
- **Papers-only digests.** Research digests have only papers and no newsletter or article sections. Their layout must not show empty sections or broken spacing.
- **Long titles and URLs.** Problem-feed URLs and long article titles must wrap and must not cause horizontal scrolling at 375px width.
- **Old published pages.** About five months of AI and Robotics digests, and about one month of Research digests, are already published with the old inline light theme. See FR-010.
- **Open Graph previews.** Social preview images (`og:image`) and podcast cover art are separate images and are out of scope. Their look does not need to change.
- **The GitHub Pages mirror.** Until it is retired on 2026-12-01 (see `docs/BACKLOG.md`), the same files are also served from `keithfry.github.io/techradar/`. Any asset referenced by an absolute keithfry.net URL will still load there. Any asset referenced by a root-relative path such as `/wp-content/...` will not.

## Requirements *(mandatory)*

### Functional requirements

- **FR-001**: Daily digest pages MUST use the site's page background, body text color, heading color, and muted text color as listed in the background table. Link text MUST use the site's hover blue `#748ffc` rather than its link blue `#4361ee`, because `#4361ee` measures 3.56:1 against `#0f172a` and fails FR-005. `#4361ee` stays in use for filled buttons, borders, and active states, where it is not body text.
- **FR-002**: Daily digest pages, topic index pages, and the landing page MUST use Inter as the primary typeface, with a system sans-serif fallback.
- **FR-003**: Topic index pages and the landing page MUST use the same colors and typeface as the digest pages.
- **FR-004**: Each tag (Policy, Models, Agents, Safety, Robotics, Voice AI, Healthcare, Research, Ethics) MUST keep a distinct color on the dark background, and tag text MUST meet WCAG AA contrast (4.5:1) against its pill background.
- **FR-005**: All body text and link text on techradar pages MUST meet WCAG AA contrast against the background it sits on.
- **FR-006**: Every interactive behavior on today's pages MUST keep working: tag filtering, the "Removed" stat pill that opens the removed-items list, the podcast audio player, the Subscribe link, the index page's Copy URL button, the per-entry listen link, and the index page's reload-on-return script.
- **FR-007**: Pages MUST render without horizontal scrolling at 375px viewport width.
- **FR-008**: The `news-radar` package MUST keep its current default look for a consumer that does not opt in to the new styling. The keithfry.net styling MUST come from this repo's configuration or files, not be hardcoded into `news-radar`. (`news-radar` ships example configs and is written as a general package, even though this repo is its only consumer today.)
- **FR-009**: All techradar pages MUST get their styling from one shared stylesheet stored in this repo under `techradar/` and published with the rest of the output. The site's colors and font MUST be defined once in it as named variables. Pages MUST link it by relative path, so the same files work at `keithfry.net/techradar/` and on the GitHub Pages mirror. Pages MUST NOT load keithfry.net's WordPress theme or Elementor CSS.
- **FR-010**: A one-time rewrite MUST convert every digest already in `techradar/` to the new styling: replace its inline style block with the link to the shared stylesheet and add the slim bar from user story 4. The rewrite MUST leave article content, links, tags, podcast players, and Open Graph tags unchanged, and MUST report any file it could not convert.
- **FR-013**: Every techradar page MUST show the slim bar described in user story 4: "Keith Fry" linking to `https://keithfry.net/`, then a breadcrumb to the current page. The bar MUST NOT copy the WordPress menu or footer.
- **FR-014**: The shared stylesheet MUST NOT be removed by the retention job (`retention.py`), which prunes old radar files.

- **FR-011**: The landing page MUST list each topic folder found under `techradar/` and MUST NOT show the "Other" group heading.
- **FR-012**: Generated output MUST stay static HTML with no build step at serve time. `deploy_techradar.sh` continues to rsync `techradar/` as-is.

### Key entities

- **Site design tokens**: the named colors, typeface, and sizes taken from keithfry.net's Astra settings. One definition, used by all three page kinds.
- **Digest page**: one topic's daily output, produced by `news-radar`.
- **Topic index page**: the month-grouped archive of one topic's digests, produced by `generate-index.sh`.
- **Landing page**: `techradar/index.html`, the target of the site's "Tech Radar" nav link.

## Success criteria *(mandatory)*

### Measurable outcomes

- **SC-001**: Opened next to keithfry.net, a digest page, a topic index page, and the landing page use the same background color, body text color, link color, and typeface as the site, checked with the browser's computed styles.
- **SC-002**: Every text and link color pair on techradar pages passes WCAG AA (4.5:1) in an automated contrast check.
- **SC-003**: All interactive behaviors listed in FR-006 work in a manual pass on desktop and at 375px width.
- **SC-004**: With requests to keithfry.net blocked, a digest page still shows all of its content with readable contrast.
- **SC-005**: A `news-radar` run with the example config, which does not opt in, produces a page whose CSS is byte-for-byte the same as before the change.
- **SC-006**: The next scheduled daily run after the change publishes AI, Research, and Robotics digests in the new style with no manual steps.
- **SC-007**: After the archive rewrite, no digest in `techradar/` contains the old inline style block, and the oldest remaining digest in each topic renders in the new style.
- **SC-008**: Changing one color variable in the shared stylesheet changes that color on every techradar page, including archived digests, with no other file edited.

## Assumptions

- "Similar style" means the colors, typeface, and general feel of keithfry.net. It does not mean reproducing its homepage hero, background imagery, or Elementor section layouts. Digest pages keep their current structure: header, stats, filter bar, card sections, and footer.
- The Astra global colors read from the live site on 2026-11-12 are the colors to match. If they change before implementation, the implementer re-reads them.
- Inter can be loaded from keithfry.net's own font files at their absolute URLs. If that is not allowed or not reliable, Google Fonts' Inter is an acceptable substitute because it is the same typeface.
- Podcast RSS feeds, podcast cover art, and Open Graph preview images are out of scope.
- The `../keithfry` and `../keithfry.github.io` repos hold a different, terminal-style landing page with green-on-black styling. They are not the keithfry.net look and are not the source for this feature.
- **Branching note**: the scheduled daily run commits generated output in this checkout to whatever branch is checked out. This work should happen in a separate worktree or between runs, so a feature branch checked out here does not receive daily radar commits.
