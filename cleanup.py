"""
Media cleanup and named exports so the project stays usable long-term.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MEDIA_DIR = SCRIPT_DIR / "media"
EXPORTS_DIR = SCRIPT_DIR / "exports"

# Cache / intermediate folders Manim fills up
_CLEAN_TARGETS = (
    MEDIA_DIR / "videos",
    MEDIA_DIR / "texts",
    MEDIA_DIR / "Tex",
    MEDIA_DIR / "images",
)


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (slug or "clip")[:max_len]


def ensure_exports_dir() -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORTS_DIR


def cleanup_media() -> list[str]:
    """
    Remove Manim cache/output under media/ so disk stays light.
    Does not touch exports/.
    """
    removed: list[str] = []
    for path in _CLEAN_TARGETS:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(str(path.relative_to(SCRIPT_DIR)))
    # Recreate empty media root so Manim is happy next run
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return removed


def export_video(
    source: Path,
    section_type: str,
    content: str,
) -> Path:
    """Copy final MP4 into exports/ with a timestamped name."""
    if not source.is_file():
        raise FileNotFoundError(f"Cannot export — missing video: {source}")

    ensure_exports_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(content)
    name = f"{stamp}-{section_type}-{slug}.mp4"
    dest = EXPORTS_DIR / name
    shutil.copy2(source, dest)
    return dest


def concat_videos(sources: list[Path], slug: str = "sequence") -> Path:
    """
    Concatenate MP4s with ffmpeg into a single exports/ file.
    Re-encodes for safety when clips share resolution but differ slightly.
    """
    import subprocess
    import tempfile

    if not sources:
        raise ValueError("No videos to concatenate.")
    for src in sources:
        if not src.is_file():
            raise FileNotFoundError(f"Missing clip for sequence: {src}")

    ensure_exports_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = EXPORTS_DIR / f"{stamp}-{_slugify(slug)}.mp4"

    with tempfile.TemporaryDirectory(prefix="clipforge-seq-") as tmp:
        list_path = Path(tmp) / "concat.txt"
        # ffmpeg concat demuxer needs absolute paths, single-quoted
        lines = []
        for src in sources:
            escaped = str(src.resolve()).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-an",
            str(dest),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip().splitlines()
            tail = err[-3:] if err else ["unknown ffmpeg error"]
            raise RuntimeError("ffmpeg concat failed: " + " | ".join(tail))

    if not dest.is_file():
        raise RuntimeError("Sequence concat finished but output file is missing.")
    return dest


def list_exports(limit: int = 30) -> list[dict]:
    ensure_exports_dir()
    files = sorted(EXPORTS_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for path in files[:limit]:
        out.append(
            {
                "name": path.name,
                "path": str(path),
                "size_kb": round(path.stat().st_size / 1024, 1),
                "url": f"/exports/{path.name}",
            }
        )
    return out


def media_size_mb() -> float:
    if not MEDIA_DIR.exists():
        return 0.0
    total = 0
    for p in MEDIA_DIR.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return round(total / (1024 * 1024), 2)
