"""
Deterministic Manim section builders for video-section workflows.

Each builder returns a complete, runnable Manim script string.
Colors, fonts, sizes, aspect ratio, and timing come from theme.json.
"""

from __future__ import annotations

import ast
import re
from typing import Callable

from theme import is_portrait, load_theme, merge_theme, text_kwargs


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_chart_data(raw: str) -> list[tuple[str, float]]:
    """Parse 'A:100, B:200, C:150' into [(label, value), ...]."""
    items: list[tuple[str, float]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Chart item must look like Label:value, got '{part}'")
        label, value = part.rsplit(":", 1)
        items.append((label.strip(), float(value.strip())))
    if not items:
        raise ValueError("Chart data is empty. Example: A:100, B:200, C:150")
    return items


def parse_bullets(raw: str) -> list[str]:
    """Parse 'Point one; Point two' or newline-separated bullets."""
    if ";" in raw:
        parts = raw.split(";")
    else:
        parts = raw.splitlines()
    bullets = [p.strip().lstrip("•-* ").strip() for p in parts if p.strip()]
    if not bullets:
        raise ValueError("Bullet data is empty. Example: Point one; Point two; Point three")
    return bullets


def parse_diagram(raw: str) -> list[str]:
    """Parse 'Client -> API -> Database' into node labels."""
    nodes = [n.strip() for n in re.split(r"\s*->\s*", raw) if n.strip()]
    if len(nodes) < 2:
        raise ValueError("Diagram needs at least two nodes. Example: Client -> API -> Database")
    return nodes


def parse_table(raw: str) -> list[list[str]]:
    """
    Parse table rows. Accepts:
      - Python list literal: [['Item','Price'],['Apple','$1']]
      - Semicolon rows with commas: Item,Price; Apple,$1; Banana,$2
      - Newline-separated rows with commas

    Uneven rows are padded with empty cells so Manim never crashes.
    """
    text = raw.strip()
    if text.startswith("["):
        try:
            rows = ast.literal_eval(text)
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Could not parse table list literal: {e}") from e
        if not isinstance(rows, list) or not rows:
            raise ValueError("Table list must be a non-empty list of rows")
        parsed = [[str(c) for c in row] for row in rows]
    else:
        chunks = text.split(";") if ";" in text else text.splitlines()
        parsed = []
        for line in chunks:
            line = line.strip()
            if not line:
                continue
            parsed.append([c.strip() for c in line.split(",")])
        if not parsed:
            raise ValueError(
                "Table data is empty. Example: Item,Price; Apple,$1; Banana,$2"
            )

    width = max(len(row) for row in parsed)
    if width < 1:
        raise ValueError("Table needs at least one column.")
    if width > 6:
        raise ValueError(
            f"Table has {width} columns — keep it to 6 or fewer so it fits on screen."
        )

    normalized: list[list[str]] = []
    for row in parsed:
        padded = list(row) + [""] * (width - len(row))
        capped = [(cell[:40] + "…") if len(cell) > 40 else cell for cell in padded]
        normalized.append(capped)

    if len(normalized) > 8:
        raise ValueError(
            f"Table has {len(normalized)} rows — keep it to 8 or fewer for a short clip."
        )
    return normalized


def parse_timeline(raw: str) -> list[tuple[str, str]]:
    """
    Parse timeline data. Accepts:
      - '2020:Launch, 2021:Growth, 2025:Today'
      - '2020 to 2025'  (years only, empty labels)
      - '2020-2025'
    """
    text = raw.strip()

    range_match = re.search(
        r"(?i)(?:from\s+)?(\d{4})\s*(?:to|-|–|—)\s*(\d{4})",
        text,
    )
    if range_match and ":" not in text:
        start, end = int(range_match.group(1)), int(range_match.group(2))
        if end < start:
            start, end = end, start
        if end - start > 20:
            raise ValueError("Timeline range too large (max 20 years)")
        return [(str(y), "") for y in range(start, end + 1)]

    items: list[tuple[str, str]] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            year, label = part.split(":", 1)
            items.append((year.strip(), label.strip()))
        else:
            items.append((part, ""))
    if len(items) < 2:
        raise ValueError(
            "Timeline needs at least two points. "
            "Example: 2020:Launch, 2022:Growth, 2025:Today  or  2020 to 2025"
        )
    return items


# ---------------------------------------------------------------------------
# Shared scene helpers
# ---------------------------------------------------------------------------

def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _resolve_theme(theme: dict | None) -> dict:
    return merge_theme(theme) if theme else load_theme()


def _timing(th: dict) -> tuple[float, float]:
    hold = float(th.get("hold_seconds", 1.2))
    speed = max(0.5, float(th.get("speed", 1.0)))
    return hold, speed


def _rt(base: float, speed: float) -> float:
    """Scale a run_time by speed (higher speed → shorter)."""
    return round(base / speed, 3)


def _scene_preamble(th: dict) -> str:
    """Manim imports, frame aspect, and safe-area fit helper."""
    if is_portrait(th):
        fw, fh = 8.0, 14.222
    else:
        fw, fh = 14.222, 8.0
    return f'''from manim import *

config.frame_width = {fw}
config.frame_height = {fh}

def _fit(mob, margin=0.55):
    """Scale a mobject down so it stays inside the safe area."""
    max_w = config.frame_width - 2 * margin
    max_h = config.frame_height - 2 * margin
    if mob.width > max_w:
        mob.scale_to_fit_width(max_w)
    if mob.height > max_h:
        mob.scale_to_fit_height(max_h)
    return mob

'''


# ---------------------------------------------------------------------------
# Code emitters
# ---------------------------------------------------------------------------

def build_title(text: str, theme: dict | None = None) -> str:
    th = _resolve_theme(theme)
    hold, speed = _timing(th)
    t = _escape(text.strip())
    title_kw = text_kwargs(th, "title_size", "text")
    return f'''{_scene_preamble(th)}class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "{th["background"]}"

        title = Text("{t}", {title_kw}, weight=BOLD)
        underline = Line(LEFT, RIGHT, color="{th["accent"]}", stroke_width=3)
        underline.width = min(title.width * 0.9, config.frame_width * 0.55)
        underline.next_to(title, DOWN, buff=0.35)
        group = _fit(VGroup(title, underline).move_to(ORIGIN))

        self.play(FadeIn(title, shift=UP * 0.3), run_time={_rt(1.0, speed)})
        self.play(Create(underline), run_time={_rt(0.6, speed)})
        self.play(title.animate.set_color("{th["accent"]}"), run_time={_rt(0.4, speed)})
        self.wait({hold})
        self.play(FadeOut(group), run_time={_rt(0.6, speed)})
'''


def build_chart(data: str, theme: dict | None = None) -> str:
    th = _resolve_theme(theme)
    hold, speed = _timing(th)
    items = parse_chart_data(data)
    values = [v for _, v in items]
    names = [lab for lab, _ in items]
    heading_kw = text_kwargs(th, "heading_size", "text")
    label_kw = text_kwargs(th, "label_size", "text")
    muted_kw = text_kwargs(th, "label_size", "muted")
    max_height = 5.5 if is_portrait(th) else 4.0
    return f'''{_scene_preamble(th)}class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "{th["background"]}"

        values = {values!r}
        names = {names!r}
        colors = {th["bar_colors"]!r}
        max_val = max(values) or 1
        bar_width = 0.9
        max_height = {max_height}
        gap = 0.55

        title = Text("Comparison", {heading_kw})
        title.to_edge(UP, buff=0.45)

        n = len(values)
        total_width = n * bar_width + (n - 1) * gap
        x0 = -total_width / 2 + bar_width / 2
        baseline = -config.frame_height * 0.18

        bars = VGroup()
        labels = VGroup()
        value_labels = VGroup()

        for i, (name, value) in enumerate(zip(names, values)):
            height = (value / max_val) * max_height
            color = colors[i % len(colors)]
            x = x0 + i * (bar_width + gap)
            bar = Rectangle(
                width=bar_width,
                height=max(height, 0.08),
                fill_color=color,
                fill_opacity=0.9,
                stroke_width=0,
            )
            bar.move_to([x, baseline, 0], aligned_edge=DOWN)
            label = Text(str(name), {label_kw})
            label.next_to(bar, DOWN, buff=0.25)
            display = int(value) if float(value) == int(value) else value
            vlabel = Text(str(display), {muted_kw})
            vlabel.next_to(bar, UP, buff=0.15)
            bars.add(bar)
            labels.add(label)
            value_labels.add(vlabel)

        chart = _fit(VGroup(bars, labels, value_labels))
        title = _fit(title)

        self.play(Write(title), run_time={_rt(0.5, speed)})
        self.play(
            LaggedStart(*[GrowFromEdge(bar, DOWN) for bar in bars], lag_ratio=0.2),
            run_time={_rt(1.4, speed)},
        )
        self.play(
            LaggedStart(*[FadeIn(m) for m in (*labels, *value_labels)], lag_ratio=0.05),
            run_time={_rt(0.6, speed)},
        )
        self.wait({hold})
        self.play(FadeOut(VGroup(title, chart)), run_time={_rt(0.5, speed)})
'''


def build_bullets(data: str, theme: dict | None = None) -> str:
    th = _resolve_theme(theme)
    hold, speed = _timing(th)
    bullets = parse_bullets(data)
    body_kw = text_kwargs(th, "body_size", "text")
    heading_kw = text_kwargs(th, "heading_size", "accent")
    lines = ",\n            ".join(
        f'Text("• {_escape(b)}", {body_kw})' for b in bullets
    )
    return f'''{_scene_preamble(th)}class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "{th["background"]}"

        title = Text("Key Points", {heading_kw})
        title.to_edge(UP, buff=0.5)

        items = VGroup(
            {lines}
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        items.next_to(title, DOWN, buff=0.7)
        group = _fit(VGroup(title, items))

        self.play(FadeIn(title), run_time={_rt(0.5, speed)})
        for item in items:
            self.play(FadeIn(item, shift=RIGHT * 0.3), run_time={_rt(0.45, speed)})
            self.wait({_rt(0.15, speed)})
        self.wait({hold})
        self.play(FadeOut(group), run_time={_rt(0.5, speed)})
'''


def build_diagram(data: str, theme: dict | None = None) -> str:
    th = _resolve_theme(theme)
    hold, speed = _timing(th)
    nodes = parse_diagram(data)
    body_kw = text_kwargs(th, "body_size", "text")
    node_lines = ",\n            ".join(
        f'Text("{_escape(n)}", {body_kw})' for n in nodes
    )
    direction = "DOWN" if is_portrait(th) else "RIGHT"
    start_edge = "get_bottom" if is_portrait(th) else "get_right"
    end_edge = "get_top" if is_portrait(th) else "get_left"
    return f'''{_scene_preamble(th)}class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "{th["background"]}"

        labels = [{node_lines}]
        boxes = VGroup()
        for label in labels:
            box = RoundedRectangle(
                corner_radius=0.15,
                width=max(label.width + 0.6, 2.2),
                height=1.0,
                color="{th["accent"]}",
                fill_color="{th["surface"]}",
                fill_opacity=1,
                stroke_width=2,
            )
            group = VGroup(box, label)
            label.move_to(box.get_center())
            boxes.add(group)

        boxes.arrange({direction}, buff=1.0)
        boxes.move_to(ORIGIN)
        _fit(boxes)

        arrows = VGroup()
        for i in range(len(boxes) - 1):
            arrow = Arrow(
                boxes[i].{start_edge}(),
                boxes[i + 1].{end_edge}(),
                buff=0.12,
                color="{th["accent_secondary"]}",
                stroke_width=3,
                max_tip_length_to_length_ratio=0.18,
            )
            arrows.add(arrow)

        self.play(
            LaggedStart(*[FadeIn(b, shift=UP * 0.2) for b in boxes], lag_ratio=0.25),
            run_time={_rt(1.2, speed)},
        )
        self.play(
            LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.2),
            run_time={_rt(0.9, speed)},
        )
        self.wait({hold})
        self.play(FadeOut(VGroup(boxes, arrows)), run_time={_rt(0.5, speed)})
'''


def build_table(data: str, theme: dict | None = None) -> str:
    th = _resolve_theme(theme)
    hold, speed = _timing(th)
    rows = parse_table(data)
    heading_kw = text_kwargs(th, "heading_size", "text")
    font_arg = f', "font": "{th["font"]}"' if th.get("font") else ""
    return f'''{_scene_preamble(th)}class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "{th["background"]}"

        table = Table(
            {rows!r},
            include_outer_lines=True,
            line_config={{"stroke_color": "{th["accent"]}", "stroke_width": 2}},
            element_to_mobject=Text,
            element_to_mobject_config={{"font_size": {th["body_size"]}, "color": "{th["text"]}"{font_arg}}},
        )
        title = Text("Overview", {heading_kw})
        title.to_edge(UP, buff=0.4)
        table.next_to(title, DOWN, buff=0.5)
        group = _fit(VGroup(title, table))

        self.play(Write(title), run_time={_rt(0.5, speed)})
        self.play(table.create(), run_time={_rt(1.8, speed)})
        self.wait({hold})
        self.play(FadeOut(group), run_time={_rt(0.5, speed)})
'''


def build_timeline(data: str, theme: dict | None = None) -> str:
    th = _resolve_theme(theme)
    hold, speed = _timing(th)
    points = parse_timeline(data)
    pairs_repr = repr([(y, lab) for y, lab in points])
    heading_kw = text_kwargs(th, "heading_size", "accent")
    label_kw = text_kwargs(th, "label_size", "text")
    muted_kw = text_kwargs(th, "label_size", "muted")
    portrait = is_portrait(th)

    if portrait:
        return f'''{_scene_preamble(th)}class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "{th["background"]}"

        points = {pairs_repr}
        n = len(points)

        heading = Text("Timeline", {heading_kw})
        heading.to_edge(UP, buff=0.45)

        span = config.frame_height * 0.55
        y0, y1 = span / 2, -span / 2
        line = Line([0, y0, 0], [0, y1, 0], color="{th["accent_secondary"]}", stroke_width=4)

        self.play(FadeIn(heading), Create(line), run_time={_rt(0.8, speed)})

        for i, (year, label) in enumerate(points):
            y = interpolate(y0, y1, i / max(n - 1, 1))
            dot = Dot(point=[0, y, 0], radius=0.12, color="{th["highlight"]}")
            tick = Line([-0.15, y, 0], [0.15, y, 0], color="{th["text"]}", stroke_width=2)
            year_t = Text(str(year), {label_kw})
            year_t.next_to(dot, LEFT, buff=0.35)

            self.play(
                FadeIn(VGroup(tick, dot), scale=0.5),
                FadeIn(year_t),
                run_time={_rt(0.35, speed)},
            )

            if label:
                event = Text(str(label), {muted_kw})
                event.next_to(dot, RIGHT, buff=0.35)
                self.play(FadeIn(event, shift=RIGHT * 0.1), run_time={_rt(0.25, speed)})

            self.wait({_rt(0.08, speed)})

        _fit(VGroup(*self.mobjects))
        self.wait({hold})
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time={_rt(0.6, speed)})
'''

    return f'''{_scene_preamble(th)}class GeneratedScene(Scene):
    def construct(self):
        self.camera.background_color = "{th["background"]}"

        points = {pairs_repr}
        n = len(points)

        heading = Text("Timeline", {heading_kw})
        heading.to_edge(UP, buff=0.45)

        half = config.frame_width * 0.42
        line = Line(LEFT * half, RIGHT * half, color="{th["accent_secondary"]}", stroke_width=4)
        line.shift(UP * 0.2)

        self.play(FadeIn(heading), Create(line), run_time={_rt(0.8, speed)})

        for i, (year, label) in enumerate(points):
            x = interpolate(-half, half, i / max(n - 1, 1))
            dot = Dot(point=[x, 0.2, 0], radius=0.12, color="{th["highlight"]}")
            tick = Line([x, 0.05, 0], [x, 0.35, 0], color="{th["text"]}", stroke_width=2)
            year_t = Text(str(year), {label_kw})
            year_t.next_to(dot, DOWN, buff=0.35)

            self.play(
                FadeIn(VGroup(tick, dot), scale=0.5),
                FadeIn(year_t),
                run_time={_rt(0.35, speed)},
            )

            if label:
                event = Text(str(label), {muted_kw})
                if i % 2 == 0:
                    event.next_to(dot, UP, buff=0.4)
                else:
                    event.next_to(year_t, DOWN, buff=0.2)
                self.play(FadeIn(event, shift=UP * 0.1), run_time={_rt(0.25, speed)})

            self.wait({_rt(0.08, speed)})

        _fit(VGroup(*self.mobjects))
        self.wait({hold})
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time={_rt(0.6, speed)})
'''


BUILDERS: dict[str, Callable[..., str]] = {
    "title": build_title,
    "chart": build_chart,
    "bullets": build_bullets,
    "diagram": build_diagram,
    "table": build_table,
    "timeline": build_timeline,
}

SECTION_HELP: dict[str, str] = {
    "title": '--type title --text "Welcome to My Channel"',
    "chart": '--type chart --data "A:100, B:200, C:150"',
    "bullets": '--type bullets --data "Point one; Point two; Point three"',
    "diagram": '--type diagram --data "Client -> API -> Database"',
    "table": "--type table --data 'Item,Price; Apple,1.00; Banana,2.00'",
    "timeline": '--type timeline --data "2020:Launch, 2022:Growth, 2025:Today"',
}


def detect_section(description: str) -> tuple[str, str] | None:
    """
    Heuristically map a freeform prompt to a (section_type, payload).
    Returns None if no reliable match — caller may fall back to LLM.
    """
    text = description.strip()
    lower = text.lower()

    if "timeline" in lower or re.search(r"\b\d{4}\s*(?:to|-|–|—)\s*\d{4}\b", lower):
        range_match = re.search(r"(\d{4}\s*(?:to|-|–|—)\s*\d{4})", text, re.I)
        if range_match:
            return "timeline", range_match.group(1)
        after = re.split(r"(?i)timeline[:\s]+", text, maxsplit=1)
        if len(after) == 2 and after[1].strip():
            return "timeline", after[1].strip()
        return "timeline", text

    title_match = re.match(r"(?i)^(?:animated\s+)?title[:\s]+(.+)$", text)
    if title_match:
        return "title", title_match.group(1).strip().strip("\"'")
    if lower.startswith("title ") and len(text) < 80:
        return "title", text[6:].strip().strip("\"'")

    if "chart" in lower or "bar chart" in lower:
        data_match = re.search(
            r"([A-Za-z0-9 _-]+:\s*[\d.]+(?:\s*,\s*[A-Za-z0-9 _-]+:\s*[\d.]+)+)",
            text,
        )
        if data_match:
            return "chart", data_match.group(1)

    if "->" in text:
        if "diagram" in lower or "flow" in lower or re.match(
            r"^[\w\s]+(\s*->\s*[\w\s]+)+$", text
        ):
            arrow_part = text
            for prefix in (
                r"(?i)(?:simple\s+)?diagram\s*(?:showing|of|:)?\s*",
                r"(?i)flow\s*(?:chart)?:?\s*",
            ):
                arrow_part = re.sub(prefix, "", arrow_part).strip()
            if "->" in arrow_part:
                return "diagram", arrow_part

    if "bullet" in lower or "key points" in lower:
        after = re.split(r"(?i)(?:bullets?|key points)[:\s]+", text, maxsplit=1)
        if len(after) == 2 and after[1].strip():
            return "bullets", after[1].strip()

    if "table" in lower:
        after = re.split(r"(?i)table[:\s]+", text, maxsplit=1)
        if len(after) == 2 and after[1].strip():
            return "table", after[1].strip()

    instructiony = re.search(
        r"(?i)\b(make|create|animate|generate|render|with|using|show|add|bigger|smaller|full.?screen|particle|spiral|morph)\b",
        text,
    )
    if (
        len(text) <= 48
        and not instructiony
        and ":" not in text
        and "->" not in text
        and ";" not in text
        and "," not in text
    ):
        return "title", text.strip().strip("\"'")

    return None
