# Clipforge

Turn short inputs into polished MP4 clips for YouTube and course videos — powered by [Manim](https://www.manim.community/).

Section types: **title**, **timeline**, **chart**, **bullets**, **diagram**, **table**, plus freeform **prompt** routing.

## Setup (any machine)

```bash
git clone <your-repo-url> clipforge
cd clipforge
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Requires Python 3.10+, `ffmpeg`, and a working Manim install (see [Manim docs](https://docs.manim.community/en/stable/installation.html)).

## Web UI (recommended)

```bash
.venv/bin/python ui.py
```

Opens **http://127.0.0.1:7860** (uses the next free port if busy).

- Pick a section type → enter content → **Render clip**
- Choose **16:9** (YouTube/course) or **9:16** (Shorts) — layouts auto-fit the frame
- Tune **Hold** (pause on final frame) and **Speed**
- **Add to sequence** → queue several clips → **Render sequence** (concatenated MP4)
- Expand **Look & theme** for colors, font, sizes, or presets
- Finished clips are saved under `exports/` (kept forever)
- Manim `media/` caches are cleared after every render

## Theme

Edit in the UI or in `theme.json`:

| Field | What it controls |
|-------|------------------|
| `aspect` | `16:9` or `9:16` |
| `hold_seconds` | Pause before fade-out |
| `speed` | Animation pace (`1.0` = normal) |
| `background` | Scene background |
| `accent` / `accent_secondary` | Underlines, boxes, timeline line |
| `text` / `muted` / `highlight` | Typography & markers |
| `font` | System font name (empty = Manim default) |
| `title_size` / `heading_size` / `body_size` | Type scale |
| `bar_colors` | Chart palette |

Presets: `dark_teal`, `midnight_gold`, `ocean`, `clean_light` (color only — aspect/timing are kept).

## Disk hygiene

Every render:
1. Clears old `media/` caches
2. Renders fresh
3. Copies MP4 → `exports/YYYYMMDD-HHMMSS-type-slug.mp4`
4. Clears `media/` again

Sequences also write a combined `exports/…-sequence-Nclips.mp4`.

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
theme.json          Active look + aspect/timing
theme.py            Presets + load/save
cleanup.py          Media wipe + exports + ffmpeg concat
sections.py         Section builders (theme-aware, safe-fit)
animate.py          CLI + render / sequence API
exports/            Kept MP4s (gitignored)
media/              Temporary (auto-cleared, gitignored)
```
