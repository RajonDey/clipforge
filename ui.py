#!/usr/bin/env python3
"""
Clipforge — local web UI for animated video section clips.

  .venv/bin/python ui.py

Opens http://127.0.0.1:7860
"""

from __future__ import annotations

import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from animate import QUALITY_DIRS, render_section
from cleanup import EXPORTS_DIR, cleanup_media, list_exports, media_size_mb
from sections import BUILDERS
from theme import PRESETS, apply_preset, load_theme, save_theme

SCRIPT_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(SCRIPT_DIR / "templates"))

SECTION_META = {
    "title": {
        "label": "Title",
        "hint": "A short title card with fade-in and underline.",
        "placeholder": "Welcome to My Channel",
        "field": "Title text",
    },
    "timeline": {
        "label": "Timeline",
        "hint": "Years along a line — optional milestone labels.",
        "placeholder": "2020:Launch, 2022:Growth, 2025:Today\n(or just: 2020 to 2025)",
        "field": "Years / milestones",
    },
    "chart": {
        "label": "Chart",
        "hint": "Animated bar comparison.",
        "placeholder": "A:100, B:200, C:150",
        "field": "Values",
    },
    "bullets": {
        "label": "Bullets",
        "hint": "Key points that fade in one by one.",
        "placeholder": "Point one; Point two; Point three",
        "field": "Points",
    },
    "diagram": {
        "label": "Diagram",
        "hint": "Boxes connected by arrows.",
        "placeholder": "Client -> API -> Database",
        "field": "Flow",
    },
    "table": {
        "label": "Table",
        "hint": "Simple animated table.",
        "placeholder": "Item,Price; Apple,1.00; Banana,2.00",
        "field": "Rows",
    },
}

_render_lock = threading.Lock()


@app.get("/")
def index():
    types = [
        {"id": key, **SECTION_META[key]}
        for key in ("title", "timeline", "chart", "bullets", "diagram", "table")
        if key in BUILDERS
    ]
    return render_template(
        "index.html",
        types=types,
        theme=load_theme(),
        presets=list(PRESETS.keys()),
        exports=list_exports(12),
        media_mb=media_size_mb(),
    )


@app.get("/api/theme")
def get_theme():
    return jsonify({"ok": True, "theme": load_theme(), "presets": list(PRESETS.keys())})


@app.post("/api/theme")
def post_theme():
    body = request.get_json(silent=True) or {}
    preset = (body.get("preset") or "").strip()
    try:
        if preset and not body.get("colors_only"):
            theme = apply_preset(preset)
        else:
            current = load_theme()
            current.update({k: v for k, v in body.items() if k != "colors_only"})
            if preset:
                current["preset"] = preset
            theme = save_theme(current)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "theme": theme})


@app.post("/api/render")
def api_render():
    body = request.get_json(silent=True) or {}
    section_type = (body.get("type") or "").strip()
    payload = (body.get("content") or "").strip()
    quality = (body.get("quality") or "l").strip()
    theme_overrides = body.get("theme") if isinstance(body.get("theme"), dict) else None

    if section_type not in BUILDERS:
        return jsonify({"ok": False, "error": f"Unknown type '{section_type}'"}), 400
    if not payload:
        return jsonify({"ok": False, "error": "Add some content first."}), 400
    if quality not in QUALITY_DIRS:
        return jsonify({"ok": False, "error": f"Unknown quality '{quality}'"}), 400

    # Persist theme overrides from the form before rendering
    if theme_overrides:
        try:
            current = load_theme()
            current.update(theme_overrides)
            save_theme(current)
        except Exception as e:
            return jsonify({"ok": False, "error": f"Theme error: {e}"}), 400

    started = time.time()
    try:
        with _render_lock:
            result = render_section(section_type, payload, quality=quality)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except (FileNotFoundError, RuntimeError) as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify(
        {
            "ok": True,
            "type": section_type,
            "quality": quality,
            "seconds": round(time.time() - started, 1),
            "video_url": f"/exports/{result['export_name']}",
            "export_name": result["export_name"],
            "media_mb": result["media_mb"],
            "exports": list_exports(12),
        }
    )


@app.get("/exports/<path:name>")
def serve_export(name: str):
    path = EXPORTS_DIR / Path(name).name
    if not path.is_file():
        return jsonify({"ok": False, "error": "Export not found."}), 404
    return send_file(path, mimetype="video/mp4", conditional=True)


@app.get("/api/exports")
def api_exports():
    return jsonify(
        {
            "ok": True,
            "exports": list_exports(30),
            "media_mb": media_size_mb(),
        }
    )


@app.post("/api/cleanup")
def api_cleanup():
    removed = cleanup_media()
    return jsonify(
        {
            "ok": True,
            "removed": removed,
            "media_mb": media_size_mb(),
        }
    )


def main() -> None:
    import socket

    host = "127.0.0.1"
    port = 7860
    # If the previous UI is still bound, slide to the next free port
    for candidate in range(7860, 7870):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
            except OSError:
                continue
            port = candidate
            break

    url = f"http://{host}:{port}"

    def _open() -> None:
        time.sleep(0.6)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()
    print(f"Clipforge → {url}")
    if port != 7860:
        print(f"(Port 7860 was busy — using {port}. Stop the old process if you want 7860.)")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
