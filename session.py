"""
session.py — Midnight Signal persistence.

Conversations are saved as plain JSON under ~/.midnight_signal/sessions so
they survive restarts, and can be exported as readable markdown.
"""

import json
import logging
import os
import re
import time

HOME_DIR = os.path.join(os.path.expanduser("~"), ".midnight_signal")
SESS_DIR = os.path.join(HOME_DIR, "sessions")
HISTORY_FILE = os.path.join(HOME_DIR, "history")
SETTINGS_FILE = os.path.join(HOME_DIR, "settings.json")
_logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {"sound": True, "volume": 60, "theme": "auto", "statusbar": True}


def load_settings() -> dict:
    """User preferences (sound, theme, status line). Missing/corrupt file -> defaults."""
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            data.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    except FileNotFoundError:
        return data
    except (OSError, ValueError) as exc:
        _logger.warning(
            "Could not load settings from %s; using defaults: %s", SETTINGS_FILE, exc
        )
    return data


def save_settings(settings: dict) -> None:
    try:
        os.makedirs(HOME_DIR, exist_ok=True)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)
    except OSError as exc:
        _logger.error("Could not save settings to %s: %s", SETTINGS_FILE, exc)


def ensure_dirs():
    os.makedirs(SESS_DIR, exist_ok=True)


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "session"


def _path(name: str) -> str:
    return os.path.join(SESS_DIR, _safe(name) + ".json")


def save_session(name: str, data: dict) -> str:
    ensure_dirs()
    path = _path(name)
    payload = dict(data)
    payload["saved_at"] = time.time()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def load_session(name: str) -> dict:
    path = _path(name)
    if not os.path.isfile(path):
        raise FileNotFoundError(name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_sessions() -> list:
    """Return [(name, saved_at, messages, mode)] newest first."""
    if not os.path.isdir(SESS_DIR):
        return []
    rows = []
    for fn in os.listdir(SESS_DIR):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(SESS_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            msgs = len([m for m in data.get("history", []) if m.get("role") in ("user", "assistant")])
            rows.append((fn[:-5], data.get("saved_at", os.path.getmtime(path)), msgs, data.get("mode", "?")))
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            _logger.warning(
                "Skipping unreadable session file %s: %s", path, exc
            )
            continue
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def export_markdown(history: list, path: str, meta: dict) -> str:
    lines = [
        "# Midnight Signal transcript",
        "",
        f"- mode: `{meta.get('mode', '?')}`",
        f"- model: `{meta.get('model', '?')}`",
        f"- exported: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for m in history:
        role = m.get("role")
        if role == "system":
            continue
        who = "You" if role == "user" else "Midnight Signal"
        lines += [f"## {who}", "", m.get("content", ""), ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
