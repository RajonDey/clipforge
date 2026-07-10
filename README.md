# Clipforge

Turn short inputs into polished MP4 clips for YouTube and course videos — powered by [Manim](https://www.manim.community/).

Section types: **title**, **timeline**, **chart**, **bullets**, **diagram**, **table**. Theme colors, fonts, and presets are editable in the UI or `theme.json`.

## Setup (any machine)

```bash
git clone <your-repo-url> clipforge
cd clipforge
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Requires Python 3.10+ and a working Manim install (see [Manim docs](https://docs.manim.community/en/stable/installation.html) for system deps like `ffmpeg`).

## Web UI (recommended)

```bash
.venv/bin/python ui.py
```

Opens **http://127.0.0.1:7860** (uses the next free port if busy).

- Pick a section type → enter content → **Render clip**
- Expand **Look & theme** to change colors, font, sizes, or presets
- Finished clips are saved under `exports/` (kept forever)
- Manim `media/` caches are cleared after every render

## Theme

Edit in the UI or in `theme.json`:

| Field | What it controls |
|-------|------------------|
| `background` | Scene background |
| `accent` / `accent_secondary` | Underlines, boxes, timeline line |
| `text` / `muted` / `highlight` | Typography & markers |
| `font` | System font name (empty = Manim default) |
| `title_size` / `heading_size` / `body_size` | Type scale |
| `bar_colors` | Chart palette |

Presets: `dark_teal`, `midnight_gold`, `ocean`, `clean_light`.

## Disk hygiene

Every render:
1. Clears old `media/` caches
2. Renders fresh
3. Copies MP4 → `exports/YYYYMMDD-HHMMSS-type-slug.mp4`
4. Clears `media/` again

Manual cleanup in the UI also wipes `media/` without touching exports.

## CLI

```bash
.venv/bin/python animate.py --type title --text "Welcome to My Channel"
.venv/bin/python animate.py --type timeline --data "2020:Launch, 2022:Growth, 2025:Today"
.venv/bin/python animate.py --list
```

## Layout

```
ui.py               Web UI
theme.json          Active look (colors/fonts/sizes)
theme.py            Presets + load/save
cleanup.py          Media wipe + exports library
sections.py         Section builders (theme-aware)
animate.py          CLI + render API
exports/            Kept MP4s (gitignored)
media/              Temporary (auto-cleared, gitignored)
```
