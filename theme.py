"""
Theme presets and persistence for section renders.

Edit theme.json (or use the UI) to change colors, fonts, and sizes
across every built-in section type.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
THEME_PATH = SCRIPT_DIR / "theme.json"

DEFAULT_THEME: dict = {
    "preset": "dark_teal",
    "background": "#0b0f19",
    "surface": "#152033",
    "accent": "#5EEAD4",
    "accent_secondary": "#60A5FA",
    "text": "#FFFFFF",
    "muted": "#9CA3AF",
    "highlight": "#FBBF24",
    "font": "",
    "title_size": 56,
    "heading_size": 40,
    "body_size": 28,
    "label_size": 24,
    "bar_colors": ["#5EEAD4", "#60A5FA", "#FBBF24", "#C084FC", "#4ADE80"],
}

PRESETS: dict[str, dict] = {
    "dark_teal": {
        **DEFAULT_THEME,
        "preset": "dark_teal",
    },
    "midnight_gold": {
        **DEFAULT_THEME,
        "preset": "midnight_gold",
        "background": "#0c0a09",
        "surface": "#1c1917",
        "accent": "#FBBF24",
        "accent_secondary": "#F59E0B",
        "text": "#FAFAF9",
        "muted": "#A8A29E",
        "highlight": "#FDE68A",
        "bar_colors": ["#FBBF24", "#F59E0B", "#E7E5E4", "#A8A29E", "#78716C"],
    },
    "ocean": {
        **DEFAULT_THEME,
        "preset": "ocean",
        "background": "#0a1628",
        "surface": "#12253f",
        "accent": "#38BDF8",
        "accent_secondary": "#818CF8",
        "text": "#F0F9FF",
        "muted": "#94A3B8",
        "highlight": "#22D3EE",
        "bar_colors": ["#38BDF8", "#818CF8", "#22D3EE", "#34D399", "#F472B6"],
    },
    "clean_light": {
        **DEFAULT_THEME,
        "preset": "clean_light",
        "background": "#F8FAFC",
        "surface": "#FFFFFF",
        "accent": "#0F766E",
        "accent_secondary": "#0369A1",
        "text": "#0F172A",
        "muted": "#64748B",
        "highlight": "#D97706",
        "bar_colors": ["#0F766E", "#0369A1", "#D97706", "#7C3AED", "#059669"],
    },
}

# Fields the UI may patch onto the active theme
EDITABLE_KEYS = (
    "background",
    "surface",
    "accent",
    "accent_secondary",
    "text",
    "muted",
    "highlight",
    "font",
    "title_size",
    "heading_size",
    "body_size",
    "label_size",
    "bar_colors",
)


def _normalize(data: dict) -> dict:
    theme = deepcopy(DEFAULT_THEME)
    theme.update({k: v for k, v in data.items() if k in theme or k == "preset"})
    # Coerce sizes
    for key in ("title_size", "heading_size", "body_size", "label_size"):
        try:
            theme[key] = int(theme[key])
        except (TypeError, ValueError):
            theme[key] = DEFAULT_THEME[key]
    if not isinstance(theme.get("bar_colors"), list) or not theme["bar_colors"]:
        theme["bar_colors"] = list(DEFAULT_THEME["bar_colors"])
    theme["font"] = str(theme.get("font") or "").strip()
    return theme


def load_theme() -> dict:
    if not THEME_PATH.is_file():
        save_theme(DEFAULT_THEME)
        return deepcopy(DEFAULT_THEME)
    try:
        data = json.loads(THEME_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULT_THEME)
    if not isinstance(data, dict):
        return deepcopy(DEFAULT_THEME)
    return _normalize(data)


def save_theme(theme: dict) -> dict:
    normalized = _normalize(theme)
    THEME_PATH.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return normalized


def apply_preset(name: str) -> dict:
    if name not in PRESETS:
        raise ValueError(f"Unknown preset '{name}'. Available: {', '.join(PRESETS)}")
    return save_theme(PRESETS[name])


def merge_theme(base: dict | None = None, overrides: dict | None = None) -> dict:
    theme = _normalize(base or load_theme())
    if not overrides:
        return theme
    patch = {k: v for k, v in overrides.items() if k in EDITABLE_KEYS and v is not None}
    if "font" in patch:
        patch["font"] = str(patch["font"]).strip()
    theme.update(patch)
    return _normalize(theme)


def text_kwargs(theme: dict, size_key: str = "body_size", color_key: str = "text") -> str:
    """Emit Manim Text keyword args from theme, e.g. 'font_size=40, color=\"#fff\", font=\"X\"'."""
    size = theme.get(size_key, theme["body_size"])
    color = theme.get(color_key, theme["text"])
    parts = [f"font_size={int(size)}", f'color="{color}"']
    font = theme.get("font") or ""
    if font:
        parts.append(f'font="{font}"')
    return ", ".join(parts)
