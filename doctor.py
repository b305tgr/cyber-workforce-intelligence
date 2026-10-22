"""
doctor.py — `python midnight_signal.py --doctor`

Checks everything Midnight Signal needs and says exactly how to fix whatever
is missing. Exits 0 when nothing is broken (warnings are fine), 1 otherwise.
"""

import os
import sys

import ui
import sounds

OK, WARN, FAIL = "ok", "warn", "fail"
_ICON = {
    OK: lambda: ui.success("  ✓"),
    WARN: lambda: ui.solid("  !", ui.gradient_color(0.3), bold=True),
    FAIL: lambda: ui.error("  ✗"),
}


def _row(status, label, detail="", hint=""):
    line = f"{_ICON[status]()} {ui.white(label.ljust(22))}{ui.gray(detail)}"
    print(line)
    if hint and status != OK:
        for h in hint.splitlines():
            print(f"      {ui.solid(h, ui.gradient_color(0.15))}")
    return status


def run(model: str, base_model: str) -> int:
    print()
    print(ui.gradient_text("  MIDNIGHT SIGNAL — system check", bold=True))
    print(ui.dim_line("  " + "─" * 46))
    results = []

    # Python
    v = sys.version_info
    results.append(_row(
        OK if v >= (3, 9) else FAIL, "python",
        f"{v.major}.{v.minor}.{v.micro}",
        "Python 3.9 or newer is required — https://www.python.org/downloads/",
    ))

    # ollama python package
    try:
        import ollama
        try:
            from importlib.metadata import version
            ver = version("ollama")
        except Exception as exc:
            ver = f"installed (version unavailable: {exc})"
        results.append(_row(OK, "ollama python package", ver))
    except ImportError:
        results.append(_row(FAIL, "ollama python package", "not installed", "pip install -r requirements.txt"))
        ollama = None

    # server + models
    names = None
    if ollama is not None:
        try:
            resp = ollama.list()
            models = resp["models"] if isinstance(resp, dict) else getattr(resp, "models", [])
            names = []
            for m in models or []:
                try:
                    n = m["model"]
                except (KeyError, TypeError):
                    n = getattr(m, "model", None) or getattr(m, "name", None)
                if n:
                    names.append(n)
            results.append(_row(OK, "ollama server", f"reachable · {len(names)} model(s) installed"))
        except Exception as exc:
            results.append(_row(
                FAIL, "ollama server", f"not reachable: {exc}",
                "Install Ollama from https://ollama.com/download , then start it:\n"
                "  ollama serve        (the desktop app does this for you)",
            ))

    def have(n):
        return names is not None and (n in names or f"{n}:latest" in names)

    if names is not None:
        results.append(_row(
            OK if have(base_model) else FAIL, "base model", base_model if have(base_model) else "not downloaded",
            f"ollama pull {base_model}",
        ))
        results.append(_row(
            OK if have(model) else FAIL, "midnight-signal model", model if have(model) else "not created yet",
            "ollama create midnight-signal -f Modelfile      (run inside the project folder)",
        ))
        # tool calling (agent mode)
        target = model if have(model) else (base_model if have(base_model) else None)
        if target and ollama is not None:
            try:
                info = ollama.show(target)
                caps = info["capabilities"] if isinstance(info, dict) else getattr(info, "capabilities", None)
                if caps is None:
                    results.append(_row(WARN, "tool calling (agent)", "can't tell — update Ollama to check", "Update Ollama: https://ollama.com/download"))
                elif "tools" in caps:
                    results.append(_row(OK, "tool calling (agent)", "supported"))
                else:
                    results.append(_row(WARN, "tool calling (agent)", "this model doesn't advertise it",
                                        "Coding agent mode needs a tool-enabled model. Chat modes are unaffected."))
            except Exception as exc:
                results.append(_row(
                    WARN, "tool calling (agent)", f"couldn't query model info: {exc}"
                ))

    # terminal
    ct = os.environ.get("COLORTERM", "").lower()
    truecolor = ct in ("truecolor", "24bit") or os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM")
    results.append(_row(
        OK if truecolor else WARN, "truecolor terminal",
        "yes" if truecolor else "not detected",
        "Gradients need 24-bit colour. Use Windows Terminal, iTerm2, kitty, GNOME Terminal, etc.\n"
        "(classic cmd.exe and the old Windows console can't show them)",
    ))

    # audio
    player = sounds.detect_player()
    results.append(_row(
        OK if player else WARN, "sound output",
        player or "no player found — terminal bell only",
        "Linux: install one of  pulseaudio-utils (paplay) · alsa-utils (aplay) · sox · ffmpeg\n"
        "or turn sounds off with /sound off",
    ))

    print(ui.dim_line("  " + "─" * 46))
    broken = sum(1 for r in results if r == FAIL)
    warns = sum(1 for r in results if r == WARN)
    if broken:
        print(ui.error(f"  {broken} problem(s) to fix") + ui.gray(" — follow the hints above, then run --doctor again."))
    elif warns:
        print(ui.success("  ready") + ui.gray(f" — {warns} optional warning(s)."))
    else:
        print(ui.success("  all systems nominal") + ui.gray(" — run: python midnight_signal.py"))
    print()
    return 1 if broken else 0
