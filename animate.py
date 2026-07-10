#!/usr/bin/env python3
"""
Clipforge — animated video section clips powered by Manim.

Reliable path (recommended): built-in section types — no LLM needed.
    .venv/bin/python animate.py --type title --text "Welcome to My Channel"
    .venv/bin/python animate.py --type chart --data "A:100, B:200, C:150"
    .venv/bin/python animate.py --type timeline --data "2020:Launch, 2022:Growth, 2025:Today"
    .venv/bin/python animate.py --type timeline --data "2020 to 2025"
    .venv/bin/python animate.py --type bullets --data "Point one; Point two; Point three"
    .venv/bin/python animate.py --type diagram --data "Client -> API -> Database"
    .venv/bin/python animate.py --type table --data 'Item,Price; Apple,1.00; Banana,2.00'

Freeform shortcuts (auto-routed to builders when recognized):
    .venv/bin/python animate.py "animated timeline 2020 to 2025"
    .venv/bin/python animate.py "title Welcome to My Channel"

Optional LLM fallback (needs Ollama; quality varies with small models):
    .venv/bin/python animate.py --llm "a glowing particle spiral morphing into a logo"

Output:
    generated_scene.py is written, then rendered with manim.
    MP4 lands under media/videos/generated_scene/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from sections import BUILDERS, SECTION_HELP, detect_section
from cleanup import cleanup_media, export_video, media_size_mb
from theme import load_theme, merge_theme

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_SCENE = SCRIPT_DIR / "generated_scene.py"
VENV_MANIM = SCRIPT_DIR / ".venv" / "bin" / "manim"

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

SYSTEM_PROMPT = """You are a Manim Community Edition code generator.
Output ONLY a valid, runnable Manim Python script. No markdown fences, no explanation.
Requirements:
- Include: from manim import *
- Define exactly one scene class named GeneratedScene that inherits from Scene
- Implement construct(self) with a clear, polished animation matching the user request
- Prefer dark background: self.camera.background_color = "#0b0f19"
- Keep the scene short (a few seconds)
- Use ONLY real Manim CE APIs. Correct examples:
  - BarChart(values=[1, 2, 3], bar_names=["A", "B", "C"])
  - Text("Hello"), Dot(), Line(), Arrow(), VGroup(), Table([["a","b"]])
  - Animations: FadeIn, FadeOut, Write, Create, GrowArrow, LaggedStart
- NEVER invent APIs (no Timer, no BarChart(x=..., y=...))
- Do not call manim CLI or write files
"""

QUALITY_FLAGS = {
    "l": "-pql",   # legacy flag (resolution now set explicitly)
    "m": "-pqm",
    "h": "-pqh",
    "k": "-pqk",
}

# Kept for API validation; actual output folder is derived from pixel height + fps
QUALITY_DIRS = {
    "l": "480p15",
    "m": "720p30",
    "h": "1080p60",
    "k": "2160p60",
}

FRAME_RATES = {"l": 15, "m": 30, "h": 60, "k": 60}

# (width, height) per aspect × quality
ASPECT_RESOLUTIONS: dict[str, dict[str, tuple[int, int]]] = {
    "16:9": {
        "l": (854, 480),
        "m": (1280, 720),
        "h": (1920, 1080),
        "k": (3840, 2160),
    },
    "9:16": {
        "l": (480, 854),
        "m": (720, 1280),
        "h": (1080, 1920),
        "k": (2160, 3840),
    },
}


def build_from_type(
    section_type: str,
    payload: str,
    theme: dict | None = None,
) -> str:
    if section_type not in BUILDERS:
        available = ", ".join(sorted(BUILDERS))
        raise ValueError(f"Unknown type '{section_type}'. Available: {available}")
    return BUILDERS[section_type](payload, theme=theme)


def resolve_aspect(theme: dict | None = None) -> str:
    aspect = (theme or load_theme()).get("aspect", "16:9")
    return aspect if aspect in ASPECT_RESOLUTIONS else "16:9"


def resolution_for(quality: str, aspect: str = "16:9") -> tuple[int, int, int]:
    """Return (width, height, fps) for a quality + aspect pair."""
    if quality not in FRAME_RATES:
        raise ValueError(f"Unknown quality '{quality}'. Use: {', '.join(FRAME_RATES)}")
    aspect = aspect if aspect in ASPECT_RESOLUTIONS else "16:9"
    width, height = ASPECT_RESOLUTIONS[aspect][quality]
    return width, height, FRAME_RATES[quality]


def video_path_for_quality(quality: str, aspect: str = "16:9") -> Path:
    _, height, fps = resolution_for(quality, aspect)
    folder = f"{height}p{fps}"
    return SCRIPT_DIR / "media" / "videos" / "generated_scene" / folder / "GeneratedScene.mp4"


def call_ollama(description: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": description},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(
            "Error: could not reach Ollama at http://localhost:11434.\n"
            "Prefer built-in sections (no LLM):\n"
            "  .venv/bin/python animate.py --list\n"
            f"Details: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    except TimeoutError:
        print("Error: Ollama request timed out. Is the model loaded?", file=sys.stderr)
        sys.exit(1)

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error: unexpected Ollama response shape: {e}\n{body}", file=sys.stderr)
        sys.exit(1)


def extract_python_code(raw: str) -> str:
    text = raw.strip()

    fence = re.search(r"```(?:python)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped.startswith("from manim")
            or stripped.startswith("import ")
            or stripped.startswith("class ")
        ):
            start = i
            break
    text = "\n".join(lines[start:]).strip()

    if "class GeneratedScene" not in text:
        print(
            "Error: model did not produce a GeneratedScene class. Raw output:\n"
            f"{raw}",
            file=sys.stderr,
        )
        sys.exit(1)

    if "from manim import" not in text and "import manim" not in text:
        text = "from manim import *\n\n" + text

    return text + "\n"


def resolve_manim() -> str:
    if VENV_MANIM.is_file() and os.access(VENV_MANIM, os.X_OK):
        return str(VENV_MANIM)
    return "manim"


def save_and_render(
    code: str,
    quality: str,
    preview: bool,
    aspect: str = "16:9",
) -> Path:
    """Write scene, render with Manim at the given aspect/quality, return MP4 path."""
    if quality not in FRAME_RATES:
        raise ValueError(f"Unknown quality '{quality}'. Use: {', '.join(FRAME_RATES)}")

    width, height, fps = resolution_for(quality, aspect)

    # Clear stale Manim caches before each run
    cleanup_media()

    OUTPUT_SCENE.write_text(code, encoding="utf-8")
    print(f"Saved scene to {OUTPUT_SCENE}")

    manim_bin = resolve_manim()
    # Explicit resolution + fps so 9:16 and 16:9 both work (quality presets are 16:9-only)
    cmd = [
        manim_bin,
        "--format", "mp4",
        "-r", f"{width},{height}",
        "--fps", str(fps),
        str(OUTPUT_SCENE),
    ]
    if preview:
        cmd.insert(1, "-p")
    print(f"Rendering {aspect} {width}x{height}@{fps} …")
    print(f"  {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "`manim` not found. Install with: .venv/bin/pip install manim"
        ) from e

    # Keep terminal feedback while still capturing for the API
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)

    if result.returncode != 0:
        detail = _summarize_manim_error(result.stderr or result.stdout or "")
        raise RuntimeError(detail)

    out = video_path_for_quality(quality, aspect)
    if not out.is_file():
        # Manim sometimes names folders differently — search for the newest mp4
        found = _find_latest_mp4()
        if found:
            out = found
        else:
            raise RuntimeError(f"Render finished but video not found at {out}")

    print(f"Done. Video: {out}")
    return out


def _find_latest_mp4() -> Path | None:
    root = SCRIPT_DIR / "media" / "videos" / "generated_scene"
    if not root.is_dir():
        return None
    candidates = sorted(root.rglob("GeneratedScene.mp4"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _summarize_manim_error(log: str) -> str:
    """Pull the useful exception line out of a Manim traceback."""
    lines = [ln.strip() for ln in log.splitlines() if ln.strip()]
    for marker in ("ValueError:", "TypeError:", "AttributeError:", "NameError:", "RuntimeError:"):
        for ln in reversed(lines):
            if marker in ln:
                msg = ln.split(marker, 1)[-1].strip()
                return f"Render failed: {msg}"
    # Fall back to last non-empty line
    if lines:
        return f"Render failed: {lines[-1][:240]}"
    return "Manim render failed. Check the terminal for details."


def render_section(
    section_type: str,
    payload: str,
    quality: str = "l",
    theme_overrides: dict | None = None,
    *,
    clean_after: bool = True,
) -> dict:
    """
    Build, render, export, and optionally clean caches.

    Returns dict with export path (durable) and cleanup info.
    """
    theme = merge_theme(load_theme(), theme_overrides)
    aspect = resolve_aspect(theme)
    code = build_from_type(section_type, payload, theme=theme)
    rendered = save_and_render(code, quality=quality, preview=False, aspect=aspect)
    exported = export_video(rendered, section_type, payload)
    print(f"Exported: {exported}")

    cleaned: list[str] = []
    if clean_after:
        cleaned = cleanup_media()
        print(f"Cleaned media caches ({media_size_mb()} MB left under media/)")

    return {
        "export": exported,
        "export_name": exported.name,
        "cleaned": cleaned,
        "media_mb": media_size_mb(),
        "theme_preset": theme.get("preset", ""),
        "resolved_type": section_type,
        "aspect": aspect,
    }


def render_from_prompt(
    prompt: str,
    quality: str = "l",
    theme_overrides: dict | None = None,
) -> dict:
    """
    Auto-route a freeform prompt to a built-in section builder.
    Raises ValueError with guidance when nothing matches.
    """
    text = prompt.strip()
    if not text:
        raise ValueError("Add a prompt first.")

    detected = detect_section(text)
    if not detected:
        raise ValueError(
            "Couldn't match that prompt to a clip type. Try one of:\n"
            '• title Welcome to My Channel\n'
            "• timeline 2020:Launch, 2022:Growth, 2025:Today\n"
            "• chart A:100, B:200, C:150\n"
            "• bullets Point one; Point two; Point three\n"
            "• Client -> API -> Database\n"
            "• table Item,Price; Apple,1.00; Banana,2.00"
        )
    section_type, payload = detected
    result = render_section(section_type, payload, quality=quality, theme_overrides=theme_overrides)
    result["resolved_type"] = section_type
    result["resolved_payload"] = payload
    return result


def render_sequence(
    clips: list[dict],
    quality: str = "l",
    theme_overrides: dict | None = None,
) -> dict:
    """
    Render multiple section clips in order, then concat into one MP4.

    Each clip dict: {"type": "title"|"prompt"|..., "content": "..."}.
    """
    from cleanup import concat_videos

    if not clips:
        raise ValueError("Sequence is empty — add at least one clip.")
    if len(clips) > 20:
        raise ValueError("Sequence is limited to 20 clips.")

    theme = merge_theme(load_theme(), theme_overrides)
    aspect = resolve_aspect(theme)
    parts: list[Path] = []
    resolved: list[dict] = []

    for i, clip in enumerate(clips, start=1):
        section_type = (clip.get("type") or "").strip()
        payload = (clip.get("content") or "").strip()
        if not payload:
            raise ValueError(f"Clip {i} has no content.")

        print(f"\n—— Sequence clip {i}/{len(clips)} ({section_type}) ——")
        if section_type == "prompt":
            result = render_from_prompt(payload, quality=quality, theme_overrides=theme)
        elif section_type in BUILDERS:
            result = render_section(
                section_type,
                payload,
                quality=quality,
                theme_overrides=theme,
                clean_after=True,
            )
        else:
            raise ValueError(f"Clip {i}: unknown type '{section_type}'")

        parts.append(Path(result["export"]))
        resolved.append(
            {
                "type": result.get("resolved_type", section_type),
                "export_name": result["export_name"],
            }
        )

    sequence_path = concat_videos(parts, slug=f"sequence-{len(parts)}clips")
    print(f"Sequence exported: {sequence_path}")

    return {
        "export": sequence_path,
        "export_name": sequence_path.name,
        "media_mb": media_size_mb(),
        "aspect": aspect,
        "clips": resolved,
        "resolved_type": "sequence",
    }


def print_list() -> None:
    print("Built-in section types (reliable, no LLM):\n")
    for name in sorted(SECTION_HELP):
        print(f"  {name:10}  .venv/bin/python animate.py {SECTION_HELP[name]}")
    print(
        "\nFreeform examples (auto-routed when recognized):\n"
        '  .venv/bin/python animate.py "animated timeline 2020 to 2025"\n'
        '  .venv/bin/python animate.py "title Welcome to My Channel"\n'
        "\nLLM fallback (optional):\n"
        '  .venv/bin/python animate.py --llm "custom animation idea"'
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Manim video sections for your channel / course.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run with --list to see all section types and examples.",
    )
    parser.add_argument(
        "description",
        nargs="?",
        help="Freeform description (auto-routed to a builder when possible)",
    )
    parser.add_argument(
        "--type",
        choices=sorted(BUILDERS.keys()),
        help="Built-in section type (recommended)",
    )
    parser.add_argument("--text", help="Text payload (title, etc.)")
    parser.add_argument("--data", help="Data payload (chart, timeline, bullets, ...)")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Force Ollama LLM generation (skip builders)",
    )
    parser.add_argument(
        "--quality",
        choices=sorted(QUALITY_FLAGS),
        default="l",
        help="Render quality: l=480p, m=720p, h=1080p, k=4K (default: l)",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Do not open the video after rendering",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List built-in section types and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write generated_scene.py but do not render",
    )
    return parser.parse_args(argv)


def resolve_code(args: argparse.Namespace) -> tuple[str, str]:
    """
    Return (source_label, manim_code).
    Prefer deterministic builders; LLM only when --llm or unrecognized freeform.
    """
    if args.type:
        payload = args.text if args.text is not None else args.data
        if payload is None:
            raise SystemExit(
                "Error: when using --type, also pass --text or --data.\n"
                f"Example: .venv/bin/python animate.py {SECTION_HELP.get(args.type, '')}"
            )
        try:
            return f"builder:{args.type}", build_from_type(args.type, payload)
        except ValueError as e:
            raise SystemExit(f"Error: {e}") from e

    if not args.description:
        raise SystemExit(
            "Error: provide a description, or use --type with --text/--data.\n"
            "Run: .venv/bin/python animate.py --list"
        )

    if not args.llm:
        detected = detect_section(args.description)
        if detected:
            section_type, payload = detected
            print(f"Matched section type '{section_type}' → using built-in builder")
            try:
                return f"builder:{section_type}", build_from_type(section_type, payload)
            except ValueError as e:
                raise SystemExit(f"Error: {e}") from e

        print(
            "No built-in section matched. Re-run with --llm to use Ollama, "
            "or pick a type from --list.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Asking Ollama ({OLLAMA_MODEL}) ...")
    raw = call_ollama(args.description)
    return "llm", extract_python_code(raw)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.list:
        print_list()
        return

    source, code = resolve_code(args)
    print(f"Source: {source}")

    if args.dry_run:
        OUTPUT_SCENE.write_text(code, encoding="utf-8")
        print(f"Dry run — wrote {OUTPUT_SCENE} (not rendered)")
        return

    try:
        theme = load_theme()
        aspect = resolve_aspect(theme)
        out = save_and_render(code, quality=args.quality, preview=False, aspect=aspect)
        label = source.split(":", 1)[-1] if source.startswith("builder:") else "clip"
        payload = args.text or args.data or args.description or "clip"
        exported = export_video(out, label, payload)
        cleanup_media()
        print(f"Exported: {exported}")
        print(f"Media cache cleaned ({media_size_mb()} MB under media/)")
        if not args.no_preview:
            subprocess.run(["open", str(exported)], check=False)
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
